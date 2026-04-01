# MapleStory Idle Calculator - Developer Context

## Project Overview

A Streamlit web app for MapleStory Idle that calculates DPS, optimizes equipment, simulates cubes, and visualizes skill rotations. The app supports multiple job classes (Bowmaster, Night Lord, I/L Mage, Shadower) with full skill rotation modeling.

**Stack:** Python 3, Streamlit, Altair/Plotly for charts, Firebase-style CSV storage.

---

## Repository Structure

```
maplestory_idle/
  skills.py              # THE MOST IMPORTANT FILE - skill definitions, DPS calculator, CD mechanics
  core/
    damage.py            # Verified damage formulas (single source of truth)
    stats.py             # Stat aggregation functions
    constants.py         # Core game constants (BASE_MIN_DMG, BASE_MAX_DMG, etc.)
  equipment.py           # Equipment & starforce mechanics
  artifacts.py           # Artifact system (calculate_book_of_ancient_bonus lives here)
  job_classes.py         # JobClass enum, JOB_DISPLAY_NAMES, get_main_stat_name, get_secondary_stat_name
  stage_settings.py      # COMBAT_SCENARIO_PARAMS, CombatMode enum
  cooldown_calc.py       # calculate_triggers(), calculate_buff_uptime() helpers
  streamlit_app/
    app.py               # Main Streamlit entry point / home page
    utils/
      dps_calculator.py  # aggregate_stats(), calculate_dps() - bridges user data to DPSCalculator
      data_manager.py    # UserData dataclass, CSV load/save
      stat_aggregator.py # StatAggregator class with source tracking
    pages/
      1_Character_Settings.py  # Job class selection, level, combat mode
      2_Equipment_Potentials.py
      8_Damage_Calculator.py   # Main DPS display page
      9_Character_Stats.py     # Detailed stat breakdown
      15_Skill_Breakdown.py    # Skill contribution charts + CD reduction slider
      17_Cooldown_Analyzer.py  # DPS vs CD reduction line chart + marginal gain
      ...20+ pages total
```

---

## Key File: skills.py (~5200 lines)

This is the core of the DPS calculation system. Key sections:

### Skill Types (SkillType enum)
- `BASIC_ATTACK` - Main attack skill (uses basic_attack_dmg_pct)
- `ACTIVE` - Cooldown-based skills (uses skill_damage_pct)
- `SUMMON` - Persistent summons with attack_interval (Dark Flare, Phoenix)
- `PASSIVE_PROC` - Proc-based skills (Final Attack, Shadow Partner, Mark of Assassin)
- `PASSIVE_BUFF` - Buff skills (Smokescreen, Shadow Shifter)
- `SKILL_ENHANCER` - Skills that grant Final Damage to other skills (Maple Hero, AFA, Enchanted Quiver)
- `PASSIVE_STAT` - Stat-granting passives

### Skill Definitions by Job
- `BOWMASTER_SKILLS` - dict of skill_name -> SkillData
- `NIGHT_LORD_SKILLS` - dict of skill_name -> SkillData
- `ICE_LIGHTNING_SKILLS` - dict of skill_name -> SkillData
- `SHADOWER_SKILLS` - dict of skill_name -> SkillData
- `SKILLS_BY_JOB` - maps JobClass enum to skill dicts

### Mastery System
- `MasteryNode(name, unlock_level, unlock_order, effect_type, effect_target, effect_value, description)`
- Masteries are per-job, provide fixed bonuses NOT affected by +All Skills
- Types include: `skill_damage_pct`, `skill_hits`, `skill_targets`, `skill_cooldown_reduction`, `skill_attack_interval`, `skill_attack_interval_pct`
- `skill_attack_interval` = flat second reduction (Mark of Assassin: -1 sec)
- `skill_attack_interval_pct` = percentage reduction (Dark Flare: -40%, Phoenix: -30%)

