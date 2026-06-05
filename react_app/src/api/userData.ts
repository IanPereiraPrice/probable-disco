import { apiClient } from './client'
import type { UserData } from './types'

export async function getUserData(username = 'default'): Promise<UserData> {
  const { data } = await apiClient.get<UserData>('/user-data', { params: { username } })
  return data
}

export async function saveUserData(userData: UserData): Promise<void> {
  await apiClient.post('/user-data', userData)
}
