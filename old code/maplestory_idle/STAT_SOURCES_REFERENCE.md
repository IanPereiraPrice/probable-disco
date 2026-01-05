# MapleStory Idle - Complete Stat Sources Reference

## Overview
This document maps ALL stat sources in the game and how they combine in the damage formula.
Use this to validate our modeling against actual in-game character stats.

---

## Target Character Stats (From Screenshots)
| Stat | Value | Status |
|------|-------|--------|
| Attack | 48,788,000 | To match |
| DEX (Main Stat) | 70,436 | To match |
| Damage % | 1,185.7% | To match |
| Damage Amp | 34.1% | To match |
| Crit Rate | 128.9% | To match |
| Crit Damage | 246.5% | To match |
| Defense Penetration | 45.8% | To match |
| Boss Damage | 82.7% | To match |
| Normal Damage | 143.4% | To match |
| Final Damage | 65.8% | To match |
| All Skill Levels | +48 | To match |
| 2nd Job Skills | +26 | To match |
| 3rd Job Skills | +18 | To match |
| 4th Job Skills | +11 | To match |

---

## 1. ATTACK STAT

### 1.1 Base Attack Sources
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Character Base | Starting attack value | Manual slider | maple_app.py |
| Equipment Main Stat (Attack) | Per-piece base attack × Main Amplify | ✅ | equipment.py |
| Equipment Flat Attack (Sub) | Per-piece sub stat × Sub Amplify | ✅ | equipment.py |
| Artifact Flat Attack | Hexagon Necklace inventory (+600 flat) | ✅ | artifacts.py |
| Guild Flat Attack | Guild skill (+100/level) | ✅ | guild.py |

### 1.2 Attack % Multipliers
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Weapon ATK% | Level × Rate per level, multiplicative | ✅ | weapons.py |
| Hero Power ATK% | From Attack % lines | ✅ | hero_power.py |
| Companion ATK% | From companion active/inventory effects | ✅ | companions.py |
| Passive Skills ATK% | From passive skills | ✅ | passives.py |
| Potential ATK% | Equipment cube lines (rare) | ✅ | cubes.py |

### Attack Formula
```
Final Attack = (Base Attack × Weapon ATK% Mult) × (1 + Total ATK%) + Flat Attack Bonuses
```

---

## 2. MAIN STAT (DEX for Bowmaster)

### 2.1 Flat Main Stat Sources
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Stats | Character base + level-up stats | ❌ Manual | - |
| Equipment 3rd Stat | Shoulder/Belt have main stat as 3rd | ✅ | equipment.py |
| Artifact Resonance | +10 main stat per total ★ | ✅ | artifacts.py |
| Potential Flat | DEX +X from cube lines | ✅ | cubes.py |
| Companion Flat | Some companions give flat stat | ❌ | companions.py |

### 2.2 Main Stat % Sources
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Potential Main % | DEX% from cube lines | ✅ | cubes.py |
| Hero Power Main % | Main Stat % lines | ✅ | hero_power.py |
| Guild Main Stat % | Guild skill (+1%/level) | ✅ | guild.py |
| Companion Main % | From companion effects | ✅ | companions.py |
| Passive Main % | Physical Training etc. | ✅ | passives.py |
| Link Skills | ❌ NOT MODELED | ❌ | - |

### Main Stat Formula
```
Final Main Stat = (Base Main Stat + Flat Bonuses) × (1 + Total Main Stat %)
```

---

## 3. DAMAGE %

### 3.1 Damage % Sources (Additive within category)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Damage % | Manual slider | Manual | maple_app.py |
| Potential Damage % | Cube lines | ✅ | cubes.py |
| Artifact Damage % | Chalice, Soul Contract inventory | ✅ | artifacts.py |
| Hero Power Damage % | Damage % lines | ✅ | hero_power.py |
| Guild Damage % | Guild skill (+2%/level) | ✅ | guild.py |
| Companion Damage % | From companion effects | ✅ | companions.py |
| Passive Damage % | Thrust etc. | ✅ | passives.py |
| Equipment Damage % | Special items only | ✅ | equipment.py |

### 3.2 Hex Multiplier (Multiplicative)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Hexagon Necklace | 20% + 2%/★ per stack, max 3 stacks | ✅ | artifacts.py |

