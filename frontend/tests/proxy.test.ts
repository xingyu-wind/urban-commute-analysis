import { describe, expect, it } from 'vitest'
import { apiProxy, backendTarget } from '../config/proxy'

describe('development API proxy', () => {
  it('defaults to reproducible Java port 8080 and preserves API paths', () => {
    const target = backendTarget()
    expect(target).toBe('http://127.0.0.1:8080')
    const proxy = apiProxy(target)
    expect(Object.keys(proxy)).toEqual(['/health', '/api'])
    expect(proxy['/health']).toMatchObject({ target, changeOrigin: true })
    expect(proxy['/api']).not.toHaveProperty('rewrite')
  })
  it('accepts a deliberately chosen alternate local Java port', () => {
    expect(apiProxy(backendTarget('http://127.0.0.1:8081'))['/api']?.target).toBe('http://127.0.0.1:8081')
  })
  it.each(['https://127.0.0.1:8080', 'http://example.com', 'http://user@localhost', 'http://localhost:8080/api'])('rejects an unsafe or ambiguous target %s', value => {
    expect(() => backendTarget(value)).toThrow()
  })
})
