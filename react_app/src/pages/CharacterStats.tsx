import { useState, useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import { apiClient } from '@/api/client'

// ─── Stat display config ──────────────────────────────────────────────────────

interface StatGroup {
  label: string
  rows: { key: string; label: string; unit?: string; transform?: (v: unknown) => number }[]
}

const STAT_GROUPS: StatGroup[] = [
  {
    label: 'Attack',
    rows: [
      { key: 'attack_flat', label: 'Attack (flat)' },
      { key: 'attack_pct', label: 'Attack %', unit: '%' },
    ],
  },
  {
    label: 'Combat',
    rows: [
      { key: 'crit_rate', label: 'Crit Rate', unit: '%' },
      { key: 'crit_damage', label: 'Crit Damage', unit: '%' },
      { key: 'damage_pct', label: 'Damage %', unit: '%' },
      { key: 'boss_damage', label: 'Boss Damage', unit: '%' },
      { key: 'normal_damage', label: 'Normal Damage', unit: '%' },
    ],
  },
  {
    label: 'Skills',
    rows: [
      { key: 'skill_damage', label: 'Skill Damage', unit: '%' },
      { key: 'basic_attack_damage', label: 'Basic Attack Damage', unit: '%' },
      { key: 'skill_cd', label: 'CD Reduction', unit: 's' },
    ],
  },
  {
    label: 'Multipliers',
    rows: [
      { key: 'min_dmg_mult', label: 'Min DMG Mult', unit: '%' },
      { key: 'max_dmg_mult', label: 'Max DMG Mult', unit: '%' },
    ],
  },
  {
    label: 'Penetration & Speed',
    rows: [
      {
        key: 'def_pen_sources',
        label: 'Def Pen (total)',
        unit: '%',
        transform: (v) => Array.isArray(v) ? (v as number[]).reduce((a, b) => a + b, 0) : Number(v),
      },
      {
        key: 'attack_speed_sources',
        label: 'Attack Speed (total)',
        unit: '%',
        transform: (v) => Array.isArray(v) ? (v as number[]).reduce((a, b) => a + b, 0) : Number(v),
      },
    ],
  },
  {
    label: 'Character',
    rows: [
      { key: 'character_level', label: 'Character Level' },
      { key: 'all_skills', label: '+All Skills' },
    ],
  },
  {
    label: 'Skill Bonuses',
    rows: [
      { key: 'skill_1st', label: '+1st Job Skills' },
      { key: 'skill_2nd', label: '+2nd Job Skills' },
      { key: 'skill_3rd', label: '+3rd Job Skills' },
      { key: 'skill_4th', label: '+4th Job Skills' },
    ],
  },
]

function fmtVal(v: number, unit?: string): string {
  if (unit === '%') return `${v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}%`
  if (unit === 's') return `${v.toFixed(1)}s`
  return v.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function CharacterStats() {
  const { userData } = useAppStore()
  const { isLoading } = useUserData()
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [isFetching, setIsFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchStats = useCallback(async () => {
    if (!userData) return
    setIsFetching(true)
    setError(null)
    try {
      const res = await apiClient.post('/aggregate-stats', userData)
      setStats(res.data)
    } catch (e) {
      setError(String(e))
    } finally {
      setIsFetching(false)
    }
  }, [userData])

  // Auto-fetch on load and debounce on userData changes
  useEffect(() => {
    if (!userData) return
    if (fetchTimer.current) clearTimeout(fetchTimer.current)
    fetchTimer.current = setTimeout(fetchStats, 400)
    return () => { if (fetchTimer.current) clearTimeout(fetchTimer.current) }
  }, [userData])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading character data...</p>
  }

  return (
    <div className="max-w-2xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={fetchStats}
          disabled={isFetching}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50 transition-colors"
        >
          {isFetching ? 'Calculating...' : 'Recalculate'}
        </button>
        {isFetching && <span className="text-xs text-slate-500">Fetching stats...</span>}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>

      {/* Stat groups */}
      {stats && STAT_GROUPS.map((group) => {
        const rows = group.rows.map((row) => {
          const raw = stats[row.key]
          const value = row.transform ? row.transform(raw) : Number(raw ?? 0)
          return { ...row, value }
        }).filter((r) => r.value !== 0)

        if (rows.length === 0) return null

        return (
          <section key={group.label}>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{group.label}</h3>
            <div className="bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden">
              {rows.map((row, i) => (
                <div
                  key={row.key}
                  className={`flex items-center justify-between px-4 py-2.5 ${
                    i < rows.length - 1 ? 'border-b border-slate-700/60' : ''
                  }`}
                >
                  <span className="text-sm text-slate-400">{row.label}</span>
                  <span className="text-sm font-semibold text-slate-100 tabular-nums">
                    {fmtVal(row.value, row.unit)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )
      })}

      {!stats && !isFetching && (
        <div className="text-center py-12 text-slate-500">
          <p>Click <span className="text-orange-400 font-medium">Recalculate</span> to compute your aggregated stats</p>
        </div>
      )}
    </div>
  )
}
