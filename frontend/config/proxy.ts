import type { ProxyOptions } from 'vite'

export function backendTarget(value = 'http://127.0.0.1:8080'): string {
  const url = new URL(value)
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
    || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('DEV_BACKEND_URL 必须是本机 HTTP 服务的 origin，例如 http://127.0.0.1:8080')
  }
  return url.origin
}

export function apiProxy(target: string): Record<string, ProxyOptions> {
  return Object.fromEntries(['/health', '/api'].map(path => [path, { target, changeOrigin: true }]))
}
