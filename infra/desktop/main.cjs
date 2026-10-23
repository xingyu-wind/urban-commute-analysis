const {app, BrowserWindow, Menu, dialog, session, shell} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const payload = path.join(process.resourcesPath, 'payload');
const testing = process.argv.includes('--acceptance-test');
const data = testing && process.env.UC_DESKTOP_TEST_ROOT
  ? path.resolve(process.env.UC_DESKTOP_TEST_ROOT)
  : path.join(process.env.LOCALAPPDATA, 'UrbanCommute', 'DesktopData');
// Electron supports appData, not localAppData on all versions.
fs.mkdirSync(path.join(data, 'browser'), {recursive:true});
app.setPath('userData', path.join(data, 'browser'));
app.setAppUserModelId('UrbanCommute.Desktop');
app.commandLine.appendSwitch('disable-background-networking');
app.commandLine.appendSwitch('disable-component-update');
app.commandLine.appendSwitch('disable-features', 'Translate,MediaRouter,OptimizationHints');
const state = path.join(data, 'state');
const python = path.join(data, 'runtime', 'python', 'python.exe');
const launcher = path.join(payload, 'launcher', 'portable.py');
const env = {...process.env, UC_DATA_HOME: data, UC_PARENT_PID: String(process.pid), PYTHONUTF8:'1', NO_PROXY:'127.0.0.1,::1,localhost'};
delete env.ELECTRON_RUN_AS_NODE;
let win, supervisor, working, quitting = false, finished = false, scenario = 'model', origin;
const wait = ms => new Promise(r=>setTimeout(r, ms));
const read = name => JSON.parse(fs.readFileSync(path.join(state,name), 'utf8').replace(/^\uFEFF/,''));
function record(event, details={}) {
  fs.mkdirSync(state,{recursive:true});
  fs.appendFileSync(path.join(state,'desktop-events.jsonl'),JSON.stringify({at:new Date().toISOString(),event,...details})+'\n');
}
function run(exe,args) {
  return new Promise((resolve,reject)=>{
    const child=spawn(exe,args,{cwd:payload,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
    let tail='';
    for(const stream of [child.stdout,child.stderr]) stream.on('data',b=>{tail=(tail+b.toString('utf8')).slice(-1800)});
    child.on('error',reject);
    child.on('exit',code=>code===0?resolve(tail):reject(new Error(`组件操作失败 (${code})\n${tail}`)));
  });
}
async function status(message) {
  if(win && !win.isDestroyed()) await win.webContents.executeJavaScript(`document.getElementById('status') && (document.getElementById('status').textContent=${JSON.stringify(message)})`).catch(()=>{});
}
async function stop() {
  if(!supervisor || supervisor.exitCode!==null) return;
  fs.writeFileSync(path.join(state,'stop.request'),'');
  for(let i=0;i<240;i++) { if(supervisor.exitCode!==null) {supervisor=null;return} await wait(250) }
  throw new Error('服务仍在关闭。请稍候；用户数据已保留。');
}
async function start() {
  await win.loadFile(path.join(__dirname,'splash.html'));
  await status('正在校验并准备离线组件。首次启动可能需要数分钟，请保持窗口打开。');
  if(!fs.existsSync(path.join(state,'instance.json')) || !fs.existsSync(python)) {
    await run(path.join(process.env.SystemRoot,'System32','WindowsPowerShell','v1.0','powershell.exe'),
      ['-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',path.join(payload,'launcher','bootstrap.ps1'),'-Action','setup','-AcceptLicenses']);
  } else if(!read('instance.json').initialized) {
    throw new Error('上次初始化未完成。数据已保留，请查看数据目录日志；不要删除已有数据库。');
  }
  if(quitting) return;
  await status('正在检查版本、启动数据库与应用服务……');
  await run(python,['-I',launcher,'upgrade']);
  fs.rmSync(path.join(state,'stop.request'),{force:true});
  fs.rmSync(path.join(state,'running.json'),{force:true});
  const output=fs.openSync(path.join(state,'supervisor.log'),'a');
  supervisor=spawn(python,['-I',launcher,'supervise','--scenario',scenario],{cwd:payload,env,windowsHide:true,stdio:['ignore',output,output]});
  fs.closeSync(output);
  supervisor.on('error',e=>record('supervisor-error',{message:e.message}));
  supervisor.on('exit',code=>{
    record('services-exit',{code});
    if(!quitting && origin) {origin=null;win.loadFile(path.join(__dirname,'splash.html')).then(()=>status('本地服务已停止。请用菜单“重试启动”恢复；日志保存在用户数据目录。'))}
  });
  for(let i=0;i<480;i++) {
    if(supervisor.exitCode!==null) throw new Error('本地服务启动失败。请从帮助菜单打开数据目录，查看 supervisor.log 和 backend.log。');
    if(fs.existsSync(path.join(state,'running.json'))) {
      const running=read('running.json');
      if(running.pid===supervisor.pid && /^http:\/\/127\.0\.0\.1:\d+$/.test(running.url)) {origin=running.url;break}
    }
    await wait(250);
  }
  if(!origin) throw new Error('本地服务启动超时。数据已保留。');
  if(!quitting) { await win.loadURL(origin); record('ready',{url:origin,scenario,version:app.getVersion()}) }
}
function begin() {
  if(working) return;
  working=start().catch(async e=>{record('startup-failed',{message:e.message});await stop().catch(()=>{});await status(e.message);if(!quitting)dialog.showErrorBox('启动未完成',e.message)}).finally(()=>{working=null});
}
async function changeScenario(next) {
  if(working || quitting || scenario===next) return;
  scenario=next; origin=null;
  working=stop().finally(()=>{working=null;begin()});
}
if(!app.requestSingleInstanceLock()) { app.quit() }
else {
  app.on('second-instance',(_event,argv)=>{ if(argv.includes('--stop-for-install')) app.quit(); else {if(win){win.restore();win.focus()}} });
  app.on('before-quit',event=>{
    if(finished) return;
    event.preventDefault();
    if(quitting) return;
    quitting=true;record('closing');
    (async()=>{if(working)await working;await stop();finished=true;record('closed');app.quit()})().catch(e=>{
      quitting=false;dialog.showErrorBox('关闭服务',e.message);
    });
  });
  app.whenReady().then(async()=>{
    fs.mkdirSync(state,{recursive:true});record('opening',{version:app.getVersion(),syntheticData:true});
    await session.defaultSession.setProxy({mode:'direct'});
    session.defaultSession.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
    session.defaultSession.webRequest.onBeforeRequest((details,callback)=>{
      const url=details.url;
      callback({cancel:!(url.startsWith('file://') || (origin && (url===origin || url.startsWith(origin+'/'))))});
    });
    win=new BrowserWindow({width:1440,height:940,minWidth:900,minHeight:650,show:false,title:'城市通勤 · 合成数据演示',
      webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}});
    win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    win.webContents.on('will-navigate',(e,url)=>{if(!origin || !url.startsWith(origin+'/'))e.preventDefault()});
    win.on('close',e=>{if(!finished){e.preventDefault();app.quit()}});
    win.once('ready-to-show',()=>win.show());
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {label:'应用',submenu:[
        {label:'重试启动',click:()=>{if(!working && !origin)begin()}},
        {label:'预测演示数据',click:()=>changeScenario('model')},
        {label:'数仓演示数据',click:()=>changeScenario('warehouse')},
        {type:'separator'},{label:'退出',accelerator:'Alt+F4',click:()=>app.quit()}]},
      {label:'查看',submenu:[{role:'reload',label:'刷新页面'},{role:'togglefullscreen',label:'全屏'},{role:'resetZoom',label:'实际大小'},{role:'zoomIn',label:'放大'},{role:'zoomOut',label:'缩小'}]},
      {label:'帮助',submenu:[
        {label:'本机演示账号',click:async()=>{try{const text=await run(python,['-I',launcher,'credentials']);await dialog.showMessageBox(win,{title:'本机账号（请勿公开）',message:text,detail:'仅供当前 Windows 用户。请勿将账号截图或密码提交到 GitHub。'})}catch(e){dialog.showErrorBox('账号未就绪',e.message)}}},
        {label:'打开用户数据目录',click:()=>shell.openPath(data)},
        {label:'关于',click:()=>dialog.showMessageBox(win,{title:'城市通勤演示版',message:`Windows ${app.getVersion()} · 待独立验收`,detail:'全部内置观测、预测与误差指标均来自合成测试数据，不代表真实交通预测效果。离线运行；不在本机启动 Hadoop/Hive 集群。'})}
      ]}
    ]));
    begin();
  }).catch(e=>{dialog.showErrorBox('应用启动失败',e.message);finished=true;app.quit()});
}
