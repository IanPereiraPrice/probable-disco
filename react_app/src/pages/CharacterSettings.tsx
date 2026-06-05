import { useCallback, useEffect, useRef } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import type { UserData } from '@/api/types'

const JOB_OPTIONS: { value: UserData['job_class']; label: string }[] = [
  { value: 'bowmaster',          label: 'Bowmaster' },
  { value: 'night_lord',         label: 'Night Lord' },
  { value: 'ice_lightning_mage', label: 'I/L Mage' },
  { value: 'shadower',           label: 'Shadower' },
]

const COMBAT_MODES: { value: UserData['combat_mode']; label: string }[] = [
  { value: 'stage',        label: 'Stage' },
  { value: 'boss',         label: 'Boss' },
  { value: 'world_boss',   label: 'World Boss' },
  { value: 'chapter_hunt', label: 'Chapter Hunt' },
]

const CHAPTERS = Array.from({ length: 35 }, (_, i) => `Chapter ${i + 1}`)

export function CharacterSettings() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced auto-save whenever userData changes
  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [
    userData?.job_class,
    userData?.character_level,
    userData?.combat_mode,
    userData?.chapter,
  ])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading character data...</p>
  }

  return (
    <div className="max-w-lg space-y-6">
      {/* Job Class */}
      <section>
        <label className="block text-sm font-medium text-slate-300 mb-2">Job Class</label>
        <div className="grid grid-cols-2 gap-2">
          {JOB_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => updateCharacterField('job_class', value)}
              className={`px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                userData.job_class === value
                  ? 'bg-orange-500 border-orange-500 text-white'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500 hover:text-slate-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* Character Level */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-slate-300">Character Level</label>
          <span className="text-orange-400 font-bold text-lg">{userData.character_level}</span>
        </div>
        <input
          type="range"
          min={1}
          max={200}
          value={userData.character_level}
          onChange={(e) => updateCharacterField('character_level', Number(e.target.value))}
          className="w-full accent-orange-500"
        />
        <div className="flex justify-between text-xs text-slate-500 mt-1">
          <span>1</span>
          <span>200</span>
        </div>
      </section>

      {/* Combat Mode */}
      <section>
        <label className="block text-sm font-medium text-slate-300 mb-2">Combat Mode</label>
        <select
          value={userData.combat_mode}
          onChange={(e) => updateCharacterField('combat_mode', e.target.value as UserData['combat_mode'])}
          className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-orange-500"
        >
          {COMBAT_MODES.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </section>

      {/* Chapter */}
      <section>
        <label className="block text-sm font-medium text-slate-300 mb-2">Chapter</label>
        <select
          value={userData.chapter}
          onChange={(e) => updateCharacterField('chapter', e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-orange-500"
        >
          {CHAPTERS.map((ch) => (
            <option key={ch} value={ch}>{ch}</option>
          ))}
        </select>
      </section>

      {/* All Skills (read-only display) */}
      <section className="bg-slate-800/50 rounded-lg p-4">
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-400">+All Skills</span>
          <span className="text-orange-400 font-bold">+{userData.all_skills}</span>
        </div>
        <p className="text-xs text-slate-500 mt-1">Auto-calculated from equipment sub-stats</p>
      </section>

      {/* Save status */}
      {isSaving && <p className="text-xs text-slate-500">Saving...</p>}
    </div>
  )
}
