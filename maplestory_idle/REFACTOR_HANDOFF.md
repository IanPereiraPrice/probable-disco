# Stat Names Standardization Refactor - Handoff Document

## Overview

This document summarizes the refactoring work done to standardize stat names across the codebase, enabling dynamic job class support and type-safe stat handling.

## What Was Accomplished

### 1. Standardized Stat Names

All stat names across the codebase now follow a consistent naming convention:

| Legacy Name | Standardized Name |
|-------------|-------------------|
| `base_attack` | `attack_flat` |
| `damage_percent` | `damage_pct` |
| `dex_percent` | `dex_pct` |
| `attack_percent` | `attack_pct` |
| `defense_pen_sources` | `def_pen_sources` |
| `flat_dex` | `dex_flat` |
| `defense_pen` | `def_pen` |

### 2. Files Modified

#### Core Files

- **`stats.py`** - Added `StatAggregator` class and `MultStatSource` dataclass
  - `StatAggregator`: Bridge between `StatBlock` and DPS calculator
  - Combines additive stats (StatBlock) with multiplicative stat source tracking
  - `to_dps_dict(job_class)`: Converts to dict format for calculate_dps()

- **`constants.py`** - Added centralized stat display helpers
  - `is_percentage_stat(stat_name)`: Determines if stat should display with %
  - `format_stat_value(stat_name, value)`: Formats stat values appropriately
  - `STAT_SHORT_NAMES` and `STAT_DISPLAY_NAMES`: Lookup tables for UI

- **`companions.py`** - Updated `get_inventory_stats()` to return standardized names
  - Returns: `attack_flat`, `main_stat_flat`, `damage_pct`, `max_hp`

#### DPS Calculator

- **`streamlit_app/utils/dps_calculator.py`** - Major refactor
  - `aggregate_stats()`: Now uses standardized stat names throughout
  - `calculate_dps()`: Added `job_class` parameter, removed `book_of_ancient_stars` param
  - Dynamic main stat keys based on job class (e.g., `dex_flat` for Bowmaster)
  - All stat dict keys use standardized names

#### UI Pages

- **`streamlit_app/pages/9_Character_Stats.py`** - Full refactor
  - `get_stat_definitions(job_class)`: Dynamic stat definitions based on job
  - `get_calculated_stats()`: Returns `(stats_dict, raw_stats, job_class)`
  - `get_stat_sources()`: Now accepts `job_class` parameter
  - All internal mappings updated to standardized names
  - Uses `is_percentage_stat()` from constants.py

#### Tests

- **`test_constants.py`** - Added tests for `is_percentage_stat()`
  - Tests flat stats return False
  - Tests percentage stats return True
  - Tests dynamic suffix handling (`_flat` vs `_pct`)

### 3. Key Design Decisions

1. **Dynamic Main Stat**: Main stat is no longer hardcoded to DEX. Instead:
   - `job_class` parameter determines which stat is "main" (dex/str/int/luk)
   - Keys like `main_flat_key` and `main_pct_key` are computed at runtime

2. **Multiplicative Stats as Source Lists**: def_pen, final_damage, and attack_speed are stored as lists:
   - `def_pen_sources`: List of `(source_name, value, priority)` tuples
   - `final_damage_sources`: List of decimal values
   - `attack_speed_sources`: List of `(source_name, value)` tuples

3. **Centralized Stat Type Detection**: `is_percentage_stat()` in constants.py determines formatting:
   - Flat stats: `*_flat`, `all_skills`, `ba_targets`, `accuracy`
   - Everything else: percentage stats

### 4. What Still Uses Legacy Names (Potential Future Work)

- **`maple_app.py`** (Tkinter app) - Uses `get_inventory_summary()` which was removed
- Some internal data structures may still store stats with legacy names (user data files)
- Hero Power internal stat names (e.g., `'damage_percent'` vs `'damage_pct'`)

### 5. Testing

All tests pass:
```
test_constants.py: 31 passed
```

DPS calculator tested and working with standardized names.

## How to Continue

### Adding New Stats

1. Add to `STAT_SHORT_NAMES` and `STAT_DISPLAY_NAMES` in constants.py
2. If flat stat, add to `flat_stats` set in `is_percentage_stat()`
3. Add to `stats` dict initialization in `aggregate_stats()`
4. Add processing in the appropriate pass of `aggregate_stats()`

