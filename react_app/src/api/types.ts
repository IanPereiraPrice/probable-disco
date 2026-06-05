/** Mirrors the Python UserData dataclass from data_manager.py */
export interface UserData {
  username: string
  character_level: number
  job_class: 'bowmaster' | 'night_lord' | 'ice_lightning_mage' | 'shadower'
  all_skills: number
  combat_mode: 'stage' | 'boss' | 'world_boss' | 'chapter_hunt'
  chapter: string
  equipped_weapon_key: string
  summoning_level: number
  active_hero_power_preset: string

  equipment_items: Record<string, Record<string, unknown>>
  equipment_potentials: Record<string, Record<string, unknown>>
  equipment_scrolls: Record<string, Record<string, unknown>>

  hero_power_lines: Record<string, Record<string, unknown>>
  hero_power_passives: Record<string, number>
  hero_power_level: Record<string, unknown>
  hero_power_presets: Record<string, Record<string, unknown>>
  hero_power_passive_values: Record<string, number>

  artifacts_equipped: Record<string, Record<string, unknown>>
  artifacts_inventory: Record<string, Record<string, unknown>>
  artifacts_resonance: Record<string, unknown>

  weapons_data: Record<string, { level: number; awakening: number }>
  companions_equipped: Record<string, Record<string, unknown>>
  companions_inventory: Record<string, Record<string, unknown>>
  companion_levels: Record<string, number>
  equipped_companions: (string | null)[]

  maple_rank: Record<string, unknown>
  equipment_sets: Record<string, number>
  manual_adjustments: Record<string, number>
  guild_skills: Record<string, number>
  unique_stats: Record<string, number>
}

export interface DpsResult {
  total: number
  basic_attack_dps: number
  active_skill_dps: number
  summon_dps: number
  proc_dps: number
  mob_phase_dps: number
  boss_phase_dps: number
  stat_mult: number
  damage_mult: number
  crit_mult: number
  def_mult: number
  fd_mult: number
  range_mult: number
  defense_pen: number
  attack_speed: number
}

export interface SkillInfo {
  display_name: string
  dps: number
  pct_of_total: number
  skill_type: string
  total_damage: number
  mob_damage: number
  boss_damage: number
}

export interface CooldownSummaryPoint {
  cd_reduction: number
  total_dps: number
}

export interface CooldownSkillRow {
  skill: string
  skill_name: string
  dps: number
  pct: number
  skill_type: string
}

export interface CooldownAnalysisResult {
  summary: CooldownSummaryPoint[]
  breakdowns: Record<string, CooldownSkillRow[]>
}
