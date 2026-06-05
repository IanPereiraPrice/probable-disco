# MapleStory Idle - Datamine Reference

Source: `maplestory_idle/data_mine/TextAsset/`

---

## File Structure Overview

### Hero.{Class}.json - Animation State Machines
These files define the animation states for each class, including skill cast animations.
Each entry has:
- **Name** - Animation state name (skill ID number or descriptive name)
- **LastFrame** - Total frame count for the animation
- **Events** - Array of animation events with StartFrame/EndFrame and effect/sound data

**Available Files:**
| File | CreatureIndex | Class |
|------|--------------|-------|
| Hero.Hero.json | 1 | Hero (Warrior) |
| Hero.DarkKnight.json | 3 | Dark Knight |
| Hero.ArchMageIL.json | 4 | Arch Mage I/L |
| Hero.ArchMageFP.json | 5 | Arch Mage F/P |
| Hero.BowMaster.json | 7 | BowMaster |
| Hero.Marksman.json | 8 | Marksman |
| Hero.NightLord.json | 9 | Night Lord |
| Hero.Shadower.json | 10 | Shadower |

### HeroSkillTable.json - Skill Registry
Maps CreatureIndex + SkillIndex to job step (job tier), skill type, and level requirements.
- `CreatureIndex` - Which class
- `SkillIndex` - Internal skill ID (format: `{CreatureIndex}{JobStep}{SkillNum}xx`)
- `JobStep` - 1-4 (1st through 4th job)
- `HeroSkillType` - `ActiveSkill` or `PassiveSkill`
- `RequireLevel` - Level needed to unlock
- `ExtraSkillIndex` - Linked/extra skill (e.g., Assassinate combo part 2)

### HeroJobStepTable.json - Job Advancement
Maps CreatureIndex to class with stat bonuses at each job step.
Contains `BannerImagePath` that confirms class identity (e.g., `Banner:Banner_Shadower`).

### Other Relevant Files
| File | Contents |
|------|----------|
| HeroSkillMasteryTable.json | Mastery node data |
| HeroSkillEnhanceTable.json | Skill enhancement data |
| HeroSkillLevelCostTable.json | Skill point costs |
| HeroLevelTable.json | Level-up stat requirements |
| HeroJobRankTable.json | Job ranking data |
| HeroPowerAbility*.json | Hero Power (inner ability) tables |

### Per-Skill Effect Files
Named `{SkillName}_{Class}_{Type}.json` where Type is Hit, Loop, LoopEnd, Dot, Fire, etc.
These define visual effects and hit properties. Example Shadower files:
- `DarkFlare_Shadower_Hit.json` - Dark Flare hit effect
- `DarkFlare_Shadower_Loop.json` - Dark Flare looping attack
- `SuddenRaid_Shadower_Hit.json` / `SuddenRaid_Shadower_Dot.json`
- `ShadowPartner_Shadower_Summoned.json` / `ShadowPartner_Shadower_Loop.json`
- `Fake_Shadower_Fire.json` - Shadow decoy effect

---

## Frame Rate

**Assumed: 30 FPS** (frames per second)

Evidence:
- All classes have `Attack1.LastFrame = 30` (base attack)
- Base attack cast time in skills.py = 1.0 seconds
- 30 frames / 30 FPS = 1.0 seconds (consistent)
- Knockback animation = 15 frames = 0.5s (reasonable)
- BowMaster Hurricane keydown phases repeat every 30 frames = 1.0s per hit

**Conversion: `seconds = LastFrame / 30`**

---

## CreatureIndex Mapping

| Index | Class | Skill ID Prefix |
|-------|-------|-----------------|
| 1 | Hero (Warrior) | 1xxxx |
| 2 | Paladin | 2xxxx |
| 3 | Dark Knight | 3xxxx |
| 4 | Arch Mage I/L | 4xxxx |
| 5 | Arch Mage F/P | 5xxxx |
| 6 | (Unknown/Incomplete) | 6xxxx |
| 7 | BowMaster | 7xxxx |
| 8 | Marksman | 8xxxx |
| 9 | Night Lord | 9xxxx |
| 10 | Shadower | 10xxxx |

