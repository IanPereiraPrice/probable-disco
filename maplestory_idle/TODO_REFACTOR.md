# TODO: Refactoring Tasks

This file tracks technical debt and refactoring items to address later.

---

## Artifacts.py - Resonance Bonus Implementation

**File:** `maplestory_idle/artifacts.py`
**Function:** `ArtifactConfig.get_resonance_bonus()` (around line 704)

**Issue:** The current implementation uses a linear approximation for resonance stats:
```python
main_stat_per_star = 10.0
hp_per_star = 100.0
return {
    "main_stat_flat": resonance * main_stat_per_star,
    "max_hp": resonance * hp_per_star,
}
```

**Problem:** Resonance stats follow a geometric series (not linear). The proper calculation is already implemented in `calculate_resonance_stats_at_level(level)` which uses the correct formula.

**Fix:** Replace the linear approximation with:
```python
return calculate_resonance_stats_at_level(resonance)
```

**Priority:** Low - the linear approximation is close for typical resonance levels but becomes inaccurate at high levels.

---
