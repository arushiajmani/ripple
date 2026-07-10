import { apiFetch } from './client.js'

export function getRepoGraph(repoId) {
  return apiFetch(`/api/repos/${repoId}/graph`)
}

export function getRepoScores(repoId) {
  return apiFetch(`/api/repos/${repoId}/scores`)
}

export function getRepoImpact(repoId, filePath) {
  const params = new URLSearchParams({ file: filePath })
  return apiFetch(`/api/repos/${repoId}/impact?${params}`)
}
