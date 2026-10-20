// Real Java -> Vite proxy -> isolated real Chromium browser. No request mocking.
import { chromium, expect as baseExpect } from '@playwright/test'
import { checkResponsiveMatrix, measureLayout } from './responsive-layout.mjs'
import { browserChannels, contractPython, javaExecutable } from '../config/runtime.ts'
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { once } from 'node:events'
import { createWriteStream, readFileSync, readdirSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const frontend = path.resolve(fileURLToPath(new URL('..', import.meta.url)))
const root = path.dirname(frontend)
const expect = baseExpect.configure({ timeout: 15000 })
const output = path.resolve(process.argv[2] ?? path.join(frontend, 'outputs', 'integration'))
mkdirSync(path.dirname(output), { recursive: true })
mkdirSync(output, { recursive: false }) // Refuse to replace previous evidence.
const manifest = { startedAt: new Date().toISOString(), noRequestMocking: true, steps: [], responses: [], processes: [], portDiagnostics: [], pageErrors: [] }
const owned = new Set()
const pendingResponses = []
let browser, page, vite, java
let phase = 'startup'

function step(name, details = {}) {
  manifest.steps.push({ name, at: new Date().toISOString(), ...details })
  console.log(`PASS ${name}`)
}

async function available(port) {
  const socket = createServer()
  try {
    await new Promise((resolve, reject) => {
      socket.once('error', reject)
      socket.listen({ port, host: '127.0.0.1', exclusive: true }, resolve)
    })
    return true
  } catch (error) {
    if (error.code !== 'EADDRINUSE' && error.code !== 'EACCES') throw error
    return false
  } finally { if (socket.listening) await new Promise(resolve => socket.close(resolve)) }
}

async function choosePort(preferred) {
  for (let port = preferred; port < preferred + 20; port++) {
    if (await available(port)) return port
    const diagnostics = process.platform === 'win32'
      ? spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
        `Get-NetTCPConnection -State Listen -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress`], { encoding: 'utf8', windowsHide: true })
      : spawnSync('ss', ['-ltnp', `sport = :${port}`], { encoding: 'utf8' })
    manifest.portDiagnostics.push({ port, occupied: true, readOnlyDiagnostic: diagnostics.stdout?.trim() || diagnostics.error?.message || 'Owner unavailable; port not touched' })
    console.log(`Port ${port} unavailable; recorded owner diagnostic; not terminating its owner`)
  }
  throw new Error('No local port available in the configured range')
}

function launch(name, command, args, env = process.env) {
  const log = createWriteStream(path.join(output, `${name}.log`), { flags: 'wx' })
  const child = spawn(command, args, { cwd: name.startsWith('java') ? path.join(root, 'backend') : frontend, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.pipe(log, { end: false }); child.stderr.pipe(log, { end: false })
  child.on('close', () => log.end())
  child.on('error', error => { child.launchError = error })
  const record = { name, pid: child.pid, command: [command, ...args], startedAt: new Date().toISOString() }
  child.record = record
  child.logFile = path.join(output, `${name}.log`)
  manifest.processes.push(record); owned.add(child)
  return child
}

async function stop(child) {
  if (!child || !owned.has(child)) return
  if (child.exitCode === null && child.signalCode === null) {
    const closed = once(child, 'close')
    child.kill('SIGTERM')
    let timer
    try { await Promise.race([closed, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`Owned process ${child.pid} failed to stop`)), 15000) })]) }
    catch {
      // Escalate only for the exact child owned by this driver, never by port or process name.
      child.kill('SIGKILL')
      await Promise.race([closed, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`Owned process ${child.pid} failed to terminate`)), 5000) })])
    }
    finally { clearTimeout(timer) }
  }
  child.record.exitCode = child.exitCode
  child.record.signal = child.signalCode
  child.record.stoppedAt = new Date().toISOString()
  child.record.stopped = child.exitCode !== null || child.signalCode !== null
  owned.delete(child)
}

