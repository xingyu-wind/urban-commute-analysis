// Real Java -> Vite proxy -> isolated real Chromium browser. No request mocking.
import { chromium, expect as baseExpect } from '@playwright/test'
import { checkResponsiveMatrix, checkDeferredChartResize, installResizeProbe } from './responsive-layout.mjs'
import { checkEtl } from './s5-etl-check.mjs'
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
const output = path.resolve(process.argv[2] ?? path.join(frontend, 'outputs', 's4-integration'))
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

function database(action) {
  const result = spawnSync(contractPython(root), [path.join(root, 'scripts/s4_database.py'), action], { cwd: root, encoding: 'utf8', windowsHide: true })
  if (result.status !== 0) throw new Error(`Controlled database ${action} failed; see private local diagnostics`)
  step(`database-${action}`, { result: JSON.parse(result.stdout) })
}
let exitCode = 0, mutated = false
try {
  javaPort = await choosePort(8080); vitePort = await choosePort(5173)
  java = await startJava('java-s4')
  const backend = `http://127.0.0.1:${javaPort}`
  vite = launch('vite-s4', process.execPath, [path.join(frontend, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'], { ...process.env, DEV_BACKEND_URL: backend })
  const base = `http://127.0.0.1:${vitePort}`
  await waitForHttp(base, vite)
  for (const channel of browserChannels()) {
    try { browser = await chromium.launch({ ...(channel === 'chromium' ? {} : { channel }), headless: true }); manifest.browserChannel = channel; break }
    catch { /* Try the explicitly supported local browser fallback. */ }
  }
  if (!browser) throw new Error('No supported real Chromium browser available')
  manifest.browserVersion = browser.version()
  const context = await browser.newContext({ viewport: { width: 1500, height: 1080 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  await installResizeProbe(context)
  page = await context.newPage()
  page.on('pageerror', error => manifest.pageErrors.push(error.stack || error.message))
  // Capture all Java traffic responses, including negative HTTP cases. No route interception.
  context.on('response', response => {
    const uri = new URL(response.url())
    if (!uri.pathname.startsWith('/api/v1/traffic/')) return
    const index = manifest.responses.length
    const file = `response-${index}.json`
    const record = { path: uri.pathname, status: response.status(), requestId: response.headers()['x-request-id'], file }
    manifest.responses.push(record)
    pendingResponses.push(response.body().then(body => writeFileSync(path.join(output, file), body)).catch(error => { manifest.pageErrors.push(`capture: ${error.message}`) }))
  })
  async function directGet(url) {
    const response = await context.request.get(url)
    const uri = new URL(url)
    const file = `response-${manifest.responses.length}.json`
    manifest.responses.push({ path: uri.pathname, status: response.status(), requestId: response.headers()['x-request-id'], file })
    writeFileSync(path.join(output, file), await response.body())
    return response
  }
  await page.goto(base)
  await expect(page.locator('#city-select')).toBeVisible()
  if (process.env.S5_FIXTURE_OUTPUT) {
    await checkEtl({ page, expect, context, backend, output, root, python: contractPython(root), step, directGet })
  } else {
  await page.locator('#city-select').selectOption('s4-demo-city')
  await page.getByRole('button', { name: '合成样本时段', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('36.00')
  await expect(page.getByTestId('kpi-count')).toContainText('3')
  await expect(page.getByTestId('kpi-congestion')).toContainText('5.00')
  await expect(page.locator('.traffic-provenance')).toContainText('synthetic_test')
  await expect(page.locator('[data-map-point]')).toHaveCount(1)
  await expect(page.locator('.map-panel')).toContainText('1 个区域缺少坐标已省略')
  await expect(page.locator('.traffic-chart svg')).toHaveCount(3)
  await page.screenshot({ path: path.join(output, 'dashboard-desktop.png'), fullPage: true })
  step('actual-api-kpi-charts-and-wgs84-map', { citySamples: 3, speed: 36, congestion: 5, noRoadGeometry: true })

  await checkDeferredChartResize(page, expect, output)
  step('deferred-chart-resize-contained-and-observer-completed')
  // Exercise the existing map/filter/pagination flow on the formerly failing mobile width.
  await page.setViewportSize({ width: 390, height: 844 })

  // Actual SVG point click, then keyboard-accessible equivalent to clear the same selection.
  const mapSymbol = page.locator('.map-panel .traffic-chart svg path[fill="#48d9bf"]').first()
  await expect(mapSymbol).toBeVisible()
  // ResizeObserver completion does not imply the SVG symbol's animated transform
  // has reached its new position. Require the real symbol inside the resized chart
  // and retain Playwright's normal stable/visible/hit-target checks for the click.
  await expect.poll(() => mapSymbol.evaluate(node => {
    const point = node.getBoundingClientRect()
    const chart = node.closest('.traffic-chart').getBoundingClientRect()
    return point.left >= chart.left && point.right <= chart.right
      && point.top >= chart.top && point.bottom <= chart.bottom
  })).toBe(true)
  await mapSymbol.click()
  await expect(page.locator('.filter-caption')).toContainText('演示东区')
  await expect(page.getByTestId('roads-table')).toContainText('演示路段A')
  await expect(page.getByTestId('roads-table')).not.toContainText('演示路段B')
  await page.locator('[data-map-point]').click()
  await expect(page.getByTestId('roads-table')).toContainText('演示路段B')
  step('actual-map-point-click-linked-to-road-query')

  await page.getByLabel('每页路段数', { exact: true }).selectOption('1')
  await expect(page.getByTestId('roads-table')).toContainText('演示路段A')
  await page.getByRole('button', { name: '路段下一页', exact: true }).click()
  await expect(page.getByTestId('roads-table')).toContainText('演示路段B')
  await page.getByLabel('路段关键词', { exact: true }).fill('不存在的路段')
  await page.getByLabel('路段关键词', { exact: true }).press('Tab')
  await expect(page.getByTestId('roads-empty')).toBeVisible()
  await page.getByLabel('路段关键词', { exact: true }).fill('')
  await page.getByLabel('路段关键词', { exact: true }).press('Tab')
  await page.getByLabel('每页路段数', { exact: true }).selectOption('10')
  await expect(page.getByTestId('roads-table')).toContainText('演示路段B')
  step('literal-search-empty-results-and-pagination')

  await page.getByLabel('趋势粒度', { exact: true }).selectOption('hour')
  await expect(page.locator('.trend-panel')).toContainText('HOURLY')
  await page.locator('.chart-data summary').click()
  await expect(page.locator('.chart-data tbody tr')).toHaveCount(48)
  await page.locator('.chart-data summary').click()
  await page.getByLabel('趋势粒度', { exact: true }).selectOption('day')
  await expect(page.locator('.trend-panel')).toContainText('DAILY')
  // ECharts SVG mouse hover exposes its interactive tooltip.
  await page.locator('.trend-panel .traffic-chart').hover({ position: { x: 170, y: 110 } })
  step('hourly-sparse-buckets-and-interactive-svg-charts')

  database('mutate'); mutated = true
  await page.getByRole('button', { name: '刷新分析', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('42.00')
  await expect(page.getByTestId('kpi-count')).toContainText('3')
  await page.screenshot({ path: path.join(output, 'database-mutated-42.png'), fullPage: true })
  step('mysql-mutation-reflected-through-java-api-in-browser', { speed: 42, count: 3 })
  database('restore'); mutated = false
  await page.getByRole('button', { name: '刷新分析', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('36.00')
  step('controlled-observation-restored-and-ui-refreshed')

  await checkResponsiveMatrix(page, expect, output, 's4-responsive')
  for (const width of [1024, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: path.join(output, `responsive-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1500, height: 1080 })
  await page.getByRole('button', { name: '比赛大屏', exact: true }).click()
  await expect(page.locator('.traffic-workspace')).toHaveClass(/presentation/)
  await page.screenshot({ path: path.join(output, 'presentation.png'), fullPage: true })
  await checkResponsiveMatrix(page, expect, output, 'presentation-responsive', '.traffic-workspace.presentation')
  await page.getByRole('button', { name: '退出大屏', exact: true }).click()
  step('competition-presentation-and-responsive-390-1024')

  await page.getByLabel('开始日期 UTC', { exact: true }).fill('2026-10-18')
  await page.getByLabel('结束日期 UTC', { exact: true }).fill('2026-10-19')
  await expect(page.getByTestId('traffic-empty')).toBeVisible()
  await expect(page.getByTestId('kpi-speed')).toContainText('—')
  await expect(page.getByTestId('kpi-count')).toContainText('0')
  await page.screenshot({ path: path.join(output, 'empty-observations.png'), fullPage: true })
  await page.getByRole('button', { name: '合成样本时段', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('36.00')
  // Different real catalog city has no traffic, then rapidly return to the S4 city.
  await page.locator('#city-select').selectOption('sample-beijing')
  await expect(page.getByTestId('traffic-empty')).toBeVisible()
  await expect(page.locator('.map-panel')).toContainText('合成一区')
  await page.locator('#city-select').selectOption('sample-shanghai')
  await page.locator('#city-select').selectOption('s4-demo-city')
  await expect(page.getByTestId('kpi-speed')).toContainText('36.00')
  step('empty-null-metrics-and-city-selection-without-stale-overwrite')

  const q = '?cityId=s4-demo-city&from=2026-10-15T00:00:00Z&to=2026-10-17T00:00:00Z'
  for (const endpoint of ['summary', 'series', 'regions', 'roads']) {
    const response = await directGet(`${backend}/api/v1/traffic/${endpoint}${q}`)
    expect(response.status()).toBe(200)
  }
  for (const query of [q + '&cityId=duplicate', q + '&datasetId=missing', q + '&pageSize=101']) {
    const response = await directGet(`${backend}/api/v1/traffic/roads${query}`)
    expect(response.status()).toBe(400)
  }
  step('actual-http-all-four-endpoints-and-invalid-parameters')

  await stop(java)
  // Separate unavailable datasource: no live schema/process/account is modified.
  const unavailablePort = await choosePort(33191)
  java = launch('java-outage', javaExecutable(process.env.JAVA_HOME), ['-jar', path.join(root, 'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'),
    '--server.address=127.0.0.1', `--server.port=${javaPort}`, '--spring.flyway.enabled=false', '--spring.datasource.hikari.initialization-fail-timeout=-1',
    '--spring.datasource.hikari.connection-timeout=1000', `--spring.datasource.url=jdbc:mysql://127.0.0.1:${unavailablePort}/unavailable?connectTimeout=200&socketTimeout=200`,
    '--spring.datasource.username=outage-test', '--spring.datasource.password=not-a-real-password'])
  await waitForHttp(`${backend}/health`, java)
  for (const endpoint of ['summary', 'series', 'regions', 'roads']) {
    const response = await directGet(`${backend}/api/v1/traffic/${endpoint}${q}`)
    expect(response.status()).toBe(503)
    expect((await response.json()).code).toBe('SERVICE_UNAVAILABLE')
  }
  await page.getByRole('button', { name: '重新请求', exact: true }).click()
  await expect(page.getByText('城市列表获取失败', { exact: true })).toBeVisible()
  await expect(page.getByTestId('traffic-dashboard')).toHaveCount(0)
  await page.screenshot({ path: path.join(output, 'database-outage.png'), fullPage: true })
  step('actual-database-unavailable-safe-503-and-stale-dashboard-removed')
  }
  expect(manifest.pageErrors).toEqual([])
} catch (error) {
  exitCode = 1; manifest.failure = error.stack; console.error(error)
  if (page && !page.isClosed()) await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
} finally {
  if (mutated) { try { database('restore') } catch (error) { exitCode = 1; manifest.restoreFailure = error.message } }
  await Promise.allSettled(pendingResponses)
  if (browser) await browser.close()
  for (const child of [...owned]) { try { await stop(child) } catch (error) { exitCode = 1; manifest.cleanupFailure = error.message } }
  manifest.cleanup = { remainingOwnedChildren: owned.size, javaPortAvailable: javaPort ? await available(javaPort) : null, vitePortAvailable: vitePort ? await available(vitePort) : null }
  if (owned.size || manifest.cleanup.javaPortAvailable === false || manifest.cleanup.vitePortAvailable === false) exitCode = 1
  manifest.exitCode = exitCode; manifest.finishedAt = new Date().toISOString()
  writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
}
process.exitCode = exitCode

