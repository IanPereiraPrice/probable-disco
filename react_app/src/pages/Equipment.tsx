import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { useUserData } from '@/hooks/useUserData'
import { getPotentialConfig } from '@/api/equipment'
import type { PotentialConfig } from '@/api/equipment'

// ─── Constants ────────────────────────────────────────────────────────────────

const EQUIPMENT_SLOTS = [
  'hat', 'top', 'bottom', 'gloves', 'shoes',
  'belt', 'shoulder', 'cape', 'ring', 'necklace', 'eye', 'face',
]

const SLOT_THIRD_STAT: Record<string, string> = {
  hat: 'Defense', top: 'Defense', bottom: 'Accuracy', gloves: 'Accuracy',
  shoes: 'Max MP', belt: 'Max MP', shoulder: 'Evasion', cape: 'Evasion',
  ring: 'Main Stat', necklace: 'Main Stat', eye: 'Main Stat', face: 'Main Stat',
}

const SPECIAL_STAT_OPTIONS: Record<string, string> = {
  damage_pct: 'Damage %',
  all_skills: '+All Skills',
  final_damage: 'Final Damage %',
  def_pen: 'Defense Pen %',
}

const TIER_COLORS: Record<string, string> = {
  rare: 'text-blue-400', epic: 'text-purple-400',
  unique: 'text-orange-400', legendary: 'text-yellow-300', mystic: 'text-red-400',
}
const TIER_BG: Record<string, string> = {
  rare: 'bg-blue-900/30 border-blue-700', epic: 'bg-purple-900/30 border-purple-700',
  unique: 'bg-orange-900/30 border-orange-700', legendary: 'bg-yellow-900/30 border-yellow-700',
  mystic: 'bg-red-900/30 border-red-700',
}

// Starforce amplify table: stars → {main, sub} multiplier (1 + amplify%)
// Each entry is the "after" value when that stage completes (i.e. the multiplier AT that star count)
const SF_MAIN = [1.0, 1.1, 1.2, 1.3, 1.4, 1.6, 1.75, 1.9, 2.05, 2.2, 2.5, 2.75, 3.0, 3.25, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0, 13.0, 16.0, 21.0]
const SF_SUB  = [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.1, 1.1, 1.1, 1.1, 1.25, 1.25, 1.25, 1.25, 1.25, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.3, 2.6, 3.0, 3.5]

function getAmplifyMultiplier(stars: number, isSub: boolean): number {
  const clamp = Math.max(0, Math.min(stars, 25))
  return (isSub ? SF_SUB : SF_MAIN)[clamp] ?? 1.0
}

// ─── Item / potential defaults ────────────────────────────────────────────────

function withDefaults(item: Record<string, unknown>): Record<string, unknown> {
  return {
    name: '', rarity: 'Normal', tier: 4, stars: 0, is_special: false,
    base_attack: 0, base_max_hp: 0, base_third_stat: 0,
    sub_boss_damage: 0, sub_normal_damage: 0, sub_crit_rate: 0,
    sub_crit_damage: 0, sub_attack_flat: 0,
    sub_skill_1st: 0, sub_skill_2nd: 0, sub_skill_3rd: 0, sub_skill_4th: 0,
    sub_min_dmg: 0, sub_max_dmg: 0,
    special_stat_type: 'damage_pct', special_stat_value: 0,
    ...item,
  }
}

function withPotDefaults(pots: Record<string, unknown>): Record<string, unknown> {
  return {
    tier: 'legendary', regular_pity: 0,
    line1_stat: '', line1_value: 0,
    line2_stat: '', line2_value: 0, line2_yellow: true,
    line3_stat: '', line3_value: 0, line3_yellow: true,
    bonus_tier: 'legendary', bonus_pity: 0,
    bonus_line1_stat: '', bonus_line1_value: 0,
    bonus_line2_stat: '', bonus_line2_value: 0, bonus_line2_yellow: true,
    bonus_line3_stat: '', bonus_line3_value: 0, bonus_line3_yellow: true,
    ...pots,
  }
}

