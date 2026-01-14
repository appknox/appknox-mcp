#!/usr/bin/env node

/**
 * Build verification script
 * Verifies that all required files are present in the build directory
 */

import { existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

const requiredFiles = [
  'build/index.js',
  'build/tools.js',
  'build/executor.js',
  'build/errors.js',
  'build/logger.js',
];

const requiredDeclarationFiles = [
  'build/index.d.ts',
  'build/tools.d.ts',
  'build/executor.d.ts',
  'build/errors.d.ts',
  'build/logger.d.ts',
];

console.log('Verifying build output...\n');

let allGood = true;

// Check required JS files
console.log('Checking JavaScript files:');
for (const file of requiredFiles) {
  const fullPath = join(projectRoot, file);
  const exists = existsSync(fullPath);
  console.log(`  ${exists ? '✓' : '✗'} ${file}`);
  if (!exists) allGood = false;
}

console.log('\nChecking TypeScript declaration files:');
for (const file of requiredDeclarationFiles) {
  const fullPath = join(projectRoot, file);
  const exists = existsSync(fullPath);
  console.log(`  ${exists ? '✓' : '✗'} ${file}`);
  if (!exists) allGood = false;
}

// Check that index.js has shebang
console.log('\nChecking shebang in index.js:');
import { readFileSync } from 'fs';
const indexContent = readFileSync(join(projectRoot, 'build/index.js'), 'utf-8');
const hasShebang = indexContent.startsWith('#!/usr/bin/env node');
console.log(`  ${hasShebang ? '✓' : '✗'} Shebang present`);
if (!hasShebang) allGood = false;

console.log('\n' + (allGood ? '✅ Build verification passed!' : '❌ Build verification failed!'));
process.exit(allGood ? 0 : 1);