**Skill ID Convention:** `{CreaturePrefix}{JobStep}{SkillNumber}0`
- Example: 103030 = Creature 10 (Shadower), Job 3 (3rd), Skill 03, variant 0

---

## Shadower (CreatureIndex 10) - Animation Data

### Skill-to-Animation Mapping

| Animation Name | Frames | Cast Time (s) | Skill Name | Job/Level | Evidence |
|---------------|--------|---------------|------------|-----------|----------|
| Attack1 | 30 | 1.00 | Basic Attack (pre-4th) | Generic | "stabO1" animation |
| 101010 | 30 | 1.00 | Double Stab | 1st / Lv1 | DoubleStab_Casting effect |
| 101030 | 6 | 0.20 | Dark Sight | 1st / Lv15 | Alert anim (toggle/buff) |
| 102010 | 30 | 1.00 | Savage Blow | 2nd / Lv30 | SavageBlow_Casting effect |
| 103010 | 30 | 1.00 | Edge Carnival | 3rd / Lv60 | EdgeCarnival_Casting effect |
| 103020 | 30 | 1.00 | Muspelheim | 3rd / Lv63 | Muspelheim_Casting effect |
| 103030 | 30 | 1.00 | Meso Explosion | 3rd / Lv66 | MesoExplosion_Casting + ShadowPartner variant |
| 103040 | 30 | 1.00 | Dark Flare (summon) | 3rd / Lv69 | DarkFlare_Shadower_Casting effect |
| 103070 | 30 | 1.00 | Into Darkness | 3rd / Lv74 | IntoDarkness_Casting effect |
| **Assassination** | **22** | **0.73** | **Assassinate (basic)** | **4th / Lv100** | 4221014_effect, "assassinationNew" sprite |
| AssassinationAdd | 30 | 1.00 | Assassinate part 2 | 4th | 4221016_effect, "assassinationNew2" sprite |
| AssassinationAdd_Bloody | 30 | 1.00 | Assassinate Bloody pt2 | 4th | 4221016_effect2 variant |
| CruelStab | 30 | 1.00 | Cruel Stab | 4th / Lv103 | 4221017_effect, "cruelStab" sprite |
| SmokeShell | 25 | 0.83 | Smoke Shell (buff) | 4th / Lv105 | "smokeshellNew" sprite, self-effect only |
| **SuddenRaid** | **39** | **1.30** | **Sudden Raid** | **4th / Lv110** | 4221010_effect, "suddenRaid" sprite |

### Shadower Skill Table (HeroSkillTable, CreatureIndex=10)

| SkillIndex | JobStep | Type | Level | Notes |
|------------|---------|------|-------|-------|
| 101010 | 1 | Active | 1 | Double Stab |
| 101020 | 1 | Passive | 10 | |
| 101030 | 1 | Active | 15 | Dark Sight |
| 101040 | 1 | Passive | (tutorial) | |
| 102010 | 2 | Active | 30 | Savage Blow |
| 102020 | 2 | Passive | 35 | |
| 102030 | 2 | Passive | 50 | |
| 102040 | 2 | Passive | 33 | |
| 102050 | 2 | Passive | 40 | |
| 102060 | 2 | Passive | 43 | |
| 102070 | 2 | Passive | 38 | |
| 102080 | 2 | Passive | 45 | |
| 103010 | 3 | Active | 60 | Edge Carnival |
| 103020 | 3 | Active | 63 | Muspelheim |
| 103030 | 3 | Active | 66 | Meso Explosion (has ExtraSkill 103031) |
| 103040 | 3 | Active | 69 | Dark Flare |
| 103050 | 3 | Passive | 60 | |
| 103060 | 3 | Passive | 72 | |
| 103070 | 3 | Active | 74 | Into Darkness |
| 103080 | 3 | Passive | 75 | |
| 104010 | 4 | Active | 100 | Assassinate (basic attack) |
| 104020 | 4 | Active | 103 | Cruel Stab |
| 104030 | 4 | Active | 105 | Smoke Shell |
| 104040 | 4 | Active | 110 | Sudden Raid |
| 104050 | 4 | Passive | 107 | (has ExtraSkill 104051) |
| 104060 | 4 | Passive | 125 | |
| 104070 | 4 | Passive | 115 | (has ExtraSkill 104071) |
| 104080 | 4 | Passive | 117 | |
| 104090 | 4 | Passive | 120 | |
| 104100 | 4 | Passive | 100 | |