### Damage % Formula
```
Total Damage % = (Base + All Additive Sources) × Hex Multiplier
Hex Multiplier = 1 + (stacks × (0.20 + 0.02 × stars))
```

---

## 4. BOSS DAMAGE %

### Boss Damage Sources (Additive)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Boss % | Manual slider | Manual | maple_app.py |
| Potential Boss % | Cube lines (5%/10%/15%) | ✅ | cubes.py |
| Artifact Boss % | Star Rock active, Lit Lamp inventory | ✅ | artifacts.py |
| Hero Power Boss % | Boss Damage % lines | ✅ | hero_power.py |
| Guild Boss % | Guild skill (+2%/level) | ✅ | guild.py |
| Companion Boss % | From companion effects | ✅ | companions.py |
| Passive Boss % | Bow Expert | ✅ | passives.py |
| Equipment Boss % | Sub stat on equipment | ✅ | equipment.py |

---

## 5. CRITICAL RATE

### Crit Rate Sources (Additive)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Crit Rate | Manual slider | Manual | maple_app.py |
| Potential Crit Rate | Cube lines | ✅ | cubes.py |
| Artifact Crit Rate | Book of Ancient active | ✅ | artifacts.py |
| Hero Power Crit Rate | Crit Rate % lines | ✅ | hero_power.py |
| Companion Crit Rate | Shadow Wolf etc. | ✅ | companions.py |
| Passive Crit Rate | Critical Shot | ✅ | passives.py |
| Equipment Crit Rate | Sub stat | ✅ | equipment.py |

---

## 6. CRITICAL DAMAGE

### Crit Damage Sources (Additive)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Crit Damage | Manual slider | Manual | maple_app.py |
| Potential Crit Damage | Cube lines | ✅ | cubes.py |
| Artifact Crit Damage | Icy Soul Rock, Book of Ancient inventory | ✅ | artifacts.py |
| Hero Power Crit Damage | Crit Damage % lines | ✅ | hero_power.py |
| Guild Crit Damage | Guild skill (+1.5%/level) | ✅ | guild.py |
| Companion Crit Damage | Phoenix Spirit etc. | ✅ | companions.py |
| Passive Crit Damage | Marksmanship, Sharp Eyes | ✅ | passives.py |
| Equipment Crit Damage | Sub stat | ✅ | equipment.py |
| Book of Ancient Conversion | CR × Conversion Rate → CD | ✅ | artifacts.py |

---

## 7. DEFENSE PENETRATION

### Def Pen Sources (MULTIPLICATIVE STACKING)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Base Def Pen | Manual slider | Manual | maple_app.py |
| Potential Def Pen | Cube lines | ✅ | cubes.py |
| Artifact Def Pen | Silver Pendant inventory | ✅ | artifacts.py |
| Hero Power Def Pen | Defense Pen % lines | ✅ | hero_power.py |
| Guild Def Pen | Guild skill (+0.5%/level) | ✅ | guild.py |
| Companion Def Pen | Shadow Wolf etc. | ✅ | companions.py |
| Passive Def Pen | Illusion Step | ✅ | passives.py |

### Def Pen Formula (Multiplicative)
```
Total Def Pen = 1 - (1-Source1) × (1-Source2) × (1-Source3) × ...
Example: 20% + 15% + 10% = 1 - (0.8 × 0.85 × 0.9) = 38.8% (not 45%)
```

---

## 8. FINAL DAMAGE

### Final Damage Sources (MULTIPLICATIVE)
| Source | Category | Modeled? | File |
|--------|----------|----------|------|
| Equipment FD | Equipment source | ✅ | equipment.py |
| Potential FD | From cube lines | ✅ | cubes.py |
| Guild FD | Guild skill (+1%/level) | ✅ | guild.py |
| Skill FD | From active skills | Manual | - |
| Mortal Blow FD | Passive/buff | Manual | - |
| Fire Flower FD | Artifact active (per target) | ✅ | artifacts.py |
| Chalice FD | Conditional (boss kill) | ✅ | artifacts.py |
| Companion FD | Phoenix Spirit etc. | ✅ | companions.py |
| Passive FD | Mortal Blow passive | ✅ | passives.py |

### Final Damage Formula (Multiplicative)
```
FD Multiplier = (1 + FD_equip) × (1 + FD_guild) × (1 + FD_skill) × (1 + FD_mortal) × (1 + FD_flower) × ...
```

