# MapleStory M Stat Mapping

**Character:** Bowmaster - Quarts | **Updated:** December 29, 2025

---

## Current Character Stats

| Stat | Value | Notes |
|------|-------|-------|
| CP | 42T 170B | |
| Attack | 48M 797K | |
| DEX | 70,456 | Primary stat |
| STR | 672 | Secondary |
| Critical Rate | 128.9% | |
| Critical Damage | 213.8% | |
| Damage % | 1,147.7% | With Hex stacks |
| Damage Amplification | 34.1% | Scrolls only |
| Final Damage | 66.1% | Multiplicative |
| Defense Penetration | 45.8% | Multiplicative |
| Boss Monster Damage | 82.7% | |
| Normal Monster Damage | 143.4% | |
| Min Damage Multiplier | 264.3% | |
| Max Damage Multiplier | 285.1% | |
| Skill Damage | 61% | |

---

## DEX Formula (VERIFIED)

```
Total_DEX = Flat_DEX_Pool × (1 + %DEX)
```

**Confirmed %DEX Multiplier: 2.6 (160% DEX)** | Test: +10 flat → +26 total

---

## Flat DEX Sources (CONFIRMED)

| Source | Flat DEX | Status |
|--------|----------|--------|
| Medal Inventory Effect | +780 | 780/1,500 |
| Costume Inventory Effect | +1,500 | MAX |
| Hero Power Stats (60/60) | +1,650 | MAX |
| Artifact Resonance (Lv.296) | +1,826 | ★72 total |
| Maple Rank Regular (1-21) | +6,770 | Stage 21 @ 5/10 |
| Maple Rank Special (20/160) | +400 | 20 pts × 20/pt |
| Mastery Enhancement | +30 | Confirmed |
| **SUBTOTAL CONFIRMED** | **+12,956** | |
| Companion 2nd Job Inventory | TBD | NEEDS CAPTURE |
| Equipment On-Equip Effects | TBD | NEEDS CAPTURE |
| Soul Arrow: Bow Skill | ~150 | Estimated |

**Target Flat Pool: 70,456 ÷ 2.6 = ~27,098 flat DEX needed**

---

## Maple Rank Main Stat Scaling (VERIFIED)

| Stages | Increment | Per Point | Stage Total (×10) |
|--------|-----------|-----------|-------------------|
| 1-7 | +2/stage | 1,3,5,7,9,11,13 | 490 |
| 8-10 | +4/stage | 17,21,25 | 630 |
| 11-21 | +5/stage | 30,35...75,80 | 5,650 (to 21) |

**Regular Main Stat total (1-20 maxed + 21@5): 6,370 + 400 = 6,770 DEX**

---

## Damage % Sources

| Source | Value | Status |
|--------|-------|--------|
| Hero Power Stats (60/60) | +45% | MAX |
| Guild Skills (10+10+20) | +40% | Confirmed |
| Maple Rank (50/50) | +35% | MAX |
| Hero Ability Line 4 | +21.5% | Legendary |
| Marksmanship (Lv.99+96) | +31.7% | 1 target only |
| **SUBTOTAL CONFIRMED** | **+173.2%** | |
| Companion 3rd/4th Job Inv. | TBD | NEEDS CAPTURE |
| Equipment Potentials | TBD | NEEDS CAPTURE |
| Hexagon Necklace Buff | ×1.72 | 3 stacks (★3) |

---

## Final Damage Sources (Multiplicative)

```
FD% = [(1+FD₁) × (1+FD₂) × ...] - 1
```

| Source | Value | Mult | Condition |
|--------|-------|------|-----------|
| Guild Skill | +6% | ×1.06 | Always |
| Extreme Archery: Bow | +21.7% | ×1.217 | Always |
| Mortal Blow (Lv.99+51) | +14.5% | ×1.145 | After 50 hits |
| Fire Flower Artifact (★1) | +12% | ×1.12 | Max 10 targets |
| Bottom Potential/Bonus | +13% | ×1.13 | Always |

---

## Defense Penetration (Multiplicative)

| Source | Value | Status |
|--------|-------|--------|
| Hero Ability Line 1 | +19% | Mystic |
| Hero Ability Line 3 | +16.5% | Mystic |
| Guild Skill | +10% | Confirmed |
| Silver Pendant Artifact | +5% | Inventory |
| Extreme Archery: Bow | -10% | Penalty |

---

## Boss Monster Damage Sources

| Source | Value | Status |
|--------|-------|--------|
| Maple Rank (30/30) | +20% | MAX |
| Hero Ability Line 2 | +19.4% | Legendary |
| **SUBTOTAL CONFIRMED** | **+39.4%** | |

---

