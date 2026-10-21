<script setup lang="ts">
import { onMounted, ref } from 'vue'

const identity = ref<{ username: string; role: string } | null>(null)
const username = ref(''), password = ref(''), message = ref(''), busy = ref(false)
const tasks = ref<Record<string, unknown[]> | null>(null)
const proposal = ref<Record<string, unknown> | null>(null), importId = ref(''), confirmed = ref(false)
const review = ref(''), file = ref<File | null>(null)
let csrf: { headerName: string; token: string } | null = null
async function request(path: string, init: RequestInit = {}) {
  if (init.method === 'POST') {
    const response = await fetch('/api/v1/auth/csrf', { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`获取安全凭证失败 (${response.status})`)
    csrf = await response.json() as typeof csrf
    init.headers = { ...init.headers, [csrf!.headerName]: csrf!.token }
  }
  const response = await fetch('/api/v1/' + path, { ...init, credentials: 'same-origin' })
  if (response.status === 401) { identity.value = null; throw new Error('请登录，或会话已经失效 (401)') }
  if (response.status === 403) throw new Error('当前账号无操作权限或安全凭证已失效 (403)')
  if (!response.ok) throw new Error(`操作被拒绝 (${response.status})`)
  return response.json()
}
async function perform(action: () => Promise<void>) {
  busy.value = true; message.value = ''
  try { await action() } catch (e) { message.value = e instanceof Error ? e.message : '操作失败' }
  finally { busy.value = false }
}
async function refresh() { tasks.value = await request('operations/tasks') }
async function login() {
  await perform(async () => {
    try {
      await request('auth/login', { method: 'POST', body: new URLSearchParams({ username: username.value, password: password.value }) })
      identity.value = await request('auth/me'); await refresh()
    } finally { password.value = '' }
  })
}
async function logout() {
  await perform(async () => {
    await request('auth/logout', { method: 'POST' }); identity.value = null; tasks.value = null
    proposal.value = null; importId.value = ''; confirmed.value = false; review.value = ''; csrf = null
  })
}
async function upload() {
  await perform(async () => {
    if (!file.value) throw new Error('先选择 CSV 或 JSON 文件')
    const body = new FormData(); body.append('file', file.value)
    const result = await request('operations/uploads', { method: 'POST', body })
    importId.value = result.id; proposal.value = result.proposal; confirmed.value = false
    message.value = '分析完成。请核对字段、单位、时区、来源许可及用途后确认。'
  })
}
async function confirm() {
  await perform(async () => {
    const parsed = JSON.parse(review.value)
    const result = await request(`operations/imports/${importId.value}/confirm`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ review: parsed, acknowledgement: proposal.value?.proposalSha256 }) })
    confirmed.value = true; message.value = `已确认：${result.configurationSha256}，操作者 ${result.confirmedBy}`
  })
}
async function execute(retryId?: string) {
  await perform(async () => {
    const result = await request(`operations/imports/${retryId || importId.value}/${retryId ? 'retry' : 'execute'}`, { method: 'POST' })
    message.value = `任务 ${result.jobId}：${result.status}，适用性 ${result.quality.status}`; await refresh()
  })
}
onMounted(async () => {
  try { identity.value = await request('auth/me'); await refresh() } catch { /* Anonymous entry displays the login form. */ }
})
</script>

