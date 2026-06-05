import { useState, useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'

// ─── Companion data (from companions.py COMPANIONS dict) ─────────────────────

type Advancement = 'basic' | 'first' | 'second' | 'third' | 'fourth'

interface CompanionDef {
  key: string
  name: string
  advancement: Advancement
  onEquipType: string
}

const MAX_LEVELS: Record<Advancement, number> = {
  basic: 100,
  first: 50,
  second: 30,
  third: 10,
  fourth: 10,
}

const ADVANCEMENT_LABELS: Record<Advancement, string> = {
  basic: 'Basic (Grey)',
  first: '1st Job (Blue)',
  second: '2nd Job (Purple)',
  third: '3rd Job',
  fourth: '4th Job',
}

const ADVANCEMENT_COLORS: Record<Advancement, string> = {
  basic: 'text-slate-400',
  first: 'text-blue-400',
  second: 'text-purple-400',
  third: 'text-yellow-400',
  fourth: 'text-orange-400',
}

const COMPANIONS: CompanionDef[] = [
  // Basic
  { key: 'aspiring_warrior', name: 'Aspiring Warrior', advancement: 'basic', onEquipType: 'flat_attack' },
  { key: 'aspiring_mage', name: 'Aspiring Mage', advancement: 'basic', onEquipType: 'flat_attack' },
  { key: 'aspiring_bowman', name: 'Aspiring Bowman', advancement: 'basic', onEquipType: 'flat_attack' },
  { key: 'aspiring_thief', name: 'Aspiring Thief', advancement: 'basic', onEquipType: 'flat_attack' },
  // 4th Job
  { key: 'bowmaster_4th', name: 'Bowmaster (4th)', advancement: 'fourth', onEquipType: 'attack_speed' },
  { key: 'marksman_4th', name: 'Marksman (4th)', advancement: 'fourth', onEquipType: 'status_effect_dmg' },
  { key: 'night_lord_4th', name: 'Night Lord (4th)', advancement: 'fourth', onEquipType: 'boss_damage' },
  { key: 'shadower_4th', name: 'Shadower (4th)', advancement: 'fourth', onEquipType: 'min_dmg_mult' },
  { key: 'hero_4th', name: 'Hero (4th)', advancement: 'fourth', onEquipType: 'max_dmg_mult' },
  { key: 'dark_knight_4th', name: 'Dark Knight (4th)', advancement: 'fourth', onEquipType: 'boss_damage' },
  { key: 'arch_mage_fp_4th', name: 'Arch Mage F/P (4th)', advancement: 'fourth', onEquipType: 'crit_rate' },
  { key: 'arch_mage_il_4th', name: 'Arch Mage I/L (4th)', advancement: 'fourth', onEquipType: 'normal_damage' },
  // 3rd Job
  { key: 'bowmaster_3rd', name: 'Bowmaster (3rd)', advancement: 'third', onEquipType: 'attack_speed' },
  { key: 'marksman_3rd', name: 'Marksman (3rd)', advancement: 'third', onEquipType: 'status_effect_dmg' },
  { key: 'night_lord_3rd', name: 'Night Lord (3rd)', advancement: 'third', onEquipType: 'boss_damage' },
  { key: 'shadower_3rd', name: 'Shadower (3rd)', advancement: 'third', onEquipType: 'min_dmg_mult' },
  { key: 'hero_3rd', name: 'Hero (3rd)', advancement: 'third', onEquipType: 'max_dmg_mult' },
  { key: 'dark_knight_3rd', name: 'Dark Knight (3rd)', advancement: 'third', onEquipType: 'accuracy' },
  { key: 'arch_mage_fp_3rd', name: 'Arch Mage F/P (3rd)', advancement: 'third', onEquipType: 'crit_rate' },
  { key: 'arch_mage_il_3rd', name: 'Arch Mage I/L (3rd)', advancement: 'third', onEquipType: 'normal_damage' },
  // 2nd Job
  { key: 'bowmaster_2nd', name: 'Bowmaster (2nd)', advancement: 'second', onEquipType: 'attack_speed' },
  { key: 'marksman_2nd', name: 'Marksman (2nd)', advancement: 'second', onEquipType: 'status_effect_dmg' },
  { key: 'night_lord_2nd', name: 'Night Lord (2nd)', advancement: 'second', onEquipType: 'boss_damage' },
  { key: 'shadower_2nd', name: 'Shadower (2nd)', advancement: 'second', onEquipType: 'min_dmg_mult' },
  { key: 'hero_2nd', name: 'Hero (2nd)', advancement: 'second', onEquipType: 'max_dmg_mult' },
  { key: 'dark_knight_2nd', name: 'Dark Knight (2nd)', advancement: 'second', onEquipType: 'accuracy' },
  { key: 'arch_mage_fp_2nd', name: 'Arch Mage F/P (2nd)', advancement: 'second', onEquipType: 'crit_rate' },
  { key: 'arch_mage_il_2nd', name: 'Arch Mage I/L (2nd)', advancement: 'second', onEquipType: 'normal_damage' },
  // 1st Job
  { key: 'bowmaster_1st', name: 'Bowmaster (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'marksman_1st', name: 'Marksman (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'night_lord_1st', name: 'Night Lord (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'shadower_1st', name: 'Shadower (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'hero_1st', name: 'Hero (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'dark_knight_1st', name: 'Dark Knight (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'arch_mage_fp_1st', name: 'Arch Mage F/P (1st)', advancement: 'first', onEquipType: 'flat_attack' },
  { key: 'arch_mage_il_1st', name: 'Arch Mage I/L (1st)', advancement: 'first', onEquipType: 'flat_attack' },
]

const ADVANCEMENT_ORDER: Advancement[] = ['basic', 'first', 'second', 'third', 'fourth']

const EQUIP_SLOTS = [
  { idx: 0, label: 'Main' },
  { idx: 1, label: 'Sub 1' },
  { idx: 2, label: 'Sub 2' },
  { idx: 3, label: 'Sub 3' },
  { idx: 4, label: 'Sub 4' },
  { idx: 5, label: 'Sub 5' },
  { idx: 6, label: 'Sub 6' },
]

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = 'inventory' | 'equipped'

export function Companions() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const [activeTab, setActiveTab] = useState<Tab>('inventory')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.companion_levels, userData?.equipped_companions])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const companionLevels = userData.companion_levels ?? {}
  const equippedCompanions: (string | null)[] = userData.equipped_companions ?? Array(7).fill(null)

  function setLevel(key: string, value: number) {
    updateCharacterField('companion_levels', { ...companionLevels, [key]: value })
  }

  function setEquipped(idx: number, value: string | null) {
    const next = [...equippedCompanions]
    while (next.length < 7) next.push(null)
    next[idx] = value || null
    updateCharacterField('equipped_companions', next)
  }

  const ownedCompanions = COMPANIONS.filter((c) => Number(companionLevels[c.key] ?? 0) > 0)

  return (
    <div className="max-w-2xl space-y-5">
      {/* Tab bar */}
      <div className="flex bg-slate-800/60 border border-slate-700 rounded-lg p-0.5 gap-0.5 w-fit">
        {([
          { key: 'inventory', label: 'Inventory' },
          { key: 'equipped', label: 'Equipped' },
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

      {/* Inventory tab */}
      {activeTab === 'inventory' && (
        <div className="space-y-5">
          {ADVANCEMENT_ORDER.map((adv) => {
            const group = COMPANIONS.filter((c) => c.advancement === adv)
            return (
              <section key={adv}>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className={`text-sm font-semibold ${ADVANCEMENT_COLORS[adv]}`}>{ADVANCEMENT_LABELS[adv]}</h3>
                  <span className="text-xs text-slate-600">max Lv {MAX_LEVELS[adv]}</span>
                </div>
                <div className="bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden">
                  {group.map((c, i) => {
                    const level = Number(companionLevels[c.key] ?? 0)
                    return (
                      <div
                        key={c.key}
                        className={`flex items-center justify-between px-4 py-2.5 ${
                          i < group.length - 1 ? 'border-b border-slate-700/60' : ''
                        }`}
                      >
                        <span className="text-sm text-slate-300">{c.name}</span>
                        <div className="flex items-center gap-2">
                          {level > 0 && (
                            <span className="text-xs text-green-400">owned</span>
                          )}
                          <input
                            type="number"
                            min={0}
                            max={MAX_LEVELS[c.advancement]}
                            value={level || ''}
                            placeholder="0"
                            onChange={(e) => setLevel(c.key, Math.min(MAX_LEVELS[c.advancement], Math.max(0, Number(e.target.value))))}
                            className="w-16 bg-slate-900 border border-slate-700 text-orange-300 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      )}

      {/* Equipped tab */}
      {activeTab === 'equipped' && (
        <div className="space-y-3">
          {ownedCompanions.length === 0 && (
            <p className="text-sm text-slate-500 italic">No companions owned yet. Set levels in the Inventory tab first.</p>
          )}
          {EQUIP_SLOTS.map(({ idx, label }) => {
            const current = equippedCompanions[idx] ?? ''
            const currentDef = COMPANIONS.find((c) => c.key === current)
            return (
              <div key={idx} className="bg-slate-800/40 border border-slate-700 rounded-lg px-4 py-3 flex items-center gap-3">
                <span className="text-sm font-bold text-slate-400 w-14 shrink-0">{label}</span>
                <select
                  value={current}
                  onChange={(e) => setEquipped(idx, e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-orange-500"
                >
                  <option value="">— none —</option>
                  {ownedCompanions.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.name} (Lv {companionLevels[c.key]})
                    </option>
                  ))}
                </select>
                {currentDef && (
                  <span className={`text-xs shrink-0 ${ADVANCEMENT_COLORS[currentDef.advancement]}`}>
                    {ADVANCEMENT_LABELS[currentDef.advancement].split(' ')[0]}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {isSaving && <p className="text-xs text-slate-500">Saving...</p>}
    </div>
  )
}
