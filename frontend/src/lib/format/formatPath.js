export function shortPath(filePath) {
  if (!filePath) {
    return ''
  }
  const parts = filePath.split('/')
  return parts[parts.length - 1] || filePath
}

export function dirname(filePath) {
  if (!filePath) {
    return ''
  }
  const idx = filePath.lastIndexOf('/')
  return idx === -1 ? '' : filePath.slice(0, idx)
}
