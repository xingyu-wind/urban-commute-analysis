// Existing real Java server + owned Vite + real Chromium. No route interception.
import { chromium, expect } from '@playwright/test'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { mkdirSync, createWriteStream, writeFileSync } from 'node:fs'
import path from 'node:path'
import { browserChannels } from '../config/runtime.ts'

const output = path.resolve(process.argv[2]); mkdirSync(output, { recursive: false })
const root = process.cwd(), evidence = [], errors = []
let vite, browser
async function availablePort() {
  const server = createServer(); await new Promise(resolve => server.listen(0,'127.0.0.1',resolve))
  const port=server.address().port; await new Promise(resolve => server.close(resolve)); return port
}
try {
  const port=await availablePort()
  vite=spawn(process.execPath,[path.join(root,'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',String(port),'--strictPort'],
    {cwd:path.join(root,'frontend'),env:{...process.env,DEV_BACKEND_URL:process.env.S8_API_BASE},windowsHide:true,stdio:['ignore','pipe','pipe']})
  const log=createWriteStream(path.join(output,'vite.log'),{flags:'wx'}); vite.stdout.pipe(log); vite.stderr.pipe(log)
  const base=`http://127.0.0.1:${port}`
  for(let i=0;i<100;i++) {
    if(vite.exitCode!==null) throw new Error('owned Vite exited')
    try { if((await fetch(base)).ok) break } catch {}
    await new Promise(resolve=>setTimeout(resolve,200))
  }
  for(const channel of browserChannels()) {
    try { browser=await chromium.launch({headless:true,...(channel==='chromium'?{}:{channel})}); break } catch {}
  }
  if(!browser) throw new Error('No existing Chromium channel available')
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  page.on('pageerror',e=>errors.push(e.name))
  await page.goto(base)
  await page.getByRole('button',{name:'权限与运行管理',exact:true}).click()
  await page.getByLabel('账号',{exact:true}).fill(process.env.COMMUTE_BOOTSTRAP_ADMIN_USER)
  await page.getByLabel('密码',{exact:true}).fill(process.env.COMMUTE_BOOTSTRAP_ADMIN_PASSWORD)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await expect(page.getByTestId('identity')).toContainText('管理员')
  await page.getByLabel('数据文件',{exact:true}).setInputFiles(process.env.S8_FIXTURE)
  await page.getByRole('button',{name:'上传并分析',exact:true}).click()
  await expect(page.getByTestId('proposal')).toContainText('PROPOSED',{timeout:60000})
  await expect(page.getByRole('button',{name:'执行导入校验',exact:true})).toBeDisabled()
  await page.getByLabel('完整映射审查 JSON',{exact:true}).fill(process.env.S8_REVIEW)
  await page.getByRole('button',{name:'确认映射与使用权',exact:true}).click()
  await expect(page.getByTestId('operations-message')).toContainText('已确认',{timeout:60000})
  await page.getByRole('button',{name:'执行导入校验',exact:true}).click()
  await expect(page.getByTestId('operations-message')).toContainText('SUCCEEDED',{timeout:60000})
  for(const [width,height] of [[1440,1000],[390,844]]) {
    await page.setViewportSize({width,height})
    await expect(page.getByRole('heading',{name:'权限与运行管理',exact:true})).toBeVisible()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    await page.screenshot({path:path.join(output,`admin-${width}.png`),fullPage:true})
    evidence.push({role:'ADMIN',width,height,unconfirmedExecuteDisabled:true,confirmedImport:'SUCCEEDED',horizontalOverflow:false})
  }
  await page.getByRole('button',{name:'退出',exact:true}).click()
  await expect(page.getByLabel('账号',{exact:true})).toBeVisible()
  await page.getByLabel('账号',{exact:true}).fill(process.env.COMMUTE_BOOTSTRAP_READER_USER)
  await page.getByLabel('密码',{exact:true}).fill(process.env.COMMUTE_BOOTSTRAP_READER_PASSWORD)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await expect(page.getByTestId('identity')).toContainText('只读用户')
  await expect(page.getByLabel('数据文件',{exact:true})).toHaveCount(0)
  await expect(page.getByRole('heading',{name:'ML 任务',exact:true})).toBeVisible()
  await page.screenshot({path:path.join(output,'reader-390.png'),fullPage:true})
  evidence.push({role:'READER',tasksVisible:true,uploadControls:0})
  const denied=await page.evaluate(async()=>{
    const csrf=await (await fetch('/api/v1/auth/csrf')).json()
    return (await fetch('/api/v1/operations/uploads',{method:'POST',headers:{[csrf.headerName]:csrf.token}})).status
  })
  expect(denied).toBe(403); evidence.push({case:'reader-real-http-upload',status:denied})
  await page.getByRole('button',{name:'退出',exact:true}).click()
  await expect(page.getByLabel('账号',{exact:true})).toBeVisible()
  expect(await page.evaluate(async()=>(await fetch('/api/v1/operations/tasks')).status)).toBe(401)
  expect(errors).toEqual([])
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed:true,evidence,pageErrors:errors},null,2))
  console.log('S8_CHROMIUM=PASS')
} finally {
  if(browser) await browser.close()
  if(vite && vite.exitCode===null) { vite.kill(); await new Promise(resolve=>vite.once('exit',resolve)) }
}
