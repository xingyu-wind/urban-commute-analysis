// Production bundle -> actual Java/MySQL. Network failures use Chromium offline mode, never mocked responses.
import { chromium, expect } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { browserChannels } from '../config/runtime.ts'
import { measureLayout } from './responsive-layout.mjs'
const output=path.resolve(process.argv[2]), base=process.argv[3], cityId=process.argv[4], kind=process.argv[5]
mkdirSync(output,{recursive:false})
let browser, page, passed=false
const errors=[], checks=[], layouts=[], requests=[]
async function nav(label) { await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click(); await page.waitForTimeout(120) }
async function ready() { await expect(page.getByLabel('城市选择',{exact:true})).toBeEnabled(); await expect(page.locator('.context-summary')).toContainText(/.+/) }
try {
  for(const channel of browserChannels()) {
    try { browser=await chromium.launch({headless:true,...(channel==='chromium'?{}:{channel})}); break } catch {}
  }
  if(!browser) throw new Error('Existing Chromium required')
  const context=await browser.newContext({locale:'zh-CN',timezoneId:'Asia/Shanghai'})
  page=await context.newPage()
  page.on('pageerror',e=>errors.push(e.message))
  page.on('response',r=>{if(r.url().startsWith(base+'/api/')) requests.push({path:new URL(r.url()).pathname,status:r.status()})})
  await page.setViewportSize({width:1920,height:1080})
  await page.goto(base); await ready()
  await expect(page.getByRole('navigation').getByRole('button')).toHaveCount(5)
  await expect(page.getByTestId('service-status')).toContainText('服务正常')
  const metadata=await (await context.request.get(base+'/api/v1/traffic/availability?cityId='+cityId)).json()
  const dataset=metadata.data.datasets.find(d=>d.datasetId===metadata.data.defaultDatasetId)
  await page.getByLabel('城市选择',{exact:true}).selectOption(cityId)
  await expect(page.getByLabel('数据集选择')).toHaveValue(dataset.datasetId)
  await expect(page.getByTestId('traffic-dashboard')).not.toHaveAttribute('aria-busy','true')
  const ranges=Object.values(dataset.levels).filter(r=>r.sampleCount>0)
  if(ranges.length) {
    const last=Math.max(...ranges.map(r=>Date.parse(r.lastObservedAt))), first=Math.min(...ranges.map(r=>Date.parse(r.firstObservedAt)))
    const end=Date.parse(new Date(last).toISOString().slice(0,10))+86400000
    expect(await page.getByLabel('开始日期 UTC').inputValue()).toBe(new Date(Math.max(Date.parse(new Date(first).toISOString().slice(0,10)),end-7*86400000)).toISOString().slice(0,10))
    expect(await page.getByLabel('结束日期 UTC').inputValue()).toBe(new Date(end).toISOString().slice(0,10))
    const from=await page.getByLabel('开始日期 UTC').inputValue(),to=await page.getByLabel('结束日期 UTC').inputValue()
    const summary=await (await context.request.get(base+'/api/v1/traffic/summary?'+new URLSearchParams({cityId,datasetId:dataset.datasetId,from:from+'T00:00:00Z',to:to+'T00:00:00Z'}))).json()
    await expect(page.getByTestId('kpi-count')).toContainText(String(summary.data.metrics.sampleCount))
    if(summary.data.metrics.sampleCount) await expect(page.getByTestId('kpi-speed')).toContainText(summary.data.metrics.avgSpeedKmh.toFixed(2))
    checks.push({check:'metadata-dataset-latest-window-and-summary',passed:true,cityId,datasetId:dataset.datasetId,from,to,sampleCount:summary.data.metrics.sampleCount})
    writeFileSync(path.join(output,'metadata-summary.json'),JSON.stringify({metadata,summary},null,2))
  }
  await nav('智能预测')
  const predictions=await (await context.request.get(base+'/api/v1/predictions?'+new URLSearchParams({cityId,datasetId:dataset.datasetId}))).json()
  if(predictions.data.release) {
    const rows=page.getByTestId('prediction-points').locator('tbody tr')
    await expect(rows).toHaveCount(7)
    for(let i=0;i<7;i++) {
      await expect(rows.nth(i)).toContainText(predictions.data.predictions[i].date)
      await expect(rows.nth(i)).toContainText(predictions.data.predictions[i].value.toFixed(6))
      expect(Date.parse(predictions.data.predictions[i].date)).toBe(Date.parse(predictions.data.release.dataCutoff)+i*86400000)
    }
    await expect(page.getByTestId('prediction-panel').locator('.traffic-chart svg')).toBeVisible()
    await expect(page.locator('.model-details')).not.toHaveAttribute('open')
    await page.locator('.model-details summary').click()
    await expect(page.locator('.model-details')).toContainText(predictions.data.release.modelVersion)
    await page.locator('.model-details summary').click()
    writeFileSync(path.join(output,'published-predictions.json'),JSON.stringify(predictions,null,2))
    checks.push({check:'published-seven-points-cutoff-model-and-chart',passed:true,points:7})
  } else { await expect(page.getByTestId('prediction-panel')).toContainText('暂无已发布模型'); checks.push({check:'no-model-no-chart',passed:true}) }
  if(kind==='warehouse') {
    await nav('交通分析')
    await page.getByRole('button',{name:'查看 Hive 数仓快照与同窗比较',exact:true}).click()
    await page.getByTestId('warehouse-panel').locator('details summary').click()
    await expect(page.getByTestId('warehouse-release')).toContainText(process.argv[6])
    await expect(page.getByTestId('warehouse-metrics').locator('tbody tr')).not.toHaveCount(0)
    await page.getByTestId('warehouse-panel').screenshot({path:path.join(output,'warehouse.png')})
    checks.push({check:'prepublished-warehouse-snapshot',passed:true})
    await page.getByRole('button',{name:'收起数仓快照',exact:true}).click()
  }
  for(const [width,height] of [[1920,1080],[1366,768],[768,1024],[390,844]]) {
    await page.setViewportSize({width,height})
    for(const [label,slug] of [['总览首页','overview'],['交通分析','traffic'],['智能预测','prediction'],['全屏大屏','screen']]) {
      await nav(label)
      await expect.poll(()=>page.locator('.traffic-chart:visible').evaluateAll(elements=>elements.every(e=>e.clientWidth>0 && Math.abs(e.querySelector('svg')?.getBoundingClientRect().width-e.clientWidth)<2))).toBe(true)
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
      const layout=await measureLayout(page)
      expect(layout.outside).toEqual([]);expect(layout.clippedKpis).toEqual([]);expect(layout.obstructed).toEqual([])
      const geometry=await page.evaluate(()=>({documentHeight:document.documentElement.scrollHeight,viewportHeight:innerHeight}))
      layouts.push({width,height,page:slug,...layout,...geometry})
      if(slug==='screen' && width>=1366) expect(geometry.documentHeight).toBeLessThanOrEqual(height)
      await page.evaluate(()=>scrollTo(0,0))
      await page.screenshot({path:path.join(output,`${slug}-${width}.png`),fullPage:true})
      if(slug==='screen' && !dataset.levels.REGION.sampleCount) {
        await expect(page.locator('.region-panel')).toContainText('暂无区域观测')
        await expect(page.locator('.region-panel .traffic-chart')).toHaveCount(0)
        await expect(page.locator('.map-panel')).toHaveCount(0)
      }
    }
  }
  checks.push({check:'four-viewports-four-pages-controls-and-echarts-resize',passed:true})
  await page.setViewportSize({width:1366,height:768}); await nav('全屏大屏')
  await page.getByRole('button',{name:'全屏 / 退出',exact:true}).click()
  await expect.poll(()=>page.evaluate(()=>Boolean(document.fullscreenElement))).toBe(true)
  await page.getByRole('button',{name:'全屏 / 退出',exact:true}).click()
  await expect.poll(()=>page.evaluate(()=>Boolean(document.fullscreenElement))).toBe(false)
  await page.locator('.traffic-filter-disclosure > summary').click()
  await expect(page.getByLabel('开始日期 UTC')).toBeVisible()
  await page.locator('.traffic-filter-disclosure > summary').click()
  checks.push({check:'browser-fullscreen-exit-and-expand-screen-filters',passed:true})
  await page.setViewportSize({width:1366,height:768})
  await nav('总览首页')
  const cityList=await (await context.request.get(base+'/api/v1/cities')).json()
  let emptyCity
  for(const c of cityList.data) {
    const a=await (await context.request.get(base+'/api/v1/traffic/availability?cityId='+c.id)).json()
    if(a.data.datasets.every(d=>!d.predictionAvailable && Object.values(d.levels).every(r=>!r.sampleCount))) { emptyCity=c.id; break }
  }
  if(emptyCity) {
    await page.getByLabel('城市选择').selectOption(emptyCity)
    await expect(page.getByTestId('traffic-empty')).toBeVisible()
    await expect(page.getByTestId('kpi-speed')).toHaveCount(0)
    await nav('智能预测');await expect(page.getByTestId('prediction-panel')).toContainText('暂无已发布模型')
    await expect(page.getByTestId('prediction-panel').locator('svg')).toHaveCount(0)
    await page.screenshot({path:path.join(output,'directory-only.png'),fullPage:true})
    await page.getByLabel('城市选择').selectOption(cityId)
    checks.push({check:'directory-only-empty-and-no-stale-city',passed:true,emptyCity})
  }
  await nav('总览首页')
  if(ranges.length) {
    await page.getByLabel('开始日期 UTC').fill('2000-01-01');await page.getByLabel('结束日期 UTC').fill('2000-01-02')
    await expect(page.getByTestId('traffic-empty')).toBeVisible()
    await expect(page.getByTestId('kpi-speed')).toContainText('—')
    await page.getByRole('button',{name:'最近有效时段',exact:true}).click()
    await expect(page.getByTestId('kpi-count')).not.toContainText('0条')
    checks.push({check:'manual-empty-window-and-latest-window-recovery',passed:true})
  }
  await context.setOffline(true)
  await page.getByRole('button',{name:'刷新数据',exact:true}).click()
  await expect(page.getByRole('alert')).toContainText('无法连接服务')
  await expect(page.getByTestId('traffic-dashboard')).toHaveCount(0)
  await context.setOffline(false)
  await page.getByRole('button',{name:'重试连接',exact:true}).click();await ready()
  await expect(page.getByTestId('traffic-dashboard')).toBeVisible()
  checks.push({check:'real-browser-offline-clear-and-retry',passed:true})
  await nav('数据管理')
  await expect(page.getByLabel('账号',{exact:true})).toBeVisible()
  const denied=await context.request.get(base+'/api/v1/operations/tasks')
  expect(denied.status()).toBe(401)
  await page.screenshot({path:path.join(output,'management-login.png'),fullPage:true})
  checks.push({check:'anonymous-public-read-protected-management',passed:true})
  expect(errors).toEqual([]);passed=true
} catch(e) {
  writeFileSync(path.join(output,'failure.txt'),e.stack)
  await page?.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{})
  throw e
} finally {
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed,bundle:'production dist',browser:browser?.version(),noInterception:true,checks,layouts,pageErrors:errors,requests},null,2))
  await browser?.close()
}
