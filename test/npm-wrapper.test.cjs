const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const wrapper = require('../lib/wrapper.cjs');

test('buildCoreCommand uses local uv run inside repo checkout', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['auto', 'evidence.json', '--json'],
    localCoreAvailable: true,
  });

  assert.deepEqual(command, {
    executable: 'uv',
    args: ['run', '--project', '/repo/ai-crawler', 'ai-crawler', 'auto', 'evidence.json', '--json'],
  });
});

test('buildCoreCommand uses uvx published python core outside repo checkout', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['mcp'],
    localCoreAvailable: false,
  });

  assert.deepEqual(command, {
    executable: 'uvx',
    args: ['--python', '3.11', '--from', 'ai-crawler[all]', 'ai-crawler', 'mcp'],
  });
});

test('buildCoreCommand honors env overrides for published python spec', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['doctor'],
    localCoreAvailable: false,
    env: {
      AI_CRAWLER_PYTHON_SPEC: 'ai-crawler[http,mcp]',
      AI_CRAWLER_UVX_PYTHON: '3.13',
    },
  });

  assert.deepEqual(command, {
    executable: 'uvx',
    args: ['--python', '3.13', '--from', 'ai-crawler[http,mcp]', 'ai-crawler', 'doctor'],
  });
});

test('packageRootFromModuleDir resolves package root from lib directory', () => {
  const packageRoot = wrapper.packageRootFromModuleDir(path.join('/repo/ai-crawler', 'lib'));
  assert.equal(packageRoot, '/repo/ai-crawler');
});
