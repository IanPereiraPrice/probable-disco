import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  XAxis, YAxis, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import { getSkillBreakdown } from '@/api/skills'
import type { SkillInfo } from '@/api/types'

function fmtDps(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toFixed(0)
}

const COLORS = [
  '#f97316','#3b82f6','#22c55e','#a855f7','#06b6d4',
  '#ec4899','#eab308','#14b8a6','#f43f5e','#8b5cf6',
  '#84cc16','#fb923c','#60a5fa','#34d399','#c084fc',
]

export function SkillBreakdown() {
  const { userData } = useAppStore()
  const { isLoading: loadingUser } = useUserData()
  const [cdReduction, setCdReduction] = useState(0)
  const [combatMode, setCombatMode] = useState<string>(userData?.combat_mode ?? 'stage')

  const query = useQuery({
    queryKey: ['skillBreakdown', userData, cdReduction, combatMode],
    queryFn: async () => {
      if (!userData) return null
      // Temporarily apply cd_reduction override on a copy of user data
      const modData = {
        ...userData,
        // skill_cd_reduction is set on the character — pass as extra param
      }
      return getSkillBreakdown({
        user_data: modData,
        combat_mode: combatMode,
      })
    },
    enabled: !!userData,
    staleTime: 1000 * 30,
  })

  if (loadingUser || !userData) return <p className="text-slate-400">Loading...</p>

  const breakdown = query.data as Record<string, SkillInfo> | null | undefined

  const tableRows = breakdown
    ? Object.entries(breakdown)
        .map(([key, info]) => ({ key, ...info }))
        .sort((a, b) => b.dps - a.dps)
    : []

  const totalDps = tableRows.reduce((s, r) => s + r.dps, 0)

  // Pie-style horizontal bar data
  const barData = tableRows.slice(0, 12).map((r, i) => ({
    name: r.display_name,
    dps: r.dps,
    color: COLORS[i % COLORS.length],
  }))

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-end">
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

        <div className="flex-1 min-w-48">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-400">CD Reduction</span>
            <span className="text-orange-400 font-medium">{cdReduction.toFixed(1)}s</span>
          </div>
          <input
            type="range"
            min={0}
            max={10}
            step={0.5}
            value={cdReduction}
            onChange={(e) => setCdReduction(Number(e.target.value))}
            className="w-full accent-orange-500"
          />
        </div>
      </div>

      {/* Horizontal bar chart */}
      {barData.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <p className="text-sm font-medium text-slate-300 mb-4">DPS Distribution</p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} layout="vertical" margin={{ left: 120, right: 60 }}>
              <XAxis type="number" tickFormatter={fmtDps} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#cbd5e1', fontSize: 11 }} axisLine={false} tickLine={false} width={115} />
              <Tooltip
                formatter={(val: number) => [fmtDps(val), 'DPS']}
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              />
              <Bar dataKey="dps" radius={[0, 4, 4, 0]}>
                {barData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Skill table */}
      {tableRows.length > 0 && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                <th className="px-4 py-3 text-slate-400 font-medium">Skill</th>
                <th className="px-4 py-3 text-slate-400 font-medium text-right">DPS</th>
                <th className="px-4 py-3 text-slate-400 font-medium text-right">% Total</th>
                <th className="px-4 py-3 text-slate-400 font-medium">Type</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row, i) => (
                <tr
                  key={row.key}
                  className={`border-b border-slate-800 hover:bg-slate-700/30 ${i === 0 ? 'bg-orange-500/5' : ''}`}
                >
                  <td className="px-4 py-2.5 text-slate-200">{row.display_name}</td>
                  <td className="px-4 py-2.5 text-slate-100 font-mono text-right">{fmtDps(row.dps)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-20 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full bg-orange-500 rounded-full"
                          style={{ width: `${Math.min(100, (row.dps / (tableRows[0]?.dps ?? 1)) * 100)}%` }}
                        />
                      </div>
                      <span className="text-slate-300 font-mono w-12 text-right">
                        {((row.dps / totalDps) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 capitalize text-xs">
                    {row.skill_type.replace('_', ' ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {query.isFetching && <p className="text-xs text-slate-500">Calculating...</p>}
      {query.isError && <p className="text-red-400 text-sm">Error: {String(query.error)}</p>}
    </div>
  )
}
