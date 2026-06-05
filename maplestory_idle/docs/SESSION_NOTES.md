# MapleStory Idle Calculator - Session Notes

## Session: December 2024 - Skill DPS Calculator & All Skills Value

### Overview
Built a comprehensive skill DPS calculator (`skills.py`) to accurately determine the value of +All Skills from cube potentials. The initial estimate of 3.5% per skill level was found to be too simplistic.

---

## Key Findings

### +1 All Skills Value
At Level 100 with +44 existing All Skills:
- **+1 All Skills = +0.6845% DPS** (not 3.5% as initially estimated)

### DPS Breakdown (Level 100, +44 All Skills)
| Source | DPS Contribution |
|--------|-----------------|
| Basic Attack (Arrow Stream) | 68.5% |
| Summons (Phoenix, Arrow Platter, Quiver) | 18.6% |
| Active Skills (Covering Fire) | 7.4% |
| Procs (Final Attack, Flash Mirage) | 5.6% |

### Why Value Is Lower Than Expected
1. **Hurricane not unlocked at Level 100** - Requires Level 103
2. **High existing +All Skills (+44)** - Diminishing returns
3. **Masteries don't scale with +All Skills** - Fixed bonuses
4. **Basic Attack dominates DPS** - 68.5% from Arrow Stream

---

## Files Created/Modified

### New Files
- `skills.py` - Comprehensive skill DPS calculator

### Modified Files
- `cubes.py` - Added DPS-based roll scoring and Monte Carlo simulation
- `maple_app.py` - Added cube simulation UI (pending All Skills integration)

---

## skills.py Architecture

### Core Components

1. **SkillType Enum**
   - `BASIC_ATTACK` - Arrow Stream (uses Basic Attack Damage %)
   - `ACTIVE` - Hurricane, Covering Fire (uses Skill Damage %)
   - `SUMMON` - Phoenix, Arrow Platter, Quiver Cartridge
   - `PASSIVE_PROC` - Final Attack, Flash Mirage
   - `PASSIVE_BUFF` - Mortal Blow, Concentration
   - `PASSIVE_STAT` - Skills providing stat bonuses

2. **DamageType Enum**
   - `BASIC` - Scales with Basic Attack Damage %
   - `SKILL` - Scales with Skill Damage %

3. **Job Progression**
   - 1st Job: Levels 1-29
   - 2nd Job: Levels 30-59
   - 3rd Job: Levels 60-99
   - 4th Job: Levels 100+

### Mastery System
- 40+ mastery nodes defined with unlock levels
- Masteries provide fixed bonuses (NOT affected by +All Skills)
- Bonuses include: damage %, targets, hits, boss damage, cooldown reduction

### Key Skills Modeled

| Skill | Type | Unlock Level | Scaling |
|-------|------|--------------|---------|
| Arrow Stream | Basic Attack | 100 | 290% + 1.19%/level |
| Hurricane | Active | 103 | 800% + 4.09%/level (40s CD) |
| Covering Fire | Active | 35 | 250% + 1.26%/level (19s CD) |
| Phoenix | Summon | 69 | 600% + 3.02%/level (60s CD, 20s duration) |
| Arrow Platter | Summon | 63 | 50% + 0.25%/level (40s CD, 60s duration) |
| Final Attack | Proc | 50 | 35% + 0.14%/level (25% chance) |
| Flash Mirage | Proc | 60 | 550% + 2.21%/level (20% chance, 5s ICD) |

### Combat Mechanics Modeled
- **Attack Speed**: Multiplicative, capped at 150% (2.5x)
- **Cast Time**: 1 second base, reduced by attack speed
- **Summon Uptime**: Based on duration/cooldown ratio
- **Proc Rates**: Account for internal cooldowns
- **Final Damage**: Multiplicative sources (Extreme Archery, Mortal Blow, etc.)

---

## Key Functions in skills.py

### `calculate_all_skills_value(level, current_all_skills, **extra_stats)`
Returns `(dps_increase_percent, breakdown_dict)`

```python
# Example usage:
increase, breakdown = calculate_all_skills_value(
    level=100,
    current_all_skills=44,
    attack=1000,
    main_stat_pct=50,
    damage_pct=30,
    boss_damage_pct=20,
    crit_rate=70,
    crit_damage=200,
    attack_speed_pct=50,
)
# Returns: (0.6845, {"basic_attack": 0.xx, "summons": 0.xx, ...})
```

### `create_character_at_level(level, all_skills_bonus)`
Creates a CharacterState with appropriate skills unlocked.

### `DPSCalculator(char: CharacterState)`
Main DPS calculation class with methods:
- `calculate_total_dps()` - Returns DPSResult
- `get_effective_attack_speed()` - Capped at 2.5x
- `get_skill_damage_pct(skill_name)` - Including masteries
- `calculate_hit_damage(...)` - Single hit damage

---

## Updates This Session

### Mastery Reorganization
- Separated masteries into **global** (affect character stats) vs **skill-specific** (affect one skill)
- Changed `effect_target="all"` to `effect_target="global"` for clarity
- Global stats: +30 DEX, +10% Crit Rate, +5% Attack Speed, +15% Basic Attack Damage, +10% Max Damage Mult, +15% Skill Damage

### Mortal Blow Uptime Calculation
- Now dynamically calculated based on hit rate
- **50 hits** to activate
- **5 sec base** + 5 sec mastery (level 90+) = **10 sec duration**
- Hit sources that COUNT: Arrow Stream (5), Phoenix (1), Final Attack (1), Flash Mirage (1), Covering Fire (3)
- Hit sources that DON'T count: Arrow Platter, Quiver Cartridge
- At level 100 with ~66% AS: **~65% uptime**
- At AS cap (150%): **~73% uptime**

