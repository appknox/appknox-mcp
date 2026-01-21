/**
 * Custom error classes for better error handling and reporting
 */

export class AppknoxMCPError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message);
    this.name = 'AppknoxMCPError';
    Error.captureStackTrace(this, this.constructor);
  }
}

export class CLINotFoundError extends AppknoxMCPError {
  constructor() {
    super(
      'Appknox CLI not found. Please install it first: ' +
      'https://github.com/appknox/appknox-go#installation',
      'CLI_NOT_FOUND'
    );
    this.name = 'CLINotFoundError';
  }
}

export class AuthenticationError extends AppknoxMCPError {
  constructor(message?: string) {
    super(
      message || 'Authentication failed. Please set APPKNOX_ACCESS_TOKEN environment variable ' +
      'or configure it using: appknox init',
      'AUTHENTICATION_FAILED'
    );
    this.name = 'AuthenticationError';
  }
}

export class ValidationError extends AppknoxMCPError {
  constructor(message: string) {
    super(`Validation error: ${message}`, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
  }
}

export class CommandTimeoutError extends AppknoxMCPError {
  constructor(timeoutMs: number) {
    super(`Command timed out after ${timeoutMs}ms`, 'COMMAND_TIMEOUT');
    this.name = 'CommandTimeoutError';
  }
}

export class CommandExecutionError extends AppknoxMCPError {
  constructor(message: string, public readonly exitCode?: number) {
    super(message, 'COMMAND_EXECUTION_ERROR');
    this.name = 'CommandExecutionError';
  }
}

export class FilePathError extends AppknoxMCPError {
  constructor(message: string) {
    super(message, 'FILE_PATH_ERROR');
    this.name = 'FilePathError';
  }
}

/**
 * Formats Zod validation errors into user-friendly messages
 */
function formatZodError(errorMessage: string): string {
  try {
    const errors = JSON.parse(errorMessage);
    if (Array.isArray(errors)) {
      const messages = errors.map((e: { path?: string[]; message?: string; expected?: string }) => {
        const field = e.path?.join('.') || 'unknown field';
        return `${field}: ${e.message || 'invalid value'}${e.expected ? ` (expected ${e.expected})` : ''}`;
      });
      return `Missing or invalid arguments: ${messages.join(', ')}`;
    }
  } catch {
    // Not a JSON error, return as is
  }
  return errorMessage;
}

/**
 * Determines error type from error message and creates appropriate error instance
 */
export function classifyError(error: unknown): AppknoxMCPError {
  const errorMessage = error instanceof Error ? error.message : String(error);

  // Check for Zod validation errors (JSON array format)
  if (errorMessage.startsWith('[') && errorMessage.includes('"code"')) {
    return new ValidationError(formatZodError(errorMessage));
  }

  // Check for CLI not found
  if (errorMessage.includes('ENOENT') || errorMessage.includes('not found')) {
    return new CLINotFoundError();
  }

  // Check for authentication errors
  if (
    errorMessage.includes('401') ||
    errorMessage.includes('Unauthorized') ||
    errorMessage.includes('Authentication') ||
    errorMessage.includes('Invalid token')
  ) {
    return new AuthenticationError();
  }

  // Check for validation errors
  if (errorMessage.includes('Invalid') || errorMessage.includes('must be')) {
    return new ValidationError(errorMessage);
  }

  // Check for timeout
  if (errorMessage.includes('timed out')) {
    return new CommandTimeoutError(0);
  }

  // Generic execution error
  if (error instanceof AppknoxMCPError) {
    return error;
  }

  return new CommandExecutionError(errorMessage);
}
