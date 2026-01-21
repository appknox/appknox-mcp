import { spawn } from 'child_process';
import { promises as fs } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import {
  CLINotFoundError,
  CommandTimeoutError,
  CommandExecutionError,
  FilePathError,
  AuthenticationError,
} from './errors.js';
import logger from './logger.js';

export interface ExecutionOptions {
  timeout?: number; // in milliseconds
  env?: Record<string, string>;
}

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/**
 * Validates that a file path doesn't contain directory traversal attempts
 */
function validateFilePath(filePath: string): void {
  // Check for directory traversal
  if (filePath.includes('..')) {
    logger.warn('Directory traversal attempt detected', { filePath });
    throw new FilePathError('Invalid file path: directory traversal not allowed');
  }

  // Check for null bytes (command injection attempt)
  if (filePath.includes('\0')) {
    logger.warn('Null byte injection attempt detected', { filePath });
    throw new FilePathError('Invalid file path: null bytes not allowed');
  }

  // Validate path length
  if (filePath.length > 4096) {
    logger.warn('Excessively long file path', { length: filePath.length });
    throw new FilePathError('Invalid file path: path too long');
  }
}

/**
 * Validates that a numeric ID is a positive integer
 */
export function validateNumericId(id: number, fieldName: string): void {
  if (!Number.isInteger(id) || id <= 0 || id > Number.MAX_SAFE_INTEGER) {
    logger.warn('Invalid numeric ID', { fieldName, id });
    throw new FilePathError(`Invalid ${fieldName}: must be a positive integer`);
  }
}

/**
 * Validates risk threshold value
 */
export function validateRiskThreshold(threshold: string): void {
  const valid = ['low', 'medium', 'high', 'critical'];
  if (!valid.includes(threshold.toLowerCase())) {
    logger.warn('Invalid risk threshold', { threshold });
    throw new FilePathError(`Invalid risk threshold: must be one of ${valid.join(', ')}`);
  }
}

/**
 * Reads the access token from the Appknox config file if it exists
 */
async function getAccessTokenFromConfig(): Promise<string | null> {
  try {
    const configPath = join(homedir(), '.config', 'appknox.json');
    logger.debug('Reading Appknox config file', { configPath });

    const configData = await fs.readFile(configPath, 'utf-8');
    const config = JSON.parse(configData);
    const token = config['access-token'] || config['access_token'] || null;

    if (token) {
      logger.debug('Access token found in config file');
    } else {
      logger.debug('No access token in config file');
    }

    return token;
  } catch (error) {
    // Config file doesn't exist or is invalid
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      logger.debug('Appknox config file not found');
    } else {
      logger.warn('Failed to read Appknox config file', { error });
    }
    return null;
  }
}

/**
 * Prepares environment variables for the CLI execution
 * Checks for environment variables first, then falls back to config file
 */
async function prepareEnvironment(userEnv?: Record<string, string>): Promise<NodeJS.ProcessEnv> {
  const env = { ...process.env };

  // Apply user-provided environment overrides
  if (userEnv) {
    Object.assign(env, userEnv);
  }

  // If APPKNOX_ACCESS_TOKEN is not set, try to read from config file
  if (!env.APPKNOX_ACCESS_TOKEN) {
    logger.debug('APPKNOX_ACCESS_TOKEN not found in environment, checking config file');
    const configToken = await getAccessTokenFromConfig();
    if (configToken) {
      env.APPKNOX_ACCESS_TOKEN = configToken;
      logger.debug('Using access token from config file');
    } else {
      logger.warn('No access token found in environment or config file');
    }
  } else {
    logger.debug('Using APPKNOX_ACCESS_TOKEN from environment');
  }

  return env;
}

/**
 * Sanitizes error messages to avoid leaking sensitive information
 */
function sanitizeError(error: string): string {
  // Remove potential token values (long alphanumeric strings)
  let sanitized = error.replace(/[a-f0-9]{32,}/gi, '[REDACTED]');

  // Remove full file paths that might contain usernames
  sanitized = sanitized.replace(/\/Users\/[^/]+/g, '/Users/[USER]');
  sanitized = sanitized.replace(/\/home\/[^/]+/g, '/home/[USER]');
  sanitized = sanitized.replace(/C:\\Users\\[^\\]+/g, 'C:\\Users\\[USER]');

  return sanitized;
}

