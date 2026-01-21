import { z } from 'zod';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  executeAppknoxCommandStrict,
  executeAppknoxCommand,
  validateNumericId,
  validateRiskThreshold,
} from './executor.js';
import logger from './logger.js';

// Zod schemas for input validation
const WhoamiSchema = z.object({});

const OrganizationsSchema = z.object({});

const ProjectsSchema = z.object({
  platform: z.string().optional().describe('Filter by platform (e.g., android, ios)'),
  package_name: z.string().optional().describe('Filter by package name'),
  query: z.string().optional().describe('Search query to filter projects'),
  offset: z.number().int().min(0).optional().describe('Pagination offset'),
  limit: z.number().int().min(1).max(100).optional().describe('Results per page (max 100)'),
});

const FilesSchema = z.object({
  project_id: z.number().int().positive().describe('Project ID'),
  version_code: z.string().optional().describe('Filter by version code'),
  offset: z.number().int().min(0).optional().describe('Pagination offset'),
  limit: z.number().int().min(1).max(100).optional().describe('Results per page (max 100)'),
});

const AnalysesSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to get analyses for'),
});

const VulnerabilitySchema = z.object({
  vulnerability_id: z.number().int().positive().describe('Vulnerability ID'),
});

const OwaspSchema = z.object({
  owasp_id: z.string().describe('OWASP ID (e.g., M1_2016)'),
});

const UploadSchema = z.object({
  file_path: z.string().describe('Local path to the APK or IPA file to upload'),
});

const CicheckSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to check'),
  risk_threshold: z.enum(['low', 'medium', 'high', 'critical']).describe('Minimum risk threshold'),
  timeout_minutes: z.number().int().min(1).max(60).optional().default(10).describe('Timeout in minutes'),
});

const SarifSchema = z.object({
  file_id: z.number().int().positive().describe('File ID'),
  risk_threshold: z.enum(['low', 'medium', 'high', 'critical']).describe('Minimum risk threshold'),
  output_path: z.string().optional().describe('Output file path for SARIF report'),
  timeout_minutes: z.number().int().min(1).max(60).optional().default(10).describe('Timeout in minutes'),
});

const ReportsCreateSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to create report for'),
});

const ReportsDownloadSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to download report for'),
});


const DastcheckSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to check DAST status for'),
  risk_threshold: z.enum(['low', 'medium', 'high', 'critical']).describe('Minimum risk threshold'),
});

