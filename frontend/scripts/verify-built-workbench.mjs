// Verify a fresh frontend production build against an existing task-owned Java service.
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { mkdirSync, createWriteStream } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const frontend=path.resolve(fileURLToPath(new URL('..',import.meta.url)))
const [output,backend,city='s7-city',kind='prediction',identity='']=process.argv.slice(2)
if(!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(backend??'')) throw new Error('An explicit loopback Java service URL is required')
mkdirSync(output,{recursive:false})
const reserve=createServer();await new Promise(resolve=>reserve.listen(0,'127.0.0.1',resolve));const port=reserve.address().port;await new Promise(resolve=>reserve.close(resolve))
const service=spawn(process.execPath,[path.join(frontend,'node_modules/vite/bin/vite.js'),'preview','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:frontend,env:{...process.env,DEV_BACKEND_URL:backend},windowsHide:true,stdio:['ignore','pipe','pipe']})
const log=createWriteStream(path.join(output,'preview.log'),{flags:'wx'});service.stdout.pipe(log);service.stderr.pipe(log)
try {
  const base='http://127.0.0.1:'+port;let ready=false
  for(let i=0;i<100;i++) {if(service.exitCode!==null)throw new Error('Preview exited');try {if((await fetch(base)).ok){ready=true;break}}catch{};await new Promise(resolve=>setTimeout(resolve,100))}
  if(!ready)throw new Error('Preview readiness failed')
  const result=spawnSync(process.execPath,[path.join(frontend,'scripts/verify-s9.mjs'),path.join(output,'browser'),base,city,kind,identity],{stdio:'inherit',windowsHide:true})
  process.exitCode=result.status??1
} finally {service.kill();await new Promise(resolve=>service.once('exit',resolve))}