### CharacterState (dataclass, ~line 2560)
Key attributes:
- `job_class: JobClass` - determines which skills are loaded
- `skill_cd_reduction: float` - flat CD reduction from hat special potential
- `all_skills_bonus: int` - +All Skills from equipment
- `skill_1st_bonus` through `skill_4th_bonus` - per-job-tier skill bonuses
- `attack`, `main_stat_flat`, `main_stat_pct`, `crit_rate`, `crit_damage`, etc.
- `get_effective_skill_cooldown(base_cd, percent_reduction)` - applies hat CD reduction

### DPSCalculator (class, ~line 3300)
Main calculation engine. Key methods:
- `calculate_total_dps(fight_duration, num_enemies, mob_time_fraction)` - legacy DPS
- `calculate_realistic_dps(...)` - phase-aware simulation (boss/mob phases)
- `get_skill_damage_breakdown(fight_duration, num_enemies, mob_time_fraction)` - per-skill breakdown
  - Returns `Dict[str, Dict]` with keys: `display_name`, `dps`, `pct_of_total`, `mob_damage`, `boss_damage`, `skill_type`, `total_damage`
- `get_skill_damage_pct(skill_name)` - base damage + mastery + level scaling
- `get_skill_hits(skill_name)` - base hits + mastery bonus
- `get_skill_targets(skill_name)` - base targets + mastery bonus
- `get_mastery_bonus(skill_name, effect_type)` - sum of all mastery values for a skill+type
- `calculate_hit_damage(damage_pct, is_basic_attack, ...)` - single hit damage with all multipliers

#### 4 Parallel DPS Code Paths (MUST STAY IN SYNC)
1. `_precalculate_skill_values()` (~line 3860) - pre-computes per-skill action values
2. `_calc_summons_dps_phased()` (~line 4350) - summon DPS in phase-aware mode
3. `calculate_total_dps()` (~line 4580) - legacy total DPS
4. `get_skill_damage_breakdown()` (~line 4943) - per-skill breakdown for visualization

All 4 paths must handle: hits multiplier, interval mastery types (flat + pct), summon calculations, proc calculations, SKILL_ENHANCER final damage.

### SKILL_ENHANCER Handling (~line 3711 in calculate_hit_damage)
Generic loop over all SKILL_ENHANCER skills:
```python
enhancer_fd = 0.0
for enhancer_name, enhancer_skill in self._skills.items():
    if enhancer_skill.skill_type != SkillType.SKILL_ENHANCER:
        continue
    if not self.char.is_skill_unlocked(enhancer_name):
        continue
    if not enhancer_skill.skill_bonuses or skill_name not in enhancer_skill.skill_bonuses:
        continue
    enhancer_fd += self.get_skill_bonus_value(enhancer_name, skill_name)
enhancer_fd += self.get_mastery_bonus(skill_name, "skill_final_damage")
if enhancer_fd > 0:
    final_mult *= (1 + enhancer_fd / 100)
```

### Cooldown Reduction Mechanic (calculate_effective_cooldown, ~line 93)
1. Percentage reduction from masteries applied first
2. Flat reduction (from hat potential) applied as per-source increments:
   - Each source is 2 seconds (hat potential lines give 2s each)
   - Remainder (if flat % 2 != 0) is a final smaller source
3. Each source applied sequentially:
   - If the source would push CD below 7s, that source loses 0.5s effectiveness
4. Hard cap: 4 seconds minimum

**Example:** Meso Explosion (11s base), 6s flat = 3 sources of 2s:
- 11 -> 9 (full) -> 7 (full) -> 5.5 (penalty: 2s - 0.5 = 1.5s effective)

**Example:** Meso Explosion (11s base), 8s flat = 4 sources of 2s:
- 11 -> 9 -> 7 -> 5.5 -> 4.0

