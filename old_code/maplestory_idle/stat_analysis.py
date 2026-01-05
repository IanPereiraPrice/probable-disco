"""
MapleStory Idle - Stat Analysis Tool
=====================================
Compares calculated stats from all modeled sources vs actual in-game stats.

Usage: python stat_analysis.py
"""

import sys
import os
import csv

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from equipment import EQUIPMENT_SLOTS
from cubes import PotentialLine, StatType, PotentialTier
from artifacts import ArtifactConfig, ArtifactInstance
from hero_power import HeroPowerConfig, HeroPowerLine, HeroPowerStatType, HeroPowerTier, HeroPowerPassiveConfig, HeroPowerPassiveStatType
from guild import GuildConfig
from companions import CompanionConfig
from skills import get_global_mastery_stats, BOWMASTER_SKILLS, SkillType
from maple_rank import MapleRankConfig
from equipment_sets import EquipmentSetsConfig, MedalConfig, CostumeConfig
from weapons import WeaponConfig, WeaponRarity


# =============================================================================
# TARGET STATS (From In-Game Screenshots)
# =============================================================================

TARGET_STATS = {
    "attack": 48_788_000,
    "dex": 70_436,
    "damage_percent": 1185.7,
    "damage_amp": 34.1,
    "crit_rate": 128.9,
    "crit_damage": 246.5,
    "defense_pen": 45.8,
    "boss_damage": 82.7,
    "normal_damage": 143.4,
    "final_damage": 65.8,
    "all_skills": 48,
    "2nd_job_skills": 26,
    "3rd_job_skills": 18,
    "4th_job_skills": 11,
    "min_dmg_mult": 264.3,
    "max_dmg_mult": 293.7,
    "skill_damage": 61.0,
    "basic_attack_damage": 47.9,
    "attack_speed": 103.5,
    "accuracy": 315,
}


