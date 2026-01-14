/**
 * Simple logging system for the MCP server
 * Logs to stderr to avoid interfering with MCP protocol on stdout
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

class Logger {
  private level: LogLevel;
  private prefix: string;

  constructor(level: LogLevel = LogLevel.INFO, prefix: string = '[Appknox MCP]') {
    this.level = level;
    this.prefix = prefix;
  }

  /**
   * Set the minimum log level
   */
  setLevel(level: LogLevel): void {
    this.level = level;
  }

  /**
   * Format a log message with timestamp
   */
  private format(level: string, message: string, meta?: Record<string, unknown>): string {
    const timestamp = new Date().toISOString();
    const metaStr = meta ? ` ${JSON.stringify(meta)}` : '';
    return `${timestamp} ${this.prefix} ${level}: ${message}${metaStr}`;
  }

  /**
   * Log debug messages
   */
  debug(message: string, meta?: Record<string, unknown>): void {
    if (this.level <= LogLevel.DEBUG) {
      console.error(this.format('DEBUG', message, meta));
    }
  }

  /**
   * Log info messages
   */
  info(message: string, meta?: Record<string, unknown>): void {
    if (this.level <= LogLevel.INFO) {
      console.error(this.format('INFO', message, meta));
    }
  }

  /**
   * Log warning messages
   */
  warn(message: string, meta?: Record<string, unknown>): void {
    if (this.level <= LogLevel.WARN) {
      console.error(this.format('WARN', message, meta));
    }
  }

  /**
   * Log error messages
   */
  error(message: string, error?: Error | unknown, meta?: Record<string, unknown>): void {
    if (this.level <= LogLevel.ERROR) {
      const errorMeta = error instanceof Error
        ? { ...meta, error: error.message, stack: error.stack }
        : { ...meta, error: String(error) };
      console.error(this.format('ERROR', message, errorMeta));
    }
  }
}

// Create singleton logger instance
const logger = new Logger(
  process.env.LOG_LEVEL === 'debug' ? LogLevel.DEBUG : LogLevel.INFO
);

export default logger;
