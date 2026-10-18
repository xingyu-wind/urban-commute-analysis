import path from 'node:path'

export function javaExecutable(javaHome: string, platform: NodeJS.Platform = process.platform): string {
  const paths = platform === 'win32' ? path.win32 : path.posix
  return paths.join(javaHome, 'bin', platform === 'win32' ? 'java.exe' : 'java')
}

export function contractPython(root: string, override = process.env.CONTRACT_PYTHON,
  platform: NodeJS.Platform = process.platform): string {
  if (override) return override
  const paths = platform === 'win32' ? path.win32 : path.posix
  return platform === 'win32'
    ? paths.join(root, 'contracts', '.venv', 'Scripts', 'python.exe')
    : paths.join(root, 'contracts', '.venv', 'bin', 'python')
}

export function browserChannels(platform: NodeJS.Platform = process.platform, specified = process.env.BROWSER_CHANNEL): string[] {
  if (specified) {
    if (!['chrome', 'msedge', 'chromium'].includes(specified)) throw new Error('Unsupported BROWSER_CHANNEL')
    return [specified]
  }
  return platform === 'win32' ? ['chrome', 'msedge'] : ['chromium']
}
