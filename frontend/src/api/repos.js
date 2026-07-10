import { apiFetch, apiPostForm } from './client.js'

export function analyzeRepo(formData) {
  return apiPostForm('/api/repos/analyze', formData)
}

export function listRepos() {
  return apiFetch('/api/repos')
}

export function getRepo(repoId) {
  return apiFetch(`/api/repos/${repoId}`)
}
