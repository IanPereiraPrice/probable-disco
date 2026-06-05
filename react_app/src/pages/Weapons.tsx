import { useState, useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'

// ─── Weapon data ──────────────────────────────────────────────────────────────

const RARITIES = ['normal', 'rare', 'epic', 'unique', 'legendary', 'mystic', 'ancient'] as const
type Rarity = typeof RARITIES[number]
const TIERS = [1, 2, 3, 4] as const

const MAX_LEVELS: Record<Rarity, number> = {
  normal: 40,
  rare: 40,
  epic: 60,
  unique: 80,
  legendary: 100,
  mystic: 120,
  ancient: 120,
}

const RARITY_COLORS: Record<Rarity, string> = {
  normal: 'text-slate-400',
  rare: 'text-blue-400',
  epic: 'text-purple-400',
  unique: 'text-yellow-400',
  legendary: 'text-orange-400',
  mystic: 'text-red-400',
  ancient: 'text-cyan-300',
}

const RARITY_BG: Record<Rarity, string> = {
  normal: 'bg-slate-800/60',
  rare: 'bg-blue-900/20 border-blue-800/60',
  epic: 'bg-purple-900/20 border-purple-800/60',
  unique: 'bg-yellow-900/20 border-yellow-800/60',
  legendary: 'bg-orange-900/20 border-orange-800/60',
  mystic: 'bg-red-900/20 border-red-800/60',
  ancient: 'bg-cyan-900/20 border-cyan-800/60',
}

// All valid weapon keys: rarity_tier, excluding ancient_1
function getWeaponKey(rarity: Rarity, tier: number): string {
  return `${rarity}_${tier}`
}

function isValidWeapon(rarity: Rarity, tier: number): boolean {
  return !(rarity === 'ancient' && tier === 1)
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = 'all' | 'equipped'

export function Weapons() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const [activeTab, setActiveTab] = useState<Tab>('all')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.weapons_data, userData?.equipped_weapon_key])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const weaponsData = userData.weapons_data ?? {}
  const equippedKey = userData.equipped_weapon_key ?? ''

  function getWeapon(key: string) {
    const w = weaponsData[key]
    return { level: w?.level ?? 0, awakening: w?.awakening ?? 0 }
  }

  function setWeaponField(key: string, field: 'level' | 'awakening', value: number) {
    const current = getWeapon(key)
    updateCharacterField('weapons_data', {
      ...weaponsData,
      [key]: { ...current, [field]: value },
    })
  }

  const ownedWeapons = RARITIES.flatMap((r) =>
    TIERS.filter((t) => isValidWeapon(r, t)).map((t) => {
      const key = getWeaponKey(r, t)
      const w = getWeapon(key)
      return { key, rarity: r, tier: t, ...w }
    })
  ).filter((w) => w.level > 0)

  return (
    <div className="max-w-3xl space-y-5">
      {/* Tab bar */}
      <div className="flex bg-slate-800/60 border border-slate-700 rounded-lg p-0.5 gap-0.5 w-fit">
        {([
          { key: 'all', label: 'All Weapons' },
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

      {/* All Weapons tab */}
      {activeTab === 'all' && (
        <div className="space-y-4">
          {RARITIES.map((rarity) => {
            const validTiers = TIERS.filter((t) => isValidWeapon(rarity, t))
            return (
              <section key={rarity}>
                <h3 className={`text-sm font-semibold mb-2 capitalize ${RARITY_COLORS[rarity]}`}>
                  {rarity.charAt(0).toUpperCase() + rarity.slice(1)}
                  <span className="text-xs text-slate-600 ml-2 font-normal">max Lv {MAX_LEVELS[rarity]}</span>
                </h3>
                <div className={`border border-slate-700 rounded-lg overflow-hidden ${RARITY_BG[rarity]}`}>
                  <div className="grid grid-cols-4 gap-0">
                    {/* Header */}
                    <div className="col-span-4 grid grid-cols-4 border-b border-slate-700/60 bg-slate-900/40">
                      {validTiers.map((t) => (
                        <div key={t} className="px-3 py-1.5 text-center text-xs font-semibold text-slate-500 uppercase">
                          Tier {t}
                        </div>
                      ))}
                      {/* Pad if < 4 tiers (only ancient) */}
                      {validTiers.length < 4 && (
                        <div className="col-span-1" />
                      )}
                    </div>
                    {/* Weapon cells */}
                    {validTiers.map((t, i) => {
                      const key = getWeaponKey(rarity, t)
                      const w = getWeapon(key)
                      const isEquipped = equippedKey === key
                      return (
                        <div
                          key={key}
                          className={`px-3 py-3 space-y-2 ${i < validTiers.length - 1 ? 'border-r border-slate-700/60' : ''} ${isEquipped ? 'bg-orange-500/10' : ''}`}
                        >
                          {isEquipped && (
                            <span className="text-xs text-orange-400 font-semibold block">Equipped</span>
                          )}
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-slate-500 shrink-0">Lv</span>
                            <input
                              type="number"
                              min={0}
                              max={MAX_LEVELS[rarity]}
                              value={w.level || ''}
                              placeholder="0"
                              onChange={(e) => setWeaponField(key, 'level', Math.min(MAX_LEVELS[rarity], Math.max(0, Number(e.target.value))))}
                              className="flex-1 min-w-0 bg-slate-900 border border-slate-700 text-orange-300 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                            />
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-slate-500 shrink-0">Awaken</span>
                            <input
                              type="number"
                              min={0}
                              max={5}
                              value={w.awakening || ''}
                              placeholder="0"
                              onChange={(e) => setWeaponField(key, 'awakening', Math.min(5, Math.max(0, Number(e.target.value))))}
                              className="flex-1 min-w-0 bg-slate-900 border border-slate-700 text-yellow-400 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                            />
                          </div>
                        </div>
                      )
                    })}
                    {/* Pad for ancient (only 3 tiers) */}
                    {validTiers.length === 3 && <div className="border-l border-slate-700/60" />}
                  </div>
                </div>
              </section>
            )
          })}
        </div>
      )}

      {/* Equipped tab */}
      {activeTab === 'equipped' && (
        <div className="space-y-5">
          <div className="space-y-3">
            <label className="block text-sm font-medium text-slate-300">Equipped Weapon</label>
            {ownedWeapons.length === 0 && (
              <p className="text-sm text-slate-500 italic">No weapons owned yet. Set levels in the All Weapons tab first.</p>
            )}
            {ownedWeapons.length > 0 && (
              <select
                value={equippedKey}
                onChange={(e) => updateCharacterField('equipped_weapon_key', e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-orange-500"
              >
                <option value="">— none —</option>
                {ownedWeapons.map((w) => (
                  <option key={w.key} value={w.key}>
                    {w.rarity.charAt(0).toUpperCase() + w.rarity.slice(1)} Tier {w.tier} — Lv {w.level} | Awaken {w.awakening}
                  </option>
                ))}
              </select>
            )}
          </div>

          {equippedKey && (() => {
            const w = getWeapon(equippedKey)
            const parts = equippedKey.split('_')
            const tier = parts[parts.length - 1]
            const rarity = parts.slice(0, -1).join('_') as Rarity
            if (!w.level) return null
            return (
              <div className={`border border-slate-700 rounded-lg p-4 space-y-2 ${RARITY_BG[rarity] ?? ''}`}>
                <h3 className={`text-sm font-semibold capitalize ${RARITY_COLORS[rarity] ?? 'text-slate-400'}`}>
                  {rarity} Tier {tier}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-800/40 border border-slate-700 rounded p-3 text-center">
                    <p className="text-xl font-bold text-orange-400">{w.level}</p>
                    <p className="text-xs text-slate-500">Level</p>
                  </div>
                  <div className="bg-slate-800/40 border border-slate-700 rounded p-3 text-center">
                    <p className="text-xl font-bold text-yellow-400">{w.awakening}</p>
                    <p className="text-xs text-slate-500">Awakening</p>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      )}

      {isSaving && <p className="text-xs text-slate-500">Saving...</p>}
    </div>
  )
}
