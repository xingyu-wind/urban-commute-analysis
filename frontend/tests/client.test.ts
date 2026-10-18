import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, getCities, getHealth, getJson } from '../src/api/client'
import cities from '../../contracts/examples/cities-success.json'
import health from '../../contracts/examples/health-success.json'
import error500 from '../../contracts/examples/error-500.json'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

describe('contract-based API client', () => {
  it('uses same-origin paths and requests JSON from real fetch in normal operation', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json(health)).mockResolvedValueOnce(json(cities))
    vi.stubGlobal('fetch', fetch)
    expect(await getHealth()).toEqual(health)
    expect(await getCities()).toEqual(cities)
    expect(fetch.mock.calls.map(call => call[0])).toEqual(['/health', '/api/v1/cities'])
    expect(fetch.mock.calls[0]?.[1]).toMatchObject({ headers: { Accept: 'application/json' }, cache: 'no-store' })
  })
  it('accepts an empty successful city list with dev metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...cities, data: [] })))
    expect((await getCities()).data).toEqual([])
  })
  it.each([
    { ...cities, data: [{ id: 1, name: '北京' }] },
    { ...cities, data: null },
    { ...cities, meta: { ...cities.meta, sourceType: 'real_time' } },
    { ...cities, meta: { ...cities.meta, dataAsOf: health.timestamp } },
  ])('rejects malformed city data rather than presenting a fake success', async body => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(body)))
    await expect(getCities()).rejects.toMatchObject({ kind: 'contract' })
  })
  it('rejects a health timestamp without a timezone', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...health, timestamp: '2026-10-18T10:00:00' })))
    await expect(getHealth()).rejects.toMatchObject({ kind: 'contract' })
  })
  it('keeps HTTP status distinct from a matching business error code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...error500, message: 'internal private detail' }, 500)))
    try { await getCities(); throw new Error('must reject') }
    catch (error) {
      expect(error).toBeInstanceOf(ApiClientError)
      expect(error).toMatchObject({ kind: 'http', status: 500, businessCode: 'INTERNAL_ERROR', requestId: error500.meta.requestId })
      expect((error as Error).message).not.toContain('private detail')
    }
  })
  it('handles a non-JSON Vite proxy failure without claiming it is a Java envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('ECONNREFUSED private stack', { status: 500 })))
    await expect(getHealth()).rejects.toMatchObject({ kind: 'http', status: 500, businessCode: undefined })
  })
  it('distinguishes network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    await expect(getHealth()).rejects.toMatchObject({ kind: 'network' })
  })
  it('aborts a request that exceeds its timeout', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_path, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const assertion = expect(getJson('/health', 10)).rejects.toMatchObject({ kind: 'timeout' })
    await vi.advanceTimersByTimeAsync(20)
    await assertion
  })
  it('rejects HTML disguised as an HTTP 200 API response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html></html>', { headers: { 'Content-Type': 'text/html' } })))
    await expect(getHealth()).rejects.toMatchObject({ kind: 'contract' })
  })
})
