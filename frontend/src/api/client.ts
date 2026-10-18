import type { CitiesResponse, ErrorCode, HealthResponse } from '../types/api'

export type FailureKind = 'http' | 'network' | 'timeout' | 'contract'
export class ApiClientError extends Error {
  constructor(public readonly kind: FailureKind, message: string, public readonly status?: number,
    public readonly businessCode?: ErrorCode, public readonly requestId?: string) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export async function getJson(path: string, timeoutMs = 5000): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(path, { headers: { Accept: 'application/json' }, signal: controller.signal, cache: 'no-store' })
    if (!response.ok) {
      // Proxy failures may not be a Java envelope. Never display raw server/proxy text.
      let businessCode: ErrorCode | undefined
      let requestId: string | undefined
      try {
        const body: unknown = await response.json()
        const codes: Record<number, ErrorCode> = { 400: 'BAD_REQUEST', 404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED', 406: 'NOT_ACCEPTABLE', 500: 'INTERNAL_ERROR', 503: 'SERVICE_UNAVAILABLE' }
        if (object(body) && keys(body, ['code', 'message', 'data', 'meta']) && body.code === codes[response.status]
          && typeof body.message === 'string' && !!body.message.trim() && body.data === null
          && object(body.meta) && keys(body.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId'])
          && typeof body.meta.requestId === 'string' && uuid.test(body.meta.requestId)
          && body.meta.dataAsOf === null && body.meta.sourceType === null && body.meta.datasetId === null) {
          businessCode = body.code as ErrorCode
          requestId = body.meta.requestId
        }
      } catch { /* Infrastructure errors can be non-JSON; retain the actual HTTP status. */ }
      throw new ApiClientError('http', `服务请求失败（HTTP ${response.status}），请稍后重新请求。`, response.status, businessCode, requestId)
    }
    if (!response.headers.get('content-type')?.toLowerCase().startsWith('application/json')) {
      throw new ApiClientError('contract', '服务响应格式异常，请稍后重试。')
    }
    try { return await response.json() }
    catch { throw new ApiClientError('contract', '服务返回了无效 JSON，请稍后重试。') }
  } catch (error) {
    if (error instanceof ApiClientError) throw error
    if (controller.signal.aborted) throw new ApiClientError('timeout', '请求超时，请检查服务后重新请求。')
    throw new ApiClientError('network', '无法连接服务，请检查后端与网络后重新请求。')
  } finally { clearTimeout(timer) }
}

// Runtime guards prevent TypeScript's erased types from turning malformed JSON into success.
// The independent Python verifier remains the complete OpenAPI Schema authority.
type JsonObject = Record<string, unknown>
const object = (value: unknown): value is JsonObject => typeof value === 'object' && value !== null && !Array.isArray(value)
const keys = (value: JsonObject, expected: string[]) => Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key))
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const timestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/

export async function getHealth(): Promise<HealthResponse> {
  const value = await getJson('/health')
  if (!object(value) || !keys(value, ['status', 'timestamp']) || value.status !== 'UP'
    || typeof value.timestamp !== 'string' || !timestamp.test(value.timestamp) || !Number.isFinite(Date.parse(value.timestamp))) {
    throw new ApiClientError('contract', '健康响应不符合接口约定。')
  }
  return value as unknown as HealthResponse
}

export async function getCities(): Promise<CitiesResponse> {
  const value = await getJson('/api/v1/cities')
  if (!object(value) || !keys(value, ['code', 'message', 'data', 'meta']) || value.code !== 'OK'
    || typeof value.message !== 'string' || !value.message.trim() || !Array.isArray(value.data)
    || !value.data.every(city => object(city) && keys(city, ['id', 'name']) && typeof city.id === 'string'
      && city.id.length <= 64 && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(city.id)
      && typeof city.name === 'string' && !!city.name.trim() && city.name.length <= 100)
    || !object(value.meta) || !keys(value.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId'])
    || typeof value.meta.requestId !== 'string' || !uuid.test(value.meta.requestId)
    || value.meta.dataAsOf !== null || value.meta.sourceType !== 'dev_seed' || value.meta.datasetId !== 'dev-seed-cities-v1') {
    throw new ApiClientError('contract', '城市响应不符合接口约定，未将其展示为有效数据。')
  }
  return value as unknown as CitiesResponse
}
