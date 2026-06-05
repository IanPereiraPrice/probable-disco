import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import { calculateDps } from '@/api/dps'
import { getSkillBreakdown } from '@/api/skills'
import type { SkillInfo } from '@/api/types'

function fmtDps(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toFixed(0)
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-orange-400">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

const SKILL_TYPE_COLORS: Record<string, string> = {
  basic:        '#f97316',
  active:       '#3b82f6',
  summon:       '#22c55e',
  passive_proc: '#a855f7',
  passive_buff: '#6b7280',
}

export function DamageCalculator() {
  const { userData } = useAppStore()
  const { isLoading: loadingUser } = useUserData()

  const dpsQuery = useQuery({
    queryKey: ['dps', userData],
    queryFn: () => calculateDps({ user_data: userData! }),
    enabled: !!userData,
    staleTime: 1000 * 30,
  })

  const breakdownQuery = useQuery({
    queryKey: ['skillBreakdown', userData],
    queryFn: () => getSkillBreakdown({ user_data: userData! }),
    enabled: !!userData,
    staleTime: 1000 * 30,
  })

  if (loadingUser || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const dps = dpsQuery.data
  const breakdown = breakdownQuery.data

  // Sort skills by DPS descending for the bar chart
  const chartData = breakdown
    ? Object.entries(breakdown as Record<string, SkillInfo>)
        .map(([key, info]) => ({
          name: info.display_name,
          dps: info.dps,
          type: info.skill_type,
          pct: info.pct_of_total,
          key,
        }))
        .sort((a, b) => b.dps - a.dps)
        .slice(0, 15)
    : []

  const isCalculating = dpsQuery.isFetching || breakdownQuery.isFetching

  return (
    <div className="space-y-6">
      {/* Recalculate button */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => { dpsQuery.refetch(); breakdownQuery.refetch() }}
          disabled={isCalculating}
          className="px-4 py-2 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {isCalculating ? 'Calculating...' : 'Recalculate'}
        </button>
        <span className="text-xs text-slate-500">
          {userData.job_class.replace('_', ' ')} · {userData.combat_mode} · {userData.chapter}
        </span>
      </div>

      {/* Stat cards */}
      {dps && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total DPS"  value={fmtDps(dps.total)} />
          <StatCard label="Basic Atk"  value={fmtDps(dps.basic_attack_dps)} sub={`${((dps.basic_attack_dps / dps.total) * 100).toFixed(1)}%`} />
          <StatCard label="Skills"     value={fmtDps(dps.active_skill_dps)} sub={`${((dps.active_skill_dps / dps.total) * 100).toFixed(1)}%`} />
          <StatCard label="Summons"    value={fmtDps(dps.summon_dps + dps.proc_dps)} sub="summon + proc" />
        </div>
      )}

      {/* Multiplier strip */}
      {dps && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">Multiplier Breakdown</p>
          <div className="flex flex-wrap gap-4 text-sm">
            {[
              ['Stat',   dps.stat_mult],
              ['Damage', dps.damage_mult],
              ['Crit',   dps.crit_mult],
              ['Def Pen', dps.def_mult],
              ['FD',     dps.fd_mult],
              ['Range',  dps.range_mult],
            ].map(([label, val]) => (
              <div key={label as string} className="flex flex-col items-center">
                <span className="text-slate-400 text-xs">{label}</span>
                <span className="text-slate-100 font-mono">{(val as number).toFixed(3)}×</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skill breakdown bar chart */}
      {chartData.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <p className="text-sm font-medium text-slate-300 mb-4">Skill DPS Breakdown (Top 15)</p>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 120, right: 60, top: 0, bottom: 0 }}>
              <XAxis type="number" tickFormatter={fmtDps} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#cbd5e1', fontSize: 11 }} axisLine={false} tickLine={false} width={115} />
              <Tooltip
                formatter={(val: number) => [fmtDps(val), 'DPS']}
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#f1f5f9' }}
              />
              <Bar dataKey="dps" radius={[0, 4, 4, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.key} fill={SKILL_TYPE_COLORS[entry.type] ?? '#6b7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-3">
            {Object.entries(SKILL_TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: color }} />
                {type.replace('_', ' ')}
              </div>
            ))}
          </div>
        </div>
      )}

      {dpsQuery.isError && (
        <p className="text-red-400 text-sm">Error: {String(dpsQuery.error)}</p>
      )}
    </div>
  )
}
