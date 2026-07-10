import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getRepoGraph, getRepoScores } from '../api/graph.js'

export function useRepoGraph(repoId) {
  const graphQuery = useQuery({
    queryKey: ['repos', repoId, 'graph'],
    queryFn: () => getRepoGraph(repoId),
    enabled: Boolean(repoId),
    staleTime: 5 * 60_000,
  })

  const scoresQuery = useQuery({
    queryKey: ['repos', repoId, 'scores'],
    queryFn: () => getRepoScores(repoId),
    enabled: Boolean(repoId),
    staleTime: 5 * 60_000,
  })

  const scoresByPath = useMemo(() => {
    const map = {}
    for (const score of scoresQuery.data?.scores ?? []) {
      map[score.file_path] = score
    }
    return map
  }, [scoresQuery.data])

  const scores = scoresQuery.data?.scores ?? []

  return {
    graph: graphQuery.data,
    scores,
    scoresByPath,
    isLoading: graphQuery.isLoading || scoresQuery.isLoading,
    isError: graphQuery.isError || scoresQuery.isError,
    error: graphQuery.error ?? scoresQuery.error,
  }
}

export function useRepoScores(repoId) {
  return useQuery({
    queryKey: ['repos', repoId, 'scores'],
    queryFn: () => getRepoScores(repoId),
    enabled: Boolean(repoId),
    staleTime: 5 * 60_000,
  })
}