### Adding New Job Classes

1. Add to `JobClass` enum in `job_classes.py`
2. Add stat mapping to `JOB_STAT_MAPPING`
3. No changes needed to DPS calculator - it handles jobs dynamically

### Debugging Stat Issues

1. Check `aggregate_stats()` PASS 2 for how the stat is being added
2. Verify the stat name matches standardized naming
3. Use `get_stat_sources()` in Character Stats page to trace sources

## File Locations

- Stats system: `maplestory_idle/stats.py`
- Constants/display: `maplestory_idle/constants.py`
- DPS calculator: `maplestory_idle/streamlit_app/utils/dps_calculator.py`
- Character Stats UI: `maplestory_idle/streamlit_app/pages/9_Character_Stats.py`
- Job classes: `maplestory_idle/job_classes.py`
- Stat names: `maplestory_idle/stat_names.py`
- Tests: `maplestory_idle/test_constants.py`

---

# Artifact System Documentation

## Overview

Artifacts provide three types of bonuses:
1. **Inventory Effects** - Always active when owned (regardless of equipped status)
2. **Active Effects** - Only active when equipped in one of 3 slots
3. **Potentials** - Random stat bonuses on equipped artifacts (unlocked at ★1, ★3, ★5)

## Key Files

| File | Purpose |
|------|---------|
| `artifacts.py` | Core artifact definitions, tiers, effects, calculations |
| `artifact_optimizer.py` | DPS evaluation, chest EV, awakening efficiency, ranking |
| `streamlit_app/pages/4_Artifacts.py` | UI for artifact management |
| `streamlit_app/utils/dps_calculator.py` | Applies artifact effects to stats |

## Artifact Effect Types

Defined in `artifacts.py`:

```python
class EffectType(Enum):
    FLAT = "flat"           # Direct stat addition (e.g., +10% crit rate)
    MULTIPLICATIVE = "mult" # Multiplier effect (e.g., Hex Necklace stacking)
    DERIVED = "derived"     # Stat derived from another (e.g., Book's CR→CD)
```

## Important Artifacts with Special Handling

### 1. Book of Ancient
- **Active Effect**: Converts Crit Rate to Crit Damage
- **Special Handling**: The CR→CD conversion is handled in `calculate_dps()` via `book_of_ancient_stars`
- **CRITICAL**: Only apply conversion when Book is EQUIPPED (not just owned)
- **Location**: `dps_calculator.py` lines 849-870 check equipped status
- **Location**: `artifact_optimizer.py` lines 397-413 handle Book specially in `calculate_active_effect_dps()`

### 2. Hexagon Necklace
- **Active Effect**: Stacking damage multiplier (up to 3 stacks)
- **Special Handling**: Uses `hex_multiplier` stat (separate from final_damage for display clarity)
- **Time-weighted**: `calculate_hex_average_multiplier()` accounts for stack ramp-up time
- **Infinite fights**: Returns max stacks multiplier directly

### 3. Athena Pierce's Gloves
- **Active Effect**: Attack Speed → Max Damage conversion (DERIVED effect)
- **Uses**: `attack_speed_sources` list to calculate total attack speed

### 4. Fire Flower
- **Active Effect**: Final Damage per enemy hit (stacking)
- **Uses**: `max_stacks` and `num_enemies` from combat scenario

## Artifact Ranking & Evaluation

### Top N Logic for Active Effects

When calculating artifact value (chest EV, awakening efficiency), we only count active effects for artifacts that would actually be equipped:

```python
# In calculate_chest_expected_value() and get_artifact_recommendations_for_optimizer():
# 1. Get current ranking for scenario
current_ranking = get_artifact_ranking_for_equip(owned_artifacts, scenario, ...)

# 2. Build set of top N artifact keys
top_artifact_keys = {score.artifact_key for score in current_ranking[:top_n]}

# 3. Only count active effects if artifact is in top N OR explicitly equipped
would_be_equipped = artifact_key in top_artifact_keys or artifact_key in equipped_artifact_keys
```

### Scenario-Aware Evaluation

Different combat scenarios affect artifact value:
- `stage` - Mixed normal/boss, ~35s fights
- `chapter_hunt` - 100% normal mobs, infinite duration, 10 enemies
- `boss` - 100% boss, ~35s fights
- `world_boss` - 100% boss, ~120s fights

Artifacts can be restricted to specific scenarios via `applicable_scenarios` in their definition.

