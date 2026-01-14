#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { tools } from './tools.js';
import { classifyError, AppknoxMCPError } from './errors.js';
import logger from './logger.js';

/**
 * Appknox MCP Server
 *
 * A secure Model Context Protocol server that wraps the Appknox CLI
 * for mobile application security testing.
 *
 * Security Features:
 * - Credentials from environment variables or config file (never in arguments)
 * - Input validation and sanitization
 * - Process isolation for each CLI invocation
 * - Error message sanitization to prevent info leakage
 */

class AppknoxMCPServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: 'appknox-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
    this.setupErrorHandling();
  }

  private setupHandlers(): void {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      logger.debug('Listing available tools');
      return {
        tools: tools.map((tool) => ({
          name: tool.name,
          description: tool.description,
          inputSchema: tool.inputSchema,
        })),
      };
    });

    // Handle tool execution
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const toolName = request.params.name;
      logger.info('Tool execution requested', { toolName });

      const tool = tools.find((t) => t.name === toolName);

      if (!tool) {
        logger.warn('Unknown tool requested', { toolName });
        throw new Error(`Unknown tool: ${toolName}`);
      }

      try {
        const result = await tool.handler(request.params.arguments || {});
        logger.info('Tool execution completed successfully', { toolName });
        return result;
      } catch (error) {
        // Classify and handle errors appropriately
        const mcpError = error instanceof AppknoxMCPError ? error : classifyError(error);

        logger.error('Tool execution failed', mcpError, {
          toolName,
          errorCode: mcpError.code,
        });

        // Re-throw with proper error message
        throw new Error(mcpError.message);
      }
    });
  }

  private setupErrorHandling(): void {
    // Handle uncaught errors
    this.server.onerror = (error) => {
      logger.error('MCP server error', error);
    };

    // Handle process errors
    process.on('uncaughtException', (error) => {
      logger.error('Uncaught exception', error);
      process.exit(1);
    });

    process.on('unhandledRejection', (reason, promise) => {
      logger.error('Unhandled rejection', reason, { promise: String(promise) });
      process.exit(1);
    });

    // Handle graceful shutdown
    process.on('SIGINT', () => {
      logger.info('Received SIGINT, shutting down gracefully');
      process.exit(0);
    });

    process.on('SIGTERM', () => {
      logger.info('Received SIGTERM, shutting down gracefully');
      process.exit(0);
    });
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);

    logger.info('Appknox MCP Server started');
    logger.info('Server version: 1.0.0');
    logger.info('Credentials will be read from:');
    logger.info('  1. APPKNOX_ACCESS_TOKEN environment variable');
    logger.info('  2. ~/.config/appknox.json (fallback)');
  }
}

// Start the server
const server = new AppknoxMCPServer();
server.run().catch((error) => {
  logger.error('Failed to start server', error);
  process.exit(1);
});
