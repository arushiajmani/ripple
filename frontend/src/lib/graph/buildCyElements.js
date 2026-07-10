import { criticalityColor } from '../health/computeHealth.js'
import { shortPath } from '../format/formatPath.js'

export function buildCyElements(graph, scoresByPath) {
  const nodes = (graph?.nodes ?? []).map((path) => {
    const score = scoresByPath[path] ?? {}
    const criticality = score.criticality ?? 0
    return {
      data: {
        id: path,
        label: shortPath(path),
        fullPath: path,
        criticality,
        pagerank: score.pagerank ?? 0,
        betweenness: score.betweenness ?? 0,
        inDegree: score.in_degree ?? 0,
        outDegree: score.out_degree ?? 0,
        color: criticalityColor(criticality),
      },
    }
  })

  const edges = (graph?.edges ?? []).map((edge, index) => ({
    data: {
      id: `e-${index}-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
    },
  }))

  return [...nodes, ...edges]
}

export function getNeighbors(edges, filePath, direction) {
  if (!filePath || !edges) {
    return []
  }

  if (direction === 'dependents') {
    return edges.filter((e) => e.target === filePath).map((e) => e.source)
  }

  return edges.filter((e) => e.source === filePath).map((e) => e.target)
}