### Factory Functions
- `create_character_at_level(level, all_skills_bonus, job_class)` - basic character with skills unlocked
- `create_default_character(level, job_class, all_skills_bonus, skill_*_bonus)` - standardized character for skill analysis (fixed stats)
- `get_skills_for_job(job_class)` - returns skill dict for a job
- `get_masteries_for_job(job_class)` - returns mastery list for a job
- `get_level_breakpoints(job_class)` - levels where skills/masteries unlock (for chart optimization)

---

## Key File: streamlit_app/utils/dps_calculator.py

### aggregate_stats(user_data) -> Dict
Aggregates all stat sources (equipment, hero power, artifacts, companions, etc.) into a single stats dict. Keys include:
- `attack_flat`, `attack_pct`, `crit_rate`, `crit_damage`, `damage_pct`
- `boss_damage`, `normal_damage`, `skill_damage`, `basic_attack_damage`
- `min_dmg_mult`, `max_dmg_mult`, `def_pen_sources`, `attack_speed_sources`
- `final_damage_sources`, `final_damage_correction`
- `character_level`, `all_skills`, `skill_cd` (hat CD reduction)
- `ba_targets`, `skill_1st` through `skill_4th`
- `book_of_ancient_stars`, `hex_multiplier`

### calculate_dps(stats, combat_mode, enemy_def, job_class, ...) -> Dict
Full DPS pipeline:
1. Gets stats from `aggregate_stats()`
2. Builds `CharacterState` via `create_character_at_level()`
3. Sets all stat attributes on the character
4. Creates `DPSCalculator` and calls `calculate_total_dps()` or `calculate_realistic_dps()`

**IMPORTANT BUG:** `calculate_dps()` does NOT pass `job_class` to `create_character_at_level()`, so it defaults to Bowmaster. Page 17 (Cooldown Analyzer) has its own `build_character_from_stats()` that DOES pass job_class correctly.

---

## Streamlit Pages

### Page 15: Skill Breakdown (15_Skill_Breakdown.py)
- Uses `create_default_character()` with standardized stats (NOT real user stats)
- Enemy defense hardcoded at 0.752
- Sidebar: Level slider, Combat Mode, +All Skills, per-job skill bonuses
- Sections:
  1. Damage Distribution table + bar chart
  2. **CD Reduction slider (0-10s)** that controls:
     - Boss (Single Target) stacked area chart by level
     - Mob Grinding (12 Enemies) stacked area chart by level
  3. Skill Damage Proportion bar + comparison table with Base CD / Eff. CD columns
  4. Skill Scaling by +All Skills (stacked area + growth line chart)
  5. Active Passive Effects table
  6. Skill Details expander

### Page 17: Cooldown Analyzer (17_Cooldown_Analyzer.py)
- Uses real user stats via `aggregate_stats()` and `build_character_from_stats()`
- Reads job class from `data.job_class` (Character Settings page)
- Correctly passes `job_class` to `create_character_at_level()`
- Sections:
  1. Total DPS vs CD Reduction line chart (0-10s sweep)
  2. Marginal DPS Gain per 0.5s bar chart + table

### Page 8: Damage Calculator (8_Damage_Calculator.py)
- Main DPS display using `calculate_dps()` wrapper
- Does NOT pass job_class to `calculate_dps()` (pre-existing bug)

---

## Job Class System

### JobClass Enum (job_classes.py)
- `BOWMASTER`, `NIGHT_LORD`, `ICE_LIGHTNING_MAGE`, `SHADOWER`

### Job-Specific Notes

**Shadower-specific skills:**
- `assassinate` - Finishing blow mechanic (extra damage below HP threshold)
- `sudden_raid` - 19s cooldown, has DoT component (360%/tick, 5s, 1s interval)
- `shadow_shifter` - Counterattack buff
- `steal` - Attack buff
- `blood_money` - Stack-based proc (stacks doubled by mastery, consumed by Meso Explosion)
- `smokescreen` - Crit damage buff with uptime calculation
- `shadow_partner` - 84% damage echo (was 60%, buffed to 84%)