### Key Observations - Shadower
1. **Assassinate is faster than default**: 22 frames (0.73s) vs 30 frames (1.0s) for most skills
2. **Assassinate has a two-part animation**: Part 1 (22f) + Part 2 (30f). In-game likely plays Part 1 as the main attack, with Part 2 as a follow-up/visual
3. **Sudden Raid has a long cast**: 39 frames (1.30s) - the longest Shadower animation
4. **Most 3rd job skills are uniform**: All 30 frames (1.0s)
5. **Smoke Shell buff is moderately fast**: 25 frames (0.83s)
6. **Dark Sight is instant-like**: 6 frames (0.20s) - just a toggle

---

## Night Lord (CreatureIndex 9) - Animation Data

| Animation Name | Frames | Cast Time (s) | Skill Name | Notes |
|---------------|--------|---------------|------------|-------|
| Attack1 | 30 | 1.00 | Basic Attack (pre-4th) | "swingO1" |
| LuckySeven | 30 | 1.00 | Lucky Seven | 1st job |
| DarkSight | 6 | 0.20 | Dark Sight | Toggle/buff |
| WindTalisman | 30 | 1.00 | Wind Talisman | 2nd job |
| TripleThrow | 30 | 1.00 | Triple Throw | 3rd job |
| ShurikenChallenge | 30 | 1.00 | Shuriken Challenge | 3rd job |
| ShurikenBurst | 30 | 1.00 | Shuriken Burst | 3rd job |
| DarkFlare | 30 | 1.00 | Dark Flare (summon) | 3rd job |
| ShadowRush | 12 | 0.40 | Shadow Rush | 3rd job (gap closer) |
| **QuadrupleThrow** | **21** | **0.70** | **Quad Throw (basic)** | **4th job, fastest basic attack** |
| ShowDownChallenge | 30 | 1.00 | Showdown Challenge | 4th job |
| **SuddenRaid** | **39** | **1.30** | **Sudden Raid** | **4th job, same as Shadower** |
| PurgeArea | 18 | 0.60 | Purge Area | 4th job buff |

### NL Skill Table (HeroSkillTable, CreatureIndex=9)

| SkillIndex | JobStep | Type | Level | Notes |
|------------|---------|------|-------|-------|
| 91010 | 1 | Active | 1 | Lucky Seven |
| 91020 | 1 | Passive | 10 | |
| 91030 | 1 | Active | 15 | |
| 91040 | 1 | Passive | (tutorial) | |
| 92010 | 2 | Active | 30 | (has ExtraSkill 92011) |
| 92020 | 2 | Active | 35 | |
| 92030 | 2 | Active | 50 | (DisableSkillLevel) |
| 92040 | 2 | Passive | 43 | (has ExtraSkill 92041) |
| 92050 | 2 | Passive | 40 | |
| 92060 | 2 | Passive | 33 | |
| 92070 | 2 | Passive | 45 | |
| 92080 | 2 | Passive | 38 | |
| 93010 | 3 | Active | 60 | |
| 93020 | 3 | Active | 63 | |
| 93030 | 3 | Passive | 60 | |
| 93040 | 3 | Active | 69 | |
| 93050 | 3 | Passive | 72 | |
| 93060 | 3 | Passive | 74 | |
| 93070 | 3 | Passive | 75 | |
| 93080 | 3 | Passive | 66 | |
| 94010 | 4 | Active | 100 | Quad Throw (basic) |
| 94020 | 4 | Active | 103 | |
| 94030 | 4 | Active | 105 | |
| 94040 | 4 | Active | 110 | |
| 94050 | 4 | Passive | 107 | |
| 94060 | 4 | Passive | 125 | |
| 94070 | 4 | Passive | 115 | (has ExtraSkill 94071) |
| 94080 | 4 | Passive | 117 | |
| 94090 | 4 | Passive | 120 | |
| 94100 | 4 | Passive | 100 | |