## Artifact Potentials

### Structure

Each artifact can have up to 3 potential slots (unlocked at ★1, ★3, ★5):

```python
# In user data (artifacts_inventory):
'book_of_ancient': {
    'stars': 5,
    'dupes': 2,
    'potentials': [
        {'stat': 'crit_damage', 'value': 12.0, 'tier': 'Mystic'},
        {'stat': 'boss_damage', 'value': 9.0, 'tier': 'Legendary'},
        {'stat': 'damage', 'value': 6.0, 'tier': 'Unique'},
    ]
}
```

### Potential Tiers & Values

| Tier | Stats Available | Value Range |
|------|-----------------|-------------|
| Mystic | All premium stats | Higher values |
| Legendary | Most stats | Medium values |
| Unique | Basic stats | Lower values |
| Epic | Limited stats | Lowest values |

### Potential Reroll System

- Uses `ArtifactPotentialDistribution` class for exact probability calculations
- Similar architecture to equipment cube system
- Calculates expected value and efficiency of rerolling

## Common Pitfalls & Rules

### 1. ALWAYS Use `deepcopy()` When Modifying Stats Temporarily

```python
# WRONG - shallow copy shares nested objects
test_stats = current_stats.copy()

# CORRECT - full isolation
from copy import deepcopy
test_stats = deepcopy(current_stats)
```

This was a bug that caused equipment potentials to be deleted during cube analysis.

### 2. Use Standard Stat Names from `stat_names.py`

```python
# WRONG - inconsistent naming
stats['damage_percent'] = 10
stats['damage_multiplier'] = 10

# CORRECT - import from stat_names.py
from stat_names import DAMAGE_PCT
stats[DAMAGE_PCT] = 10  # 'damage_pct'
```

### 3. Don't Duplicate Stat Mappings

If you need to translate stat names, import from the central source:

```python
# WRONG - duplicating mappings
artifact_stat_mapping = {
    'damage': 'damage_pct',
    'attack_buff': 'attack_pct',
    ...
}

# CORRECT - import standard names, only add truly artifact-specific translations
from stat_names import DAMAGE_PCT, ATTACK_PCT
artifact_stat_mapping = {
    'damage': DAMAGE_PCT,      # Artifact uses 'damage', DPS calc uses 'damage_pct'
    'attack_buff': ATTACK_PCT, # Only for non-standard artifact stat names
}
```

### 4. Book of Ancient CR→CD: Only When Equipped

The `book_of_ancient_stars` stat controls CR→CD conversion in `calculate_dps()`. This should ONLY be set when Book is actually equipped in a slot:

```python
# In aggregate_stats():
# First check if Book is in an equipped slot
for slot_key in ['slot0', 'slot1', 'slot2']:
    if artifact_key == 'book_of_ancient':
        book_of_ancient_stars = stars
        break

# NOT: Always set if owned in inventory (this overvalues other artifacts)
```

### 5. Use try/finally When Temporarily Modifying User Data

```python
original_pots = deepcopy(user_data.equipment_potentials.get(slot, {}))
user_data.equipment_potentials[slot] = test_pots

try:
    result = calculate_dps(...)
finally:
    user_data.equipment_potentials[slot] = original_pots  # Always restore
```

## Testing Artifacts

### Quick Test for Artifact DPS Values

```python
from artifact_optimizer import calculate_active_effect_dps

def mock_dps(stats, mode):
    # Implement minimal DPS calc that responds to relevant stats
    return {'total': base * (1 + stats.get('damage_pct', 0)/100)}

dps_gain = calculate_active_effect_dps(
    artifact_key='book_of_ancient',
    stars=5,
    current_stats={'crit_rate': 110, 'crit_damage': 150, 'book_of_ancient_stars': 0},
    calculate_dps_func=mock_dps,
    scenario='chapter_hunt',
)
print(f"Book at 5★: {dps_gain:.2f}% DPS")
```

### Verify Artifact Ranking

```python
from artifact_optimizer import get_artifact_ranking_for_equip

ranking = get_artifact_ranking_for_equip(
    owned_artifacts=owned,
    scenario='chapter_hunt',
    current_stats=stats,
    calculate_dps_func=dps_func,
)
for i, score in enumerate(ranking[:5]):
    print(f"{i+1}. {score.artifact_name}: {score.equip_value:.2f}")
```