<template>
  <section class="panel operations-panel" aria-labelledby="operations-title">
    <h2 id="operations-title">权限与运行管理</h2>
    <p>管理员可上传并确认映射；只读账号可查看任务。分析功能无需登录。</p>
    <form v-if="!identity" @submit.prevent="login" class="operations-form">
      <label>账号<input v-model="username" autocomplete="username" required maxlength="64"></label>
      <label>密码<input v-model="password" type="password" autocomplete="current-password" required maxlength="72"></label>
      <button :disabled="busy">登录</button>
      <p>账号由本机部署负责人显式配置，系统没有默认账号。</p>
    </form>
    <template v-else>
      <p data-testid="identity">{{ identity.username }} · {{ identity.role === 'ADMIN' ? '管理员' : '只读用户' }}</p>
      <button :disabled="busy" @click="logout">退出</button>
      <button :disabled="busy" @click="perform(refresh)">刷新任务</button>
      <div v-if="identity.role === 'ADMIN'" class="operations-form">
        <h3>1. 上传与字段分析</h3>
        <p>限 2 MiB CSV / 平面 JSON；仅上传有权使用的文件。外部原始文件保留于隔离目录。</p>
        <label>数据文件<input type="file" accept=".csv,.json" @change="file = ($event.target as HTMLInputElement).files?.[0] ?? null"></label>
        <button :disabled="busy || !file" @click="upload">上传并分析</button>
        <template v-if="proposal">
          <p>字段分析完成，建议状态：{{ proposal.state }}。建议本身不可执行。</p>
          <details><summary>查看字段、候选映射及未确认项</summary><pre data-testid="proposal">{{ JSON.stringify(proposal, null, 2) }}</pre></details>
          <h3>2. 核对与确认映射</h3>
          <p>填写完整审查 JSON：字段、目标与单位、时区、频率、空间粒度、缺失策略、数据集版本、来源及许可用途。确认绑定当前文件哈希，保存后不可改写。</p>
          <label>完整映射审查 JSON<textarea v-model="review" rows="15" spellcheck="false" aria-label="完整映射审查 JSON" /></label>
          <button :disabled="busy || confirmed || !review.trim()" @click="confirm">确认映射与使用权</button>
          <h3>3. 导入与质量检查</h3>
          <p>复用 S7 标准化和任务适用性检查。成功仅产生隔离研究输入；训练和正式发布仍使用既有受控离线流程。</p>
          <button :disabled="busy || !confirmed" @click="execute()">执行导入校验</button>
        </template>
      </div>
      <div v-if="tasks" class="operations-tasks">
        <template v-for="name in ['imports', 'etl', 'hive', 'ml']" :key="name">
          <h3>{{ { imports: '导入校验', etl: 'ETL 批次', hive: 'Hive 发布', ml: 'ML 任务' }[name] || name }}</h3>
          <p v-if="!tasks[name]?.length">暂无任务</p>
          <div v-for="(item, index) in tasks[name]" :key="index" class="task-card">
            <p><strong>{{ (item as Record<string, unknown>).status }}</strong> · {{ (item as Record<string, unknown>).id || (item as Record<string, unknown>).batch_id || (item as Record<string, unknown>).release_id || (item as Record<string, unknown>).job_id }}</p>
            <p v-if="(item as Record<string, unknown>).error_code">失败原因：{{ (item as Record<string, unknown>).error_code }}</p>
            <details><summary>版本、批次与操作追溯</summary><pre>{{ JSON.stringify(item, null, 2) }}</pre></details>
            <button v-if="identity.role === 'ADMIN' && name === 'imports' && (item as Record<string, unknown>).status === 'FAILED' && Number((item as Record<string, unknown>).attempts) < 3"
              :disabled="busy" @click="execute(String((item as Record<string, unknown>).import_id))">重试失败导入</button>
          </div>
        </template>
      </div>
    </template>
    <p role="status" data-testid="operations-message">{{ message }}</p>
  </section>
</template>

<style scoped>
.operations-panel { margin-block: 1.5rem; padding: clamp(16px, 3vw, 32px); min-width: 0; }
.operations-form { display: grid; gap: 12px; margin-block: 20px; }
label { display: grid; gap: 6px; }
input, textarea { max-width: 100%; min-width: 0; padding: 10px; border: 1px solid #bdc8cf; border-radius: 6px; font: inherit; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f2f5f7; padding: 12px; max-height: 380px; overflow: auto; font-size: 12px; }
button { padding: 8px 14px; margin: 4px; cursor: pointer; }
button:disabled { cursor: default; opacity: .5; }
.task-card { border: 1px solid #dce3e7; padding: 12px; margin-block: 10px; border-radius: 6px; overflow-wrap: anywhere; }
summary { cursor: pointer; padding-block: 6px; }
</style>