/**
 * Executes an appknox CLI command securely
 */
export async function executeAppknoxCommand(
  command: string,
  args: string[] = [],
  options: ExecutionOptions = {}
): Promise<CommandResult> {
  const { timeout = 120000, env: userEnv } = options; // Default 2 minute timeout

  logger.debug('Executing Appknox command', { command, args: args.length });

  // Validate all file path arguments
  args.forEach((arg) => {
    if (arg.startsWith('/') || arg.startsWith('./') || arg.startsWith('../')) {
      validateFilePath(arg);
    }
  });

  // Prepare environment with token from env vars or config file
  const env = await prepareEnvironment(userEnv);

  // Check if we have an access token
  if (!env.APPKNOX_ACCESS_TOKEN) {
    logger.error('No access token available');
    throw new AuthenticationError();
  }

  return new Promise((resolve, reject) => {
    // Use absolute path to appknox CLI to ensure it works in sandboxed environments (e.g., Claude Desktop)
    const appknoxPath = process.env.APPKNOX_CLI_PATH || '/usr/local/bin/appknox';

    logger.info('Executing appknox command', {
      appknoxPath,
      command,
      args,
      hasAccessToken: !!env.APPKNOX_ACCESS_TOKEN,
      timeout,
    });

    const childProcess = spawn(appknoxPath, [command, ...args], {
      env,
      shell: false, // Prevent command injection
    });

    let stdout = '';
    let stderr = '';
    let timeoutHandle: NodeJS.Timeout | null = null;
    let killed = false;

    // Set up timeout
    if (timeout > 0) {
      timeoutHandle = setTimeout(() => {
        killed = true;
        childProcess.kill('SIGTERM');
        logger.warn('Command timed out', { command, timeout });
        reject(new CommandTimeoutError(timeout));
      }, timeout);
    }

    childProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      stdout += chunk;
      logger.debug('stdout chunk', { command, chunk: chunk.substring(0, 500) });
    });

    childProcess.stderr.on('data', (data) => {
      const chunk = data.toString();
      stderr += chunk;
      logger.debug('stderr chunk', { command, chunk: chunk.substring(0, 500) });
    });

    childProcess.on('error', (error) => {
      if (timeoutHandle) clearTimeout(timeoutHandle);
      if (killed) return; // Ignore errors after timeout

      logger.error('Process spawn error', {
        command,
        args,
        errorCode: (error as NodeJS.ErrnoException).code,
        errorMessage: error.message,
      });

      // Check if appknox CLI is not installed
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        logger.error('Appknox CLI not found at path', { appknoxPath });
        reject(new CLINotFoundError());
      } else {
        logger.error('Command execution failed', error);
        reject(new CommandExecutionError(sanitizeError(error.message)));
      }
    });

    childProcess.on('close', (exitCode) => {
      if (timeoutHandle) clearTimeout(timeoutHandle);
      if (killed) return; // Already handled by timeout

      const result = {
        stdout: stdout.trim(),
        stderr: sanitizeError(stderr.trim()),
        exitCode: exitCode || 0,
      };

      logger.info('Command completed', {
        command,
        args,
        exitCode,
        stdoutLength: stdout.length,
        stderrLength: stderr.length,
        stdout: stdout.substring(0, 1000),
        stderr: stderr.substring(0, 1000),
      });

      if (exitCode !== 0) {
        logger.debug('Command completed with non-zero exit code', { command, exitCode });
      } else {
        logger.debug('Command completed successfully', { command });
      }

      resolve(result);
    });
  });
}

/**
 * Executes a command and returns the stdout, throwing an error if the command fails
 */
export async function executeAppknoxCommandStrict(
  command: string,
  args: string[] = [],
  options: ExecutionOptions = {}
): Promise<string> {
  const result = await executeAppknoxCommand(command, args, options);

  if (result.exitCode !== 0) {
    const errorMessage = result.stderr || result.stdout || 'Command failed';
    logger.error('Command failed with error', undefined, { command, exitCode: result.exitCode });

    // Check for authentication errors in the output
    if (errorMessage.includes('401') || errorMessage.includes('Unauthorized')) {
      throw new AuthenticationError();
    }

    throw new CommandExecutionError(`Appknox CLI error: ${errorMessage}`, result.exitCode);
  }

  return result.stdout;
}