def load_saved_configs():
    """Load saved configurations from CSV files."""
    base_path = os.path.dirname(os.path.abspath(__file__))

    configs = {}

    # 1. Load Maple Rank
    mr_file = os.path.join(base_path, "maple_rank_save.csv")
    if os.path.exists(mr_file):
        mr_config = MapleRankConfig()
        try:
            with open(mr_file, 'r') as f:
                reader = csv.DictReader(f)
                mr_data = {}
                for row in reader:
                    mr_data[row['stat']] = row['value']

            mr_config.current_stage = int(mr_data.get('current_stage', 1))
            mr_config.main_stat_level = int(mr_data.get('main_stat_level', 0))
            mr_config.special_main_stat_points = int(mr_data.get('special_main_stat_points', 0))
            mr_config.damage_percent_level = int(mr_data.get('damage_percent', 0))
            mr_config.boss_damage_level = int(mr_data.get('boss_damage', 0))
            mr_config.normal_damage_level = int(mr_data.get('normal_damage', 0))
            mr_config.skill_damage_level = int(mr_data.get('skill_damage', 0))
            mr_config.crit_damage_level = int(mr_data.get('crit_damage', 0))
            mr_config.crit_rate_level = int(mr_data.get('crit_rate', 0))
            mr_config.min_dmg_mult_level = int(mr_data.get('min_dmg_mult', 0))
            mr_config.max_dmg_mult_level = int(mr_data.get('max_dmg_mult', 0))
            mr_config.attack_speed_level = int(mr_data.get('attack_speed', 0))
            mr_config.accuracy_level = int(mr_data.get('accuracy', 0))
            configs['maple_rank'] = mr_config
        except Exception as e:
            print(f"  Error loading Maple Rank: {e}")
            configs['maple_rank'] = MapleRankConfig()
    else:
        configs['maple_rank'] = MapleRankConfig()

    # 2. Load Hero Power Passive
    hpp_file = os.path.join(base_path, "hero_power_passive_save.csv")
    if os.path.exists(hpp_file):
        hpp_config = HeroPowerPassiveConfig()
        try:
            with open(hpp_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stat_type = row['stat_type']
                    level = int(row['level'])
                    if stat_type == 'main_stat':
                        hpp_config.main_stat_level = level
                    elif stat_type == 'damage_percent':
                        hpp_config.damage_percent_level = level
                    elif stat_type == 'attack':
                        hpp_config.attack_level = level
                    elif stat_type == 'max_hp':
                        hpp_config.max_hp_level = level
                    elif stat_type == 'accuracy':
                        hpp_config.accuracy_level = level
                    elif stat_type == 'defense':
                        hpp_config.defense_level = level
            configs['hero_power_passive'] = hpp_config
        except Exception as e:
            print(f"  Error loading Hero Power Passive: {e}")
            configs['hero_power_passive'] = HeroPowerPassiveConfig()
    else:
        configs['hero_power_passive'] = HeroPowerPassiveConfig()

    # 3. Load Hero Power Ability Lines
    hp_file = os.path.join(base_path, "hero_power_save.csv")
    if os.path.exists(hp_file):
        hp_config = HeroPowerConfig()
        try:
            with open(hp_file, 'r') as f:
                reader = csv.DictReader(f)
                lines = []
                for row in reader:
                    stat_type_str = row['stat_type']
                    value = float(row['value'])
                    tier_str = row['tier']

                    # Map stat type
                    stat_map = {
                        'damage': HeroPowerStatType.DAMAGE,
                        'boss_damage': HeroPowerStatType.BOSS_DAMAGE,
                        'crit_damage': HeroPowerStatType.CRIT_DAMAGE,
                        'def_pen': HeroPowerStatType.DEF_PEN,
                        'main_stat': HeroPowerStatType.MAIN_STAT,
                        'attack_pct': HeroPowerStatType.ATTACK_PCT,
                        'min_dmg_mult': HeroPowerStatType.MIN_DMG_MULT,
                        'max_dmg_mult': HeroPowerStatType.MAX_DMG_MULT,
                    }
                    stat_type = stat_map.get(stat_type_str, HeroPowerStatType.DAMAGE)

                    tier_map = {
                        'rare': HeroPowerTier.RARE,
                        'epic': HeroPowerTier.EPIC,
                        'unique': HeroPowerTier.UNIQUE,
                        'legendary': HeroPowerTier.LEGENDARY,
                        'mystic': HeroPowerTier.MYSTIC,
                    }
                    tier = tier_map.get(tier_str, HeroPowerTier.RARE)

                    lines.append(HeroPowerLine(stat_type=stat_type, value=value, tier=tier))

                hp_config.lines = lines
            configs['hero_power'] = hp_config
        except Exception as e:
            print(f"  Error loading Hero Power: {e}")
            configs['hero_power'] = HeroPowerConfig()
    else:
        configs['hero_power'] = HeroPowerConfig()

    # 4. Load Companions
    comp_file = os.path.join(base_path, "companions_save.csv")
    if os.path.exists(comp_file):
        comp_config = CompanionConfig()
        try:
            comp_config.load_from_csv(comp_file)
            configs['companions'] = comp_config
        except Exception as e:
            print(f"  Error loading Companions: {e}")
            configs['companions'] = CompanionConfig()
    else:
        configs['companions'] = CompanionConfig()

    # 5. Load Weapons
    weapon_file = os.path.join(base_path, "weapons_save.csv")
    if os.path.exists(weapon_file):
        weapon_config = WeaponConfig()
        try:
            weapon_config.load_from_csv(weapon_file)
            configs['weapons'] = weapon_config
        except Exception as e:
            print(f"  Error loading Weapons: {e}")
            configs['weapons'] = WeaponConfig()
    else:
        configs['weapons'] = WeaponConfig()

    # 6. Load Artifacts
    art_file = os.path.join(base_path, "artifacts_save.csv")
    if os.path.exists(art_file):
        art_config = ArtifactConfig()
        try:
            art_config.load_from_csv(art_file)
            configs['artifacts'] = art_config
        except Exception as e:
            print(f"  Error loading Artifacts: {e}")
            configs['artifacts'] = ArtifactConfig()
    else:
        configs['artifacts'] = ArtifactConfig()

    return configs


def analyze_stat_sources():
    """Analyze all stat sources and compare to targets."""

    print("=" * 70)
    print("MAPLESTORY IDLE - STAT ANALYSIS")
    print("Loading saved configurations...")
    print("=" * 70)
    print()

    # Load saved configs
    configs = load_saved_configs()

    # Collect stats from each source
    sources = {}

    # 1. POTENTIALS (Equipment Cubes) - Need to load from CSV or estimate
    print("1. POTENTIALS (Equipment Cubes)")
    print("-" * 40)
    pot_stats = {
        "damage_percent": 0,
        "boss_damage": 0,
        "crit_damage": 0,
        "defense_pen": 0,
        "dex_percent": 0,
        "dex_flat": 0,
        "final_damage": 0,
        "all_skills": 0,
    }
    print("  Note: Potential stats need to be loaded from app state")
    sources["potentials"] = pot_stats

    # 2. ARTIFACTS
    print("\n2. ARTIFACTS")
    print("-" * 40)
    art_config = configs['artifacts']
    art_stats = art_config.get_all_stats()
    print(f"  Damage %: {art_stats.get('damage', 0) * 100:.1f}%")
    print(f"  Boss Damage %: {art_stats.get('boss_damage', 0) * 100:.1f}%")
    print(f"  Crit Damage %: {art_stats.get('crit_damage', 0) * 100:.1f}%")
    print(f"  Def Pen %: {art_stats.get('def_pen', 0) * 100:.1f}%")
    print(f"  Crit Rate %: {art_stats.get('crit_rate', 0) * 100:.1f}%")
    print(f"  Main Stat Flat: {art_stats.get('main_stat_flat', 0)}")
    print(f"  Attack Flat: {art_stats.get('attack_flat', 0)}")
    sources["artifacts"] = art_stats

    # 3. HERO POWER (Ability Lines)
    print("\n3. HERO POWER (Ability Lines)")
    print("-" * 40)
    hp_config = configs['hero_power']
    hp_stats = hp_config.get_all_stats()
    print(f"  Lines: {len(hp_config.lines)}")
    for i, line in enumerate(hp_config.lines):
        print(f"    L{i+1}: {line.stat_type.value} +{line.value:.1f}% ({line.tier.value})")
    print(f"  Def Pen %: {hp_stats.get('def_pen', 0):.1f}%")
    print(f"  Attack %: {hp_stats.get('attack_pct', 0):.1f}%")
    print(f"  Min Dmg Mult %: {hp_stats.get('min_dmg_mult', 0):.1f}%")
    print(f"  Max Dmg Mult %: {hp_stats.get('max_dmg_mult', 0):.1f}%")
    sources["hero_power"] = hp_stats

    # 4. HERO POWER PASSIVE STATS
    print("\n4. HERO POWER PASSIVE STATS")
    print("-" * 40)
    hpp_config = configs['hero_power_passive']
    hpp_stats = hpp_config.get_all_stats()
    print(f"  Main Stat Flat: {hpp_stats.get('main_stat_flat', 0):.0f}")
    print(f"  Damage %: {hpp_stats.get('damage_percent', 0):.1f}%")
    print(f"  Attack Flat: {hpp_stats.get('attack_flat', 0):.0f}")
    print(f"  Accuracy: {hpp_stats.get('accuracy', 0):.0f}")
    sources["hero_power_passive"] = hpp_stats

    # 5. GUILD (Using assumed max values)
    print("\n5. GUILD")
    print("-" * 40)
    guild_config = GuildConfig(
        final_damage=6,  # 3 skills: 3+3 = 6%
        damage=20,  # 2 skills: 10+10 = 20%
        main_stat=10,  # 10%
        crit_damage=15,  # 15%
        boss_damage=20,  # 20%
        def_pen=10,  # 10%
        attack_flat=1000,  # 1000 flat attack
        max_hp=10,
    )
    guild_stats = guild_config.get_all_stats()
    print(f"  Damage %: {guild_stats.get('damage', 0):.1f}%")
    print(f"  Boss Damage %: {guild_stats.get('boss_damage', 0):.1f}%")
    print(f"  Crit Damage %: {guild_stats.get('crit_damage', 0):.1f}%")
    print(f"  Def Pen %: {guild_stats.get('def_pen', 0):.1f}%")
    print(f"  Final Damage %: {guild_stats.get('final_damage', 0):.1f}%")
    print(f"  Main Stat %: {guild_stats.get('main_stat_pct', 0):.1f}%")
    print(f"  Attack Flat: {guild_stats.get('attack_flat', 0)}")
    sources["guild"] = guild_stats

    # 6. COMPANIONS
    print("\n6. COMPANIONS")
    print("-" * 40)
    comp_config = configs['companions']
    comp_stats = comp_config.get_all_stats()
    print(f"  Damage %: {comp_stats.get('damage', 0):.1f}%")
    print(f"  Flat Main Stat: {comp_stats.get('flat_main_stat', 0)}")
    print(f"  Boss Damage %: {comp_stats.get('boss_damage', 0):.1f}%")
    print(f"  Crit Rate %: {comp_stats.get('crit_rate', 0):.1f}%")
    print(f"  Min Dmg Mult %: {comp_stats.get('min_dmg_mult', 0):.1f}%")
    print(f"  Max Dmg Mult %: {comp_stats.get('max_dmg_mult', 0):.1f}%")
    print(f"  Attack Speed %: {comp_stats.get('attack_speed', 0):.1f}%")
    print(f"  Flat Attack: {comp_stats.get('flat_attack', 0)}")
    sources["companions"] = comp_stats

    # 7. PASSIVE SKILLS (from skills.py)
    print("\n7. PASSIVE SKILLS (from skills.py)")
    print("-" * 40)
    character_level = 290
    all_skills_bonus = 48
    mastery_stats = get_global_mastery_stats(character_level)
    print(f"  From Global Mastery (Lv.{character_level}):")
    for key, value in mastery_stats.items():
        print(f"    {key}: {value}")

    # Get PASSIVE_STAT skill contributions
    passive_stats = dict(mastery_stats)  # Copy mastery stats
    print(f"\n  From PASSIVE_STAT skills (+{all_skills_bonus} All Skills):")
    for skill_name, skill in BOWMASTER_SKILLS.items():
        if skill.skill_type == SkillType.PASSIVE_STAT:
            if character_level >= skill.unlock_level:
                effective_level = 1 + all_skills_bonus
                value = skill.base_stat_value + skill.stat_per_level * (effective_level - 1)
                stat_key = skill.stat_type

                # Aggregate into passive_stats
                if stat_key in passive_stats:
                    passive_stats[stat_key] += value
                else:
                    passive_stats[stat_key] = value

                print(f"    {skill_name}: +{value:.1f}% {stat_key}")
    sources["passives"] = passive_stats

    # 8. MAPLE RANK
    print("\n8. MAPLE RANK")
    print("-" * 40)
    mr_config = configs['maple_rank']
    mr_stats = mr_config.get_all_stats()
    print(f"  Stage: {mr_config.current_stage}, Main Stat Level: {mr_config.main_stat_level}")
    print(f"  Main Stat Flat: {mr_stats.get('main_stat_flat', 0):.0f}")
    print(f"  Damage %: {mr_stats.get('damage_percent', 0):.1f}%")
    print(f"  Boss Damage %: {mr_stats.get('boss_damage', 0):.1f}%")
    print(f"  Normal Damage %: {mr_stats.get('normal_damage', 0):.1f}%")
    print(f"  Crit Damage %: {mr_stats.get('crit_damage', 0):.1f}%")
    print(f"  Crit Rate %: {mr_stats.get('crit_rate', 0):.1f}%")
    print(f"  Skill Damage %: {mr_stats.get('skill_damage', 0):.1f}%")
    print(f"  Min Dmg Mult %: {mr_stats.get('min_dmg_mult', 0):.1f}%")
    print(f"  Max Dmg Mult %: {mr_stats.get('max_dmg_mult', 0):.1f}%")
    print(f"  Attack Speed %: {mr_stats.get('attack_speed', 0):.1f}%")
    sources["maple_rank"] = mr_stats

    # 9. EQUIPMENT SETS (Medals + Costumes)
    print("\n9. EQUIPMENT SETS (Medals + Costumes)")
    print("-" * 40)
    equip_sets = EquipmentSetsConfig(
        medal_config=MedalConfig(inventory_effect=780),
        costume_config=CostumeConfig(inventory_effect=1500),
    )
    es_stats = equip_sets.get_all_stats()
    print(f"  Medal Main Stat Flat: {equip_sets.medal_config.get_main_stat()}")
    print(f"  Costume Main Stat Flat: {equip_sets.costume_config.get_main_stat()}")
    print(f"  Total Main Stat Flat: {es_stats.get('main_stat_flat', 0)}")
    sources["equipment_sets"] = es_stats

    # 10. WEAPONS
    print("\n10. WEAPONS")
    print("-" * 40)
    weapon_config = configs['weapons']
    weapon_stats = weapon_config.get_all_stats()
    print(f"  Weapon ATK %: {weapon_stats.get('weapon_atk_percent', 0):.1f}%")
    sources["weapons"] = weapon_stats

    # =============================================================================
    # SUMMARY: CALCULATED VS TARGET
    # =============================================================================
    print("\n" + "=" * 70)
    print("CALCULATED VS TARGET COMPARISON")
    print("=" * 70)
    print()
    print(f"{'Stat':<25} {'Calculated':>15} {'Target':>15} {'Diff':>15}")
    print("-" * 70)

    # Aggregate stats
    calc_stats = aggregate_stats(sources)

    comparisons = [
        ("DEX (Flat)", calc_stats.get("dex_flat", 0), TARGET_STATS["dex"]),
        ("Damage %", calc_stats.get("damage_percent", 0), TARGET_STATS["damage_percent"]),
        ("Boss Damage %", calc_stats.get("boss_damage", 0), TARGET_STATS["boss_damage"]),
        ("Crit Damage %", calc_stats.get("crit_damage", 0), TARGET_STATS["crit_damage"]),
        ("Defense Pen %", calc_stats.get("defense_pen", 0), TARGET_STATS["defense_pen"]),
        ("Final Damage %", calc_stats.get("final_damage", 0), TARGET_STATS["final_damage"]),
        ("Crit Rate %", calc_stats.get("crit_rate", 0), TARGET_STATS["crit_rate"]),
        ("Normal Damage %", calc_stats.get("normal_damage", 0), TARGET_STATS["normal_damage"]),
        ("Skill Damage %", calc_stats.get("skill_damage", 0), TARGET_STATS["skill_damage"]),
        ("Min Dmg Mult %", calc_stats.get("min_dmg_mult", 0), TARGET_STATS["min_dmg_mult"]),
        ("Max Dmg Mult %", calc_stats.get("max_dmg_mult", 0), TARGET_STATS["max_dmg_mult"]),
        ("Attack Speed %", calc_stats.get("attack_speed", 0), TARGET_STATS["attack_speed"]),
    ]

    for stat_name, calc_val, target_val in comparisons:
        diff = calc_val - target_val
        diff_pct = (diff / target_val * 100) if target_val != 0 else 0
        sign = "+" if diff >= 0 else ""

        # Status indicators
        if abs(diff_pct) < 5:
            status = "~"
        elif diff_pct > 0:
            status = "+"
        else:
            status = "-"

        print(f"{stat_name:<25} {calc_val:>15.1f} {target_val:>15.1f} {sign}{diff:>14.1f} ({status})")

    print("\n" + "=" * 70)
    print("STAT SOURCE BREAKDOWN")
    print("=" * 70)

    # Show where each major stat comes from
    show_stat_breakdown("DEX (Flat)", sources, "dex_flat")
    show_stat_breakdown("Damage %", sources, "damage_percent")
    show_stat_breakdown("Boss Damage %", sources, "boss_damage")
    show_stat_breakdown("Crit Damage %", sources, "crit_damage")
    show_stat_breakdown("Final Damage %", sources, "final_damage")
    show_stat_breakdown("Defense Pen %", sources, "defense_pen")
    show_stat_breakdown("Min Dmg Mult %", sources, "min_dmg_mult")
    show_stat_breakdown("Max Dmg Mult %", sources, "max_dmg_mult")

    print("\n" + "=" * 70)
    print("MISSING STAT SOURCES (Not Yet Modeled)")
    print("=" * 70)
    print("""
- Base Character Stats (level-up stats) - ~15,000+ base DEX
- Link Skills
- Union/Legion effects
- Titles
- Item Scrolling (adds flat stats to equipment)
- Hyper Stats
- Active skill buffs
- Equipment Potentials (need to load from app)
- Some equipment base stats (need to aggregate from equipment_save.csv)
""")

    return sources, calc_stats


def show_stat_breakdown(stat_name, sources, stat_key):
    """Show where a stat comes from."""
    print(f"\n{stat_name}:")

    source_map = {
        "artifacts": ("Artifacts", lambda s: s.get(stat_key.replace("_percent", "").replace("dex_flat", "main_stat_flat"), 0)),
        "hero_power": ("Hero Power Lines", lambda s: s.get(stat_key.replace("_percent", "").replace("dex_flat", "main_stat_pct"), 0)),
        "hero_power_passive": ("Hero Power Passive", lambda s: s.get(stat_key, 0)),
        "guild": ("Guild", lambda s: s.get(stat_key.replace("_percent", "").replace("dex_flat", "main_stat_pct"), 0)),
        "companions": ("Companions", lambda s: s.get(stat_key.replace("dex_flat", "flat_main_stat").replace("_percent", ""), 0)),
        "passives": ("Passive Skills", lambda s: s.get(stat_key.replace("dex_flat", "main_stat_flat").replace("_percent", ""), 0)),
        "maple_rank": ("Maple Rank", lambda s: s.get(stat_key, 0)),
        "equipment_sets": ("Equipment Sets", lambda s: s.get(stat_key.replace("dex_flat", "main_stat_flat"), 0)),
    }

    total = 0
    for source_key, (source_name, getter) in source_map.items():
        if source_key in sources:
            value = getter(sources[source_key])
            if stat_key == "dex_flat" and source_key == "artifacts":
                value = sources[source_key].get("main_stat_flat", 0)
            elif stat_key == "damage_percent" and source_key == "artifacts":
                value = sources[source_key].get("damage", 0) * 100
            elif stat_key == "boss_damage" and source_key == "artifacts":
                value = sources[source_key].get("boss_damage", 0) * 100
            elif stat_key == "crit_damage" and source_key == "artifacts":
                value = sources[source_key].get("crit_damage", 0) * 100
            elif stat_key == "crit_rate" and source_key == "artifacts":
                value = sources[source_key].get("crit_rate", 0) * 100
            elif stat_key == "defense_pen" and source_key == "artifacts":
                value = sources[source_key].get("def_pen", 0) * 100
            elif stat_key == "final_damage" and source_key in ("guild", "passives"):
                value = sources[source_key].get("final_damage", 0)
            elif stat_key == "damage_percent" and source_key in ("guild", "companions", "hero_power_passive"):
                value = sources[source_key].get("damage", 0) if source_key != "hero_power_passive" else sources[source_key].get("damage_percent", 0)
            elif stat_key == "dex_flat" and source_key == "companions":
                value = sources[source_key].get("flat_main_stat", 0)
            elif stat_key == "min_dmg_mult" and source_key in ("hero_power", "passives", "companions", "maple_rank"):
                value = sources[source_key].get("min_dmg_mult", 0)
            elif stat_key == "max_dmg_mult" and source_key in ("hero_power", "passives", "companions", "maple_rank"):
                value = sources[source_key].get("max_dmg_mult", 0)

            if value != 0:
                print(f"  {source_name}: +{value:.1f}")
                total += value

    print(f"  TOTAL: {total:.1f}")


def aggregate_stats(sources):
    """Aggregate stats from all sources."""
    calc = {
        "dex_flat": 0,
        "dex_percent": 0,
        "damage_percent": 0,
        "boss_damage": 0,
        "crit_damage": 0,
        "defense_pen": 0,
        "final_damage": 0,
        "crit_rate": 0,
        "normal_damage": 0,
        "skill_damage": 0,
        "min_dmg_mult": 0,
        "max_dmg_mult": 0,
        "attack_speed": 0,
        "attack_flat": 0,
    }

    # Artifacts
    art = sources.get("artifacts", {})
    calc["damage_percent"] += art.get("damage", 0) * 100
    calc["boss_damage"] += art.get("boss_damage", 0) * 100
    calc["crit_damage"] += art.get("crit_damage", 0) * 100
    calc["crit_rate"] += art.get("crit_rate", 0) * 100
    calc["defense_pen"] += art.get("def_pen", 0) * 100
    calc["dex_flat"] += art.get("main_stat_flat", 0)
    calc["attack_flat"] += art.get("attack_flat", 0)

    # Hero Power (ability lines)
    hp = sources.get("hero_power", {})
    calc["damage_percent"] += hp.get("damage", 0)
    calc["boss_damage"] += hp.get("boss_damage", 0)
    calc["crit_damage"] += hp.get("crit_damage", 0)
    calc["defense_pen"] += hp.get("def_pen", 0)
    calc["dex_percent"] += hp.get("main_stat_pct", 0)
    calc["min_dmg_mult"] += hp.get("min_dmg_mult", 0)
    calc["max_dmg_mult"] += hp.get("max_dmg_mult", 0)

    # Hero Power Passive
    hpp = sources.get("hero_power_passive", {})
    calc["damage_percent"] += hpp.get("damage_percent", 0)
    calc["dex_flat"] += hpp.get("main_stat_flat", 0)
    calc["attack_flat"] += hpp.get("attack_flat", 0)

    # Guild
    guild = sources.get("guild", {})
    calc["damage_percent"] += guild.get("damage", 0)
    calc["boss_damage"] += guild.get("boss_damage", 0)
    calc["crit_damage"] += guild.get("crit_damage", 0)
    calc["defense_pen"] += guild.get("def_pen", 0)
    calc["final_damage"] += guild.get("final_damage", 0)
    calc["dex_percent"] += guild.get("main_stat_pct", 0)
    calc["attack_flat"] += guild.get("attack_flat", 0)

    # Companions
    comp = sources.get("companions", {})
    calc["damage_percent"] += comp.get("damage", 0)
    calc["dex_flat"] += comp.get("flat_main_stat", 0)
    calc["boss_damage"] += comp.get("boss_damage", 0)
    calc["crit_rate"] += comp.get("crit_rate", 0)
    calc["min_dmg_mult"] += comp.get("min_dmg_mult", 0)
    calc["max_dmg_mult"] += comp.get("max_dmg_mult", 0)
    calc["attack_speed"] += comp.get("attack_speed", 0)
    calc["attack_flat"] += comp.get("flat_attack", 0)

    # Passives (skills.py)
    passive = sources.get("passives", {})
    calc["crit_rate"] += passive.get("crit_rate", 0)
    calc["attack_speed"] += passive.get("attack_speed", 0)
    calc["min_dmg_mult"] += passive.get("min_dmg_mult", 0)
    calc["final_damage"] += passive.get("final_damage", 0)
    calc["dex_flat"] += passive.get("main_stat_flat", 0)
    calc["dex_flat"] += passive.get("dex_flat", 0)
    calc["skill_damage"] += passive.get("skill_damage", 0)
    calc["max_dmg_mult"] += passive.get("max_dmg_mult", 0)
    calc["defense_pen"] += passive.get("def_pen", 0)

    # Maple Rank
    mr = sources.get("maple_rank", {})
    calc["dex_flat"] += mr.get("main_stat_flat", 0)
    calc["damage_percent"] += mr.get("damage_percent", 0)
    calc["boss_damage"] += mr.get("boss_damage", 0)
    calc["normal_damage"] += mr.get("normal_damage", 0)
    calc["crit_damage"] += mr.get("crit_damage", 0)
    calc["crit_rate"] += mr.get("crit_rate", 0)
    calc["skill_damage"] += mr.get("skill_damage", 0)
    calc["min_dmg_mult"] += mr.get("min_dmg_mult", 0)
    calc["max_dmg_mult"] += mr.get("max_dmg_mult", 0)
    calc["attack_speed"] += mr.get("attack_speed", 0)

    # Equipment Sets (Medals + Costumes)
    es = sources.get("equipment_sets", {})
    calc["dex_flat"] += es.get("main_stat_flat", 0)

    return calc


if __name__ == "__main__":
    sources, calc_stats = analyze_stat_sources()
