// Actual installed Electron window -> bundled Python/Java/MySQL, no intercepted responses.
import {_electron, expect} from '@playwright/test';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
const [installation,dataRoot,output,mode='first']=process.argv.slice(2).map((v,i)=>i<3?path.resolve(v):v);
mkdirSync(output,{recursive:false});
const state=path.join(dataRoot,'state');
const read=name=>JSON.parse(readFileSync(path.join(state,name),'utf8'));
const env={...process.env,UC_DESKTOP_TEST_ROOT:dataRoot,PATH:path.join(process.env.SystemRoot,'System32'),
  JAVA_HOME:'Z:\\intentionally-absent',PYTHONPATH:'Z:\\intentionally-absent',DB_URL:'jdbc:mysql://invalid/no',
  HTTP_PROXY:'http://127.0.0.1:1',HTTPS_PROXY:'http://127.0.0.1:1'};
delete env.ELECTRON_RUN_AS_NODE;delete env.NODE_OPTIONS;
const checks=[],errors=[];
let electron;
async function closedPorts(running) {
  const config=read('instance.json');
  for(const port of [config.dbPort,config.apiPort,config.webPort]) {
    const net=await import('node:net');
    const listening=await new Promise(resolve=>{const socket=net.connect({host:'127.0.0.1',port});socket.once('connect',()=>{socket.destroy();resolve(true)});socket.once('error',()=>resolve(false))});
    expect(listening,`port ${port} closed`).toBe(false);
  }
}
async function launch() {
  const app=await _electron.launch({executablePath:path.join(installation,'UrbanCommute.exe'),args:['--acceptance-test'],env,timeout:30000});
  const page=await app.firstWindow();
  page.on('pageerror',e=>errors.push(e.message));
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\//,{timeout:480000});
  await expect(page.getByTestId('service-status')).toContainText('服务正常',{timeout:30000});
  return {app,page};
}
async function quit(app) {
  await app.close();
  await expect.poll(()=>{try{return readFileSync(path.join(state,'desktop-events.jsonl'),'utf8').trim().split('\n').map(JSON.parse).at(-1).event}catch{return ''}},{timeout:60000}).toBe('closed');
  await closedPorts();
}
try {
  let launched=await launch();electron=launched.app;let page=launched.page;
  const base=new URL(page.url()).origin;
  const config=read('instance.json');
  expect(config.initialized).toBe(true);
  const versions=await electron.evaluate(({app})=>({version:app.getVersion(),electron:process.versions.electron}));
  writeFileSync(path.join(output,'identity.json'),JSON.stringify({versions,schemas:config.schemas,applicationJar:config.applicationJar,serverUuid:config.serverUuid,ports:[config.dbPort,config.apiPort,config.webPort]},null,2));
  await page.getByLabel('城市选择',{exact:true}).selectOption('s7-city');
  await expect(page.getByTestId('traffic-dashboard')).not.toHaveAttribute('aria-busy','true');
  await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
  for(const label of ['交通分析','智能预测','数据管理','全屏大屏','总览首页']) {
    await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click();
    if(label==='智能预测') {
      const response=await page.request.get(base+'/api/v1/predictions?cityId=s7-city');
      const api=await response.json();expect(api.data.predictions).toHaveLength(7);
      const rows=page.getByTestId('prediction-points').locator('tbody tr');
      await expect(rows).toHaveCount(7);
      for(let i=0;i<7;i++) {
        await expect(rows.nth(i)).toContainText(api.data.predictions[i].date);
        await expect(rows.nth(i)).toContainText(api.data.predictions[i].value.toFixed(6));
      }
      await expect(page.getByTestId('prediction-panel').locator('.traffic-chart svg')).toBeVisible();
      await page.screenshot({path:path.join(output,'prediction.png'),fullPage:true});
      writeFileSync(path.join(output,'predictions.json'),JSON.stringify(api,null,2));
    }
    checks.push({check:'actual-window-'+label,passed:true});
  }
  // Verify the renderer has no Node API and refuses public-network requests.
  expect(await page.evaluate(()=>typeof window.require)).toBe('undefined');
  expect(await page.evaluate(async()=>{try{await fetch('https://example.com');return false}catch{return true}})).toBe(true);
  checks.push({check:'sandbox-and-external-network-block',passed:true});
  // A second launch must focus this instance, without creating another supervisor.
  const pid=read('running.json').pid;
  const second=spawnSync(path.join(installation,'UrbanCommute.exe'),['--acceptance-test'],{env,windowsHide:true,timeout:30000});
  expect(second.status).toBe(0);expect(read('running.json').pid).toBe(pid);
  checks.push({check:'single-instance',passed:true});
  // Shell menu switches real isolated database scenarios and returns to model.
  await electron.evaluate(({Menu})=>Menu.getApplicationMenu().items[0].submenu.items[2].click());
  await expect.poll(()=>{try{return read('running.json').scenario}catch{return ''}},{timeout:120000}).toBe('warehouse');
  await expect(page.getByTestId('service-status')).toContainText('服务正常',{timeout:30000});
  checks.push({check:'warehouse-scenario-services',passed:true});
  await electron.evaluate(({Menu})=>Menu.getApplicationMenu().items[0].submenu.items[1].click());
  await expect.poll(()=>{try{return read('running.json').scenario}catch{return ''}},{timeout:120000}).toBe('model');
  await expect(page.getByTestId('service-status')).toContainText('服务正常',{timeout:30000});
  await quit(electron);electron=null;
  checks.push({check:'normal-close-all-owned-ports',passed:true});
  // Restart the EXE and confirm stable DB identity and no reseeding.
  launched=await launch();electron=launched.app;page=launched.page;
  expect(read('instance.json').serverUuid).toBe(config.serverUuid);
  expect(read('instance.json').schemas).toEqual(config.schemas);
  await quit(electron);electron=null;
  checks.push({check:'restart-preserves-database-and-shuts-down',passed:true});
  expect(errors).toEqual([]);
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed:true,mode,checks,errors,internetProxyUnreachable:true,globalDeveloperPathRemoved:true,cleanWindows:false},null,2));
} catch(error) {
  writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed:false,mode,checks,errors,error:error.stack},null,2));throw error;
} finally {if(electron)await electron.close().catch(()=>{})}