---

## 9. SKILL LEVELS

### All Skills Sources
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Potential All Skills | +1/+2 All Skills lines | ✅ | cubes.py |
| Equipment All Skills | Special item sub stat | ✅ | equipment.py |
| Artifact All Skills | ❌ None give this | - | - |
| Link Skills | ❌ NOT MODELED | ❌ | - |

### Job-Specific Skill Sources
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Equipment Sub Stats | +1/+2 1st/2nd/3rd/4th job | ✅ | equipment.py |

---

## 10. OTHER STATS

### Normal Damage %
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| Equipment Normal % | Sub stat | ✅ | equipment.py |
| Artifact Normal % | Fire Flower inventory, Sayram's | ✅ | artifacts.py |
| Hero Power Normal % | Normal Damage % lines | ✅ | hero_power.py |

### Damage Amp (Amplification)
| Source | How it works | Modeled? | File |
|--------|--------------|----------|------|
| ??? | Need to identify source | ❌ | - |

---

## 11. STACKING RULES SUMMARY

| Stat Type | Stacking Method |
|-----------|-----------------|
| Damage % | Additive → then Hex multiplied |
| Boss Damage % | Additive |
| Normal Damage % | Additive |
| Crit Rate | Additive |
| Crit Damage | Additive |
| Main Stat % | Additive |
| Attack % | Multiplicative (each source multiplies) |
| Defense Pen | Multiplicative (diminishing returns) |
| Final Damage | Multiplicative (each source multiplies) |

---

## 12. NOT YET MODELED

| System | Priority | Notes |
|--------|----------|-------|
| Item Scrolling | Medium | Adds flat stats to equipment |
| Level-up Stats | Low | Base stat increases per level |
| Link Skills | Medium | Character-specific bonuses |
| Union/Legion | Medium | Account-wide bonuses |
| Titles | Low | Various bonuses |
| Buffs/Skills | Low | Active skill bonuses |
| Hyper Stats | Medium | Stat point allocation |

---

## 13. DATA COLLECTION TEMPLATE

To match your character, please provide:

### Equipment (Per Slot)
- [ ] Slot name
- [ ] Rarity (epic/unique/legendary/mystic)
- [ ] Tier (T1-T4)
- [ ] Starforce level (0-25)
- [ ] Base Attack value
- [ ] Base HP value
- [ ] Sub stats (boss%, normal%, crit rate%, crit dmg%, etc.)
- [ ] Is Special item? (Y/N)
- [ ] Special stat type and value

### Potentials (Per Slot)
- [ ] Regular potential tier
- [ ] Regular potential lines (stat + value)
- [ ] Bonus potential tier
- [ ] Bonus potential lines (stat + value)

### Weapons
- [ ] Equipped weapon rarity + tier + level
- [ ] Inventory weapons (rarity + tier + level each)

### Hero Power
- [ ] All 5 lines (stat type + value + tier)

### Artifacts
- [ ] Equipped artifacts (3 slots) with stars
- [ ] Inventory artifacts with stars
- [ ] Potential lines on artifacts

### Guild
- [ ] Final Damage skill level (0-10)
- [ ] Damage skill level (0-10)
- [ ] Main Stat skill level (0-10)
- [ ] Crit Damage skill level (0-10)
- [ ] Boss Damage skill level (0-10)
- [ ] Def Pen skill level (0-10)
- [ ] Attack skill level (0-10)

### Companions
- [ ] Main companion (name + level)
- [ ] Sub companion (name + level)
- [ ] Inventory companions (for passive bonuses)

### Passives
- [ ] Job class
- [ ] Each passive skill level

---

## 14. VALIDATION CHECKLIST

After inputting all data, compare calculated vs actual:

| Stat | Calculated | Actual | Diff |
|------|------------|--------|------|
| Attack | | 48,788,000 | |
| DEX | | 70,436 | |
| Damage % | | 1,185.7% | |
| Damage Amp | | 34.1% | |
| Crit Rate | | 128.9% | |
| Crit Damage | | 246.5% | |
| Def Pen | | 45.8% | |
| Boss Damage | | 82.7% | |
| Normal Damage | | 143.4% | |
| Final Damage | | 65.8% | |

If there are discrepancies, identify which source is missing or incorrectly calculated.
