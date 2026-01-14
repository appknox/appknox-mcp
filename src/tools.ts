import { z } from 'zod';
import {
  executeAppknoxCommandStrict,
  executeAppknoxCommand,
  validateNumericId,
  validateRiskThreshold,
} from './executor.js';

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
  report_id: z.number().int().positive().describe('Report ID to download'),
  output_path: z.string().describe('Output file path'),
  format: z.enum(['csv', 'excel']).describe('Report format'),
});

const ScheduleDastAutomationSchema = z.object({
  file_id: z.number().int().positive().describe('File ID to schedule DAST for'),
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
    description: 'List all files for a specific project with optional version filtering',
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
    description: 'List all security analyses for a specific file',
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
    description: 'Upload a mobile application package (APK/IPA) for security scanning. Returns the file ID.',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: {
          type: 'string',
          description: 'Local path to the APK or IPA file (required)',
        },
      },
      required: ['file_path'],
    },
    handler: async (args: unknown) => {
      const params = UploadSchema.parse(args);
      const result = await executeAppknoxCommandStrict('upload', [params.file_path]);
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
    description: 'Check for vulnerabilities based on risk threshold. Fails (exit code 1) if vulnerabilities above threshold are found.',
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
    description: 'Download a vulnerability report in CSV or Excel format',
    inputSchema: {
      type: 'object',
      properties: {
        report_id: {
          type: 'number',
          description: 'Report ID to download (required)',
        },
        output_path: {
          type: 'string',
          description: 'Output file path (required)',
        },
        format: {
          type: 'string',
          enum: ['csv', 'excel'],
          description: 'Report format: csv or excel (required)',
        },
      },
      required: ['report_id', 'output_path', 'format'],
    },
    handler: async (args: unknown) => {
      const params = ReportsDownloadSchema.parse(args);
      validateNumericId(params.report_id, 'report_id');

      const subcommand = params.format === 'csv' ? 'summary-csv' : 'summary-excel';
      const cmdArgs = [
        'download',
        subcommand,
        params.report_id.toString(),
        '--output',
        params.output_path,
      ];

      const result = await executeAppknoxCommandStrict('reports', cmdArgs);
      return {
        content: [{
          type: 'text',
          text: `Report downloaded successfully to: ${params.output_path}`,
        }],
      };
    },
  },
  {
    name: 'appknox_schedule_dast',
    description: 'Schedule an automated dynamic application security testing (DAST) scan for a file',
    inputSchema: {
      type: 'object',
      properties: {
        file_id: {
          type: 'number',
          description: 'File ID to schedule DAST for (required)',
        },
      },
      required: ['file_id'],
    },
    handler: async (args: unknown) => {
      const params = ScheduleDastAutomationSchema.parse(args);
      validateNumericId(params.file_id, 'file_id');

      const result = await executeAppknoxCommandStrict('schedule-dast-automation', [params.file_id.toString()]);
      return { content: [{ type: 'text', text: result }] };
    },
  },
  {
    name: 'appknox_dastcheck',
    description: 'Check the status of a dynamic scan and display results when complete',
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
