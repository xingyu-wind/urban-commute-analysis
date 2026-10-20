// Real HTTP and Chromium, no request substitution. All child processes are owned.
import { chromium, expect } from '@playwright/test'
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { createWriteStream, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { browserChannels, javaExecutable, contractPython } from '../config/runtime.ts'

const root = path.resolve(fileURLToPath(new URL('../..', import.meta.url)))
const output = path.resolve(process.argv[2])
const expected = JSON.parse(readFileSync(process.argv[3], 'utf8'))
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
    '--path', '/api/v1/predictions', '--status', String(status)], { encoding: 'utf8', windowsHide: true })
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
  for (const [query, status] of [['cityId=s7-city', 200], ['cityId=s7-empty', 200],
    ['cityId=s7-city&datasetId=s7-synthetic-v1', 200], ['cityId=s7-city&cityId=s7-city', 400],
    ['cityId=s7-city&from=bad', 400], ['cityId=unknown-city', 400], ['cityId=s7-city&datasetId=missing', 400], ['', 400]]) {
    const response = await fetch(`http://127.0.0.1:${apiPort}/api/v1/predictions?${query}`)
    expect(response.status).toBe(status)
    const body = await response.json()
    validate(body, status, responses.length)
    responses.push({ query, status, body })
  }
  const actual = responses[0].body
  expect(actual.meta.sourceType).toBe('synthetic_test')
  expect(actual.data.release.jobId).toBe(expected.jobId)
  expect(actual.data.release.modelVersion).toBe(expected.result.modelVersion)
  expect(actual.data.release.dataCutoff).toBe(expected.result.dataCutoff)
  expect(actual.meta.dataAsOf).toBe(expected.result.dataAsOf)
  expect(actual.data.predictions).toEqual(expected.result.predictions)
  expect(actual.data.history).toEqual(expected.result.history)
  expect(actual.data.release.metrics).toEqual(expected.result.metrics)
  expect(actual.data.evaluations).toHaveLength(8)
  for (const evaluation of actual.data.evaluations) {
    const reference = expected.evaluation[evaluation.split][evaluation.modelName]
    const errors = reference.windows.flatMap(w => w.predictions.map((v, i) => v - w.actual[i]))
    expect(evaluation.mae).toBeCloseTo(errors.reduce((n, v) => n + Math.abs(v), 0) / errors.length, 12)
    expect(evaluation.rmse).toBeCloseTo(Math.sqrt(errors.reduce((n, v) => n + v * v, 0) / errors.length), 12)
    for (let i = 0; i < 7; i++) {
      expect(evaluation.byHorizon[i].step).toBe(i + 1)
      expect(evaluation.byHorizon[i].mae).toBeCloseTo(reference.byHorizon[i].mae, 12)
      expect(evaluation.byHorizon[i].rmse).toBeCloseTo(reference.byHorizon[i].rmse, 12)
    }
  }
  expect(responses[1].body.data).toEqual({ release: null, history: [], predictions: [], evaluations: [] })
  for (let i = 0; i < 7; i++) {
    expect(Date.parse(actual.data.predictions[i].date)).toBe(Date.parse(actual.data.release.dataCutoff) + i * 86400000)
    expect(actual.data.predictions[i].value).toBeGreaterThanOrEqual(0)
    expect(actual.data.predictions[i].value).toBeLessThanOrEqual(10)
  }
  for (const channel of browserChannels()) {
    try { browser = await chromium.launch({ headless: true, ...(channel === 'chromium' ? {} : { channel }) }); break } catch {}
  }
  if (!browser) throw new Error('No actual Chromium available')
  const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } })
  page.on('pageerror', e => errors.push(e.message))
  await page.goto(`http://127.0.0.1:${webPort}`)
  await page.getByLabel('城市', { exact: true }).selectOption('s7-empty')
  await page.getByRole('button', { name: '打开七日预测', exact: true }).click()
  await expect(page.getByTestId('prediction-panel')).toContainText('暂无已发布模型')
  await page.getByLabel('城市', { exact: true }).selectOption('s7-city')
  await expect(page.getByTestId('prediction-model')).toContainText(expected.result.modelVersion)
  await expect(page.getByTestId('prediction-limitation')).toContainText('合成演示')
  const rows = page.getByTestId('prediction-points').locator('tbody tr')
  await expect(rows).toHaveCount(7)
  for (let i = 0; i < 7; i++) {
    await expect(rows.nth(i)).toContainText(expected.result.predictions[i].date)
    await expect(rows.nth(i)).toContainText(expected.result.predictions[i].value.toFixed(6))
  }
  const panel = page.getByTestId('prediction-panel')
  await expect(panel.locator('svg')).toBeVisible()
  // Read the actual ECharts instance used by the SVG renderer, independently of the table.
  const chartData = await page.evaluate(async () => {
    const url = performance.getEntriesByType('resource').map(e => e.name).find(n => /echarts_core\.js(?:\?|$)/.test(n))
    if (!url) throw new Error('ECharts module URL missing')
    const { getInstanceByDom } = await import(url)
    const chart = getInstanceByDom(document.querySelector('[data-testid="prediction-panel"] .traffic-chart'))
    const o = chart.getOption()
    return { x: o.xAxis[0].data, series: o.series.map(s => ({ name: s.name, data: s.data, lineStyle: s.lineStyle })) }
  })
  expect(chartData.x).toEqual([...expected.result.history, ...expected.result.predictions].map(p => p.date))
  expect(chartData.series[0].data).toEqual([...expected.result.history.map(p => p.value), ...Array(7).fill(null)])
  expect(chartData.series[1].data).toEqual([...Array(28).fill(null), ...expected.result.predictions.map(p => p.value)])
  expect(chartData.series[1].lineStyle.type).toBe('dashed')
  writeFileSync(path.join(output, 'chart-data.json'), JSON.stringify(chartData, null, 2))
  await panel.screenshot({ path: path.join(output, 'prediction-desktop.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect.poll(() => page.evaluate(() => {
    const element = document.querySelector('[data-testid="prediction-panel"] .traffic-chart')
    const svg = element.querySelector('svg')
    return Math.abs(svg.getBoundingClientRect().width - element.clientWidth) < 1
      && Math.abs(svg.getBoundingClientRect().height - element.clientHeight) < 1
  })).toBe(true)
  const mobileGeometry = await page.evaluate(async () => {
    const url = performance.getEntriesByType('resource').map(e => e.name).find(n => /echarts_core\.js(?:\?|$)/.test(n))
    const { getInstanceByDom } = await import(url)
    const element = document.querySelector('[data-testid="prediction-panel"] .traffic-chart')
    const chart = getInstanceByDom(element)
    return { width: chart.getWidth(), height: chart.getHeight(),
      pixels: chart.getOption().series[1].data.slice(28).map((v, i) => chart.convertToPixel({ xAxisIndex: 0, yAxisIndex: 0 }, [28 + i, v])) }
  })
  expect(mobileGeometry.pixels).toHaveLength(7)
  for (const [x, y] of mobileGeometry.pixels) {
    expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThanOrEqual(mobileGeometry.width)
    expect(y).toBeGreaterThanOrEqual(0); expect(y).toBeLessThanOrEqual(mobileGeometry.height)
  }
  writeFileSync(path.join(output, 'mobile-geometry.json'), JSON.stringify(mobileGeometry, null, 2))
  await panel.screenshot({ path: path.join(output, 'prediction-mobile.png') })
  // Real bad dataset -> real 400 -> UI error, followed by recovery to published version.
  await page.getByLabel('预测数据集', { exact: false }).fill('missing')
  await page.getByRole('button', { name: '查询预测', exact: true }).click()
  await expect(panel.getByRole('alert')).toContainText('HTTP 400')
  await expect(panel.locator('svg')).toHaveCount(0)
  await page.getByLabel('预测数据集', { exact: false }).fill('')
  await page.getByRole('button', { name: '查询预测', exact: true }).click()
  await expect(page.getByTestId('prediction-model')).toContainText(expected.result.modelVersion)
  expect(errors).toEqual([])
  passed = true
  console.log('S7_REAL_TRAIN_MYSQL_HTTP_CHROMIUM_PASS')
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
