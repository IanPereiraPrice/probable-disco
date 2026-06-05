import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { getUserData, saveUserData } from '@/api/userData'
import { useAppStore } from '@/store/useAppStore'

export function useUserData() {
  const { username, setUserData } = useAppStore()
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['userData', username],
    queryFn: () => getUserData(username),
  })

  // Sync fetched data into the Zustand store
  useEffect(() => {
    if (query.data) setUserData(query.data)
  }, [query.data, setUserData])

  const mutation = useMutation({
    mutationFn: saveUserData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userData', username] })
    },
  })

  return {
    isLoading: query.isLoading,
    isError: query.isError,
    save: mutation.mutateAsync,
    isSaving: mutation.isPending,
  }
}
