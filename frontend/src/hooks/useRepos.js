import { useQuery } from '@tanstack/react-query'
import { listRepos, getRepo } from '../api/repos.js'

export function useRepos() {
  return useQuery({
    queryKey: ['repos'],
    queryFn: listRepos,
    staleTime: 30_000,
  })
}

export function useRepo(repoId) {
  return useQuery({
    queryKey: ['repos', repoId],
    queryFn: () => getRepo(repoId),
    enabled: Boolean(repoId),
    staleTime: 5 * 60_000,
  })
}