function withScrollDefaults(scroll: Record<string, unknown>): Record<string, unknown> {
  return { damage_amp: 0, flat_attack: 0, flat_main_stat: 0, ...scroll }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function autoValue(cfg: PotentialConfig, slot: string, tier: string, stat: string, yellow: boolean) {
  return cfg.value_table[slot]?.[tier]?.[stat]?.[yellow ? 'yellow' : 'grey'] ?? 0
}

function fmt(v: number, decimals = 0) {
  return v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

// ─── Shared input components ──────────────────────────────────────────────────

function NumInput({
  label, value, onChange, step = 1, min = 0, suffix = '', afterSF,
}: {
  label: string; value: number; onChange: (v: number) => void;
  step?: number; min?: number; suffix?: string; afterSF?: number;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-slate-400 shrink-0">{label}</span>
      <div className="flex items-center gap-2">
        {afterSF !== undefined && (
          <span className="text-xs text-green-400 tabular-nums">{fmt(afterSF, step < 1 ? 1 : 0)}{suffix}</span>
        )}
        <div className="flex items-center gap-1">
          <input
            type="number"
            step={step}
            min={min}
            value={value || ''}
            placeholder="0"
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-24 bg-slate-900 border border-slate-700 text-slate-100 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
          />
          {suffix && <span className="text-xs text-slate-500">{suffix}</span>}
        </div>
      </div>
    </div>
  )
}

// ─── Potential line editor ─────────────────────────────────────────────────────

function PotLine({
  cfg, slot, tier, stat, value, isYellow, lineNum, prefix, onUpdate,
}: {
  cfg: PotentialConfig; slot: string; tier: string; stat: string; value: number;
  isYellow: boolean; lineNum: number; prefix: '' | 'bonus_';
  onUpdate: (k: string, v: unknown) => void;
}) {
  const isLine1 = lineNum === 1
  const statOptions = cfg.slot_stats[slot] ?? []

  function handleStatChange(s: string) {
    onUpdate(`${prefix}line${lineNum}_stat`, s)
    onUpdate(`${prefix}line${lineNum}_value`, s ? autoValue(cfg, slot, tier, s, isLine1 ? true : isYellow) : 0)
  }

  function handleYellowToggle() {
    const next = !isYellow
    onUpdate(`${prefix}line${lineNum}_yellow`, next)
    if (stat) onUpdate(`${prefix}line${lineNum}_value`, autoValue(cfg, slot, tier, stat, next))
  }

  return (
    <div className="flex items-center gap-1.5">
      {isLine1 ? (
        <span className="text-xs text-yellow-400 font-bold w-5 shrink-0 text-center">[Y]</span>
      ) : (
        <button onClick={handleYellowToggle}
          className={`text-xs font-bold w-5 shrink-0 text-center transition-colors ${isYellow ? 'text-yellow-400' : 'text-slate-600 hover:text-slate-400'}`}
        >
          [{isYellow ? 'Y' : 'G'}]
        </button>
      )}
      <select
        value={stat}
        onChange={(e) => handleStatChange(e.target.value)}
        className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded px-1.5 py-1 text-xs focus:outline-none focus:border-orange-500 min-w-0"
      >
        <option value="">— none —</option>
        {statOptions.map((s) => (
          <option key={s} value={s}>{cfg.stat_labels[s]?.display ?? s}</option>
        ))}
      </select>
      <input
        type="number"
        step="any"
        value={value || ''}
        placeholder="0"
        onChange={(e) => onUpdate(`${prefix}line${lineNum}_value`, Number(e.target.value))}
        className="w-16 bg-slate-900 border border-slate-700 text-orange-300 rounded px-1.5 py-1 text-xs text-right focus:outline-none focus:border-orange-500 shrink-0"
      />
    </div>
  )
}

// ─── Potential block (regular or bonus) ───────────────────────────────────────

function PotBlock({
  cfg, slot, pots, prefix, label, onUpdate,
}: {
  cfg: PotentialConfig; slot: string; pots: Record<string, unknown>;
  prefix: '' | 'bonus_'; label: string;
  onUpdate: (k: string, v: unknown) => void;
}) {
  const tierKey  = prefix === '' ? 'tier' : 'bonus_tier'
  const pityKey  = prefix === '' ? 'regular_pity' : 'bonus_pity'
  const tier     = String(pots[tierKey] ?? 'legendary')
  const pity     = Number(pots[pityKey] ?? 0)
  const pityMax  = prefix === ''
    ? (cfg.regular_pity_thresholds[tier] ?? 999999)
    : (cfg.bonus_pity_thresholds[tier] ?? 999999)
  const pityPct  = pityMax < 999999 ? Math.min(100, (pity / pityMax) * 100) : 0

  function handleTierChange(newTier: string) {
    onUpdate(tierKey, newTier)
    for (let i = 1; i <= 3; i++) {
      const s = String(pots[`${prefix}line${i}_stat`] ?? '')
      if (!s) continue
      const yellow = i === 1 ? true : Boolean(pots[`${prefix}line${i}_yellow`] ?? true)
      onUpdate(`${prefix}line${i}_value`, autoValue(cfg, slot, newTier, s, yellow))
    }
  }

  return (
    <div className={`rounded-lg border p-3 space-y-2 ${TIER_BG[tier] ?? 'bg-slate-800/40 border-slate-700'}`}>
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider w-10">{label}</span>
        <select
          value={tier}
          onChange={(e) => handleTierChange(e.target.value)}
          className={`bg-slate-900 border border-slate-700 rounded px-2 py-0.5 text-xs font-bold focus:outline-none focus:border-orange-500 ${TIER_COLORS[tier] ?? ''}`}
        >
          {cfg.tiers.map((t) => (
            <option key={t} value={t} className="text-slate-200">
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-xs text-slate-500">Pity</span>
          <input
            type="number"
            min={0}
            value={pity}
            onChange={(e) => onUpdate(pityKey, Number(e.target.value))}
            className="w-14 bg-slate-900 border border-slate-700 text-slate-300 rounded px-1.5 py-0.5 text-xs text-right focus:outline-none focus:border-orange-500"
          />
          {pityMax < 999999 && (
            <span className={`text-xs font-medium ${pityPct >= 80 ? 'text-green-400' : 'text-slate-500'}`}>
              {pityPct.toFixed(0)}%
            </span>
          )}
        </div>
      </div>
      {pityMax < 999999 && pityPct > 0 && (
        <div className="w-full bg-slate-800 rounded-full h-1 overflow-hidden">
          <div className="h-full bg-orange-500 rounded-full transition-all" style={{ width: `${pityPct}%` }} />
        </div>
      )}
      {[1, 2, 3].map((n) => (
        <PotLine
          key={n} cfg={cfg} slot={slot} tier={tier}
          stat={String(pots[`${prefix}line${n}_stat`] ?? '')}
          value={Number(pots[`${prefix}line${n}_value`] ?? 0)}
          isYellow={n === 1 ? true : Boolean(pots[`${prefix}line${n}_yellow`] ?? true)}
          lineNum={n} prefix={prefix} onUpdate={onUpdate}
        />
      ))}
    </div>
  )
}

// ─── Stats tab content ────────────────────────────────────────────────────────

function StatsTab({ slot }: { slot: string }) {
  const { userData, updateEquipmentItem } = useAppStore()
  const rawItem = (userData?.equipment_items?.[slot] ?? {}) as Record<string, unknown>
  const item = withDefaults(rawItem)
  const set = (k: string, v: unknown) => updateEquipmentItem(slot, { ...item, [k]: v })

  const stars = Number(item.stars ?? 0)
  const mainMult = getAmplifyMultiplier(stars, false)
  const subMult  = getAmplifyMultiplier(stars, true)
  const thirdLabel = SLOT_THIRD_STAT[slot] ?? '3rd Stat'
  const isSpecial = Boolean(item.is_special)

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Item Name</label>
          <input
            type="text"
            value={String(item.name ?? '')}
            onChange={(e) => set('name', e.target.value)}
            placeholder={slot.charAt(0).toUpperCase() + slot.slice(1)}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-500 w-40"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Stars</label>
          <input
            type="number" min={0} max={25}
            value={stars}
            onChange={(e) => set('stars', Number(e.target.value))}
            className="w-20 bg-slate-800 border border-slate-700 text-orange-400 font-bold rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:border-orange-500"
          />
        </div>
        <div className="ml-auto text-right">
          <p className="text-xs text-slate-500">Main ×{mainMult.toFixed(2)}</p>
          <p className="text-xs text-slate-500">Sub ×{subMult.toFixed(2)}</p>
        </div>
      </div>

      {/* Main Stats */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Main Stats</h3>
          <span className="text-xs text-slate-600">base → after SF</span>
        </div>
        <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3 space-y-2">
          <NumInput label="Attack"       value={Number(item.base_attack ?? 0)}     onChange={(v) => set('base_attack', v)}     afterSF={Number(item.base_attack ?? 0) * mainMult} />
          <NumInput label="Max HP"       value={Number(item.base_max_hp ?? 0)}     onChange={(v) => set('base_max_hp', v)}     afterSF={Number(item.base_max_hp ?? 0) * mainMult} />
          <NumInput label={thirdLabel}   value={Number(item.base_third_stat ?? 0)} onChange={(v) => set('base_third_stat', v)} afterSF={Number(item.base_third_stat ?? 0) * mainMult} />
        </div>
      </section>

      {/* Sub Stats */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sub Stats</h3>
          <span className="text-xs text-slate-600">base → after SF</span>
        </div>
        <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3 grid grid-cols-2 gap-x-6 gap-y-2">
          <NumInput label="Boss Damage"   value={Number(item.sub_boss_damage ?? 0)}   onChange={(v) => set('sub_boss_damage', v)}   step={0.1} suffix="%" afterSF={Number(item.sub_boss_damage ?? 0) * subMult} />
          <NumInput label="Normal Dmg"    value={Number(item.sub_normal_damage ?? 0)} onChange={(v) => set('sub_normal_damage', v)} step={0.1} suffix="%" afterSF={Number(item.sub_normal_damage ?? 0) * subMult} />
          <NumInput label="Crit Rate"     value={Number(item.sub_crit_rate ?? 0)}     onChange={(v) => set('sub_crit_rate', v)}     step={0.1} suffix="%" afterSF={Number(item.sub_crit_rate ?? 0) * subMult} />
          <NumInput label="Crit Damage"   value={Number(item.sub_crit_damage ?? 0)}   onChange={(v) => set('sub_crit_damage', v)}   step={0.1} suffix="%" afterSF={Number(item.sub_crit_damage ?? 0) * subMult} />
          <NumInput label="Attack (flat)" value={Number(item.sub_attack_flat ?? 0)}   onChange={(v) => set('sub_attack_flat', v)}              afterSF={Number(item.sub_attack_flat ?? 0) * subMult} />
          <NumInput label="Min DMG"       value={Number(item.sub_min_dmg ?? 0)}       onChange={(v) => set('sub_min_dmg', v)}       step={0.1} suffix="%" afterSF={Number(item.sub_min_dmg ?? 0) * subMult} />
          <NumInput label="Max DMG"       value={Number(item.sub_max_dmg ?? 0)}       onChange={(v) => set('sub_max_dmg', v)}       step={0.1} suffix="%" afterSF={Number(item.sub_max_dmg ?? 0) * subMult} />
          <div />
          <NumInput label="+1st Job" value={Number(item.sub_skill_1st ?? 0)} onChange={(v) => set('sub_skill_1st', v)} afterSF={Number(item.sub_skill_1st ?? 0) * subMult} />
          <NumInput label="+2nd Job" value={Number(item.sub_skill_2nd ?? 0)} onChange={(v) => set('sub_skill_2nd', v)} afterSF={Number(item.sub_skill_2nd ?? 0) * subMult} />
          <NumInput label="+3rd Job" value={Number(item.sub_skill_3rd ?? 0)} onChange={(v) => set('sub_skill_3rd', v)} afterSF={Number(item.sub_skill_3rd ?? 0) * subMult} />
          <NumInput label="+4th Job" value={Number(item.sub_skill_4th ?? 0)} onChange={(v) => set('sub_skill_4th', v)} afterSF={Number(item.sub_skill_4th ?? 0) * subMult} />
        </div>
      </section>

      {/* Special Stat */}
      <section>
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Special Stat</h3>
          <label className="flex items-center gap-1.5 ml-auto cursor-pointer">
            <input type="checkbox" checked={isSpecial} onChange={(e) => set('is_special', e.target.checked)} className="accent-orange-500" />
            <span className="text-xs text-slate-400">Is special item</span>
          </label>
        </div>
        {isSpecial ? (
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3 flex items-center gap-3">
            <select
              value={String(item.special_stat_type ?? 'damage_pct')}
              onChange={(e) => set('special_stat_type', e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-orange-500"
            >
              {Object.entries(SPECIAL_STAT_OPTIONS).map(([k, lbl]) => (
                <option key={k} value={k}>{lbl}</option>
              ))}
            </select>
            <input
              type="number" step="any"
              value={Number(item.special_stat_value ?? 0) || ''}
              placeholder="0"
              onChange={(e) => set('special_stat_value', Number(e.target.value))}
              className="w-24 bg-slate-900 border border-slate-700 text-orange-300 rounded px-2 py-1.5 text-sm text-right focus:outline-none focus:border-orange-500"
            />
            <span className="text-xs text-green-400 shrink-0">
              → {fmt(Number(item.special_stat_value ?? 0) * subMult, 1)}
            </span>
          </div>
        ) : (
          <p className="text-xs text-slate-600 italic">Enable for items with special stats (damage %, all skills, etc.)</p>
        )}
      </section>
    </div>
  )
}

// ─── Potentials tab content ───────────────────────────────────────────────────

function PotentialsTab({ slot, cfg }: { slot: string; cfg: PotentialConfig }) {
  const { userData, updateEquipmentPotential } = useAppStore()
  const rawPots = (userData?.equipment_potentials?.[slot] ?? {}) as Record<string, unknown>
  const pots = withPotDefaults(rawPots)
  const set = (k: string, v: unknown) => updateEquipmentPotential(slot, { ...pots, [k]: v })

  const specialStat = cfg.special_per_slot[slot]

  return (
    <div className="space-y-3">
      {specialStat && (
        <div className="text-xs bg-purple-900/30 text-purple-300 border border-purple-700 rounded-lg px-3 py-2">
          This slot has a special potential line: <span className="font-semibold">{cfg.stat_labels[specialStat]?.display ?? specialStat}</span>
        </div>
      )}
      <PotBlock cfg={cfg} slot={slot} pots={pots} prefix=""       label="Reg"   onUpdate={set} />
      <PotBlock cfg={cfg} slot={slot} pots={pots} prefix="bonus_" label="Bonus" onUpdate={set} />
    </div>
  )
}

// ─── Scrolls tab content ──────────────────────────────────────────────────────

function ScrollsTab() {
  const { userData, updateEquipmentScroll } = useAppStore()

  const scrolls = userData?.equipment_scrolls ?? {}
  const getScroll = (slot: string) => withScrollDefaults((scrolls[slot] ?? {}) as Record<string, unknown>)
  const set = (slot: string, k: string, v: unknown) => {
    const cur = getScroll(slot)
    updateEquipmentScroll(slot, { ...cur, [k]: v })
  }

  // Totals
  let totalDmgAmp = 0, totalFlatAtk = 0, totalFlatStat = 0
  for (const slot of EQUIPMENT_SLOTS) {
    const s = getScroll(slot)
    totalDmgAmp  += Number(s.damage_amp ?? 0)
    totalFlatAtk += Number(s.flat_attack ?? 0)
    totalFlatStat += Number(s.flat_main_stat ?? 0)
  }

  return (
    <div className="space-y-4">
      {/* Totals */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Damage Amp', value: `+${fmt(totalDmgAmp, 1)}%` },
          { label: 'Flat Attack', value: `+${fmt(totalFlatAtk)}` },
          { label: 'Flat Main Stat', value: `+${fmt(totalFlatStat)}` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-800/40 border border-slate-700 rounded-lg p-3 text-center">
            <p className="text-xl font-bold text-green-400">{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Per-slot rows */}
      <div className="space-y-1">
        {EQUIPMENT_SLOTS.map((slot) => {
          const s = getScroll(slot)
          return (
            <div key={slot} className="bg-slate-800/30 border border-slate-700/60 rounded-lg px-3 py-2.5 flex items-center gap-4">
              <span className="text-sm font-medium text-slate-300 capitalize w-20 shrink-0">{slot}</span>
              <div className="flex-1 grid grid-cols-3 gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-500 shrink-0">Dmg Amp</span>
                  <input
                    type="number" step={0.5} min={0}
                    value={Number(s.damage_amp ?? 0) || ''}
                    placeholder="0"
                    onChange={(e) => set(slot, 'damage_amp', Number(e.target.value))}
                    className="w-20 bg-slate-900 border border-slate-700 text-slate-100 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                  />
                  <span className="text-xs text-slate-600">%</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-500 shrink-0">Flat Atk</span>
                  <input
                    type="number" step={100} min={0}
                    value={Number(s.flat_attack ?? 0) || ''}
                    placeholder="0"
                    onChange={(e) => set(slot, 'flat_attack', Number(e.target.value))}
                    className="w-24 bg-slate-900 border border-slate-700 text-slate-100 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                  />
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-500 shrink-0">Main Stat</span>
                  <input
                    type="number" step={100} min={0}
                    value={Number(s.flat_main_stat ?? 0) || ''}
                    placeholder="0"
                    onChange={(e) => set(slot, 'flat_main_stat', Number(e.target.value))}
                    className="w-24 bg-slate-900 border border-slate-700 text-slate-100 rounded px-2 py-1 text-sm text-right focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Tab = 'stats' | 'potentials' | 'scrolls'

const TABS: { key: Tab; label: string }[] = [
  { key: 'stats',      label: 'Stats'      },
  { key: 'potentials', label: 'Potentials' },
  { key: 'scrolls',    label: 'Scrolls'    },
]

export function Equipment() {
  const { userData } = useAppStore()
  const { isLoading, save, isSaving } = useUserData()
  const [selectedSlot, setSelectedSlot] = useState(EQUIPMENT_SLOTS[0])
  const [activeTab, setActiveTab] = useState<Tab>('stats')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const cfgQuery = useQuery({
    queryKey: ['potentialConfig'],
    queryFn: getPotentialConfig,
    staleTime: Infinity,
  })

  const debouncedSave = useCallback(() => {
    if (!userData) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => save(userData), 800)
  }, [userData, save])

  useEffect(() => {
    if (userData) debouncedSave()
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [userData?.equipment_items, userData?.equipment_potentials, userData?.equipment_scrolls])

  if (isLoading || !userData) return <p className="text-slate-400">Loading...</p>
  if (cfgQuery.isLoading) return <p className="text-slate-400">Loading config...</p>
  if (!cfgQuery.data) return null

  const cfg = cfgQuery.data
  const slotListVisible = activeTab !== 'scrolls'

  return (
    <div className="flex gap-4 h-full">
      {/* ── Slot list (hidden on Scrolls tab) ── */}
      {slotListVisible && (
        <aside className="w-36 shrink-0">
          <div className="bg-slate-800/40 border border-slate-700 rounded-xl overflow-hidden">
            {EQUIPMENT_SLOTS.map((slot) => {
              const item = withDefaults((userData.equipment_items?.[slot] ?? {}) as Record<string, unknown>)
              const stars = Number(item.stars ?? 0)
              const pots = withPotDefaults((userData.equipment_potentials?.[slot] ?? {}) as Record<string, unknown>)
              const tier = String(pots.tier ?? 'legendary')
              const isActive = slot === selectedSlot
              return (
                <button
                  key={slot}
                  onClick={() => setSelectedSlot(slot)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 text-sm border-b border-slate-700/60 last:border-0 transition-colors ${
                    isActive
                      ? 'bg-orange-500/15 text-orange-300'
                      : 'text-slate-400 hover:bg-slate-700/40 hover:text-slate-200'
                  }`}
                >
                  <span className="capitalize font-medium">{slot}</span>
                  <div className="flex flex-col items-end gap-0.5">
                    {stars > 0 && <span className="text-xs text-yellow-400">★{stars}</span>}
                    <span className={`text-xs font-bold ${TIER_COLORS[tier] ?? 'text-slate-600'}`}>
                      {tier[0].toUpperCase()}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
          {isSaving && <p className="text-xs text-slate-500 text-center mt-2">Saving...</p>}
        </aside>
      )}

      {/* ── Detail panel ── */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="bg-slate-800/20 border border-slate-700 rounded-xl p-5">
          {/* Tab bar + slot name */}
          <div className="flex items-center gap-3 mb-5">
            {slotListVisible && (
              <h2 className="text-lg font-semibold text-slate-100 capitalize mr-2">{selectedSlot}</h2>
            )}
            <div className="flex bg-slate-800/60 border border-slate-700 rounded-lg p-0.5 gap-0.5">
              {TABS.map(({ key, label }) => (
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
            {!slotListVisible && isSaving && (
              <span className="text-xs text-slate-500 ml-auto">Saving...</span>
            )}
          </div>

          {/* Tab content */}
          {activeTab === 'stats'      && <StatsTab slot={selectedSlot} />}
          {activeTab === 'potentials' && <PotentialsTab slot={selectedSlot} cfg={cfg} />}
          {activeTab === 'scrolls'    && <ScrollsTab />}
        </div>
      </div>
    </div>
  )
}