**Night Lord-specific skills:**
- `shadow_partner` - 84% damage echo (was 70%, buffed to 84%)
- `mark_of_assassin` - Proc with -1s flat interval mastery

**Common patterns:**
- Both NL and Shadower share Sudden Raid, Steal, Toxic Venom, Venom
- Maple Hero variant: `maple_hero` for NL/Shadower, `maple_hero_mage` for I/L Mage

---

## Session State & Data Flow

- `st.session_state.user_data` - `UserData` dataclass (from data_manager.py)
- `data.job_class` - string like "bowmaster", "night_lord", "shadower", "ice_lightning_mage"
- `data.chapter` - string like "Chapter 27"
- `data.combat_mode` - string like "stage"
- Job class set in Character Settings page (page 1), persisted to CSV

---

## Common Patterns

### Character Building in Streamlit Pages
```python
# For pages using real user stats:
stats = aggregate_stats(data)
char = create_character_at_level(level, all_skills, job_class=selected_job)
char.attack = base_atk
char.skill_cd_reduction = cd_value
# ... set all other stats ...
calc = DPSCalculator(char, enemy_def=enemy_def)
breakdown = calc.get_skill_damage_breakdown(fight_duration, num_enemies, mob_fraction)

# For pages using default/standardized stats:
char = create_default_character(level, job_class, all_skills, ...)
char.skill_cd_reduction = cd_value
calc = DPSCalculator(char, enemy_def=0.752)
```

### Caching Pattern
```python
@st.cache_data(ttl=300, show_spinner="...")
def cached_function(hashable_param1: str, hashable_param2: int, ...) -> result:
    # IMPORTANT: Do NOT prefix params with _ unless they're truly unhashable
    # _param means Streamlit skips it for cache key!
    ...
```

### Interval Mastery Handling (7 locations in skills.py)
Both flat and percentage interval reductions must be checked:
```python
flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
if flat_reduction != 0:
    interval = max(1.0, interval + flat_reduction)  # flat_reduction is negative
pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
if pct_reduction != 0:
    interval = max(1.0, interval * (1 + pct_reduction / 100))  # pct_reduction is negative like -40
```

---

## Recent Changes (Feb 2026 Sessions)

### Shadower Skills Implementation
- Assassinate finishing blow, Sudden Raid DoT, Shadow Shifter counterattack
- Steal attack buff, Blood Money stack doubling, Smokescreen crit damage mastery

### Bug Fixes Applied
1. `get_attack_speed_multiplier` -> `calculate_attack_speed_mult` (3 references)
2. Shadow Partner buffed: NL 70->84%, Shadower 60->84%
3. Maple Hero: replaced hardcoded checks with generic SKILL_ENHANCER loop
4. Summon `hits` multiplier: was missing in all 4 DPS code paths
5. Interval mastery: split `skill_attack_interval` (flat) from `skill_attack_interval_pct` (percentage)
6. Sudden Raid cooldown: 40s -> 19s (both NL and Shadower)
7. CD reduction formula: rewritten from lump-sum to per-source (2s increments with 0.5s penalty below 7s)
8. Page 17: fixed missing job_class pass to `create_character_at_level()`
9. Page 17: fixed `_stats_keys` underscore prefix causing cache to skip stat changes

### Features Added
- **Page 17 (Cooldown Analyzer)**: DPS vs CD reduction line chart, marginal gain bars
- **Page 15 (Skill Breakdown)**: CD reduction slider (0-10s) that updates level progression charts, skill proportion bar, comparison table with Base CD / Eff. CD columns

---

## Known Issues / Pre-existing Bugs

1. `calculate_dps()` in `dps_calculator.py` does NOT pass `job_class` to `create_character_at_level()` - affects page 8 (Damage Calculator). Page 17's `build_character_from_stats()` does this correctly.
2. Some older Streamlit pages may still assume Bowmaster-only.