// Tool definitions with handlers
export const tools = [
  {
    name: 'appknox_whoami',
    description: 'Get information about the currently authenticated Appknox user',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    handler: async () => {
      const result = await executeAppknoxCommandStrict('whoami');
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_organizations',
    description: 'List all organizations accessible to the authenticated user',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    handler: async () => {
      const result = await executeAppknoxCommandStrict('organizations');
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_projects',
    description: 'List all projects with optional filtering by platform, package name, or search query',
    inputSchema: {
      type: 'object',
      properties: {
        platform: {
          type: 'string',
          description: 'Filter by platform (e.g., android, ios)',
        },
        package_name: {
          type: 'string',
          description: 'Filter by package name',
        },
        query: {
          type: 'string',
          description: 'Search query to filter projects',
        },
        offset: {
          type: 'number',
          description: 'Pagination offset',
        },
        limit: {
          type: 'number',
          description: 'Results per page (max 100)',
        },
      },
    },
    handler: async (args: unknown) => {
      const params = ProjectsSchema.parse(args);
      const cmdArgs: string[] = [];

      if (params.platform) cmdArgs.push('--platform', params.platform);
      if (params.package_name) cmdArgs.push('--package_name', params.package_name);
      if (params.query) cmdArgs.push('--query', params.query);
      if (params.offset !== undefined) cmdArgs.push('--offset', params.offset.toString());
      if (params.limit !== undefined) cmdArgs.push('--limit', params.limit.toString());

      const result = await executeAppknoxCommandStrict('projects', cmdArgs);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_files',
    description: 'List all files (app versions) for a specific project. Requires project_id which can be obtained from appknox_projects.',
    inputSchema: {
      type: 'object',
      properties: {
        project_id: {
          type: 'number',
          description: 'Project ID (required)',
        },
        version_code: {
          type: 'string',
          description: 'Filter by version code',
        },
        offset: {
          type: 'number',
          description: 'Pagination offset',
        },
        limit: {
          type: 'number',
          description: 'Results per page (max 100)',
        },
      },
      required: ['project_id'],
    },
    handler: async (args: unknown) => {
      const params = FilesSchema.parse(args);
      validateNumericId(params.project_id, 'project_id');

      const cmdArgs: string[] = [params.project_id.toString()];
      if (params.version_code) cmdArgs.push('--version_code', params.version_code);
      if (params.offset !== undefined) cmdArgs.push('--offset', params.offset.toString());
      if (params.limit !== undefined) cmdArgs.push('--limit', params.limit.toString());

      const result = await executeAppknoxCommandStrict('files', cmdArgs);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_analyses',
    description: 'List all security analysis results (vulnerabilities) for a specific file. Requires file_id which can be obtained from appknox_files.',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID (required)',
        },
      },
      required: ['file_id'],
    },
    handler: async (args: unknown) => {
      const params = AnalysesSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');

      const result = await executeAppknoxCommandStrict('analyses', [params.file_id.toString()]);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_vulnerability',
    description: 'Get detailed information about a specific vulnerability',
    inputSchema: {
      type: 'object',
      properties: {
        vulnerability_id: {
          type: 'number',
          description: 'Vulnerability ID (required)',
        },
      },
      required: ['vulnerability_id'],
    },
    handler: async (args: unknown) => {
      const params = VulnerabilitySchema.parse(args);
      validateNumericId(params.vulnerability_id, 'vulnerability_id');

      const result = await executeAppknoxCommandStrict('vulnerability', [params.vulnerability_id.toString()]);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_owasp',
    description: 'Get OWASP category details by ID (e.g., M1_2016)',
    inputSchema: {
      type: 'object',
      properties: {
        owasp_id: {
          type: 'string',
          description: 'OWASP ID (e.g., M1_2016) (required)',
        },
      },
      required: ['owasp_id'],
    },
    handler: async (args: unknown) => {
      const params = OwaspSchema.parse(args);
      const result = await executeAppknoxCommandStrict('owasp', [params.owasp_id]);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_upload',
    description: 'Upload a mobile application package (APK/IPA) for security scanning. Returns the file ID. IMPORTANT: The file_path must be an absolute path on the HOST machine filesystem (e.g., /Users/username/Downloads/app.apk on Mac, or C:\\Users\\username\\Downloads\\app.apk on Windows). Paths inside Claude Desktop sandbox (/mnt/user-data/, /tmp/ inside sandbox) will NOT work. The user must provide the real path where the file exists on their actual computer, not paths from drag-and-drop uploads.',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: {
          type: 'string',
          description: 'Absolute path to the APK or IPA file on the local filesystem (required). Must be a real path like /Users/name/Downloads/app.apk, NOT a sandbox path like /mnt/user-data/uploads/',
        },
      },
      required: ['file_path'],
    },
    handler: async (args: unknown) => {
      const params = UploadSchema.parse(args);

      logger.info('Upload requested', {
        file_path: params.file_path,
        fileExists: fs.existsSync(params.file_path),
      });

      // Check if file exists
      if (!fs.existsSync(params.file_path)) {
        const error = `File not found: ${params.file_path}`;
        logger.error('Upload failed - file not found', { file_path: params.file_path });
        return {
          content: [{
            type: 'text',
            text: error,
          }],
          isError: true,
        };
      }

      // Get file stats
      const stats = fs.statSync(params.file_path);
      logger.info('File stats', {
        file_path: params.file_path,
        size: stats.size,
        isFile: stats.isFile(),
      });

      const result = await executeAppknoxCommandStrict('upload', [params.file_path]);

      logger.info('Upload completed', {
        file_path: params.file_path,
        result: result.substring(0, 500),
      });

      return {
        content: [{
          type: 'text',
          text: `File uploaded successfully. File ID: ${result}`,
        }],
      };
    },
  },
  {
    name: 'appknox_cicheck',
    description: 'Check for vulnerabilities based on risk threshold. Fails if vulnerabilities above threshold are found. Requires file_id (from appknox_files) and risk_threshold.',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID to check (required)',
        },
        risk_threshold: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Minimum risk threshold (required)',
        },
        timeout_minutes: {
          type: 'number',
          description: 'Timeout in minutes (default: 10)',
        },
      },
      required: ['file_id', 'risk_threshold'],
    },
    handler: async (args: unknown) => {
      const params = CicheckSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');
      validateRiskThreshold(params.risk_threshold);

      const cmdArgs = [
        params.file_id.toString(),
        '--risk-threshold',
        params.risk_threshold,
        '--timeout',
        params.timeout_minutes.toString(),
      ];

      // cicheck may exit with code 1 if vulnerabilities are found, which is expected
      const result = await executeAppknoxCommand('cicheck', cmdArgs, {
        timeout: params.timeout_minutes * 60 * 1000,
      });

      return {
        content: [{
          type: 'text',
          text: result.stdout || result.stderr,
        }],
        isError: result.exitCode !== 0,
      };
    },
  },
  {
    name: 'appknox_sarif',
    description: 'Generate a SARIF (Static Analysis Results Interchange Format) report for the scanned file',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID (required)',
        },
        risk_threshold: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Minimum risk threshold (required)',
        },
        output_path: {
          type: 'string',
          description: 'Output file path for SARIF report',
        },
        timeout_minutes: {
          type: 'number',
          description: 'Timeout in minutes (default: 10)',
        },
      },
      required: ['file_id', 'risk_threshold'],
    },
    handler: async (args: unknown) => {
      const params = SarifSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');
      validateRiskThreshold(params.risk_threshold);

      const cmdArgs = [
        params.file_id.toString(),
        '--risk-threshold',
        params.risk_threshold,
        '--timeout',
        params.timeout_minutes.toString(),
      ];

      if (params.output_path) {
        cmdArgs.push('--output', params.output_path);
      }

      const result = await executeAppknoxCommandStrict('sarif', cmdArgs, {
        timeout: params.timeout_minutes * 60 * 1000,
      });

      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_reports_create',
    description: 'Create a vulnerability analysis report for a file. Returns the report ID.',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID to create report for (required)',
        },
      },
      required: ['file_id'],
    },
    handler: async (args: unknown) => {
      const params = ReportsCreateSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');

      const result = await executeAppknoxCommandStrict('reports', ['create', params.file_id.toString()]);
      return {
        content: [{
          type: 'text',
          text: `Report created successfully. Report ID: ${result}`,
        }],
      };
    },
  },
  {
    name: 'appknox_reports_download',
    description: 'Download a vulnerability report for a file in CSV format. Requires file_id (from appknox_files). Automatically creates a new report if one does not exist. Returns the CSV content directly as text - no file path needed.',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID to download report for (required)',
        },
      },
      required: ['file_id'],
    },
    handler: async (args: unknown) => {
      const params = ReportsDownloadSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');

      // First, create a report for the file (this will return the report ID)
      let reportId: string;
      try {
        const createResult = await executeAppknoxCommandStrict('reports', ['create', params.file_id.toString()]);
        const trimmedResult = createResult.trim();

        // Check if the result contains an error (CLI may return 0 even on API errors)
        if (trimmedResult.includes('400') || trimmedResult.includes('404') || trimmedResult.includes('error')) {
          throw new Error(`API returned error: ${trimmedResult}. The scan may not be complete yet - some analyses are still in 'Waiting' status.`);
        }

        // Extract report ID (should be a numeric value)
        const reportIdMatch = trimmedResult.match(/(\d+)/);
        if (!reportIdMatch) {
          throw new Error(`Could not extract report ID from response: ${trimmedResult}`);
        }
        reportId = reportIdMatch[1];
      } catch (error) {
        throw new Error(`Failed to create report for file ${params.file_id}: ${error}`);
      }

      const tempDir = os.tmpdir();
      const tempFile = path.join(tempDir, `appknox_report_${params.file_id}_${Date.now()}.csv`);

      const cmdArgs = [
        'download',
        'summary-csv',
        reportId,
        '--output',
        tempFile,
      ];

      try {
        await executeAppknoxCommandStrict('reports', cmdArgs);

        // Read the file content
        const fileContent = fs.readFileSync(tempFile);

        // Clean up temp file
        fs.unlinkSync(tempFile);

        // Return CSV as text
        return {
          content: [{
            type: 'text',
            text: fileContent.toString('utf-8'),
          }],
        };
      } catch (error) {
        // Clean up temp file on error if it exists
        if (fs.existsSync(tempFile)) {
          fs.unlinkSync(tempFile);
        }
        throw error;
      }
    },
  },
  {
    name: 'appknox_dastcheck',
    description: 'Check the status of a dynamic scan and display results when complete. Requires file_id (from appknox_files) and risk_threshold.',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID to check DAST status for (required)',
        },
        risk_threshold: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Minimum risk threshold (required)',
        },
      },
      required: ['file_id', 'risk_threshold'],
    },
    handler: async (args: unknown) => {
      const params = DastcheckSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');
      validateRiskThreshold(params.risk_threshold);

      const cmdArgs = [
        params.file_id.toString(),
        '--risk-threshold',
        params.risk_threshold,
      ];

      // dastcheck may exit with code 1 if vulnerabilities are found
      const result = await executeAppknoxCommand('dastcheck', cmdArgs);

      return {
        content: [{
          type: 'text',
          text: result.stdout || result.stderr,
        }],
        isError: result.exitCode !== 0,
      };
    },
  },
];
