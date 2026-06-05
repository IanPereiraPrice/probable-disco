import { apiClient } from './client'

export interface StatLabel {
  display: string
  short: string
}

export interface PotentialConfig {
  tiers: string[]                                                     // ['rare','epic','unique','legendary','mystic']
  stat_labels: Record<string, StatLabel>
  slot_stats: Record<string, string[]>                                // slot → available stat keys
  special_per_slot: Record<string, string | null>                     // slot → special stat key or null
  value_table: Record<string, Record<string, Record<string, { yellow: number; grey: number }>>>
  regular_pity_thresholds: Record<string, number>
  bonus_pity_thresholds: Record<string, number>
}

export async function getPotentialConfig(): Promise<PotentialConfig> {
  const { data } = await apiClient.get<PotentialConfig>('/potential-config')
  return data
}