## Normal Monster Damage Sources

| Source | Value | Status |
|--------|-------|--------|
| Maple Rank (30/30) | +20% | MAX |
| Fire Flower Inventory | +18% | ★1 |
| **SUBTOTAL CONFIRMED** | **+38%** | |

---

## Skill Damage Sources

| Source | Value | Status |
|--------|-------|--------|
| Maple Rank (30/30) | +25% | MAX |
| Mastery Enhancement | +15% | Estimated |

---

## Critical Rate Sources

| Source | Value | Status |
|--------|-------|--------|
| Maple Rank (10/10) | +10% | MAX |
| Book of Ancient Active | +12% | ★1 |
| Squashy Ring On-Equip | +10.7% | Confirmed |

---

## Critical Damage Sources

| Source | Value | Status |
|--------|-------|--------|
| Maple Rank (30/30) | +20% | MAX |
| Book of Ancient Conversion | +46.4% | 128.9% CR × 36% |
| Concentration Skill | +30.1% | Max 7 stacks |

---

## Min/Max Damage Multiplier

| Source | Min | Max | Status |
|--------|-----|-----|--------|
| Maple Rank (20/20) | +11% | +11% | MAX |
| Hero Ability Line 5 | - | +23.6% | Legendary |
| Bow Mastery (Lv.90+26) | +20.2% | - | |
| Mastery Enhancement | - | +10% | |

---

## Hero Power - Passive Stats (Stage 6)

| Stat | Value | Level | Status |
|------|-------|-------|--------|
| Main Stat (DEX) | +1,650 | 60/60 | MAX |
| Damage % | +45% | 60/60 | MAX |
| Attack | +6,225 | 60/60 | MAX |
| Max HP | +124,500 | 60/60 | MAX |
| Accuracy | +45 | 20/20 | MAX |
| Defense | +5,625 | 48/60 | In Progress |

---

## Hero Power - Ability Preset 5

| # | Ability | Value | Tier | Rating |
|---|---------|-------|------|--------|
| 1 | Defense Penetration | 19% | Mystic | ★★★★★ |
| 2 | Boss Monster Damage | 19.4% | Legendary | ★★★★☆ |
| 3 | Defense Penetration | 16.5% | Mystic | ★★★★★ |
| 4 | Damage | 21.5% | Legendary | ★★★★☆ |
| 5 | Max Damage Multiplier | 23.6% | Legendary | ★★★★☆ |

---

## Guild Skills (CONFIRMED)

| Skill | Value | Category |
|-------|-------|----------|
| Damage % (×3 skills) | +10%,+10%,+20% | = +40% total |
| Defense Penetration | +10% | Multiplicative |
| Final Damage | +6% | ×1.06 |
| Defense | +20% | |

---

## Maple Rank Stage 21 - Complete Stats

| Stat | Level | Value | Status |
|------|-------|-------|--------|
| Main Stat (Regular) | 5/10 | +400 | 80/pt, 6770 cumulative |
| Attack Speed | 20/20 | +7% | MAX |
| Critical Rate | 10/10 | +10% | MAX |
| Min Damage Mult | 20/20 | +11% | MAX |
| Max Damage Mult | 20/20 | +11% | MAX |
| Accuracy | 20/20 | +23 | MAX |
| Critical Damage | 30/30 | +20% | MAX |
| Normal Monster Damage | 30/30 | +20% | MAX |
| Boss Monster Damage | 30/30 | +20% | MAX |
| Skill Damage | 30/30 | +25% | MAX |
| Damage % | 50/50 | +35% | MAX |
| Main Stat (Special) | 20/160 | +400 | 20/pt, In Progress |

---

## Artifacts

| Artifact | ★ | Active Effect | Inventory Effect |
|----------|---|---------------|------------------|
| Hexagon Necklace | ★3 | +24% Dmg ×3 stacks | ATK +600 |
| Book of Ancient | ★1 | +12% CR, +36% CR as CD | CR 6%, CD cond. |
| Fire Flower | ★1 | +1.2% FD/target (max 12%) | NM +18% |

**Resonance:** ★72 | Lv.296/440 | +1,826 DEX | +18,263 HP

---

## Data Collection TODO

1. Companion Inventory Effects (2nd/3rd/4th job)
2. Equipment Potentials (all 12 slots)
3. Equipment On-Equip Effects
4. Artifact Potentials
5. Weapon stats & Scroll breakdown

---

## Version History

- **v3.0 (Dec 29):** Added full Maple Rank special stats (+35% Dmg, +20% Boss/NM, +25% Skill Dmg, special main stat)
- **v2.0 (Dec 29):** Confirmed sources, %DEX=160%, Maple Rank scaling formula
