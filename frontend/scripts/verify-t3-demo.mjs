// Real installed production UI. Credentials arrive only through an anonymous pipe.
import { chromium, expect } from '@playwright/test'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { browserChannels } from '../config/runtime.ts'
const [output,base,root]=process.argv.slice(2)
const secrets=JSON.parse(readFileSync(0,'utf8')), errors=[], requests=[]
mkdirSync(output,{recursive:false})
let browser
const started=performance.now()
try {
  for(const channel of browserChannels()) {
    try { browser=await chromium.launch({headless:true,...(channel==='chromium'?{}:{channel})}); break } catch {}
  }
  if(!browser) throw new Error('Existing Chromium required')
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  page.on('pageerror',e=>errors.push(e.name))
  page.on('response',r=>{if(r.url().startsWith(base+'/api/')) requests.push({path:new URL(r.url()).pathname,status:r.status()})})
  await page.goto(base)
  await page.getByRole('button',{name:'数据管理',exact:true}).click()
  async function login(role) {
    await page.getByLabel('账号',{exact:true}).fill(secrets[role].username)
    await page.getByLabel('密码',{exact:true}).fill(secrets[role].password)
    await page.getByRole('button',{name:'登录',exact:true}).click()
    await expect(page.getByTestId('identity')).toContainText(role==='ADMIN'?'管理员':'只读用户')
    await expect(page.getByRole('button',{name:'刷新任务',exact:true})).toBeEnabled()
  }
  await login('ADMIN')
  await page.getByLabel('数据文件',{exact:true}).setInputFiles(path.join(root,'database/research-demo.csv'))
  await page.getByRole('button',{name:'上传并分析',exact:true}).click()
  // The bundled scientific Python runtime may cold-start while Windows scans
  // newly extracted native libraries; wait for the real completed response.
  await expect(page.getByTestId('operations-message')).toContainText('分析完成',{timeout:60000})
  await expect(page.getByRole('button',{name:'执行导入校验',exact:true})).toBeDisabled()
  // Maintainer explicitly reviewed this original synthetic fixture against its review file.
  await page.getByLabel('完整映射审查 JSON',{exact:true}).fill(readFileSync(path.join(root,'database/research-review.json'),'utf8'))
  await page.getByRole('button',{name:'确认映射与使用权',exact:true}).click()
  await expect(page.getByTestId('operations-message')).toContainText('已确认',{timeout:60000})
  await page.getByRole('button',{name:'执行导入校验',exact:true}).click()
  await expect(page.getByTestId('operations-message')).toContainText('SUCCEEDED',{timeout:60000})
  await page.getByRole('button',{name:'退出',exact:true}).click()
  await login('READER')
  await expect(page.getByLabel('数据文件',{exact:true})).toHaveCount(0)
  await expect(page.getByRole('button',{name:'上传并分析',exact:true})).toHaveCount(0)
  await expect(page.getByText('SUCCEEDED',{exact:true}).first()).toBeVisible()
  await page.screenshot({path:path.join(output,'reader.png'),fullPage:true})
  await page.getByRole('button',{name:'退出',exact:true}).click()
  expect(errors).toEqual([])
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed:true,seconds:Math.round((performance.now()-started)/1000),
    actualProductionUI:true,noInterception:true,adminLogin:true,explicitReview:true,import:'SUCCEEDED',readerUploadHidden:true,
    readerTasksVisible:true,logout:true,pageErrors:errors,requests},null,2))
} finally { await browser?.close() }
