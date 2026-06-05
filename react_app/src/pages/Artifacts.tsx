import { useCallback, useRef, useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'

// ─── Artifact list (from artifacts.py ARTIFACTS dict) ────────────────────────

const ARTIFACT_OPTIONS: { key: string; label: string }[] = [
  { key: 'hexagon_necklace', label: 'Hexagon Necklace' },
  { key: 'book_of_ancient', label: 'Book of Ancient' },
  { key: 'chalice', label: 'Chalice' },
  { key: 'star_rock', label: 'Star Rock' },
  { key: 'sayrams_necklace', label: "Sayram's Necklace" },
  { key: 'lit_lamp', label: 'Lit Lamp' },
  { key: 'soul_contract', label: 'Soul Contract' },
  { key: 'ancient_text_piece', label: 'Ancient Text Piece' },
  { key: 'clear_spring_water', label: 'Clear Spring Water' },
  { key: 'fire_flower', label: 'Fire Flower' },
  { key: 'icy_soul_rock', label: 'Icy Soul Rock' },
  { key: 'silver_pendant', label: 'Silver Pendant' },
  { key: 'rainbow_snail_shell', label: 'Rainbow-colored Snail Shell' },
  { key: 'mushmom_cap', label: "Mushmom's Cap" },
  { key: 'shamaness_marble', label: 'Shamaness Marble' },
  { key: 'contract_of_darkness', label: 'Contract of Darkness' },
  { key: 'charm_of_undead', label: 'Charm of the Undead' },
  { key: 'pigs_ribbon', label: "Pig's Ribbon" },
  { key: 'arwens_glass_shoes', label: "Arwen's Glass Shoes" },
  { key: 'athena_pierces_gloves', label: "Athena Pierce's Old Gloves" },
  { key: 'old_music_box', label: 'Old Music Box' },
  { key: 'lunar_dew', label: 'Lunar Dew' },
  { key: 'soul_pouch', label: 'Soul Pouch' },
  { key: 'zakum_raid_artifact', label: 'Zakum Raid Artifact' },
  { key: 'flaming_lava', label: 'Flaming Lava' },
  { key: 'bottle_of_emotions', label: 'Bottle of Emotions' },
  { key: 'candle', label: 'Candle' },
  { key: 'peach_tree_herb_pouch', label: 'Peach Tree Herb Pouch' },
]

const SLOTS = ['slot_1', 'slot_2', 'slot_3', 'slot_4', 'slot_5', 'slot_6']

function defaultSlot() {
  return { artifact_id: '', stars: 0, level: 1 }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function Artifacts() {
  const { userData, updateCharacterField } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 600)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.artifacts_equipped, userData?.artifacts_resonance])

  if (isLoading || !userData) {
    return <p className="text-slate-400">Loading...</p>
  }

  const equipped = userData.artifacts_equipped ?? {}
  const resonance = userData.artifacts_resonance ?? {}

  function getSlot(slotId: string) {
    return { ...defaultSlot(), ...(equipped[slotId] as Record<string, unknown> ?? {}) }
  }

  function setSlotField(slotId: string, field: string, value: unknown) {
    const current = getSlot(slotId)
    updateCharacterField('artifacts_equipped', {
      ...equipped,
      [slotId]: { ...current, [field]: value },
    })
  }

  function setResonance(key: string, value: number) {
    updateCharacterField('artifacts_resonance', { ...resonance, [key]: value })
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Equipped slots */}
      <section>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Artifact Slots</h3>
        <div className="grid grid-cols-1 gap-3">
          {SLOTS.map((slotId, idx) => {
            const slot = getSlot(slotId)
            const artifactLabel = ARTIFACT_OPTIONS.find((a) => a.key === slot.artifact_id)?.label ?? ''
            return (
              <div key={slotId} className="bg-slate-800/40 border border-slate-700 rounded-lg px-4 py-3 flex items-center gap-3">
                <span className="text-sm font-bold text-slate-500 w-6 shrink-0">#{idx + 1}</span>

                {/* Artifact selector */}
                <select
                  value={String(slot.artifact_id)}
                  onChange={(e) => setSlotField(slotId, 'artifact_id', e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-orange-500 min-w-0"
                  title={artifactLabel}
                >
                  <option value="">— none —</option>
                  {ARTIFACT_OPTIONS.map((a) => (
                    <option key={a.key} value={a.key}>{a.label}</option>
                  ))}
                </select>

                {/* Stars */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-xs text-slate-500">Stars</span>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={Number(slot.stars)}
                    onChange={(e) => setSlotField(slotId, 'stars', Math.min(5, Math.max(0, Number(e.target.value))))}
                    className="w-12 bg-slate-900 border border-slate-700 text-yellow-400 font-bold rounded px-2 py-1 text-sm text-center focus:outline-none focus:border-orange-500"
                  />
                  <span className="text-yellow-500 text-xs">★</span>
                </div>

                {/* Level */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-xs text-slate-500">Lv</span>
                  <input
                    type="number"
                    min={1}
                    value={Number(slot.level)}
                    onChange={(e) => setSlotField(slotId, 'level', Math.max(1, Number(e.target.value)))}
                    className="w-16 bg-slate-900 border border-slate-700 text-orange-300 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Resonance */}
      <section>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Artifact Resonance</h3>
        <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-4 space-y-4">
          {[
            { key: 'resonance_main_stat_level', label: 'Main Stat Resonance Level', maxLevel: 20 },
            { key: 'resonance_hp_level', label: 'HP Resonance Level', maxLevel: 20 },
          ].map((r) => {
            const level = Number(resonance[r.key] ?? 0)
            return (
              <div key={r.key} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">{r.label}</span>
                  <span className="text-sm font-bold text-orange-400">Lv {level}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={r.maxLevel}
                  value={level}
                  onChange={(e) => setResonance(r.key, Number(e.target.value))}
                  className="w-full accent-orange-500"
                />
                <div className="flex justify-between text-xs text-slate-600">
                  <span>0</span>
                  <span>{r.maxLevel}</span>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {isSaving && <p className="text-xs text-slate-500">Saving...</p>}
    </div>
  )
}