async function waitForHttp(url, child) {
  const end = Date.now() + 60000
  while (Date.now() < end) {
    if (child.launchError) throw child.launchError
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Owned service ${child.record.name} exited before readiness`)
    if (child.record.name.startsWith('java') && (!existsSync(child.logFile) || !readFileSync(child.logFile, 'utf8').includes('Started UrbanCommuteApplication'))) {
      await new Promise(resolve => setTimeout(resolve, 200)); continue
    }
    try { const response = await fetch(url, { signal: AbortSignal.timeout(1000) }); if (response.ok) return }
    catch { /* Startup is polled without changing network configuration. */ }
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  throw new Error(`Service startup timed out: ${url}`)
}

let javaPort, vitePort
async function startJava(name, empty = false) {
  const javaHome = process.env.JAVA_HOME
  if (!javaHome) throw new Error('JAVA_HOME is required for this process')
  const jar = path.join(root, 'backend', 'target', 'urban-commute-backend-0.1.0-SNAPSHOT.jar')
  const child = launch(name, javaExecutable(javaHome), ['-jar', jar, '--server.address=127.0.0.1', `--server.port=${javaPort}`, ...(empty ? ['--commute.cities.dataset-filter=absent-ci-dataset'] : [])])
  await waitForHttp(`http://127.0.0.1:${javaPort}/health`, child)
  return child
}

let exitCode = 0
try {
  javaPort = await choosePort(8080); vitePort = await choosePort(5173)
  manifest.javaPort = javaPort; manifest.vitePort = vitePort
  manifest.backendTarget = `http://127.0.0.1:${javaPort}`
  java = await startJava('java-initial')
  vite = launch('vite', process.execPath, [path.join(frontend, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'], { ...process.env, DEV_BACKEND_URL: manifest.backendTarget })
  const base = `http://127.0.0.1:${vitePort}`
  await waitForHttp(base, vite)
  for (const channel of browserChannels()) {
    try { browser = await chromium.launch({ ...(channel === 'chromium' ? {} : { channel }), headless: true }); manifest.browserChannel = channel; break }
    catch (error) { manifest.steps.push({ name: 'browser-launch-fallback', channel, error: error.message.split('\n')[0] }) }
  }
  if (!browser) throw new Error('Configured browser could not be launched; install Playwright Chromium in CI or use local Chrome/Edge. No browser evidence available')
  manifest.browserVersion = browser.version()
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  page = await context.newPage()
  page.on('pageerror', error => manifest.pageErrors.push(error.message))
  page.on('response', response => {
    const url = new URL(response.url())
    if (url.origin !== base || !['/health', '/api/v1/cities'].includes(url.pathname)) return
    const responsePhase = phase
    const index = manifest.responses.length
    const row = { index, phase: responsePhase, url: response.url(), contractPath: url.pathname, status: response.status(), headers: response.headers() }
    manifest.responses.push(row)
    pendingResponses.push((async () => {
      try {
        const body = await response.body()
        row.bodyFile = `response-${index}.${response.headers()['content-type']?.includes('application/json') ? 'json' : 'txt'}`
        writeFileSync(path.join(output, row.bodyFile), body, { flag: 'wx' })
        row.source = response.status() !== 200 && ['backend-stopped', 'empty-restarting'].includes(responsePhase) ? 'vite-proxy-transport-failure' : 'java-via-vite'
      } catch (error) { row.captureError = error.message }
    })())
  })
  phase = 'initial'
  await page.goto(base)
  await expect(page.getByTestId('service-status')).toHaveText('服务正常')
  await expect(page.getByLabel('城市', { exact: true })).toBeVisible()
  const options = await page.locator('#city-select option').allTextContents()
  expect(options).toEqual(['请选择城市', '北京', '上海'])
  await page.getByLabel('城市', { exact: true }).selectOption('sample-beijing')
  await expect(page.getByTestId('selected-city')).toHaveText('北京')
  step('real-beijing-selection', { cityId: 'sample-beijing' })
  await page.getByLabel('城市', { exact: true }).selectOption('sample-shanghai')
  await expect(page.getByTestId('selected-city')).toHaveText('上海')
  await expect(page.locator('.source-badge')).toContainText('synthetic_test')
  await expect(page.locator('.data-notice')).toContainText('synthetic_test 合成测试数据')
  await expect(page.locator('.data-notice')).not.toContainText('北京、上海')
  await page.screenshot({ path: path.join(output, 'success.png'), fullPage: true })
  step('real-shanghai-selection-and-source', { cityId: 'sample-shanghai', options })
  await page.setViewportSize({ width: 1024, height: 768 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: path.join(output, 'desktop-1024.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: path.join(output, 'narrow-390.png'), fullPage: true })
  await checkResponsiveMatrix(page, expect, output, 'responsive')
  await page.setViewportSize({ width: 1365, height: 900 })
  step('responsive-layout-no-horizontal-overflow')

  phase = 'backend-stopped'
  await stop(java)
  // Wait for the page's automatic 15-second check, without clicking or mocking.
  await expect(page.getByTestId('service-status')).toHaveText('服务暂不可用', { timeout: 22000 })
  await expect(page.getByText('城市列表获取失败', { exact: true })).toBeVisible()
  await expect(page.locator('#city-select')).toHaveCount(0)
  await expect(page.locator('.data-notice')).toContainText('暂无法确认数据来源')
  await page.screenshot({ path: path.join(output, 'backend-stopped.png'), fullPage: true })
  await checkResponsiveMatrix(page, expect, output, 'error-responsive')
  step('backend-stop-detected-automatically', { noRetryClick: true })

  java = await startJava('java-restored')
  phase = 'restored'
  await page.getByRole('button', { name: '重新请求', exact: true }).click()
  await expect(page.getByTestId('service-status')).toHaveText('服务正常')
  await expect(page.locator('#city-select')).toBeVisible()
  await page.screenshot({ path: path.join(output, 'restored.png'), fullPage: true })
  step('backend-restart-manual-retry-restored-success')

  phase = 'browser-offline'
  await context.setOffline(true)
  await page.getByRole('button', { name: '重新请求', exact: true }).click()
  await expect(page.getByTestId('service-status')).toHaveText('服务暂不可用')
  await expect(page.locator('.error-message')).toContainText('无法连接服务')
  step('actual-browser-network-offline-state')
  await context.setOffline(false)
  phase = 'network-restored'
  await page.getByRole('button', { name: '重新请求', exact: true }).click()
  await expect(page.getByTestId('service-status')).toHaveText('服务正常')
  step('browser-network-retry-restored-success')

  // Automatic refresh can run while the next Java process is starting on slower machines.
  phase = 'empty-restarting'
  await stop(java)
  java = await startJava('java-empty', true)
  phase = 'empty'
  await page.getByRole('button', { name: '重新请求', exact: true }).click()
  await expect(page.getByText('暂无可选城市', { exact: true })).toBeVisible()
  await expect(page.getByTestId('service-status')).toHaveText('服务正常')
  await expect(page.locator('.source-badge')).toContainText('database_catalog')
  await expect(page.locator('.data-notice')).toContainText('本次 API 未返回城市条目')
  await expect(page.locator('.data-notice')).not.toContainText('synthetic_test')
  await page.screenshot({ path: path.join(output, 'empty.png'), fullPage: true })
  step('real-java-empty-list-rendered-as-success')
  expect(manifest.pageErrors).toEqual([])
} catch (error) {
  exitCode = 1
  manifest.failure = error.stack
  console.error(error)
  if (page && !page.isClosed()) {
    await measureLayout(page).then(layout => writeFileSync(path.join(output, 'failure-layout.json'), JSON.stringify(layout, null, 2))).catch(() => {})
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
  }
} finally {
  await Promise.allSettled(pendingResponses)
  if (browser) await browser.close()
  for (const child of [...owned]) {
    try { await stop(child) } catch (error) { exitCode = 1; manifest.cleanupFailure = error.message }
  }
  manifest.cleanup = { javaPortAvailable: javaPort ? await available(javaPort) : null, vitePortAvailable: vitePort ? await available(vitePort) : null, remainingOwnedChildren: owned.size }
  if (owned.size || manifest.cleanup.javaPortAvailable === false || manifest.cleanup.vitePortAvailable === false) exitCode = 1
  const walk = directory => readdirSync(directory, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(path.join(directory, entry.name)) : [path.join(directory, entry.name)])
  const sources = [...walk(path.join(frontend, 'src')), ...walk(path.join(frontend, 'config')),
    ...['index.html', 'vite.config.ts', 'tsconfig.json', 'package.json', 'package-lock.json'].map(name => path.join(frontend, name))]
  manifest.sourceHashes = Object.fromEntries(sources.map(file => [path.relative(frontend, file).replaceAll('\\', '/'), createHash('sha256').update(readFileSync(file)).digest('hex')]))
  manifest.backendJarSha256 = createHash('sha256').update(readFileSync(path.join(root, 'backend', 'target', 'urban-commute-backend-0.1.0-SNAPSHOT.jar'))).digest('hex')
  manifest.testDriverSha256 = createHash('sha256').update(readFileSync(fileURLToPath(import.meta.url))).digest('hex')
  manifest.driverExitCode = exitCode; manifest.finishedAt = new Date().toISOString()
  writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' })
}
if (exitCode === 0) {
  const python = contractPython(root)
  const result = spawnSync(python, [path.join(frontend, 'scripts', 'validate-captures.py'), output], { cwd: root, stdio: 'inherit', windowsHide: true })
  exitCode = result.status ?? 1
  manifest.schemaValidationExitCode = exitCode
  manifest.driverExitCode = exitCode
  writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
}
console.log(`BROWSER_INTEGRATION_EXIT=${exitCode}; EVIDENCE=${output}`)
process.exitCode = exitCode