### Key Observations - Night Lord
1. **Quad Throw is the fastest basic attack**: 21 frames (0.70s) vs Assassinate's 22 frames
2. **Shadow Rush is very fast**: 12 frames (0.40s) - a gap closer, not sustained damage
3. **Purge Area is quick**: 18 frames (0.60s) - likely a buff/debuff

---

## BowMaster (CreatureIndex 7) - Animation Data

| Animation Name | Frames | Cast Time (s) | Skill Name | Notes |
|---------------|--------|---------------|------------|-------|
| Attack1 | 30 | 1.00 | Basic Attack | "shoot1" |
| 71010 | 30 | 1.00 | Arrow Blow | 1st job, 3 arrows (frames 12/15/18) |
| 72010 | 30 | 1.00 | Arrows of Wind | 2nd job |
| 72020 | 30 | 1.00 | Retreat Shot | 2nd job (has jump + end effects) |
| **73010** | **20** | **0.67** | **Arrow Platter (summon)** | **3rd job, fast summon cast** |
| 73020 | 30 | 1.00 | (passive/buff anim) | 3rd job |
| **73030** | **20** | **0.67** | **Phoenix (summon)** | **3rd job, fast summon cast** |
| **73040** | **20** | **0.67** | **Quiver Flow (summon)** | **3rd job, fast summon cast** |
| SharpEyes | 18 | 0.60 | Sharp Eyes (buff) | |
| ArrowPlatter | 20 | 0.67 | Arrow Platter (named) | Duplicate of 73010 |
| UncountableArrow | 30 | 1.00 | Uncountable Arrow | 4th job, "uncountableArrow" sprite |
| WindArrow2 | 30 | 1.00 | Wind Arrow v2 | 4th job (upgraded Arrows of Wind) |
| **StormArrow** | **150** | **5.00** | **Hurricane (channel)** | **4th job, channeled skill** |
| **StormArrow2** | **240** | **8.00** | **Hurricane v2 (channel)** | **4th job, extended channel** |

### BowMaster Skill Table (HeroSkillTable, CreatureIndex=7)

| SkillIndex | JobStep | Type | Level | Notes |
|------------|---------|------|-------|-------|
| 71010 | 1 | Active | 1 | Arrow Blow |
| 71020 | 1 | Passive | (tutorial) | |
| 71030 | 1 | Passive | 15 | |
| 71040 | 1 | Passive | 10 | |
| 72010 | 2 | Active | 30 | Arrows of Wind |
| 72020 | 2 | Active | 35 | Retreat Shot |
| 72030 | 2 | Passive | 40 | |
| 72040 | 2 | Passive | 33 | |
| 72050 | 2 | Passive | 45 | |
| 72060 | 2 | Passive | 43 | |
| 72070 | 2 | Passive | 50 | |
| 72080 | 2 | Passive | 38 | |
| 73010 | 3 | Active | 60 | Arrow Platter |
| 73020 | 3 | Passive | 60 | |
| 73030 | 3 | Active | 69 | Phoenix |
| 73040 | 3 | Active | 63 | Quiver Flow |
| 73050 | 3 | Passive | 75 | |
| 73060 | 3 | Passive | 72 | |
| 73070 | 3 | Passive | 66 | |
| 73080 | 3 | Passive | 74 | |
| 74010 | 4 | Active | 100 | Arrow Stream (basic) |
| 74020 | 4 | Active | 103 | Hurricane |
| 74030 | 4 | Active | 115 | |
| 74040 | 4 | Passive | 110 | |
| 74050 | 4 | Passive | 107 | |
| 74060 | 4 | Passive | 120 | |
| 74070 | 4 | Passive | 117 | (has ExtraSkill 74071) |
| 74080 | 4 | Passive | 105 | |
| 74090 | 4 | Passive | 125 | |
| 74100 | 4 | Passive | 100 | |

