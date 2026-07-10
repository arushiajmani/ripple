export function criticalityBand(criticality) {
  if (criticality >= 0.7) {
    return 'high'
  }
  if (criticality >= 0.4) {
    return 'medium'
  }
  return 'low'
}

export function criticalityLabel(criticality) {
  const band = criticalityBand(criticality)
  if (band === 'high') {
    return 'High criticality'
  }
  if (band === 'medium') {
    return 'Medium criticality'
  }
  return 'Low criticality'
}

export function criticalityColor(criticality) {
  const band = criticalityBand(criticality)
  if (band === 'high') {
    return 'var(--color-error)'
  }
  if (band === 'medium') {
    return 'var(--color-warning)'
  }
  return 'var(--color-accent-light)'
}

export function computeHealth({ summary, statistics, scores, cycleCount }) {
  const findings = []
  const signals = []

  const cycles = cycleCount ?? summary?.cycle_count ?? 0
  if (cycles > 0) {
    signals.push('cycles')
    findings.push({
      type: 'warning',
      text: `${cycles} circular import loop${cycles === 1 ? '' : 's'} detected — review coupling before refactoring.`,
    })
  }

  const density = statistics?.graph_density
  if (density != null && density > 0.05) {
    signals.push('density')
    findings.push({
      type: 'info',
      text: `Graph density is ${(density * 100).toFixed(1)}% — modules are tightly interconnected.`,
    })
  }

  const top = scores?.[0]
  if (top && top.criticality >= 0.8) {
    signals.push('concentration')
    findings.push({
      type: 'info',
      text: `Risk is concentrated in \`${top.file_path}\` — a small set of files carries most architectural weight.`,
    })
  }

  if (top) {
    findings.push({
      type: 'success',
      text: `Start with \`${top.file_path}\` — highest criticality (imported by ${top.in_degree} file${top.in_degree === 1 ? '' : 's'}).`,
    })
  }

  let overall = 'healthy'
  if (signals.includes('cycles') || (top?.criticality ?? 0) >= 0.85) {
    overall = 'at-risk'
  } else if (signals.includes('density') || signals.includes('concentration')) {
    overall = 'attention'
  }

  return {
    overall,
    findings: findings.slice(0, 4),
    signals,
  }
}

export function healthLabel(overall) {
  if (overall === 'at-risk') {
    return 'Needs attention'
  }
  if (overall === 'attention') {
    return 'Moderate complexity'
  }
  return 'Structurally sound'
}
