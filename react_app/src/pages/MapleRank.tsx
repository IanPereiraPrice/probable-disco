import { useState, useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'

// ─── Constants ────────────────────────────────────────────────────────────────

const MR_STATS = [
  { key: 'damage_percent', label: 'Damage %', maxLevel: 20, perLevel: 0.35 },
  { key: 'boss_damage', label: 'Boss Damage %', maxLevel: 10, perLevel: 1.0 },
  { key: 'normal_damage', label: 'Normal Damage %', maxLevel: 20, perLevel: 0.55 },
  { key: 'crit_damage', label: 'Crit Damage %', maxLevel: 20, perLevel: 0.55 },
  { key: 'skill_damage', label: 'Skill Damage %', maxLevel: 20, perLevel: 1.15 },
  { key: 'attack_speed', label: 'Attack Speed %', maxLevel: 30, perLevel: 0.667 },
  { key: 'crit_rate', label: 'Crit Rate %', maxLevel: 30, perLevel: 0.667 },
  { key: 'min_dmg_mult', label: 'Min DMG Mult %', maxLevel: 30, perLevel: 0.667 },
  { key: 'max_dmg_mult', label: 'Max DMG Mult %', maxLevel: 30, perLevel: 0.833 },
  { key: 'accuracy', label: 'Accuracy', maxLevel: 50, perLevel: 0.7 },
]

// Main stat per point based on stage:
// Stage 1-7: base starts 1, increments by 2 per stage (1,3,5,7,9,11,13)
// Stage 8-10: increments by 4 (17,21,25)
// Stage 11+: increments by 5 (30,35,40,...)
// Max stage 21, max 10 points per stage
function getMainStatPerPoint(stage: number): number {
  if (stage <= 0) return 0
  if (stage <= 7) return 1 + (stage - 1) * 2       // 1,3,5,7,9,11,13
  if (stage <= 10) {
    const base = 13 + (stage - 7) * 4              // 17,21,25
    return base
  }
  // stage 11+
  const base = 25 + (stage - 10) * 5              // 30,35,40,...
  return base
}

function getRegularMainStat(stage: number, level: number): number {
  if (stage <= 0 || level <= 0) return 0
  // Each point in each stage gives getMainStatPerPoint(stage) main stat
  // We accumulate all stages up to stage-1 at 10 points, then current stage at level points
  let total = 0
  for (let s = 1; s < stage; s++) {
    total += getMainStatPerPoint(s) * 10
  }
  total += getMainStatPerPoint(stage) * level
  return total
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = 'stage' | 'stats'

export function MapleRank() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const [activeTab, setActiveTab] = useState<Tab>('stage')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.maple_rank])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const rank = (userData.maple_rank ?? {}) as Record<string, unknown>
  const currentStage = Number(rank.current_stage ?? 1)
  const mainStatLevel = Number(rank.main_stat_level ?? 0)
  const specialMainStat = Number(rank.special_main_stat ?? 0)
  const statLevels = (rank.stat_levels ?? {}) as Record<string, number>

  function setRankField(key: string, value: unknown) {
    updateCharacterField('maple_rank', { ...rank, [key]: value })
  }

  function setStatLevel(statKey: string, value: number) {
    updateCharacterField('maple_rank', {
      ...rank,
      stat_levels: { ...statLevels, [statKey]: value },
    })
  }

  const regularMainStat = getRegularMainStat(currentStage, mainStatLevel)
  const specialMainStatValue = 100 + specialMainStat * 50
  const totalMainStat = regularMainStat + (specialMainStat > 0 ? specialMainStatValue : 0)

  return (
    <div className="max-w-2xl space-y-5">
      {/* Tab bar */}
      <div className="flex bg-slate-800/60 border border-slate-700 rounded-lg p-0.5 gap-0.5 w-fit">
        {([
          { key: 'stage', label: 'Stage Progress' },
          { key: 'stats', label: 'Stat Bonuses' },
        ] as { key: Tab; label: string }[]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === key
                ? 'bg-orange-500 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Stage Progress tab */}
      {activeTab === 'stage' && (
        <div className="space-y-5">
          {/* Current Stage */}
          <section className="bg-slate-800/40 border border-slate-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-300">Current Stage</label>
              <span className="text-orange-400 font-bold text-lg">{currentStage}</span>
            </div>
            <input
              type="range"
              min={1}
              max={21}
              value={currentStage}
              onChange={(e) => setRankField('current_stage', Number(e.target.value))}
              className="w-full accent-orange-500"
            />
            <div className="flex justify-between text-xs text-slate-600">
              <span>1</span>
              <span>21</span>
            </div>
          </section>

          {/* Main Stat Level */}
          <section className="bg-slate-800/40 border border-slate-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-300">
                Main Stat Level <span className="text-xs text-slate-500">(current stage)</span>
              </label>
              <div className="text-right">
                <span className="text-orange-400 font-bold">{mainStatLevel}/10</span>
                <p className="text-xs text-slate-500">{getMainStatPerPoint(currentStage)} per point</p>
              </div>
            </div>
            <input
              type="range"
              min={0}
              max={10}
              value={mainStatLevel}
              onChange={(e) => setRankField('main_stat_level', Number(e.target.value))}
              className="w-full accent-orange-500"
            />
          </section>

          {/* Special Main Stat */}
          <section className="bg-slate-800/40 border border-slate-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-300">
                Special Main Stat <span className="text-xs text-slate-500">(50 each, base 100)</span>
              </label>
              <div className="text-right">
                <span className="text-orange-400 font-bold">{specialMainStat}/20</span>
                <p className="text-xs text-slate-500">{specialMainStatValue} total</p>
              </div>
            </div>
            <input
              type="range"
              min={0}
              max={20}
              value={specialMainStat}
              onChange={(e) => setRankField('special_main_stat', Number(e.target.value))}
              className="w-full accent-orange-500"
            />
          </section>

          {/* Summary */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Regular Main Stat', value: regularMainStat.toLocaleString() },
              { label: 'Special Main Stat', value: specialMainStat > 0 ? specialMainStatValue.toLocaleString() : '—' },
              { label: 'Total', value: totalMainStat.toLocaleString() },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/40 border border-slate-700 rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-green-400">{value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stat Bonuses tab */}
      {activeTab === 'stats' && (
        <div className="space-y-3">
          {MR_STATS.map((stat) => {
            const level = Number(statLevels[stat.key] ?? 0)
            const value = level * stat.perLevel
            return (
              <div key={stat.key} className="bg-slate-800/40 border border-slate-700 rounded-lg px-4 py-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-300">{stat.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-green-400 tabular-nums">
                      {value.toLocaleString('en-US', { maximumFractionDigits: 1 })}%
                    </span>
                    <span className="text-sm font-bold text-orange-400">Lv {level}</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={0}
                  max={stat.maxLevel}
                  value={level}
                  onChange={(e) => setStatLevel(stat.key, Number(e.target.value))}
                  className="w-full accent-orange-500"
                />
                <div className="flex justify-between text-xs text-slate-600">
                  <span>0</span>
                  <span>{stat.maxLevel}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {isSaving && <p className="text-xs text-slate-500">Saving...</p>}
    </div>
  )
}
