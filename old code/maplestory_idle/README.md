# MapleStory Idle - Game Mechanics Library

A Python library for MapleStory Idle damage calculations, stat optimization, and game system analysis.

**Last Updated:** December 2025  
**Character:** Bowmaster Lv.96 - Quarts

## Project Structure

```
maplestory_idle/
├── __init__.py           # Package initialization
├── constants.py          # Shared enums, constants, reference data
├── formulas.py           # Core damage formulas (VERIFIED)
├── equipment.py          # Equipment, starforce, potentials
├── artifacts.py          # Artifact system and awakening
├── calculator.py         # Interactive CLI calculator
└── MAPLESTORY_KNOWLEDGE_BASE.md  # Complete documentation
```

## Installation

```bash
# Clone or copy the maplestory_idle folder to your project
cd your_project
# No external dependencies required - pure Python
```

## Quick Start

```python
from maplestory_idle import (
    calculate_total_dex,
    calculate_damage_percent,
    calculate_final_damage,
    calculate_defense_penetration,
)

# Calculate total DEX
dex = calculate_total_dex(flat_pool=18700, percent_dex=1.265)
print(f"Total DEX: {dex:,.0f}")  # 42,346

# Calculate Final Damage (multiplicative)
fd_sources = {"bottom": 0.13, "guild": 0.10, "extreme_archery": 0.217}
fd = calculate_final_damage(fd_sources)
print(f"Final Damage: {fd * 100:.1f}%")  # 51.8%

# Calculate Defense Penetration (multiplicative)
def_pen = calculate_defense_penetration([0.424, 0.19, 0.165])
print(f"Defense Pen: {def_pen * 100:.1f}%")  # 60.9%
```

## Interactive Calculator

```bash
python -m maplestory_idle.calculator
```

## Verified Formulas

### Master Damage Formula
```
Damage = ATK × (1 + Stat%) × (1 + Damage%) × (1 + DamageAmp%) × 
         (1 + FinalDamage%) × (1 + CritDamage%) × DefenseMultiplier
```

### Stat Stacking Types

| Stat | Stacking | Notes |
|------|----------|-------|
| DEX % | Additive | All sources sum |
| Damage % | Additive | Hex Necklace multiplies total |
| Damage Amp | Additive | Separate multiplier (scrolls only) |
| Final Damage | **Multiplicative** | Each source multiplies |
| Defense Pen | **Multiplicative** | Each source multiplies |
| Crit Rate/Damage | Additive | All sources sum |

### Key Constants

- **Damage Amp Divisor:** 396.5 (formula: 1 + amp/396.5)
- **Hex Necklace:** ×1.24 per stack (max 3 = ×1.72)
- **Book of Ancient:** CD bonus = CR × 0.36

## Modules

### `formulas.py`
Core damage calculations with verified formulas from empirical testing.

### `equipment.py`
- Starforce enhancement tables (stages 0-25)
- Stat amplification calculations
- Potential system probabilities
- Expected cost calculators

### `artifacts.py`
- Artifact definitions (Hexagon, Book of Ancient, Fire Flower)
- Awakening progression and costs
- Active/inventory effect calculations

### `constants.py`
- All enums and shared constants
- Enemy defense values
- Shop prices
- Stat stacking reference

## Known Data Points

### Enemy Defense Values (Verified)
- Maple Island 1-1: 0.0
- Aquarium 14: 0.388
- Mu Lung 27-1: 0.752
- World Boss (King Castle Golem): 6.527

### Bowmaster Final Damage Sources
- Bottom (pot + bonus): 13%
- Guild Skill: 10%
- Extreme Archery: Bow: 21.7%
- Mortal Blow: 14.4% (conditional)
- Fire Flower: 1.2% per target (max 12%)

## TODO / Data Gaps

1. [ ] Starforce stages 20-25 need verification
2. [ ] Missing ~3,320 flat DEX sources
3. [ ] Mythic rarity stat ranges
4. [ ] Set bonus contributions
5. [ ] Medal income rate for planning

## Testing Methodology

When testing stat changes:
1. Remove ONE source at a time
2. Record before/after values exactly
3. Calculate ratio to determine additive vs multiplicative
4. Verify with reverse calculation

**Additive test:** Remove X% → stat drops by exactly X%  
**Multiplicative test:** Remove X% → calculate (1-before) × (1-X) vs (1-after)

---

See `MAPLESTORY_KNOWLEDGE_BASE.md` for complete documentation.