### Unit Tests Added
- Created `test_skills.py` with **34 tests** covering:
  - Job progression
  - Mastery unlocks and calculations
  - Character state management
  - DPS calculations
  - Attack speed cap
  - Mortal Blow uptime
  - Maple Hero Final Damage application
  - +All Skills value and diminishing returns
  - Job-specific skill bonuses (+5 3rd Job, etc.)

### Job-Specific Skill Bonuses
Added support for equipment like "+5 3rd Job Skills":

```python
# New classes and functions:
JobSkillBonus          # Dataclass to track bonuses by job
create_character_with_job_bonuses()   # Create character with per-job bonuses
calculate_job_skill_value()           # Value of +1 to specific job
calculate_all_skills_value_by_job()   # Breakdown by job contribution
```

**Value of +1 Skill Level by Job (Level 100, +44 All Skills):**
| Job | +1 Skill Value |
|-----|----------------|
| 1st Job | +0.02% DPS |
| 2nd Job | +0.06% DPS |
| 3rd Job | +0.16% DPS |
| 4th Job | +0.53% DPS |
| **All Skills** | **+0.68% DPS** |

### Cube Optimizer Integration (COMPLETED)
The `maple_app.py` now uses dynamic All Skills calculation:

1. **Character Settings UI** added to Damage Calculator tab:
   - Character Level slider (60-200)
   - Current +All Skills slider (0-100)
   - Live display of "+1 All Skills = +X.XX% DPS"

2. **Dynamic Calculation**:
   - `get_all_skills_dps_value()` method calculates value using skills.py
   - Replaces hardcoded `ALL_SKILLS_TO_FINAL_DAMAGE = 3.5`
   - Value updates when level or All Skills changes
   - Cube scoring now uses accurate per-character value

3. **Cached Calculation**:
   - Value is cached for performance
   - Cache invalidated when level or All Skills changes

### Hat Special Potential: Skill Cooldown Decrease
Added support for Hat special potential (Skill CD Reduction):

**Values by tier:**
| Tier | Reduction |
|------|-----------|
| Epic | -0.5 sec |
| Unique | -1.0 sec |
| Legendary | -1.5 sec |
| Mystic | -2.0 sec |

**Mechanic (from game):**
1. % reduction applies first (capped at 100%)
2. Flat reduction applies second
3. **Diminishing returns below 7 seconds**: loses 0.5s of effectiveness per second below 7
4. **Minimum cooldown: 4 seconds**

Added `calculate_effective_cooldown()` function in skills.py to model this.

### Belt Special Potential: Buff Duration Increase
Added support for Belt special potential (Buff Duration Increase):

**Values by tier:**
| Tier | Duration Increase |
|------|-------------------|
| Epic | +5% |
| Unique | +8% |
| Legendary | +12% |
| Mystic | +20% |

Increases the duration of buffs by the specified percentage.

### Face Accessory Special Potential: Main Stat per Level
Added support for Face Accessory special potential (+X Main Stat per Level):

**Values by tier:**
| Tier | Stat per Level |
|------|----------------|
| Epic | +3 |
| Unique | +5 |
| Legendary | +8 |
| Mystic | +12 |

Grants +X main stat for each character level (e.g., at level 100 with Mystic: +1200 main stat).

### Equipment Editor Redesign (COMPLETED)
Redesigned the equipment system with slot-based stat rules:

**Slot-Based Third Main Stat:**
| Slot | Third Main Stat |
|------|-----------------|
| Weapon, Ring, Necklace, Face | Main Stat |
| Hat, Top | Defense |
| Bottom, Gloves | Accuracy |
| Shoes, Belt | Max MP |
| Shoulder, Cape | Evasion |

**Default Sub Stats (available on ALL equipment):**
- Boss Damage %, Normal Damage %, Crit Rate %, Crit Damage %
- Attack (flat)
- Job-specific skill bonuses: +1st Job, +2nd Job, +3rd Job, +4th Job

**Special Sub Stats (only on items with is_special=True):**
- Damage %
- All Skills
- Final Damage %

**Starforce Amplification:**
- Main stats (Attack, Max HP, Third Stat) use **Main Amplify**
- ALL sub stats (including skill bonuses) use **Sub Amplify**

**UI Changes in maple_app.py:**
- Dynamic third stat label based on slot type
- Job skills row moved to default sub stats section
- Special stats section with checkbox toggle
- Added Final Damage % field

## Pending Work

### Future Improvements
- [x] Add UI inputs for job-specific skill bonuses (+5 3rd Job, etc.) - DONE
- [ ] Show breakdown of All Skills value by job in cube optimizer
- [ ] Support different classes (currently Bowmaster only)
- [ ] Add more 4th job skills (Hurricane at 103, etc.)
- [ ] More precise Concentration uptime calculation
- [ ] Integrate Skill CD Reduction into DPS calculations

---

## User Data Sources
- 26 skill screenshots in `Skill_photos/` folder
- Level 1 wiki values for base scaling
- Complete mastery tree from user

---

## Value at Different Levels (with +44 All Skills)

| Character Level | +1 All Skills Value |
|-----------------|---------------------|
| 60 | ~0.68% DPS |
| 80 | ~0.68% DPS |
| 100 | ~0.68% DPS |
| 120 | Higher (Hurricane unlocked) |
| 140 | Higher (more skills/masteries) |

Note: Value increases at higher levels due to more skills being unlocked and benefiting from +All Skills.
