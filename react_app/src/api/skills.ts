import { apiClient } from './client'
import type { UserData, SkillInfo, CooldownAnalysisResult } from './types'

export interface SkillBreakdownParams {
  user_data: UserData
  combat_mode?: string
  enemy_def?: number
}

export async function getSkillBreakdown(
  params: SkillBreakdownParams
): Promise<Record<string, SkillInfo>> {
  const { data } = await apiClient.post<Record<string, SkillInfo>>('/skill-breakdown', params)
  return data
}

export async function getCooldownAnalysis(
  params: SkillBreakdownParams
): Promise<CooldownAnalysisResult> {
  const { data } = await apiClient.post<CooldownAnalysisResult>('/cooldown-analysis', params)
  return data
}
