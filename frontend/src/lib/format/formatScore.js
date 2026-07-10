export function formatScore(value, decimals = 4) {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }
  return Number(value).toFixed(decimals)
}

export function formatPercent(value, decimals = 1) {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }
  return `${Number(value).toFixed(decimals)}%`
}
