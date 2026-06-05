"""
Verification script: Compare hardcoded skill values in skills.py against SkillTable.json datamine.

Run from maplestory_idle directory:
    python verify_datamine.py
"""
import json
import os

# -------------------------------------------------------------
# Load datamine
# -------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data_mine", "TextAsset")

with open(os.path.join(DATA_DIR, "SkillTable.json")) as f:
    raw_skills = json.load(f)
SKILL_TABLE = {entry["SkillIndex"]: entry for entry in raw_skills}

with open(os.path.join(DATA_DIR, "SkillLevelFactorTable.json")) as f:
    raw_factors = json.load(f)
FACTOR_TABLE = {int(e["Level"]): [int(x) for x in e["Factor"]] for e in raw_factors}

# -------------------------------------------------------------
# Import our skill definitions
# -------------------------------------------------------------
from game.skills import BOWMASTER_SKILLS, NIGHT_LORD_SKILLS, SHADOWER_SKILLS


def get_damage_op(skill_entry):
    """Find the first GetDamageR operation in a SkillTable entry."""
    ops = skill_entry.get("Operations", [])
    for op in ops:
        if op and op.get("Type") == "GetDamageR":
            return op
    return None


def get_dot_op(skill_entry):
    """Find the first GetDotR operation in a SkillTable entry."""
    ops = skill_entry.get("Operations", [])
    for op in ops:
        if op and op.get("Type") == "GetDotR":
            return op
    return None


def get_value(val_str):
    """Convert datamine value string to int, handling 'None'."""
    if val_str is None or val_str == "None":
        return None
    return int(val_str)


# -------------------------------------------------------------
# Skill name -> SkillIndex mapping
# -------------------------------------------------------------

# (our_skill_name, datamine_skill_index, follow_up_skill_index_for_FB)
SHADOWER_MAP = [
    # 4th job
    ("cruel_stab", "104010", None),
    ("assassinate", "104020", "104021"),  # 104021 = finishing blow
    ("sudden_raid", "104030", None),
    ("smokescreen", "104040", None),
    # 3rd job
    ("midnight_carnival", "103010", None),
    ("phase_dash", "103020", None),
    ("meso_explosion", "103030", None),
    ("dark_flare", "103040", "103041"),  # 103041 = summon damage
]

NIGHT_LORD_MAP = [
    # 4th job
    ("showdown", "94010", None),
    ("quad_star", "94020", None),
    ("sudden_raid", "94030", None),
    # 3rd job
    ("shuriken_challenge", "93010", None),
    ("triple_throw", "93020", None),
    ("mark_of_assassin", "93031", None),  # 93031 = the actual damage proc
    ("dark_flare", "93040", "93041"),  # 93041 = summon damage
]

BOWMASTER_MAP = [
    # 4th job
    ("arrow_stream", "74010", None),
    ("hurricane", "74020", None),
    # 3rd job
    ("wind_arrow_ii", "73010", None),
    ("flash_mirage", "73020", None),
    ("phoenix", "73030", "73031"),  # 73031 = summon damage
    ("arrow_platter", "73040", "73041"),  # 73041 = summon damage
    # 2nd job
    ("covering_fire", "72020", None),
]


