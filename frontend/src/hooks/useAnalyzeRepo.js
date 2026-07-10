import { useMutation, useQueryClient } from '@tanstack/react-query'
import { analyzeRepo } from '../api/repos.js'

export function useAnalyzeRepo() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: analyzeRepo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repos'] })
    },
  })
}
