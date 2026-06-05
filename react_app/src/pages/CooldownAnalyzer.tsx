import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, Cell, ReferenceLine,
} from 'recharts'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import { getCooldownAnalysis } from '@/api/skills'
import type { CooldownSummaryPoint } from '@/api/types'

function fmtDps(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toFixed(0)
}

export function CooldownAnalyzer() {
  const { userData } = useAppStore()
  const { isLoading: loadingUser } = useUserData()
  const [combatMode, setCombatMode] = useState<string>(userData?.combat_mode ?? 'stage')

  const query = useQuery({
    queryKey: ['cooldownAnalysis', userData, combatMode],
    queryFn: () => getCooldownAnalysis({ user_data: userData!, combat_mode: combatMode }),
    enabled: !!userData,
    staleTime: 1000 * 60,
  })

  if (loadingUser || !userData) return <p className="text-slate-400">Loading...</p>

  const result = query.data
  const summary: CooldownSummaryPoint[] = result?.summary ?? []

  // Marginal DPS gain per 0.5s step
  const marginal = summary.slice(1).map((pt, i) => ({
    cd: `+${pt.cd_reduction.toFixed(1)}s`,
    gain: pt.total_dps - summary[i].total_dps,
  }))

  const baseDps = summary[0]?.total_dps ?? 0
  const maxDps = summary[summary.length - 1]?.total_dps ?? 0

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Combat Mode</label>
          <select
            value={combatMode}
            onChange={(e) => setCombatMode(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-500"
          >
            <option value="stage">Stage</option>
            <option value="boss">Boss</option>
            <option value="world_boss">World Boss</option>
            <option value="chapter_hunt">Chapter Hunt</option>
          </select>
        </div>

        {summary.length > 0 && (
          <div className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2 text-sm">
            <span className="text-slate-400">0s → 10s gain: </span>
            <span className="text-orange-400 font-bold">{fmtDps(maxDps - baseDps)}</span>
            <span className="text-slate-500 ml-1">
              (+{(((maxDps - baseDps) / baseDps) * 100).toFixed(1)}%)
            </span>
          </div>
        )}
      </div>

      {/* DPS vs CD line chart */}
      {summary.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <p className="text-sm font-medium text-slate-300 mb-4">Total DPS vs Cooldown Reduction</p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={summary} margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="cd_reduction"
                tickFormatter={(v: number) => `${v}s`}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
              />
              <YAxis
                tickFormatter={fmtDps}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip
                formatter={(val: number) => [fmtDps(val), 'Total DPS']}
                labelFormatter={(l: number) => `CD Reduction: ${l}s`}
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              />
              <Line
                type="monotone"
                dataKey="total_dps"
                stroke="#f97316"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, fill: '#f97316' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Marginal gain bar chart */}
      {marginal.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <p className="text-sm font-medium text-slate-300 mb-4">Marginal DPS Gain per 0.5s</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={marginal} margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="cd" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} />
              <YAxis tickFormatter={fmtDps} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(val: number) => [fmtDps(val), 'DPS Gain']}
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              />
              <ReferenceLine y={0} stroke="#334155" />
              <Bar dataKey="gain" radius={[4, 4, 0, 0]}>
                {marginal.map((entry, i) => (
                  <Cell key={i} fill={entry.gain >= 0 ? '#f97316' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary table */}
      {summary.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                <th className="px-4 py-3 text-slate-400 font-medium">CD Reduction</th>
                <th className="px-4 py-3 text-slate-400 font-medium text-right">Total DPS</th>
                <th className="px-4 py-3 text-slate-400 font-medium text-right">vs Baseline</th>
              </tr>
            </thead>
            <tbody>
              {summary.filter((_, i) => i % 2 === 0).map((pt) => (
                <tr key={pt.cd_reduction} className="border-b border-slate-800 hover:bg-slate-700/30">
                  <td className="px-4 py-2 text-slate-300">{pt.cd_reduction.toFixed(1)}s</td>
                  <td className="px-4 py-2 text-slate-100 font-mono text-right">{fmtDps(pt.total_dps)}</td>
                  <td className="px-4 py-2 text-right">
                    {pt.cd_reduction === 0 ? (
                      <span className="text-slate-500">baseline</span>
                    ) : (
                      <span className="text-green-400 font-mono">
                        +{(((pt.total_dps - baseDps) / baseDps) * 100).toFixed(2)}%
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {query.isFetching && <p className="text-xs text-slate-500">Calculating sweep...</p>}
      {query.isError && <p className="text-red-400 text-sm">Error: {String(query.error)}</p>}
    </div>
  )
}
