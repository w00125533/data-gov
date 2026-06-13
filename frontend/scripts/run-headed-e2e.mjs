import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const slowMo = process.env.PW_SLOW_MO ?? '700'
const isWindows = process.platform === 'win32'
const cwd = fileURLToPath(new URL('..', import.meta.url))
const playwrightBin = isWindows ? 'node_modules\\.bin\\playwright.cmd' : 'node_modules/.bin/playwright'
const command = isWindows ? 'cmd.exe' : playwrightBin
const args = [
  'test',
  'tests/e2e/formal-lineage.acceptance.spec.ts',
  '--headed',
  '--workers=1',
  ...process.argv.slice(2),
]
const spawnArgs = isWindows ? ['/d', '/s', '/c', playwrightBin, ...args] : args

const child = spawn(command, spawnArgs, {
  cwd,
  env: {
    ...process.env,
    PW_HEADED: '1',
    PW_SLOW_MO: slowMo,
  },
  stdio: 'inherit',
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 1)
})
