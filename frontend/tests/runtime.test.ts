import { describe, expect, it } from 'vitest'
import { browserChannels, contractPython, javaExecutable } from '../config/runtime.ts'

describe('local Windows and CI Linux runtime entry points', () => {
  it('chooses the actual Java executable for each platform', () => {
    expect(javaExecutable('D:\\JDK', 'win32')).toBe('D:\\JDK\\bin\\java.exe')
    expect(javaExecutable('/opt/jdk', 'linux')).toBe('/opt/jdk/bin/java')
  })
  it('uses platform venv paths or the explicitly provisioned CI Python', () => {
    expect(contractPython('D:\\repo', '', 'win32')).toBe('D:\\repo\\contracts\\.venv\\Scripts\\python.exe')
    expect(contractPython('/repo', '', 'linux')).toBe('/repo/contracts/.venv/bin/python')
    expect(contractPython('/repo', 'python', 'linux')).toBe('python')
  })
  it('uses installed Windows browsers locally and bundled Chromium in CI', () => {
    expect(browserChannels('win32', '')).toEqual(['chrome', 'msedge'])
    expect(browserChannels('linux', '')).toEqual(['chromium'])
    expect(browserChannels('win32', 'chromium')).toEqual(['chromium'])
    expect(() => browserChannels('linux', 'untrusted-channel')).toThrow()
  })
})
