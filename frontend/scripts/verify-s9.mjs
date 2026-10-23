// Actual built dist and API proxy, no request interception or generated success screens.
import { chromium, expect } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { browserChannels } from '../config/runtime.ts'
const output=path.resolve(process.argv[2]), base=process.argv[3]
mkdirSync(output,{recursive:false})
let browser
const errors=[], timings=[]
try {
  for(const channel of browserChannels()) {
    try { browser=await chromium.launch({headless:true,...(channel==='chromium'?{}:{channel})}); break } catch {}
  }
  if(!browser) throw new Error('Existing Chromium required')
  const page=await browser.newPage()
  page.on('pageerror',e=>errors.push(e.name))
  for(const [width,height] of [[1440,1000],[390,844]]) {
    await page.setViewportSize({width,height})
    const start=performance.now()
    await page.goto(base)
    await expect(page.getByRole('button',{name:'权限与运行管理',exact:true})).toBeVisible()
    await expect(page.getByRole('button',{name:'权限与运行管理',exact:true})).toBeEnabled()
    await expect(page.getByLabel('城市',{exact:true}).locator(`option[value="${process.argv[4]}"]`)).toHaveCount(1)
    await page.getByLabel('城市',{exact:true}).selectOption(process.argv[4])
    await page.waitForLoadState('networkidle')
    timings.push({width,height,navigationAndNetworkIdleMs:Math.round(performance.now()-start),
      navigation:await page.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];return {domContentLoadedMs:n.domContentLoadedEventEnd,loadMs:n.loadEventEnd}})})
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    await page.screenshot({path:path.join(output,`production-${width}.png`),fullPage:true})
    const denied=await page.evaluate(async()=>{const r=await fetch('/api/v1/operations/tasks');return {status:r.status,body:await r.json()}})
    expect(denied.status).toBe(401); expect(denied.body.code).toBe('UNAUTHORIZED')
    for(const [button,testId] of [['打开七日预测','prediction-panel'],['打开 Hive 离线分析','warehouse-panel']]) {
      const opened=performance.now()
      await page.getByRole('button',{name:button,exact:true}).click()
      await expect(page.getByTestId(testId)).toBeVisible()
      await page.waitForLoadState('networkidle')
      if(testId==='prediction-panel' && process.argv[5]==='prediction')
        await expect(page.getByTestId('prediction-points').locator('tbody tr')).toHaveCount(7)
      if(testId==='warehouse-panel' && process.argv[5]==='warehouse')
        await expect(page.getByTestId('warehouse-release')).toContainText(process.argv[6])
      timings.push({width,height,panel:testId,openAndNetworkIdleMs:Math.round(performance.now()-opened)})
      await page.getByTestId(testId).screenshot({path:path.join(output,`${testId}-${width}.png`)})
    }
  }
  expect(errors).toEqual([])
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed:true,bundle:'production dist',timings,pageErrors:errors,noInterception:true},null,2))
} finally { await browser?.close() }
