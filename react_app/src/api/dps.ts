import { apiClient } from './client'
import type { UserData, DpsResult } from './types'

export interface CalculateDpsParams {
  user_data: UserData
  combat_mode?: string
  enemy_def?: number
  use_realistic_dps?: boolean
  boss_importance?: number
}

export async function calculateDps(params: CalculateDpsParams): Promise<DpsResult> {
  const { data } = await apiClient.post<DpsResult>('/calculate-dps', params)
  return data
}

export async function aggregateStats(userData: UserData): Promise<Record<string, unknown>> {
  const { data } = await apiClient.post<Record<string, unknown>>('/aggregate-stats', userData)
  return data
}
