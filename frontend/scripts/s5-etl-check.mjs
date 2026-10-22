// Called by the existing S4 real Java/Vite/Chromium driver, sharing its lifecycle.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { readFileSync, writeFileSync } from 'node:fs'

export async function checkEtl({ page, expect, context, backend, output, root, python, step, directGet }) {
  const fixture = path.resolve(process.env.S5_FIXTURE_OUTPUT)
  function run(action) {
    const result = spawnSync(python, [path.join(root, 'scripts/s5_browser_data.py'), action, '--output', fixture], { cwd: root, encoding: 'utf8', windowsHide: true })
    if (result.status !== 0) throw new Error(`Python ETL ${action} failed: ${result.stderr}`)
    return result.stdout.trim()
  }
  await page.getByLabel('城市选择', { exact: true }).selectOption('s5-city-ui')
  await expect(page.getByTestId('traffic-empty')).toBeVisible()
  await expect(page.getByTestId('kpi-speed')).toHaveCount(0)
  const q = '?cityId=s5-city-ui&from=2026-10-15T00:00:00Z&to=2026-10-17T00:00:00Z'
  const snapshots = []
  async function assertApi(phase, count, speed, index) {
    const api = {}
    for (const endpoint of ['summary', 'series', 'regions', 'roads']) {
      const response = await directGet(`${backend}/api/v1/traffic/${endpoint}${q}`)
      expect(response.status()).toBe(200)
      api[endpoint] = await response.json()
    }
    expect(api.summary.data.metrics.sampleCount).toBe(count)
    expect(api.summary.data.metrics.avgSpeedKmh).toBe(speed)
    expect(api.summary.data.metrics.congestionIndex).toBe(index)
    expect(api.summary.meta.sourceType).toBe('synthetic_test')
    if (count) {
      expect(api.regions.data.items[0].metrics.avgSpeedKmh).toBe(36)
      expect(api.roads.data.items[0].metrics.avgSpeedKmh).toBe(18)
      expect(api.series.data.items[0].metrics.avgSpeedKmh).toBe(54)
      expect(api.series.data.items[1].metrics.avgSpeedKmh).toBe(count === 3 ? 12 : null)
    }
    snapshots.push({ phase, api, independentSql: JSON.parse(run('oracle')) })
  }
  await assertApi('before', 0, null, null)
  await page.screenshot({ path: path.join(output, 's5-before.png'), fullPage: true })
  run('csv')
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('54.00')
  await expect(page.getByTestId('kpi-count')).toContainText('2')
  await assertApi('csv', 2, 54, 3)
  await expect(page.locator('.traffic-chart svg')).toHaveCount(3)
  await page.screenshot({ path: path.join(output, 's5-after-csv.png'), fullPage: true })
  const csvTrend = await page.locator('.trend-panel .traffic-chart svg').innerHTML()
  run('json')
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(page.getByTestId('kpi-speed')).toContainText('40.00')
  await expect(page.getByTestId('kpi-count')).toContainText('3')
  await expect(page.getByTestId('kpi-congestion')).toContainText('5.00')
  await assertApi('json', 3, 40, 5)
  await expect.poll(() => page.locator('.trend-panel .traffic-chart svg').innerHTML()).not.toBe(csvTrend)
  await page.locator('.chart-data summary').click()
  await expect(page.locator('.chart-data tbody tr').first()).toContainText('54.00')
  await expect(page.locator('.chart-data tbody tr').nth(1)).toContainText('12.00')
  // Inspect actual rendered ECharts SVG labels and region/road data, not screenshot pixels alone.
  await expect(page.locator('.region-buttons')).toContainText('3.00')
  await expect(page.locator('[data-map-point]')).toHaveCount(1)
  await page.getByRole('button', { name: '全屏大屏', exact: true }).click()
  await expect(page.locator('.traffic-workspace')).toHaveClass(/presentation/)
  await page.screenshot({ path: path.join(output, 's5-after-json-presentation.png'), fullPage: true })
  run('repeat')
  const repeat = JSON.parse(readFileSync(path.join(fixture, 'repeat/batch.json'), 'utf8'))
  expect(repeat.written_count).toBe(0); expect(repeat.existing_count).toBe(9)
  await assertApi('repeat', 3, 40, 5)
  run('alternate')
  await assertApi('separate-dataset-default-unchanged', 3, 40, 5)
  const alternate = await directGet(`${backend}/api/v1/traffic/summary${q}&datasetId=s5-synthetic-alternate-ui`)
  const alternateBody = await alternate.json()
  expect(alternate.status()).toBe(200)
  expect(alternateBody.data.metrics.avgSpeedKmh).toBe(200)
  expect(alternateBody.data.metrics.sampleCount).toBe(3)
  const invalid = await directGet(`${backend}/api/v1/traffic/summary${q}&cityId=duplicate`)
  expect(invalid.status()).toBe(400)
  writeFileSync(path.join(output, 'etl-oracle.json'), JSON.stringify(snapshots, null, 2) + '\n')
  step('s5-python-csv-json-idempotency-mysql-api-vue-echarts', { noManualObservationSql: true, citySpeed: [null, 54, 40, 40], cityCount: [0, 2, 3, 3] })
}
