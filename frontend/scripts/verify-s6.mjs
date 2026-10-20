// Real HTTP and Chromium, no request substitution. All child processes are owned.
import { chromium, expect } from '@playwright/test'
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { createWriteStream, mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { browserChannels, javaExecutable, contractPython } from '../config/runtime.ts'

const root = path.resolve(fileURLToPath(new URL('../..', import.meta.url)))
const output = path.resolve(process.argv[2])
mkdirSync(output, { recursive: false })
const children = [], errors = [], responses = []
let browser, passed = false
async function port() {
  const server = createServer()
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const chosen = server.address().port
  await new Promise(resolve => server.close(resolve))
  return chosen
}
function launch(name, command, args, env) {
  const child = spawn(command, args, { cwd: name === 'vite' ? path.join(root, 'frontend') : root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  const log = createWriteStream(path.join(output, name + '.log'), { flags: 'wx' })
  child.stdout.pipe(log); child.stderr.pipe(log)
  children.push(child)
  return child
}
async function wait(url, child) {
  for (let i = 0; i < 120; i++) {
    if (child.exitCode !== null) throw new Error('Owned service exited during startup')
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  throw new Error('Service startup timeout')
}
function validate(body, status, index) {
  const file = path.join(output, `response-${index}.json`)
  writeFileSync(file, JSON.stringify(body, null, 2))
  const result = spawnSync(contractPython(root), [path.join(root, 'contracts/validate_contract.py'), '--instance', file,
    '--path', '/api/v1/warehouse/metrics', '--status', String(status)], { encoding: 'utf8', windowsHide: true })
  if (result.status !== 0) throw new Error('Actual HTTP response schema failed: ' + result.stdout + result.stderr)
}
try {
  const apiPort = await port(), webPort = await port()
  const java = launch('java', javaExecutable(process.env.JAVA_HOME), ['-jar', path.join(root, 'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'),
    '--server.address=127.0.0.1', '--server.port=' + apiPort], process.env)
  await wait(`http://127.0.0.1:${apiPort}/health`, java)
  const vite = launch('vite', process.execPath, [path.join(root, 'frontend/node_modules/vite/bin/vite.js'),
    '--config', path.join(root, 'frontend/vite.config.ts'), '--host', '127.0.0.1', '--port', String(webPort), '--strictPort'],
    { ...process.env, DEV_BACKEND_URL: `http://127.0.0.1:${apiPort}` })
  await wait(`http://127.0.0.1:${webPort}`, vite)
  for (const [query, status] of [['cityId=s5-city', 200], ['cityId=s5-city&grain=HOUR', 200],
    ['cityId=s5-city&grain=DAY', 200], ['cityId=s5-other', 200], ['cityId=s5-city&grain=BAD', 400],
    ['cityId=s5-city&cityId=s5-city', 400], ['cityId=s5-city&from=bad', 400], ['cityId=unknown-city', 400]]) {
    const response = await fetch(`http://127.0.0.1:${apiPort}/api/v1/warehouse/metrics?${query}`)
    expect(response.status).toBe(status)
    const body = await response.json()
    validate(body, status, responses.length)
    responses.push({ query, status, body })
  }
  const city = responses[0].body
  expect(city.meta.sourceType).toBe('synthetic_test')
  expect(city.data.release.id).toBe('s6-failed-switch')
  expect(city.data.items.find(r => r.targetType === 'CITY')).toMatchObject({ sampleCount: 3, avgSpeedKmh: 40, congestionIndex: 5, speedSum: 120 })
  for (const channel of browserChannels()) {
    try { browser = await chromium.launch({ headless: true, ...(channel === 'chromium' ? {} : { channel }) }); break } catch {}
  }
  if (!browser) throw new Error('No actual Chromium available')
  const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } })
  page.on('pageerror', e => errors.push(e.message))
  await page.goto(`http://127.0.0.1:${webPort}`)
  await page.getByLabel('城市', { exact: true }).selectOption('s5-city')
  await page.getByRole('button', { name: '打开 Hive 离线分析', exact: true }).click()
  await expect(page.getByTestId('warehouse-release')).toContainText('s6-failed-switch')
  await expect(page.getByTestId('warehouse-metrics')).toContainText('40.00')
  await expect(page.getByTestId('warehouse-metrics')).toContainText('36.00')
  await expect(page.getByTestId('warehouse-metrics')).toContainText('18.00')
  await expect(page.getByTestId('warehouse-comparison')).toContainText('3 条，均速 40.00')
  await page.getByTestId('warehouse-panel').screenshot({ path: path.join(output, 'warehouse-desktop.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByTestId('warehouse-panel').screenshot({ path: path.join(output, 'warehouse-mobile.png') })
  expect(errors).toEqual([])
  passed = true
  console.log('S6_REAL_HTTP_CHROMIUM_PASS')
} finally {
  await browser?.close()
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      child.kill('SIGTERM')
      await Promise.race([new Promise(resolve => child.once('exit', resolve)), new Promise(resolve => setTimeout(resolve, 5000))])
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
    }
  }
  writeFileSync(path.join(output, 'manifest.json'), JSON.stringify({ passed, noRequestMocking: true, errors, responses }, null, 2))
}