def compare_skill(class_name, skill_dict, skill_name, dm_index, fb_index=None):
    """Compare a single skill against datamine, printing results."""
    if skill_name not in skill_dict:
        print(f"  !! {skill_name}: NOT FOUND in our code")
        return

    skill = skill_dict[skill_name]
    dm_main = SKILL_TABLE.get(dm_index)

    if not dm_main:
        print(f"  !! {skill_name} ({dm_index}): NOT FOUND in SkillTable.json")
        return

    print(f"\n  {skill.name} (ours) vs SkillIndex {dm_index} (datamine):")

    issues = []

    # --- Cooldown ---
    dm_cd_ms = get_value(dm_main.get("CoolTimeMs"))
    dm_cd = dm_cd_ms / 1000.0 if dm_cd_ms else 0
    if skill.cooldown != dm_cd:
        status = "MISMATCH" if abs(skill.cooldown - dm_cd) > 0.5 else "CLOSE"
        issues.append(f"cooldown: ours={skill.cooldown}s, datamine={dm_cd}s [{status}]")
    else:
        print(f"    cooldown: {skill.cooldown}s OK")

    # --- Base damage ---
    # For summons, damage is in the follow-up skill
    dm_skill_for_damage = dm_main
    if fb_index and skill.base_damage_pct > 0:
        dm_follow = SKILL_TABLE.get(fb_index)
        if dm_follow:
            follow_dmg_op = get_damage_op(dm_follow)
            main_dmg_op = get_damage_op(dm_main)
            # Use follow-up if main doesn't have damage or if it's a summon/projectile
            if follow_dmg_op and (not main_dmg_op or dm_main.get("Operations", [None, {}])[1].get("Type") in ("CreateProjectile",)):
                dm_skill_for_damage = dm_follow

    dmg_op = get_damage_op(dm_skill_for_damage)
    if dmg_op:
        values = dmg_op.get("Values", [])
        dm_damage_raw = get_value(values[0]) if len(values) > 0 else None
        dm_damage_pct = dm_damage_raw / 10.0 if dm_damage_raw else None
        dm_hits = get_value(values[2]) if len(values) > 2 else None

        if dm_damage_pct is not None:
            if abs(skill.base_damage_pct - dm_damage_pct) < 0.1:
                print(f"    base_damage_pct: {skill.base_damage_pct}% OK")
            else:
                issues.append(f"base_damage_pct: ours={skill.base_damage_pct}%, datamine={dm_damage_pct}%")

        if dm_hits is not None:
            if skill.base_hits == dm_hits:
                print(f"    base_hits: {skill.base_hits} OK")
            else:
                issues.append(f"base_hits: ours={skill.base_hits}, datamine_Values[2]={dm_hits}")

        # ValueLevelFactors
        vlf = dmg_op.get("ValueLevelFactors")
        if vlf and len(vlf) >= 2:
            factor_idx = int(vlf[1])
            print(f"    level_factor_index: {factor_idx} (from ValueLevelFactors[1])")
    else:
        print(f"    (no GetDamageR operation found in datamine)")

    # --- DoT ---
    dot_op = get_dot_op(dm_main)
    if dot_op:
        dot_values = dot_op.get("Values", [])
        dm_dot_pct = get_value(dot_values[0]) / 10.0 if dot_values else None
        dm_dot_dur = get_value(dot_op.get("DurationMs")) / 1000.0 if dot_op.get("DurationMs") else None
        dm_dot_tick = get_value(dot_op.get("TickTimeMs")) / 1000.0 if dot_op.get("TickTimeMs") else None

        if hasattr(skill, 'dot_damage_pct') and skill.dot_damage_pct > 0:
            if dm_dot_pct and abs(skill.dot_damage_pct - dm_dot_pct) < 0.1:
                print(f"    dot_damage_pct: {skill.dot_damage_pct}% OK")
            elif dm_dot_pct:
                issues.append(f"dot_damage_pct: ours={skill.dot_damage_pct}%, datamine={dm_dot_pct}%")
        else:
            issues.append(f"MISSING DoT in our code: datamine has {dm_dot_pct}% / {dm_dot_dur}s / {dm_dot_tick}s tick")

    # --- Finishing blow (for Assassinate-type skills) ---
    if fb_index and hasattr(skill, 'finishing_blow_pct') and skill.finishing_blow_pct > 0:
        fb_entry = SKILL_TABLE.get(fb_index)
        if fb_entry:
            fb_op = get_damage_op(fb_entry)
            if fb_op:
                fb_values = fb_op.get("Values", [])
                dm_fb_pct = get_value(fb_values[0]) / 10.0 if fb_values else None
                if dm_fb_pct and abs(skill.finishing_blow_pct - dm_fb_pct) < 0.1:
                    print(f"    finishing_blow_pct: {skill.finishing_blow_pct}% OK")
                elif dm_fb_pct:
                    issues.append(f"finishing_blow_pct: ours={skill.finishing_blow_pct}%, datamine={dm_fb_pct}%")

                fb_vlf = fb_op.get("ValueLevelFactors")
                if fb_vlf and len(fb_vlf) >= 2:
                    print(f"    finishing_blow_factor_index: {int(fb_vlf[1])}")

    # --- Print issues ---
    for issue in issues:
        print(f"    XX {issue}")

    if not issues:
        print(f"    -- ALL CLEAR --")


def main():
    print("=" * 70)
    print("DATAMINE VERIFICATION REPORT")
    print("Comparing hardcoded skills.py values vs SkillTable.json")
    print("=" * 70)

    print("\n" + "-" * 50)
    print("SHADOWER")
    print("-" * 50)
    for skill_name, dm_idx, fb_idx in SHADOWER_MAP:
        compare_skill("Shadower", SHADOWER_SKILLS, skill_name, dm_idx, fb_idx)

    print("\n" + "-" * 50)
    print("NIGHT LORD")
    print("-" * 50)
    for skill_name, dm_idx, fb_idx in NIGHT_LORD_MAP:
        compare_skill("Night Lord", NIGHT_LORD_SKILLS, skill_name, dm_idx, fb_idx)

    print("\n" + "-" * 50)
    print("BOWMASTER")
    print("-" * 50)
    for skill_name, dm_idx, fb_idx in BOWMASTER_MAP:
        compare_skill("BowMaster", BOWMASTER_SKILLS, skill_name, dm_idx, fb_idx)

    # ---------------------------------------------------------
    # Factor table spot-check
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("FACTOR TABLE SPOT-CHECK (Assassinate at skill level 6)")
    print("=" * 70)
    factors_l6 = FACTOR_TABLE.get(6)
    if factors_l6:
        main_factor = factors_l6[21]
        fb_factor = factors_l6[12]
        print(f"  Factor[21] at L6 = {main_factor} -> 1400 × {main_factor}/1000 = {1400 * main_factor / 1000}%")
        print(f"  Factor[12] at L6 = {fb_factor} -> 3000 × {fb_factor}/1000 = {3000 * fb_factor / 1000}%")
        print(f"  Expected in-game: 1433.6% / 3090% (user confirmed)")


if __name__ == "__main__":
    main()
