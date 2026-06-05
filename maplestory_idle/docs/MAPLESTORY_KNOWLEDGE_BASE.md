# MapleStory Idle - Complete Knowledge Base

**Last Updated:** December 2025  
**Character:** Bowmaster Lv.96 - Quarts

This document contains all verified game mechanics, formulas, and systems discovered through empirical testing.

---

## Table of Contents

1. [Master Damage Formula](#master-damage-formula)
2. [Stat Stacking Behavior](#stat-stacking-behavior)
3. [DEX Formula](#dex-formula)
4. [Damage Percentage System](#damage-percentage-system)
5. [Final Damage System](#final-damage-system)
6. [Defense Penetration](#defense-penetration)
7. [Enemy Defense Formula](#enemy-defense-formula)
8. [Critical Damage](#critical-damage)
9. [Bowmaster Skills](#bowmaster-skills)
10. [Equipment System](#equipment-system)
11. [Starforce Enhancement](#starforce-enhancement)
12. [Potential System](#potential-system)
13. [Artifact System](#artifact-system)
14. [Hero Power System](#hero-power-system)
15. [Companion System](#companion-system)
16. [Shop Prices](#shop-prices)
17. [Optimization Priorities](#optimization-priorities)

---

## Master Damage Formula

**VERIFIED FORMULA:**
```
Actual Damage = Base ATK × (1 + Stat%) × (1 + Damage%) × (1 + Damage Amp%) × 
                (1 + Final Damage%) × (1 + Crit Damage%) × Defense Multiplier
```

### Component Breakdown

| Component | Formula | Stacking Type |
|-----------|---------|---------------|
| Stat Proportional | (DEX × 1%) + (STR × 0.25%) | Additive |
| Damage % | Sum of sources × Hex multiplier | Additive + Multiplicative |
| Damage Amp | 1 + (Input / 396.5) | Additive (separate) |
| Final Damage | (1+FD₁) × (1+FD₂) × ... | Multiplicative |
| Crit Damage | Sum of all sources | Additive |
| Defense | 1 / (1 + EnemyDef × (1 - DefPen)) | Multiplicative |

---

## Stat Stacking Behavior

| Stat | Stacking | Notes |
|------|----------|-------|
| DEX (%) | ADDITIVE | All %DEX sources sum together |
| DEX (Flat) | ADDITIVE | Then multiplied by (1 + %DEX) |
| Damage % | ADDITIVE | Hex Necklace MULTIPLIES the total |
| Damage Amp | ADDITIVE | Separate multiplier, scrolls ONLY |
| Final Damage | MULTIPLICATIVE | Each source multiplies separately |
| Defense Pen | MULTIPLICATIVE | Each source multiplies |
| Critical Rate | ADDITIVE | All sources sum |
| Critical Damage | ADDITIVE | All sources sum |
| Min/Max Dmg Mult | ADDITIVE | All sources sum |
| Boss/Normal Dmg | ADDITIVE | Within category |

---

## DEX Formula

**Formula:**
```
Total_DEX = Flat_DEX_Pool × (1 + %DEX)
```

**Current Values:**
- Total %DEX: 126.5%
- Multiplier: 2.265
- Flat DEX Pool: ~18,700

**Test Evidence:**
- Companion +19 flat → +43 DEX (multiplier 2.26x) ✓
- Hero Ability -560 flat → -1,178 DEX (multiplier 2.10x) ✓
- Artifact -7% → -1,305 DEX (pool calc: 18,643) ✓

**Equivalence:**
- At 126.5% bonus, each 1% DEX = ~187 flat DEX

---

## Damage Percentage System

### Additive Sources (sum together)
- Equipment Potentials
- Hero Ability
- Companion Inventory Effects
- Maple Rank
- Guild Skills
- Skills (like Marksmanship)

### Multiplicative Source
- **Hexagon Necklace Buff:** ×1.24 per stack (max 3 = ×1.72)

**Test Data:**

| Hex Stacks | Damage % | Change |
|------------|----------|--------|
| 0 | 484.1% | - |
| 1 | 597.8% | +113.7% |
| 2 | 711.6% | +113.8% |
| 3 | 825.4% | +113.8% |

---

## Final Damage System

**Formula:**
```
Final Damage % = [(1 + FD₁) × (1 + FD₂) × (1 + FD₃) × ...] - 1
```

### Known Sources (Bowmaster)

| Source | FD % | Multiplier | Condition |
|--------|------|------------|-----------|
| Bottom (pot + bonus) | 13% | ×1.13 | Always |
| Guild Skill | 10% | ×1.10 | Always |
| Extreme Archery: Bow | 21.7% | ×1.217 | Always |
| Mortal Blow | 14.4% | ×1.144 | After 50 hits, 5s |
| Fire Flower | 12% | ×1.12 | Max 10 targets |

**Test Evidence:**

| State | Final Damage | Calculation |
|-------|--------------|-------------|
| Base (no Mortal/Flower) | 51.8% | - |
| + Mortal Blow | 73.6% | 1.518 × 1.144 = 1.737 ✓ |
| + Fire Flower | 94.5% | 1.736 × 1.12 = 1.944 ✓ |

---

## Defense Penetration

**Type:** MULTIPLICATIVE

**Formula:**
```
Remaining = (1 - IED₁) × (1 - IED₂) × (1 - IED₃) × ...
Total Def Pen = 1 - Remaining
```

**Test Evidence:**
```
Base: 42.4%
+ Hero Ability 19%: (1-0.424) × (1-0.19) = remaining 46.7%
+ Hero Ability 16.5%: × (1-0.165) = remaining 38.9%
Total Def Pen = 1 - 0.389 = 61.1% (Actual: 60.9%) ✓
```

---

## Enemy Defense Formula

**Formula:**
```
Damage = BaseDamage / (1 + EnemyDefValue × (1 - YourDefPen))
```

### Known Enemy Defense Values

| Location | Defense Value |
|----------|---------------|
| Maple Island 1-1 | 0.0 |
| Aquarium 14 | 0.388 |
| Mu Lung 27-1 | 0.752 |
| World Boss (King Castle Golem) | 6.527 |

---

## Critical Damage

### Book of Ancient Special Effect
```
"Critical Damage by 36% of Critical Rate"
Your CR: 111.9% → Bonus CD: 111.9 × 0.36 = 40.3%
```

---

## Bowmaster Skills

### Key Passive Skills

| Skill | Level | Effect | Category |
|-------|-------|--------|----------|
| Marksmanship | 93+56 | +28.9% ATK (1 target) | Damage % |
| Mortal Blow | 93+56 | +14.4% FD (5s after 50 hits) | Final Damage |
| Extreme Archery: Bow | 93+56 | +21.7% FD, -10% Def | Final Damage |
| Concentration | 93+56 | +4.3% CD/stack (max 7 = 30.1%) | Crit Damage |
| Soul Arrow: Bow | 90+38 | +75-226 DEX | Flat DEX |
| Bow Mastery | 90+38 | +20.7% Min Dmg Mult | Min Damage |
| Critical Shot | 60+38 | +6.4% Crit Rate | Crit Rate |

### Mastery Enhancements
- Max Damage Multiplier +10%
- Main Stat +30 flat
- Critical Rate +5%
- Critical Shot +5%p
- Skill Damage +15%
- Basic Attack Damage +15%
- Final Attack Damage +50%

---

## Equipment System

### On-Equip Stats by Slot

| Slot | Third Main Stat | Special Sub Stats |
|------|-----------------|-------------------|
| Weapon | Main Stat | Boss Monster Damage |
| Hat | Defense | Boss/Normal Dmg, CR, CD |
| Top | Defense | Boss/Normal Dmg, CR, CD |
| Bottom | Accuracy | Boss/Normal Dmg, CR, CD |
| Gloves | Accuracy | Boss/Normal Dmg, CR, CD |
| Shoes | Max MP | Boss/Normal Dmg, CR, CD |
| Belt | Max MP | Boss/Normal Dmg, CR, CD |
| Shoulder | Evasion | Boss/Normal Dmg, CR, CD |
| Cape | Evasion | Boss/Normal Dmg, CR, CD |
| Ring | Main Stat | **Damage %**, CR, CD, Normal Dmg |
| Necklace | Main Stat | **Damage %**, CR, CD, Skill Lv |
| Face | Main Stat | **Damage %**, Boss Monster Dmg |

### Rarity Multipliers (vs Epic baseline)
- Epic: 1.0×
- Unique: 2.0×
- Legendary: 3.4×
- Mystic: ~5.0×
- Ancient: ~7.0×

### Tier Multipliers (vs T4 baseline)
- T4: 1.0×
- T3: 1.15×
- T2: 1.32×
- T1: 1.52×

---

## Starforce Enhancement

### Complete Table (Stages 0-19)

| Stage | Success | Maintain | Decrease | Destroy | Main Amp | Sub Amp | Stones | Meso |
|-------|---------|----------|----------|---------|----------|---------|--------|------|
| 0→1 | 100% | 0% | 0% | 0% | 0%→10% | - | 1 | 30K |
| 1→2 | 100% | 0% | 0% | 0% | 10%→20% | - | 1 | 30K |
| 2→3 | 90% | 10% | 0% | 0% | 20%→30% | - | 2 | 40K |
| 3→4 | 85% | 15% | 0% | 0% | 30%→40% | - | 3 | 50K |
| 4→5 | 80% | 20% | 0% | 0% | 40%→60% | 0%→10% | 4 | 60K |
| 5→6 | 70% | 30% | 0% | 0% | 60%→75% | 10% | 5 | 70K |
| 6→7 | 65% | 35% | 0% | 0% | 75%→90% | 10% | 6 | 90K |
| 7→8 | 60% | 40% | 0% | 0% | 90%→105% | 10% | 7 | 110K |
| 8→9 | 55% | 45% | 0% | 0% | 105%→120% | 10% | 8 | 130K |
| 9→10 | 50% | 50% | 0% | 0% | 120%→150% | 10%→25% | 9 | 150K |
| 10→11 | 35% | 65% | 0% | 0% | 150%→175% | 25% | 10 | 170K |
| 11→12 | 34% | 66% | 0% | 0% | 175%→200% | 25% | 11 | 190K |
| 12→13 | 33% | 67% | 0% | 0% | 200%→225% | 25% | 12 | 210K |
| 13→14 | 32% | 56% | 12% | 0% | 225%→250% | 25% | 13 | 230K |
| 14→15 | 31% | 57% | 12% | 0% | 250%→300% | 25%→50% | 14 | 250K |
| 15→16 | 30% | 67% | 0% | 3% | 300%→350% | 50%→60% | 15 | 270K |
| 16→17 | 28% | 55% | 10% | 7% | 350%→400% | 60%→70% | 16 | 300K |
| 17→18 | 26% | 52% | 12% | 10% | 400%→450% | 70%→80% | 17 | 330K |
| 18→19 | 22.5% | 55% | 15% | 7.5% | 450%→500% | 80%→90% | 18 | 360K |
| 19→20 | 22% | 48% | 15% | 15% | 500%→550% | 90%→100% | 19 | 400K |

### Stat Calculation Formula
```
Final Stat = Base Stat × (1 + Amplify%)
Base Stat = Final Stat ÷ (1 + Amplify%)
```

### Key Milestones
- ★0-9: Safe zone (no decrease/destruction)
- ★10-12: Moderate risk (maintain but no decrease)
- ★13-14: Decrease zone (12% decrease chance)
- ★15+: Destruction zone (3%+ destruction)

---

## Potential System

### Slot Probability Distribution

| Slot | Yellow (Current Tier) | Grey (Previous Tier) |
|------|----------------------|----------------------|
| 1 | 100% | 0% |
| 2 | 24% | 76% |
| 3 | 8% | 92% |

### Tier Upgrade Rates
- Normal → Rare: 6%
- Rare → Epic: 1.67%
- Epic → Unique: 0.6%
- Unique → Legendary: 0.21%
- Legendary → Mystic: 0.083%

### Special Potential Rate
- 1% chance per slot for special line

### Special Potentials by Slot
- Ring/Necklace: +All Skills Lv.1
- Gloves: +10.9% Crit Damage
- Shoulder: +5% Defense Penetration
- Bottom: +8% Final Damage (Slot 1 seen)

---

## Artifact System

### Current Artifacts

| Artifact | Awakening | Active Effect | Inventory | Potentials |
|----------|-----------|---------------|-----------|------------|
| Hexagon Necklace | ★3 | +24% Dmg buff ×3 | ATK 600 | Boss 9%, Main 7% |
| Book of Ancient | ★1 | +12% CR, +36% of CR as CD | CR 6% | Main 10%, MaxDmg 4.5%, Boss 6% |
| Fire Flower | ★1 | +1.2% FD/target (max 12%) | Normal 18% | Min Dmg 13% |

### Awakening System
- Each awakening star improves active and inventory effects
- Legendary artifacts have highest awakening potential
- Epic artifacts cap lower but still useful

---

## Hero Power System

### Reroll Costs (Medals)

| Locked Lines | Cost |
|--------------|------|
| 0 | 86 |
| 1 | 129 |
| 2 | 172 |
| 3 | 215 |
| 4 | 258 |

### Tier Probabilities (per line)
- Mystic: 0.12%
- Legendary: 1.54%

### Mystic Tier Valuable Stats
- Damage: 28%-40%
- Boss Monster Damage: 28%-40%
- Defense Penetration: 14%-20%
- Max Damage Multiplier: 28%-40%

### Current Preset 5 (Excellent)
1. Defense Penetration: 19% (Mystic)
2. Boss Monster Damage: 19.4% (Legendary)
3. Defense Penetration: 16.5% (Mystic)
4. Damage: 21.5% (Legendary)
5. Max Damage Multiplier: 23.6% (Legendary)

---

## Companion System

### Inventory Effects (Always Active)

| Job | Effect | Current Total |
|-----|--------|---------------|
| 2nd Job | Flat Main Stat | 2,658 DEX |
| 3rd Job | Damage % | 84.1% |
| 4th Job | Damage % | 82% |

### On-Equip Effects
- Only applies to main/sub companion slot
- Various stats depending on companion

---

## Shop Prices

### Starforce Scrolls

| Source | Price | Limit |
|--------|-------|-------|
| Normal Shop (💎) | 6,000 | 200/week |
| Normal Shop (❤️) | 1,500 | 3/week |
| Arena Shop | 500 coins | 25/week |
| Monthly Pack | 300 💎 | 10/month |
| Weekly Pack | 350 💎 | 60/week |

### Potential Cubes

| Source | Price | Limit |
|--------|-------|-------|
| Normal Shop (💎) | 3,000 | Unlimited |
| Normal Shop (❤️) | 1,000 | 5/week |
| World Boss | 500 coins | 10/week |

---

## Optimization Priorities

### Cost Efficiency Ranking (per 1% damage)

| System | Medal Cost | Priority | Notes |
|--------|------------|----------|-------|
| Equipment Potential | 1,000-2,000 | ★★★★★ | Best ROI |
| Starforce 1-10 | 1,500-3,000 | ★★★★★ | Safe & valuable |
| Equipment Tier Upgrade | 2,000-5,000 | ★★★★☆ | Good scaling |
| Starforce 11-15 | 3,000-8,000 | ★★★★☆ | Higher risk |
| Artifact Awakening | 5,000-15,000 | ★★★☆☆ | Legendary priority |
| Starforce 16+ | 10,000-50,000 | ★★★☆☆ | Use protection |
| Hero Power Reroll | 80,000+ | ★☆☆☆☆ | Last resort |

### Key Insights

1. **Final Damage is most valuable** - multiplicative stacking means small gains multiply against everything
2. **Damage Amplification (scrolls) is underrated** - separate multiplier against high Damage % pool
3. **Hexagon Necklace buff is huge** - ×1.72 multiplier on entire Damage % pool
4. **%DEX vs Flat DEX** - at 126.5% bonus, each 1% DEX = ~187 flat DEX equivalent
5. **Defense Penetration has diminishing returns** - multiplicative formula means less value at higher %
6. **Ring/Necklace are special** - only slots with Damage % on-equip effect
7. **Slot 1 potentials are 10× more valuable** - grey line system makes Slots 2/3 mostly previous tier

---

## Current Character Stats

| Stat | Value |
|------|-------|
| Damage % | 825.4% (w/ 3 Hex stacks) |
| Damage % | 484.1% (no Hex) |
| Damage Amplification | 23.2% |
| Final Damage | 94.5% |
| Defense Penetration | 60.9% (w/ Hero Preset 5) |
| Critical Rate | 111.9% |
| Critical Damage | 184.5% |
| Min Damage Multiplier | 163.7% |
| Max Damage Multiplier | 200% |
| Boss Monster Damage | 64.5% |
| Normal Monster Damage | 125.8% |
| Skill Damage | 58% |
| Basic Attack Damage | 46.8% |

---

## Known Gaps / TODO

1. Missing ~3,320 flat DEX (need to find sources)
2. Starforce stages 20-25 need verification
3. Weapon base stats not fully documented
4. Set bonuses contribution unknown
5. Medal income rate needed for investment planning
6. Equipment tier upgrade costs need verification
7. Mythic rarity stat ranges need more data

---

**END OF KNOWLEDGE BASE**
