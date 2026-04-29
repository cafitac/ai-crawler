const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function packageRootFromModuleDir(moduleDir = __dirname) {
  return path.resolve(moduleDir, '..');
}

function localCoreAvailable(packageRoot) {
  return fs.existsSync(path.join(packageRoot, 'pyproject.toml'));
}

function publishedPythonSpec(env = process.env) {
  return env.AI_CRAWLER_PYTHON_SPEC || 'ai-crawler[all]';
}

function uvxPythonVersion(env = process.env) {
  return env.AI_CRAWLER_UVX_PYTHON || '3.11';
}

function buildCoreCommand({
  argv,
  packageRoot = packageRootFromModuleDir(),
  localCoreAvailable: hasLocalCore = localCoreAvailable(packageRoot),
  env = process.env,
}) {
  if (hasLocalCore) {
    return {
      executable: 'uv',
      args: ['run', '--project', packageRoot, 'ai-crawler', ...argv],
    };
  }

  return {
    executable: 'uvx',
    args: ['--python', uvxPythonVersion(env), '--from', publishedPythonSpec(env), 'ai-crawler', ...argv],
  };
}

function printHelp(packageRoot = packageRootFromModuleDir()) {
  const packageJsonPath = path.join(packageRoot, 'package.json');
  let version = '0.0.0';
  if (fs.existsSync(packageJsonPath)) {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    version = packageJson.version || version;
  }

  console.log(`ai-crawler npm wrapper v${version}

Usage:
  ai-crawler <core-cli-args...>

Behavior:
  - In the repo checkout, uses local Python core via 'uv run --project <repo> ai-crawler ...'
  - Outside the repo, uses published Python core via 'uvx --from "${publishedPythonSpec()}" ai-crawler ...'

Environment overrides:
  - AI_CRAWLER_PYTHON_SPEC   Override published Python package spec (default: ai-crawler[all])
  - AI_CRAWLER_UVX_PYTHON    Override uvx Python version (default: 3.11)`);
}

function runCli(argv, options = {}) {
  const args = Array.isArray(argv) ? argv : [];
  if (args.includes('--help') || args.includes('-h') || args[0] === 'help') {
    printHelp(options.packageRoot || packageRootFromModuleDir());
    return 0;
  }

  if (args.includes('--version') || args.includes('-V')) {
    const command = buildCoreCommand({
      argv: ['--version'],
      packageRoot: options.packageRoot,
      localCoreAvailable: options.localCoreAvailable,
      env: options.env,
    });
    return executeCommand(command, options);
  }

  const command = buildCoreCommand({
    argv: args,
    packageRoot: options.packageRoot,
    localCoreAvailable: options.localCoreAvailable,
    env: options.env,
  });
  return executeCommand(command, options);
}

function executeCommand(command, options = {}) {
  const spawn = options.spawnSync || spawnSync;
  const result = spawn(command.executable, command.args, {
    stdio: 'inherit',
    env: options.env || process.env,
    cwd: options.cwd || process.cwd(),
  });

  if (typeof result.status === 'number') {
    return result.status;
  }
  return 1;
}

module.exports = {
  buildCoreCommand,
  localCoreAvailable,
  packageRootFromModuleDir,
  printHelp,
  runCli,
};
