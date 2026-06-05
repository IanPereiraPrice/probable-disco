import { useState, useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'

// ─── Constants ────────────────────────────────────────────────────────────────

const HP_STATS = [
  { key: 'damage', label: 'Damage %' },
  { key: 'boss_damage', label: 'Boss Damage %' },
  { key: 'normal_damage', label: 'Normal Damage %' },
  { key: 'def_pen', label: 'Defense Pen %' },
  { key: 'max_dmg_mult', label: 'Max Damage Mult %' },
  { key: 'min_dmg_mult', label: 'Min Damage Mult %' },
  { key: 'crit_rate', label: 'Crit Rate %' },
  { key: 'main_stat_flat', label: 'Main Stat (flat)' },
  { key: 'attack_speed', label: 'Attack Speed %' },
  { key: 'max_hp', label: 'Max HP' },
]

const HP_TIERS = [
  { key: 'common', label: 'Common', color: 'text-slate-400' },
  { key: 'rare', label: 'Rare', color: 'text-blue-400' },
  { key: 'epic', label: 'Epic', color: 'text-purple-400' },
  { key: 'unique', label: 'Unique', color: 'text-yellow-400' },
  { key: 'legendary', label: 'Legendary', color: 'text-green-400' },
  { key: 'mystic', label: 'Mystic', color: 'text-red-400' },
]

const TIER_COLOR_MAP: Record<string, string> = Object.fromEntries(HP_TIERS.map((t) => [t.key, t.color]))

const HP_PASSIVES = [
  { key: 'main_stat', label: 'Main Stat', maxLevel: 60, perLevel: 27.5, unit: '' },
  { key: 'damage_percent', label: 'Damage %', maxLevel: 60, perLevel: 0.75, unit: '%' },
  { key: 'attack', label: 'Attack', maxLevel: 60, perLevel: 103.75, unit: '' },
  { key: 'max_hp', label: 'Max HP', maxLevel: 60, perLevel: 2075, unit: '' },
  { key: 'accuracy', label: 'Accuracy', maxLevel: 20, perLevel: 2.25, unit: '' },
  { key: 'defense', label: 'Defense', maxLevel: 60, perLevel: 93.75, unit: '' },
]

// Default line structure
function defaultLine() {
  return { stat: '', tier: 'legendary', value: 0 }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = 'lines' | 'passives'

export function HeroPower() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const [activeTab, setActiveTab] = useState<Tab>('lines')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.hero_power_lines, userData?.hero_power_passives])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const lines = userData.hero_power_lines ?? {}
  const passives = userData.hero_power_passives ?? {}

  function getLine(lineKey: string) {
    const raw = lines[lineKey] ?? {}
    return { ...defaultLine(), ...(raw as Record<string, unknown>) }
  }

  function setLine(lineKey: string, field: string, value: unknown) {
    const current = getLine(lineKey)
    updateCharacterField('hero_power_lines', {
      ...lines,
      [lineKey]: { ...current, [field]: value },
    })
  }

  function setPassive(key: string, value: number) {
    updateCharacterField('hero_power_passives', { ...passives, [key]: value })
  }

  return (
    <div className="max-w-2xl space-y-5">
      {/* Tab bar */}
      <div className="flex bg-slate-800/60 border border-slate-700 rounded-lg p-0.5 gap-0.5 w-fit">
        {([
          { key: 'lines', label: 'Ability Lines' },
          { key: 'passives', label: 'Passive Stats' },
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

      {/* Ability Lines */}
      {activeTab === 'lines' && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5, 6].map((n) => {
            const lineKey = `line_${n}`
            const line = getLine(lineKey)
            const tierColor = TIER_COLOR_MAP[String(line.tier)] ?? 'text-slate-400'
            return (
              <div key={lineKey} className="bg-slate-800/40 border border-slate-700 rounded-lg px-4 py-3 flex items-center gap-3">
                <span className="text-sm font-bold text-slate-500 w-4 shrink-0">{n}</span>

                {/* Tier select */}
                <select
                  value={String(line.tier)}
                  onChange={(e) => setLine(lineKey, 'tier', e.target.value)}
                  className={`bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs font-bold focus:outline-none focus:border-orange-500 ${tierColor}`}
                >
                  {HP_TIERS.map((t) => (
                    <option key={t.key} value={t.key} className="text-slate-200">{t.label}</option>
                  ))}
                </select>

                {/* Stat select */}
                <select
                  value={String(line.stat)}
                  onChange={(e) => setLine(lineKey, 'stat', e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-orange-500 min-w-0"
                >
                  <option value="">— none —</option>
                  {HP_STATS.map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>

                {/* Value input */}
                <input
                  type="number"
                  step="any"
                  value={Number(line.value) || ''}
                  placeholder="0"
                  onChange={(e) => setLine(lineKey, 'value', Number(e.target.value))}
                  className="w-24 bg-slate-900 border border-slate-700 text-orange-300 rounded px-2 py-1.5 text-sm text-right focus:outline-none focus:border-orange-500"
                />
              </div>
            )
          })}
        </div>
      )}

      {/* Passive Stats */}
      {activeTab === 'passives' && (
        <div className="space-y-3">
          {HP_PASSIVES.map((p) => {
            const level = Number(passives[p.key] ?? 0)
            const currentValue = level * p.perLevel
            return (
              <div key={p.key} className="bg-slate-800/40 border border-slate-700 rounded-lg px-4 py-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-300">{p.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-green-400 tabular-nums">
                      {currentValue.toLocaleString('en-US', { maximumFractionDigits: 1 })}{p.unit}
                    </span>
                    <span className="text-sm font-bold text-orange-400">Lv {level}</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={0}
                  max={p.maxLevel}
                  value={level}
                  onChange={(e) => setPassive(p.key, Number(e.target.value))}
                  className="w-full accent-orange-500"
                />
                <div className="flex justify-between text-xs text-slate-600">
                  <span>0</span>
                  <span>{p.maxLevel}</span>
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