### Key Observations - BowMaster
1. **Summon casts are fast**: Phoenix, Arrow Platter, Quiver all at 20 frames (0.67s)
2. **Hurricane is a channel, not a cast**: StormArrow (150f) and StormArrow2 (240f) are full channel durations
3. **Hurricane tick interval = 30 frames (1.0s)**: Keydown effect repeats at frames 16-45, 45-75, 75-105, 105-135 (every 30 frames)
4. **StormArrow vs StormArrow2**: Version 1 has 4 hit phases (150f), Version 2 has 7 hit phases (240f) - likely before/after mastery upgrade
5. **Arrow Blow fires 3 arrows**: At frames 12, 15, 18 (staggered by 3 frames = 0.1s apart)

---

## Cross-Class Cast Time Comparison

### Basic Attacks (4th Job)
| Class | Skill | Frames | Cast Time | Relative Speed |
|-------|-------|--------|-----------|----------------|
| Night Lord | Quad Throw | 21 | 0.70s | Fastest (30% faster) |
| Shadower | Assassinate | 22 | 0.73s | Fast (27% faster) |
| BowMaster | Arrow Stream | 30 | 1.00s | Standard baseline |

### Sudden Raid (Shared)
Both NL and Shadower: 39 frames = 1.30s (30% slower than standard)

### Buff Activations
| Skill | Frames | Cast Time | Class |
|-------|--------|-----------|-------|
| Dark Sight | 6 | 0.20s | NL/Shadower |
| Sharp Eyes | 18 | 0.60s | BowMaster |
| Purge Area | 18 | 0.60s | Night Lord |
| Smoke Shell | 25 | 0.83s | Shadower |

### Summon Casts
| Skill | Frames | Cast Time | Class |
|-------|--------|-----------|-------|
| Phoenix | 20 | 0.67s | BowMaster |
| Arrow Platter | 20 | 0.67s | BowMaster |
| Quiver Flow | 20 | 0.67s | BowMaster |
| Dark Flare | 30 | 1.00s | NL/Shadower |

---

## Implications for DPS Modeling (skills.py)

### Current State
- skills.py uses `cast_time = 1.0s` as default for all skills
- Attack speed multiplier scales this: `effective_cast_time = 1.0 / attack_speed_mult`
- This means NL's Quad Throw and Shadower's Assassinate are modeled ~30% slower than datamine shows

### Potential Improvements
If datamine cast times are accurate to gameplay:
1. **Assassinate base cast time should be 0.73s** (not 1.0s)
2. **Quad Throw base cast time should be 0.70s** (not 1.0s)
3. **Sudden Raid cast time should be 1.30s** (not 1.0s) - reduces its DPS contribution
4. **BM summon casts should be 0.67s** - less time "lost" when casting summons
5. **Hurricane tick interval**: confirmed at 1.0s base from keydown phase spacing

### Caveats
- Frame counts represent animation duration, which MAY not equal the game's internal cast time
- The game might use animation canceling, allowing the next action before the animation finishes
- Attack speed might scale differently for different frame-count skills
- These values need verification against in-game behavior before changing DPS calculations

---

## Job Advancement Stats (from HeroJobStepTable)

All classes receive the same stat bonuses at each job step:

| Job Step | Required Level | Attack Bonus | Max HP Bonus |
|----------|---------------|-------------|-------------|
| 1st Job | 1 (tutorial) | +10 | +50 |
| 2nd Job | 30 | +200 | +1,000 |
| 3rd Job | 60 | +1,000 | +5,000 |
| 4th Job | 100 | +5,000 | +25,000 |

---

## Data Not In These Files

The Hero.{Class}.json files contain animation/visual data ONLY. They do NOT contain:
- Skill damage percentages
- Skill cooldowns
- Number of hits/targets
- Mastery effects
- Buff durations/values
- Proc rates

These gameplay values must be sourced from in-game screenshots/wiki or potentially from other datamine tables (HeroSkillEnhanceTable, etc.) that we haven't fully explored yet.
