"""
Character Stats Page
Compare calculated stats vs actual in-game values to identify gaps.
Click on any stat to see a breakdown of all contributing sources.

Adjustments are applied to DPS calculations throughout the app.
"""
import streamlit as st
from typing import Dict, Any, List, Tuple
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
    calculate_basic_attack_damage,
    calculate_effective_defense_pen_with_sources,
    calculate_effective_attack_speed_with_sources,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
)
from game.equipment import get_amplify_multiplier
from game.job_classes import JobClass, get_main_stat_name, get_secondary_stat_name
from constants import is_percentage_stat

st.set_page_config(page_title="Character Stats", page_icon="📊", layout="wide")

# Custom CSS for the stat comparison table
st.markdown("""
<style>
    .stat-table {
        width: 100%;
        border-collapse: collapse;
        font-family: monospace;
        font-size: 14px;
    }
    .stat-table th {
        background: #2a2a4e;
        color: #ffd700;
        padding: 10px;
        text-align: center;
        border-bottom: 2px solid #444;
    }
    .stat-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #333;
        text-align: center;
    }
    .stat-table tr:hover {
        background: #1a1a2e;
    }
    .stat-name {
        text-align: left !important;
        color: #fff;
        font-weight: bold;
    }
    .stat-calc { color: #66ff66; }
    .stat-adj { color: #ffaa00; }
    .stat-final { color: #66ccff; }
    .stat-actual { color: #ffffff; }
    .gap-positive { color: #66ff66; }
    .gap-negative { color: #ff6666; }
    .gap-zero { color: #888; }
    .clickable-stat {
        cursor: pointer;
        text-decoration: underline;
        color: #66ccff;
    }
    .clickable-stat:hover {
        color: #99ddff;
    }
    .section-header {
        font-size: 18px;
        font-weight: bold;
        color: #ffd700;
        margin: 20px 0 10px 0;
        padding: 10px;
        background: #2a2a4e;
        border-radius: 4px;
    }
    .source-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 8px;
        border-bottom: 1px solid #333;
    }
    .source-name { color: #aaa; }
    .source-value { color: #66ff66; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Baselines
BASE_CRIT_DMG = 30.0
BASE_CRIT_RATE = 0.0


def auto_save():
    save_user_data(st.session_state.username, data)


def get_stat_sources(stat_key: str, raw_stats: Dict, job_class: JobClass = None, debug: bool = False) -> List[Tuple[str, float]]:
    """
    Get breakdown of sources for a specific stat.
    Returns list of (source_name, value) tuples.

    Uses standardized stat names (attack_flat, dex_pct, damage_pct, etc.)
    """
    sources = []
    _debug = debug and stat_key in ('dex_flat', 'crit_damage')  # Debug for main stat and crit damage

    # Get main stat keys for this job class
    if job_class is None:
        job_class = JobClass.BOWMASTER
    main_stat = get_main_stat_name(job_class)  # e.g., 'dex'
    main_flat_key = f'{main_stat}_flat'
    main_pct_key = f'{main_stat}_pct'

    # Equipment base stats (with starforce)
    # Map stat_key to equipment base field and sub field
    from game.equipment import SLOT_THIRD_MAIN_STAT
    equip_base_mapping = {
        'attack_flat': ('base_attack', 'sub_attack_flat'),
        main_flat_key: ('base_third_stat', None),  # Only for slots where third_stat is main_stat
        'max_hp': ('base_max_hp', None),
    }
    equip_base_info = equip_base_mapping.get(stat_key)
    if equip_base_info:
        base_field, sub_field = equip_base_info
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            stars = int(item.get('stars', 0))
            main_mult = get_amplify_multiplier(stars, is_sub=False)
            sub_mult = get_amplify_multiplier(stars, is_sub=True)

            # For main_stat, only count slots where third_stat IS main_stat
            if stat_key == main_flat_key and base_field == 'base_third_stat':
                third_stat_type = SLOT_THIRD_MAIN_STAT.get(slot, 'main_stat')
                if third_stat_type != 'main_stat':
                    continue

            base_val = item.get(base_field, 0) * main_mult
            if base_val > 0:
                sources.append((f"{slot.title()} (Base)", base_val))

            if sub_field:
                sub_val = item.get(sub_field, 0) * sub_mult
                if sub_val > 0:
                    sources.append((f"{slot.title()} (Sub)", sub_val))

    # Equipment sub-stats (secondary stats like crit_damage, boss_damage, normal_damage, skill levels)
    equip_sub_mapping = {
        'damage_pct': 'sub_damage_pct',
        'crit_damage': 'sub_crit_damage',
        'crit_rate': 'sub_crit_rate',
        'boss_damage': 'sub_boss_damage',
        'normal_damage': 'sub_normal_damage',
        'skill_1st_bonus': 'sub_skill_1st',
        'skill_2nd_bonus': 'sub_skill_2nd',
        'skill_3rd_bonus': 'sub_skill_3rd',
        'skill_4th_bonus': 'sub_skill_4th',
    }
    equip_sub_key = equip_sub_mapping.get(stat_key)
    if equip_sub_key:
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            stars = int(item.get('stars', 0))
            sub_mult = get_amplify_multiplier(stars, is_sub=True)
            sub_val = item.get(equip_sub_key, 0) * sub_mult
            # Use int() for skill level stats
            if stat_key.startswith('skill_'):
                sub_val = int(sub_val)
            if sub_val > 0:
                sources.append((f"{slot.title()} (Sub)", sub_val))

    # Equipment special stats (damage_pct, all_skills, final_damage on special items)
    if stat_key == 'all_skills_bonus':
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            if item.get('is_special', False):
                special_type = item.get('special_stat_type', '')
                special_value = item.get('special_stat_value', 0)
                if special_type == 'all_skills' and special_value > 0:
                    stars = int(item.get('stars', 0))
                    sub_mult = get_amplify_multiplier(stars, is_sub=True)
                    total_val = int(special_value * sub_mult)
                    if total_val > 0:
                        sources.append((f"{slot.title()} (Special)", total_val))

    # Equipment potentials
    pot_stats = {}
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0) or 0)
                if stat and value > 0:
                    key = f"{slot}_{prefix}pot"
                    if key not in pot_stats:
                        pot_stats[key] = {}
                    pot_stats[key][stat] = pot_stats[key].get(stat, 0) + value

    # Map stat_key to potential stat names (using standardized names)
    pot_stat_mapping = {
        main_pct_key: [main_pct_key, 'main_stat_pct'],
        main_flat_key: [main_flat_key, 'main_stat_flat'],
        'damage_pct': ['damage_pct', 'damage'],
        'boss_damage': ['boss_damage'],
        'normal_damage': ['normal_damage'],
        'crit_rate': ['crit_rate'],
        'crit_damage': ['crit_damage'],
        'def_pen': ['def_pen'],
        'final_damage': ['final_damage'],
        'attack_speed': ['attack_speed'],
        'min_dmg_mult': ['min_dmg_mult'],
        'max_dmg_mult': ['max_dmg_mult'],
        'all_skills_bonus': ['all_skills'],
    }

    pot_names = pot_stat_mapping.get(stat_key, [])
    for slot_key, stats in pot_stats.items():
        slot_total = sum(stats.get(pn, 0) for pn in pot_names)
        if slot_total > 0:
            # Use int() for all_skills (skill levels are integers)
            if stat_key == 'all_skills_bonus':
                slot_total = int(slot_total)
            is_bonus = 'bonus_' in slot_key
            # Extract just the slot name (e.g., "hat" from "hat_bonus_pot" or "hat_pot")
            slot_name = slot_key.replace('_bonus_pot', '').replace('_pot', '')
            label = f"{slot_name.title()} {'Bonus ' if is_bonus else ''}Potential"
            sources.append((label, slot_total))

    # Hero Power Lines (uses standardized stat names)
    # Note: Hero Power's 'main_stat_pct' is actually flat main stat (legacy naming issue)
    # Use active preset's lines, not hero_power_lines directly
    active_preset = getattr(data, 'active_hero_power_preset', '1')
    hero_power_presets = getattr(data, 'hero_power_presets', {})

    if active_preset and active_preset in hero_power_presets:
        preset_data = hero_power_presets[active_preset]
        hp_lines = preset_data.get('lines', {})
    else:
        hp_lines = data.hero_power_lines

    hp_stat_mapping = {
        'damage_pct': 'damage',          # HP uses 'damage', not 'damage_pct'
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_rate': 'crit_rate',
        'def_pen': 'def_pen',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        main_flat_key: 'main_stat_flat',  # Hero Power flat main stat
    }
    hp_name = hp_stat_mapping.get(stat_key)
    if hp_name:
        hp_total = 0
        for line_key, line in hp_lines.items():
            if line.get('stat') == hp_name:
                hp_total += float(line.get('value', 0) or 0)
        if hp_total > 0:
            sources.append(("Hero Power Lines", hp_total))

    # Hero Power Passives - use direct values from hero_power_passive_values
    hpp_mapping = {
        main_flat_key: 'main_stat',
        'damage_pct': 'damage_percent',
        'attack_flat': 'attack',
    }
    hpp_key = hpp_mapping.get(stat_key)
    if hpp_key:
        passive_values = getattr(data, 'hero_power_passive_values', {}) or {}
        value = passive_values.get(hpp_key, 0)
        if value > 0:
            sources.append(("Hero Power Passives", value))

    # Maple Rank
    from game.maple_rank import MapleRankStatType, MAPLE_RANK_STATS, get_cumulative_main_stat, MAIN_STAT_SPECIAL
    mr = data.maple_rank or {}
    mr_mapping = {
        main_flat_key: 'main_stat_flat',
        'damage_pct': 'damage_percent',
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_damage': 'crit_damage',
        'crit_rate': 'crit_rate',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        'attack_speed': 'attack_speed',
        'skill_damage': 'skill_damage',
    }

    if stat_key == main_flat_key:
        stage = mr.get('current_stage', 1)
        ms_level = mr.get('main_stat_level', 0)
        special = mr.get('special_main_stat', 0)
        regular_ms = get_cumulative_main_stat(stage, ms_level)
        special_ms = MAIN_STAT_SPECIAL["base_value"] + special * MAIN_STAT_SPECIAL["per_point"]
        total_ms = regular_ms + special_ms
        if total_ms > 0:
            sources.append(("Maple Rank", total_ms))
    else:
        mr_key = mr_mapping.get(stat_key)
        if mr_key:
            stat_levels = mr.get('stat_levels', {})
            for stat_type in MapleRankStatType:
                if stat_type.value == mr_key and stat_type in MAPLE_RANK_STATS:
                    level = stat_levels.get(mr_key, 0)
                    if level > 0:
                        per_level = MAPLE_RANK_STATS[stat_type]["per_level"]
                        value = level * per_level
                        sources.append(("Maple Rank", value))

    # Companions (inventory stats use standardized names)
    from game.companions import COMPANIONS
    companion_levels = data.companion_levels or {}
    comp_mapping = {
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_rate': 'crit_rate',
        'crit_damage': 'crit_damage',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        'attack_speed': 'attack_speed',
        'attack_flat': 'attack_flat',
        'damage_pct': 'damage_pct',
        'skill_damage': 'skill_damage',
        'basic_attack_damage': 'basic_attack_damage',
        main_flat_key: 'main_stat_flat',
        main_pct_key: 'main_stat_pct',
    }
    comp_stat = comp_mapping.get(stat_key)
    if comp_stat:
        on_equip_total = 0
        inv_total = 0

        # On-equip from equipped companions
        for comp_key in (data.equipped_companions or []):
            if not comp_key or comp_key not in COMPANIONS:
                continue
            level = companion_levels.get(comp_key, 0)
            if level <= 0:
                continue
            companion = COMPANIONS[comp_key]
            if companion.on_equip_type.value == comp_stat:
                on_equip_total += companion.get_on_equip_value(level)

        # Inventory stats
        for comp_key, level in companion_levels.items():
            if level <= 0 or comp_key not in COMPANIONS:
                continue
            companion = COMPANIONS[comp_key]
            inv_stats = companion.get_inventory_stats(level)
            if comp_stat in inv_stats:
                inv_total += inv_stats[comp_stat]

        if on_equip_total > 0:
            sources.append(("Companions (Equipped)", on_equip_total))
        if inv_total > 0:
            sources.append(("Companions (Inventory)", inv_total))

    # Artifacts - potentials now use standardized stat names
    # main_stat_pct is used for generic main stat % in artifacts
    art_stat_key = stat_key
    if stat_key == main_pct_key:
        art_stat_key = 'main_stat_pct'  # artifacts use generic main_stat_pct

    # Read from session state to ensure latest data
    from game.artifacts import ARTIFACTS
    _user_data = st.session_state.user_data
    artifacts_inventory = getattr(_user_data, 'artifacts_inventory', {}) or {}
    artifacts_equipped = getattr(_user_data, 'artifacts_equipped', {}) or {}

    # Artifact potentials - only from EQUIPPED artifacts
    # Build set of equipped artifact keys
    equipped_artifact_keys = set()
    for slot_key in ['slot0', 'slot1', 'slot2', 'slot3']:
        slot_data = artifacts_equipped.get(slot_key, {})
        if not isinstance(slot_data, dict):
            continue
        name = slot_data.get('name', '')
        if not name or name == '(Empty)':
            continue
        # Find artifact key by name
        for k, d in ARTIFACTS.items():
            if d.name == name:
                equipped_artifact_keys.add(k)
                break

    from game.artifacts import POTENTIAL_SLOT_UNLOCKS, ArtifactTier
    for art_key in equipped_artifact_keys:
        art_data = artifacts_inventory.get(art_key, {})
        if not isinstance(art_data, dict):
            continue

        # Determine how many slots are unlocked based on stars
        # Slot 0: unlocked at 1★, Slot 1: unlocked at 3★, Slot 2: unlocked at 5★
        stars = int(art_data.get('stars', 0))
        slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
        # For non-legendary artifacts, cap at 2 slots
        art_defn = ARTIFACTS.get(art_key)
        if art_defn and art_defn.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
            slots_unlocked = 2

        potentials = art_data.get('potentials', [])
        art_value = 0
        if isinstance(potentials, list):
            for idx, pot in enumerate(potentials):
                # Skip slots that aren't unlocked yet
                if idx >= slots_unlocked:
                    continue
                if isinstance(pot, dict):
                    pot_stat = pot.get('stat', '')
                    pot_value = float(pot.get('value', 0) or 0)
                    if pot_stat == art_stat_key and pot_value > 0:
                        art_value += pot_value
        if art_value > 0:
            # Get artifact display name
            art_info = ARTIFACTS.get(art_key)
            if art_info and hasattr(art_info, 'name'):
                art_name = art_info.name
            else:
                art_name = art_key.replace('_', ' ').title()
            sources.append((f"Artifact: {art_name}", art_value))

    # Artifact inventory stats (passive bonuses from owning artifacts, separate from potentials)
    # Map stat_key to artifact inventory_stat values
    art_inv_mapping = {
        'normal_damage': 'normal_damage',
        'boss_damage': 'boss_damage',
        'crit_rate': 'crit_rate',
        'crit_damage': 'crit_damage',
        'attack_flat': 'attack_flat',
        'damage_pct': 'damage',
        'max_dmg_mult': 'max_damage_mult',
        'def_pen': 'def_pen',
        'basic_attack_damage': 'basic_attack_damage',
        'skill_damage': 'skill_damage',
    }
    art_inv_stat = art_inv_mapping.get(stat_key)
    if art_inv_stat:
        if _debug:
            print(f"[DEBUG get_stat_sources] Looking for artifacts with inventory_stat='{art_inv_stat}'")
            print(f"[DEBUG get_stat_sources] artifacts_inventory keys: {list(artifacts_inventory.keys())}")
        for art_key, art_data in artifacts_inventory.items():
            if art_key not in ARTIFACTS:
                if _debug:
                    print(f"[DEBUG get_stat_sources] Skipping {art_key}: not in ARTIFACTS")
                continue
            if not isinstance(art_data, dict):
                if _debug:
                    print(f"[DEBUG get_stat_sources] Skipping {art_key}: art_data is not dict: {type(art_data)}")
                continue
            defn = ARTIFACTS[art_key]
            # Check if this artifact provides this inventory stat
            if defn.inventory_stat != art_inv_stat:
                continue
            stars = int(art_data.get('stars', 0))
            inv_value = defn.get_inventory_value(stars)
            if _debug:
                print(f"[DEBUG get_stat_sources] {art_key}: stars={stars}, inv_value={inv_value}")
            if inv_value > 0:
                # Convert to percentage for display (inventory values are decimals)
                display_value = inv_value * 100 if art_inv_stat != 'attack_flat' else inv_value
                sources.append((f"Artifact: {defn.name} (Inventory)", display_value))
                if _debug:
                    print(f"[DEBUG get_stat_sources] Added {defn.name} inventory: {display_value}")

    # Artifact active effects (combat bonuses when equipped)
    # Map stat_key to artifact effect stat names
    art_active_mapping = {
        'normal_damage': 'normal_damage',
        'boss_damage': 'boss_damage',
        'crit_rate': 'crit_rate',
        'crit_damage': 'crit_damage',
        'damage_pct': 'damage',
        'max_dmg_mult': 'max_damage_mult',
    }
    art_active_stat = art_active_mapping.get(stat_key)
    if art_active_stat:
        from game.artifacts import EffectType
        # Use artifacts_equipped already loaded above from session state

        for slot_key in ['slot0', 'slot1', 'slot2', 'slot3']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue

            # Get artifact name from slot data
            name = slot_data.get('name', '')
            if not name or name == '(Empty)':
                continue

            # Find artifact definition by name
            art_key = None
            defn = None
            for k, d in ARTIFACTS.items():
                if d.name == name:
                    art_key = k
                    defn = d
                    break

            if not defn or not defn.active_effects:
                continue

            # Get stars from inventory (source of truth) or slot data
            if art_key and art_key in artifacts_inventory:
                inv_data = artifacts_inventory.get(art_key, {})
                stars = int(inv_data.get('stars', 0)) if isinstance(inv_data, dict) else 0
            else:
                stars = int(slot_data.get('stars', 0))

            for effect in defn.active_effects:
                if effect.stat != art_active_stat:
                    continue

                # Handle derived effects (e.g., Athena Pierce's max_dmg from attack_speed)
                if effect.effect_type == EffectType.DERIVED:
                    if effect.derived_from == 'attack_speed':
                        # Get total attack speed from raw_stats
                        atk_spd_sources = raw_stats.get('attack_speed_sources', [])
                        if atk_spd_sources:
                            total_atk_spd, _ = calculate_effective_attack_speed_with_sources(atk_spd_sources)
                            # Derived value = coefficient * source_value
                            coefficient = effect.get_value(stars)  # e.g., 0.50 for 50%
                            effect_value = coefficient * total_atk_spd  # Already in percentage
                            if effect_value > 0:
                                sources.append((f"Artifact: {defn.name} (Derived)", effect_value))
                    elif effect.derived_from == 'crit_rate':
                        # Book of Ancient CD from CR
                        source_value = raw_stats.get('crit_rate', 0) / 100
                        coefficient = effect.get_value(stars)
                        effect_value = coefficient * source_value * 100
                        if effect_value > 0:
                            sources.append((f"Artifact: {defn.name} (Derived)", effect_value))
                    continue

                effect_value = effect.get_value(stars) * 100  # Convert to percentage
                if effect_value > 0:
                    sources.append((f"Artifact: {defn.name} (Active)", effect_value))

    # Guild Skills
    guild_skills = getattr(data, 'guild_skills', {}) or {}
    guild_mapping = {
        'def_pen': 'def_pen',
        'final_damage': 'final_damage',
        'damage_pct': 'damage',
        'boss_damage': 'boss_damage',
        'crit_damage': 'crit_damage',
        main_pct_key: 'main_stat',
        'attack_flat': 'attack',
    }
    guild_stat = guild_mapping.get(stat_key)
    if guild_stat:
        guild_val = guild_skills.get(guild_stat, 0)
        if guild_val > 0:
            sources.append(("Guild Skills", guild_val))

    # Equipment Scrolls (damage_amp, flat_attack, flat_main_stat)
    equipment_scrolls = getattr(data, 'equipment_scrolls', {}) or {}
    scroll_mapping = {
        'damage_amp': 'damage_amp',
        'attack_flat': 'flat_attack',
        main_flat_key: 'flat_main_stat',
    }
    scroll_key = scroll_mapping.get(stat_key)
    if scroll_key:
        scroll_total = 0
        for slot, scroll_data in equipment_scrolls.items():
            if scroll_data:
                val = float(scroll_data.get(scroll_key, 0) or 0)
                if val > 0:
                    scroll_total += val
        if scroll_total > 0:
            sources.append(("Equipment Scrolls", scroll_total))

    # Equipment Sets (medal, costume)
    if stat_key == main_flat_key:
        medal_val = data.equipment_sets.get('medal', 0)
        costume_val = data.equipment_sets.get('costume', 0)
        if medal_val > 0:
            sources.append(("Medal Set", medal_val))
        if costume_val > 0:
            sources.append(("Costume Set", costume_val))

    # Artifact Resonance (flat main stat)
    if stat_key == main_flat_key:
        from game.artifacts import calculate_resonance_main_stat
        artifacts_resonance = getattr(data, 'artifacts_resonance', {}) or {}
        resonance_level = int(artifacts_resonance.get('resonance_level', 0))
        if resonance_level > 0:
            resonance_main = calculate_resonance_main_stat(resonance_level)
            if resonance_main > 0:
                sources.append(("Artifact Resonance", resonance_main))

    # Weapon Mastery stats (from weapon awakening levels)
    from game.weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
    weapons_data = getattr(data, 'weapons_data', {}) or {}
    if weapons_data:
        mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)
        mastery_stats = calculate_mastery_stats(mastery_stages)

        mastery_mapping = {
            'attack_flat': 'attack',
            main_flat_key: 'main_stat',
            'accuracy': 'accuracy',
            'min_dmg_mult': 'min_dmg_mult',
            'max_dmg_mult': 'max_dmg_mult',
        }
        mastery_key = mastery_mapping.get(stat_key)
        if mastery_key and mastery_stats.get(mastery_key, 0) > 0:
            sources.append(("Weapon Mastery", mastery_stats[mastery_key]))

    # Weapons (attack %)
    if stat_key == 'attack_pct':
        from game.weapons import calculate_weapon_atk_str, get_inventory_ratio
        weapons_data = getattr(data, 'weapons_data', {}) or {}
        equipped_weapon_key = getattr(data, 'equipped_weapon_key', '') or ''

        total_inv_atk = 0.0
        equipped_atk = 0.0

        for key, weapon_data in weapons_data.items():
            level = weapon_data.get('level', 0)
            if level <= 0:
                continue

            parts = key.rsplit('_', 1)
            if len(parts) != 2:
                continue

            rarity, tier = parts[0], int(parts[1])
            calc_stats = calculate_weapon_atk_str(rarity, tier, level)

            # Inventory ATK always applies
            total_inv_atk += calc_stats['inventory_atk']

            # Equipped weapon also gets on_equip ATK
            if key == equipped_weapon_key:
                equipped_atk = calc_stats['on_equip_atk']

        if equipped_atk > 0:
            sources.append(("Weapon (Equipped)", equipped_atk))
        if total_inv_atk > 0:
            sources.append(("Weapon (Inventory)", total_inv_atk))

    # Passive Skills (from skills.py PASSIVE_STAT type skills)
    # Map stat_key to skill stat names
    skill_stat_mapping = {
        'min_dmg_mult': 'min_dmg_mult',  # bow_mastery
        'max_dmg_mult': 'max_dmg_mult',  # mastery node
        'attack_speed': 'attack_speed',  # archer_mastery
        'final_damage': 'final_damage',  # extreme_archery, armor_break
        'def_pen': 'defense_pen',        # armor_break
        'crit_rate': 'crit_rate',        # critical_shot
        main_flat_key: 'dex_flat',       # soul_arrow (dex for bowmaster)
        'attack_pct': 'attack_pct',      # marksmanship (boss scenario)
        'skill_damage': 'skill_damage',  # mastery node (global)
        'basic_attack_damage': 'basic_attack_damage',  # physical_training + mastery node
    }
    skill_stat = skill_stat_mapping.get(stat_key)
    if skill_stat:
        try:
            from game.skills import DPSCalculator, CharacterState, get_global_mastery_stats, BOWMASTER_SKILLS, SkillType
            # Use correct UserData attributes
            char_level = getattr(data, 'character_level', 100)
            all_skills_bonus = getattr(data, 'all_skills', 0)

            # Calculate job-specific skill bonuses from equipment sub-stats
            skill_1st_total = 0
            skill_2nd_total = 0
            skill_3rd_total = 0
            skill_4th_total = 0
            for slot in EQUIPMENT_SLOTS:
                item = data.equipment_items.get(slot, {})
                stars = int(item.get('stars', 0))
                sub_mult = get_amplify_multiplier(stars, is_sub=True)
                skill_1st_total += int(item.get('sub_skill_1st', 0) * sub_mult)
                skill_2nd_total += int(item.get('sub_skill_2nd', 0) * sub_mult)
                skill_3rd_total += int(item.get('sub_skill_3rd', 0) * sub_mult)
                skill_4th_total += int(item.get('sub_skill_4th', 0) * sub_mult)

            char = CharacterState(
                level=char_level,
                all_skills_bonus=all_skills_bonus,
                skill_1st_bonus=skill_1st_total,
                skill_2nd_bonus=skill_2nd_total,
                skill_3rd_bonus=skill_3rd_total,
                skill_4th_bonus=skill_4th_total,
            )
            calc = DPSCalculator(char)

            # Get individual skill contributions (not summed)
            for skill_name, skill in BOWMASTER_SKILLS.items():
                if skill.skill_type != SkillType.PASSIVE_STAT or not skill.skill_bonuses:
                    continue
                if skill.scenario != "all":
                    continue  # Only permanent stats for char sheet
                if not char.is_skill_unlocked(skill_name):
                    continue
                if skill_stat not in skill.skill_bonuses:
                    continue

                level = char.get_effective_skill_level(skill_name)
                base, per_level = skill.skill_bonuses[skill_stat]
                value = calc.calc_skill_value(base, per_level, level)
                if value > 0:
                    # Use the skill's display name
                    sources.append((skill.name, value))

            # Also check mastery nodes (global stats)
            mastery_stats = get_global_mastery_stats(char_level)
            # For main stat (dex_flat), mastery nodes use generic 'main_stat_flat' key
            mastery_key = 'main_stat_flat' if stat_key == main_flat_key else skill_stat
            if mastery_key in mastery_stats:
                mastery_val = mastery_stats[mastery_key]
                if mastery_val > 0:
                    sources.append(("Mastery Nodes", mastery_val))
        except Exception:
            pass  # Skills module not available or other error

    if _debug:
        print(f"[DEBUG get_stat_sources] {stat_key} sources: {sources}")
        print(f"[DEBUG get_stat_sources] {stat_key} total: {sum(v for _, v in sources)}")
    return sources


def show_stat_breakdown_dialog(stat_name: str, stat_key: str, raw_stats: Dict, calculated_value: float, job_class: JobClass = None):
    """Show a dialog with stat breakdown."""
    sources = get_stat_sources(stat_key, raw_stats, job_class)
    is_pct = is_percentage_stat(stat_key)

    with st.container():
        st.markdown(f"### {stat_name} (Calculated)")
        st.markdown(f"**Total: {calculated_value:,.1f}{'%' if is_pct else ''}**")

        if sources:
            st.markdown("---")
            for source_name, value in sources:
                if is_pct:
                    st.write(f"**{source_name}:** {value:.1f}%")
                else:
                    st.write(f"**{source_name}:** {value:,.0f}")
        else:
            st.write("*No sources tracked for this stat*")


# ============================================================================
# STAT DEFINITIONS (Using standardized stat names)
# ============================================================================

def get_stat_definitions(job_class: JobClass = None):
    """Get stat definitions with dynamic main stat based on job class."""
    if job_class is None:
        job_class = JobClass.BOWMASTER
    main_stat = get_main_stat_name(job_class).upper()  # e.g., 'DEX', 'STR'
    main_stat_lower = main_stat.lower()

    # Define all stats to show in the comparison table
    # (key, display_name, is_percentage, include_baseline, baseline_value)
    return [
        # Main stats (dynamic based on job)
        ("total_main_stat", f"{main_stat} (Total)", False, False, 0),
        (f"{main_stat_lower}_flat", f"{main_stat} (Flat)", False, False, 0),
        (f"{main_stat_lower}_pct", f"{main_stat} %", True, False, 0),
        # Attack
        ("total_attack", "Attack (Total)", False, False, 0),
        ("attack_flat", "Attack (Flat)", False, False, 0),
        ("attack_pct", "Attack %", True, False, 0),
        # Damage stats
        ("damage_pct", "Damage %", True, False, 0),
        ("damage_amp", "Damage Amp %", True, False, 0),
        ("boss_damage", "Boss Damage %", True, False, 0),
        ("normal_damage", "Normal Dmg %", True, False, 0),
        ("basic_attack_damage", "Basic Attack Dmg %", True, False, 0),
        # Crit stats
        ("crit_rate", "Crit Rate %", True, True, BASE_CRIT_RATE),
        ("crit_damage", "Crit Damage %", True, True, BASE_CRIT_DMG),
        # Defense/Final
        ("def_pen", "Defense Pen %", True, False, 0),
        ("final_damage", "Final Damage %", True, False, 0),
        # Other
        ("skill_damage", "Skill Damage %", True, False, 0),
        ("min_dmg_mult", "Min Dmg Mult %", True, True, BASE_MIN_DMG),
        ("max_dmg_mult", "Max Dmg Mult %", True, True, BASE_MAX_DMG),
        ("attack_speed", "Attack Speed %", True, False, 0),
        ("accuracy", "Accuracy", False, False, 0),
        # Skill level bonuses
        ("skill_1st_bonus", "1st Job Skill Lvl", False, False, 0),
        ("skill_2nd_bonus", "2nd Job Skill Lvl", False, False, 0),
        ("skill_3rd_bonus", "3rd Job Skill Lvl", False, False, 0),
        ("skill_4th_bonus", "4th Job Skill Lvl", False, False, 0),
        ("all_skills_bonus", "All Skills", False, False, 0),
    ]


def get_calculated_stats(job_class: JobClass = None) -> Tuple[Dict[str, float], Dict, JobClass]:
    """Get all calculated stats from the shared aggregate function.

    Uses apply_adjustments=False to get raw calculated values
    (before manual adjustments are applied).

    Returns (stats_dict, raw_stats, job_class)
    """
    raw_stats = shared_aggregate_stats(data, apply_adjustments=False)

    # Determine job class for main stat keys
    if job_class is None:
        job_class = JobClass(data.job_class)

    main_stat = get_main_stat_name(job_class)  # e.g., 'dex'
    main_flat_key = f'{main_stat}_flat'
    main_pct_key = f'{main_stat}_pct'

    stats = {}

    # Main stats (using standardized names)
    stats[main_flat_key] = raw_stats.get(main_flat_key, 0)
    stats[main_pct_key] = raw_stats.get(main_pct_key, 0)
    stats['attack_flat'] = raw_stats.get('attack_flat', 0)
    stats['attack_pct'] = raw_stats.get('attack_pct', 0)
    stats['damage_pct'] = raw_stats.get('damage_pct', 0)
    stats['damage_amp'] = raw_stats.get('damage_amp', 0)
    stats['boss_damage'] = raw_stats.get('boss_damage', 0)
    stats['normal_damage'] = raw_stats.get('normal_damage', 0)
    stats['basic_attack_damage'] = raw_stats.get('basic_attack_damage', 0)
    stats['crit_rate'] = raw_stats.get('crit_rate', 0) + BASE_CRIT_RATE
    stats['crit_damage'] = raw_stats.get('crit_damage', 0) + BASE_CRIT_DMG
    stats['skill_damage'] = raw_stats.get('skill_damage', 0)
    stats['min_dmg_mult'] = raw_stats.get('min_dmg_mult', 0) + BASE_MIN_DMG
    stats['max_dmg_mult'] = raw_stats.get('max_dmg_mult', 0) + BASE_MAX_DMG
    stats['accuracy'] = raw_stats.get('accuracy', 0)

    # Calculate total main stat
    stats['total_main_stat'] = stats[main_flat_key] * (1 + stats[main_pct_key] / 100)

    # Calculate total attack (base * (1 + atk%/100))
    stats['total_attack'] = stats['attack_flat'] * (1 + stats['attack_pct'] / 100)

    # Defense pen from sources
    def_pen_sources = raw_stats.get('def_pen_sources', [])
    if def_pen_sources:
        total_def_pen, _ = calculate_effective_defense_pen_with_sources(def_pen_sources)
        stats['def_pen'] = total_def_pen * 100
    else:
        stats['def_pen'] = 0

    # Attack speed from sources
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(atk_spd_sources)
        stats['attack_speed'] = total_atk_spd
    else:
        stats['attack_speed'] = 0

    # Final damage from sources
    fd_sources = raw_stats.get('final_damage_sources', [])
    if fd_sources:
        fd_mult = 1.0
        for fd in fd_sources:
            fd_mult *= (1 + fd)
        stats['final_damage'] = (fd_mult - 1) * 100
    else:
        stats['final_damage'] = 0

    return stats, raw_stats, job_class


# ============================================================================
# PAGE LAYOUT
# ============================================================================

st.title("📊 Character Stats")

# Initialize manual adjustments if needed
if not hasattr(data, 'manual_adjustments') or data.manual_adjustments is None:
    data.manual_adjustments = {}

# Initialize actual stats in session state
if 'actual_stats' not in st.session_state:
    st.session_state.actual_stats = {}

# Quick info bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Level", data.character_level)
with col2:
    st.metric("All Skills", f"+{data.all_skills}")
with col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

# ============================================================================
# BASIC ATTACK SINGLE LINE DAMAGE
# ============================================================================
st.markdown("---")
st.markdown("<div class='section-header'>Basic Attack Single Line Damage</div>", unsafe_allow_html=True)

# Get aggregated stats with adjustments
from core import ENEMY_DEFENSE_VALUES
ba_stats = shared_aggregate_stats(data, apply_adjustments=True)

# Get enemy defense based on selected chapter
combat_mode = getattr(data, 'combat_mode', 'stage')
enemy_def = ENEMY_DEFENSE_VALUES.get(getattr(data, 'chapter', 'Chapter 27'), 0.752)

# Calculate for mobs and boss
ba_job_class = JobClass(data.job_class)
ba_mob = calculate_basic_attack_damage(ba_stats, enemy_def=enemy_def, job_class=ba_job_class, vs_boss=False)
ba_boss = calculate_basic_attack_damage(ba_stats, enemy_def=enemy_def, job_class=ba_job_class, vs_boss=True)

st.markdown(f"**{ba_mob['skill_display_name']}** ({ba_mob['skill_damage_pct']:.0f}% × {ba_mob['hits']} hits × {ba_mob['targets']} targets)")

# Show the actual formula with numbers
st.markdown("**Formula: ATK × Stat × Dmg% × Normal/Boss% × Amp × FD × Def × Skill% × BA% × Hex**")

st.code(f"""
vs Mobs:
{ba_mob['total_attack']:,.0f} × {ba_mob['stat_mult']:.4f} × {ba_mob['damage_mult']:.4f} × {ba_mob['target_dmg_mult']:.4f} × {ba_mob['amp_mult']:.4f} × {ba_mob['fd_mult']:.4f} × {ba_mob['def_mult']:.4f} × {ba_mob['skill_mult']:.4f} × {ba_mob['ba_dmg_mult']:.4f} × {ba_mob['hex_mult']:.4f}
= {ba_mob['min']:,.0f} - {ba_mob['max']:,.0f} (after {ba_mob['min_dmg_range']:.0f}%-{ba_mob['max_dmg_range']:.0f}% range)
× {ba_mob['crit_mult']:.4f} crit = {ba_mob['crit_min']:,.0f} - {ba_mob['crit_max']:,.0f}

vs Boss:
{ba_boss['total_attack']:,.0f} × {ba_boss['stat_mult']:.4f} × {ba_boss['damage_mult']:.4f} × {ba_boss['target_dmg_mult']:.4f} × {ba_boss['amp_mult']:.4f} × {ba_boss['fd_mult']:.4f} × {ba_boss['def_mult']:.4f} × {ba_boss['skill_mult']:.4f} × {ba_boss['ba_dmg_mult']:.4f} × {ba_boss['hex_mult']:.4f}
= {ba_boss['min']:,.0f} - {ba_boss['max']:,.0f} (after {ba_boss['min_dmg_range']:.0f}%-{ba_boss['max_dmg_range']:.0f}% range)
× {ba_boss['crit_mult']:.4f} crit = {ba_boss['crit_min']:,.0f} - {ba_boss['crit_max']:,.0f}
""")

with st.expander("Multiplier breakdown"):
    st.markdown(f"""
| Component | Value | Calculation |
|-----------|-------|-------------|
| ATK | {ba_mob['total_attack']:,.0f} | {ba_stats.get('attack_flat', 0):,.0f} × (1 + {ba_stats.get('attack_pct', 0):.1f}%) |
| Stat | {ba_mob['stat_mult']:.4f} | 1 + ({ba_mob['total_main_stat']:,.0f}/10000) + ({ba_mob.get('total_secondary_stat', 0):,.0f}/40000) |
| Dmg% | {ba_mob['damage_mult']:.4f} | 1 + {ba_mob['damage_pct']:.1f}% / 100 |
| Normal% | {ba_mob['target_dmg_mult']:.4f} | 1 + {ba_mob['normal_damage']:.1f}% / 100 |
| Boss% | {ba_boss['target_dmg_mult']:.4f} | 1 + {ba_boss['boss_damage']:.1f}% / 100 |
| Amp | {ba_mob['amp_mult']:.4f} | 1 + {ba_mob['damage_amp']:.1f}% / 100 |
| FD | {ba_mob['fd_mult']:.4f} | multiplicative sources |
| Def | {ba_mob['def_mult']:.4f} | 1 / (1 + {ba_mob['enemy_def']:.3f} × (1 - {ba_mob['defense_pen']:.4f})) |
| Skill% | {ba_mob['skill_mult']:.4f} | {ba_mob['skill_damage_pct']:.0f}% / 100 |
| BA% | {ba_mob['ba_dmg_mult']:.4f} | 1 + {ba_mob['basic_attack_damage']:.1f}% / 100 |
| Hex | {ba_mob['hex_mult']:.4f} | Hex Necklace avg stacks |
| Crit | {ba_mob['crit_mult']:.4f} | 1 + {ba_mob['crit_damage']:.1f}% / 100 |
    """)
    st.caption("Stat multiplier: Main stat gives 1% per point, secondary stat gives 0.25% per point")

# Medal/Costume inputs
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    medal_val = st.number_input(
        "Medal Main Stat",
        min_value=0, max_value=1500,
        value=int(data.equipment_sets.get('medal', 0)),
        help="Total main stat from medal set"
    )
    if medal_val != data.equipment_sets.get('medal', 0):
        data.equipment_sets['medal'] = medal_val
        auto_save()
with col2:
    costume_val = st.number_input(
        "Costume Main Stat",
        min_value=0, max_value=3000,
        value=int(data.equipment_sets.get('costume', 0)),
        help="Total main stat from costume set"
    )
    if costume_val != data.equipment_sets.get('costume', 0):
        data.equipment_sets['costume'] = costume_val
        auto_save()

st.markdown("---")

# Get calculated stats (with job class)
calculated_stats, raw_stats, current_job_class = get_calculated_stats()

# Get stat definitions for this job class
STAT_DEFINITIONS = get_stat_definitions(current_job_class)

# ============================================================================
# STAT COMPARISON TABLE
# ============================================================================

st.markdown("<div class='section-header'>Stat Comparison (Calculated vs Actual)</div>", unsafe_allow_html=True)
st.caption("Enter your actual in-game values to identify gaps in our model")

# Track which stat to show breakdown for
if 'breakdown_stat' not in st.session_state:
    st.session_state.breakdown_stat = None

# Header row
header_cols = st.columns([2, 1.5, 1, 1.5, 1.5, 1])
with header_cols[0]:
    st.markdown("**Stat**")
with header_cols[1]:
    st.markdown("**Calculated**")
with header_cols[2]:
    st.markdown("**Adjustment**")
with header_cols[3]:
    st.markdown("**Final**")
with header_cols[4]:
    st.markdown("**Actual**")
with header_cols[5]:
    st.markdown("**Gap**")

st.markdown("---")

# Stat rows
for stat_key, display_name, is_pct, has_baseline, baseline in STAT_DEFINITIONS:
    calc_val = calculated_stats.get(stat_key, 0)

    # Final Damage uses multiplicative correction, not additive
    if stat_key == 'final_damage':
        fd_correction = data.manual_adjustments.get('final_damage_correction', 1.0)
        # Convert calc FD% to multiplier, apply correction, convert back to %
        calc_mult = 1 + calc_val / 100
        final_mult = calc_mult * fd_correction
        final_val = (final_mult - 1) * 100
        adj_display = f"×{fd_correction:.3f}" if fd_correction != 1.0 else None
    else:
        adj_val = data.manual_adjustments.get(stat_key, 0)
        final_val = calc_val + adj_val
        adj_display = f"{adj_val:+.1f}" if adj_val != 0 else None

    # Get actual from session state or default to final
    actual_val = st.session_state.actual_stats.get(stat_key, final_val)

    gap = actual_val - final_val

    cols = st.columns([2, 1.5, 1, 1.5, 1.5, 1])

    with cols[0]:
        # Clickable stat name
        if st.button(f"▸ {display_name}", key=f"btn_{stat_key}", use_container_width=True):
            st.session_state.breakdown_stat = stat_key

    with cols[1]:
        if is_pct:
            st.markdown(f"<span style='color:#66ff66;'>{calc_val:.1f}%</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:#66ff66;'>{calc_val:,.0f}</span>", unsafe_allow_html=True)

    with cols[2]:
        if adj_display:
            color = "#ffaa00"
            st.markdown(f"<span style='color:{color};'>{adj_display}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#888;'>-</span>", unsafe_allow_html=True)

    with cols[3]:
        if is_pct:
            st.markdown(f"<span style='color:#66ccff;'>{final_val:.1f}%</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:#66ccff;'>{final_val:,.0f}</span>", unsafe_allow_html=True)

    with cols[4]:
        new_actual = st.number_input(
            f"actual_{stat_key}",
            value=float(actual_val),
            step=0.1 if is_pct else 1.0,
            label_visibility="collapsed",
            key=f"actual_{stat_key}"
        )
        st.session_state.actual_stats[stat_key] = new_actual

    with cols[5]:
        gap = new_actual - final_val
        if abs(gap) > 0.01:
            color = "#66ff66" if gap > 0 else "#ff6666"
            if is_pct:
                st.markdown(f"<span style='color:{color};'>{gap:+.1f}%</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:{color};'>{gap:+,.0f}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#888;'>0</span>", unsafe_allow_html=True)

# ============================================================================
# ACTION BUTTONS
# ============================================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Apply Adjustments", type="primary", use_container_width=True):
        # Save current adjustments
        auto_save()
        st.success("Adjustments saved!")
        st.rerun()

with col2:
    if st.button("Auto-Fill from Gap", use_container_width=True):
        for stat_key, _, _, _, _ in STAT_DEFINITIONS:
            actual = st.session_state.actual_stats.get(stat_key, 0)
            calc = calculated_stats.get(stat_key, 0)

            # Final Damage is multiplicative - store correction as multiplier
            # If calc FD is 300% (mult=4.0) and actual is 100% (mult=2.0),
            # correction = actual_mult / calc_mult = 2.0 / 4.0 = 0.5
            if stat_key == 'final_damage':
                calc_mult = 1 + calc / 100  # e.g., 300% -> 4.0
                actual_mult = 1 + actual / 100  # e.g., 100% -> 2.0
                if calc_mult > 0:
                    # Store as correction multiplier (0.5 means halve FD)
                    data.manual_adjustments['final_damage_correction'] = actual_mult / calc_mult
                    data.manual_adjustments[stat_key] = 0  # Clear additive adjustment
                else:
                    data.manual_adjustments[stat_key] = 0
            else:
                data.manual_adjustments[stat_key] = actual - calc
        auto_save()
        st.success("Adjustments auto-filled from gaps!")
        st.rerun()

with col3:
    if st.button("Reset Adjustments", use_container_width=True):
        data.manual_adjustments = {}
        auto_save()
        st.success("Adjustments reset!")
        st.rerun()

# ============================================================================
# STAT BREAKDOWN DIALOG
# ============================================================================

if st.session_state.breakdown_stat:
    stat_key = st.session_state.breakdown_stat
    # Find display name
    display_name = stat_key
    for key, name, _, _, _ in STAT_DEFINITIONS:
        if key == stat_key:
            display_name = name
            break

    calc_val = calculated_stats.get(stat_key, 0)
    is_pct = is_percentage_stat(stat_key)

    @st.dialog(f"Stat Breakdown: {display_name} (Calculated)")
    def show_breakdown():
        st.markdown(f"### {display_name} (Calculated)")

        sources = get_stat_sources(stat_key, raw_stats, current_job_class, debug=True)

        # Check if this stat has a baseline
        baseline_value = 0.0
        for key, name, _, has_baseline, baseline in STAT_DEFINITIONS:
            if key == stat_key and has_baseline:
                baseline_value = baseline
                break

        # Check if this is a multiplicative stat (def_pen, final_damage, attack_speed)
        is_multiplicative = stat_key in ('def_pen', 'final_damage', 'attack_speed')

        # Calculate total from sources (this is the ground truth)
        if is_multiplicative:
            if stat_key == 'def_pen':
                remaining = 1.0
                for _, value in sources:
                    remaining *= (1 - value / 100)
                source_total = (1 - remaining) * 100
            elif stat_key == 'final_damage':
                mult = 1.0
                for _, value in sources:
                    mult *= (1 + value / 100)
                source_total = (mult - 1) * 100
            elif stat_key == 'attack_speed':
                # Attack speed uses calculated_stats since it has diminishing returns
                source_total = calculated_stats.get(stat_key, 0)
            else:
                source_total = sum(v for _, v in sources)
        else:
            source_total = baseline_value + sum(v for _, v in sources)

        # Display total at top
        if is_pct:
            st.markdown(f"**Total: {source_total:.1f}%**")
        else:
            st.markdown(f"**Total: {source_total:,.0f}**")

        if sources or baseline_value > 0:
            st.markdown("---")

            if is_multiplicative:
                # Multiplicative stats: show raw values and effective gain
                # def_pen/final_damage: remaining = remaining * (1 - value/100)
                # attack_speed: uses diminishing returns formula
                st.caption("*Multiplicative stacking - each source has diminishing returns*")
                remaining = 1.0  # For def_pen: 100% defense remaining

                for source_name, value in sources:
                    if stat_key == 'def_pen':
                        # Defense penetration: multiplicative reduction
                        effective_gain = remaining * (value / 100)
                        remaining *= (1 - value / 100)
                        total_pen = (1 - remaining) * 100
                        st.write(f"**{source_name}:** {value:.1f}% (eff: +{effective_gain:.1f}%) → {total_pen:.1f}%")
                    elif stat_key == 'final_damage':
                        # Final damage: multiplicative stacking
                        # Each source multiplies: total = (1+a)(1+b)(1+c) - 1
                        mult_before = 1 / remaining if remaining != 1.0 else 1.0
                        remaining *= 1 / (1 + value / 100)
                        mult_after = 1 / remaining
                        total_fd = (mult_after - 1) * 100
                        st.write(f"**{source_name}:** +{value:.1f}% → {total_fd:.1f}%")
                    else:
                        # Attack speed: diminishing returns toward cap
                        st.write(f"**{source_name}:** +{value:.1f}%")
            else:
                # Additive stats: simple running total
                running_total = 0.0

                # Show baseline first if applicable
                if baseline_value > 0:
                    running_total = baseline_value
                    if is_pct:
                        st.write(f"**Baseline:** +{baseline_value:.0f}% → {running_total:.1f}%")
                    else:
                        st.write(f"**Baseline:** +{baseline_value:,.0f} → {running_total:,.0f}")

                for source_name, value in sources:
                    running_total += value
                    if is_pct:
                        st.write(f"**{source_name}:** +{value:.1f}% → {running_total:.1f}%")
                    else:
                        st.write(f"**{source_name}:** +{value:,.0f} → {running_total:,.0f}")
        else:
            st.info("No tracked sources for this stat. The value may come from baseline or untracked sources.")

        if st.button("Close"):
            st.session_state.breakdown_stat = None
            st.rerun()

    show_breakdown()

# ============================================================================
# ADDITIONAL COMBAT STATS
# ============================================================================

st.markdown("---")
st.markdown("<div class='section-header'>Additional Combat Stats (click for breakdown)</div>", unsafe_allow_html=True)

# Show defense pen and attack speed breakdowns
col1, col2 = st.columns(2)

with col1:
    def_pen_sources = raw_stats.get('def_pen_sources', [])
    if def_pen_sources:
        total_def_pen, breakdown = calculate_effective_defense_pen_with_sources(def_pen_sources)
        with st.expander(f"▸ Defense Pen %: {total_def_pen*100:.1f}%"):
            for source_name, raw_value, effective_gain in breakdown:
                display_name = source_name.replace('_', ' ').title()
                st.write(f"**{display_name}:** {raw_value*100:.1f}% (eff: +{effective_gain*100:.1f}%)")

with col2:
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        total_atk_spd, breakdown = calculate_effective_attack_speed_with_sources(atk_spd_sources)

        # Calculate attack speed multiplier (capped at 2.5x / 150%)
        atk_spd_mult = min(1 + total_atk_spd / 100, 2.5)

        with st.expander(f"▸ Attack Speed: {total_atk_spd:.1f}% ({atk_spd_mult:.2f}x cast speed)"):
            st.markdown("**Attack Speed Scaling:**")
            st.markdown(f"- Total Attack Speed: **{total_atk_spd:.1f}%**")
            st.markdown(f"- Speed Multiplier: **{atk_spd_mult:.2f}x** (cap: 2.5x at 150%)")
            st.markdown(f"- Cast Time Reduction: **{(1 - 1/atk_spd_mult) * 100:.1f}%**")

            st.markdown("---")
            st.markdown("**Sources (with diminishing returns):**")
            for source_name, raw_value, effective_gain in breakdown:
                display_name = source_name.replace('_', ' ').title()
                st.write(f"**{display_name}:** {raw_value:.1f}% raw → +{effective_gain:.1f}% effective")

# Final damage sources
fd_sources = raw_stats.get('final_damage_sources', [])
if fd_sources:
    fd_mult = 1.0
    for fd in fd_sources:
        fd_mult *= (1 + fd)
    total_fd = (fd_mult - 1) * 100
    with st.expander(f"▸ Final Damage %: {total_fd:.1f}% (Multiplicative)"):
        for i, fd in enumerate(fd_sources):
            st.write(f"**Source {i+1}:** +{fd*100:.1f}%")
        st.write(f"*Multiplied: {' × '.join([f'(1+{fd*100:.1f}%)' for fd in fd_sources])} = {fd_mult:.4f}*")

# ============================================================================
# INFO
# ============================================================================

st.markdown("---")
st.info("""
**How to use this page:**
1. Click on any stat name to see a breakdown of all contributing sources
2. Enter your actual in-game values in the "Actual" column
3. Click "Auto-Fill from Gap" to automatically calculate adjustments
4. Click "Apply Adjustments" to save - these will be used in all DPS calculations

**Note:** Adjustments help account for stats from sources we don't track (passive skills, buffs, etc.)
""")

# ============================================================================
# VALIDATION TAB - Compare aggregate_stats vs get_stat_sources
# ============================================================================

with st.expander("🔍 **Debug: Stat Validation** (compare aggregate_stats vs get_stat_sources)"):
    st.markdown("""
    This section compares the values from `aggregate_stats()` with the sum of sources
    from `get_stat_sources()`. Any mismatch indicates a bug in one of the two functions.
    """)

    # Get main stat name for this job class
    _main_stat = get_main_stat_name(current_job_class)  # e.g., 'dex'
    _main_stat_display = _main_stat.upper()  # e.g., 'DEX'

    # Stats to validate (key, display_name, is_multiplicative, baseline)
    validation_stats = [
        (f"{_main_stat}_flat", f"{_main_stat_display} (Flat)", False, 0),
        (f"{_main_stat}_pct", f"{_main_stat_display} %", False, 0),
        ("attack_flat", "Attack (Flat)", False, 0),
        ("attack_pct", "Attack %", False, 0),
        ("damage_pct", "Damage %", False, 0),
        ("boss_damage", "Boss Damage %", False, 0),
        ("normal_damage", "Normal Dmg %", False, 0),
        ("crit_rate", "Crit Rate %", False, BASE_CRIT_RATE),
        ("crit_damage", "Crit Damage %", False, BASE_CRIT_DMG),
        ("min_dmg_mult", "Min Dmg Mult %", False, BASE_MIN_DMG),
        ("max_dmg_mult", "Max Dmg Mult %", False, BASE_MAX_DMG),
        ("skill_damage", "Skill Damage %", False, 0),
        ("basic_attack_damage", "Basic Attack Dmg %", False, 0),
        ("damage_amp", "Damage Amp %", False, 0),
        # Skill level bonuses
        ("skill_1st_bonus", "1st Job Skill Lvl", False, 0),
        ("skill_2nd_bonus", "2nd Job Skill Lvl", False, 0),
        ("skill_3rd_bonus", "3rd Job Skill Lvl", False, 0),
        ("skill_4th_bonus", "4th Job Skill Lvl", False, 0),
        ("all_skills_bonus", "All Skills", False, 0),
    ]

    validation_rows = []
    has_mismatch = False

    for stat_key, display_name, is_mult, baseline in validation_stats:
        # Get value from aggregate_stats
        agg_value = raw_stats.get(stat_key, 0)
        if baseline > 0:
            agg_value += baseline  # Add baseline for comparison

        # Get sources and sum them
        sources = get_stat_sources(stat_key, raw_stats, current_job_class)
        sources_sum = sum(v for _, v in sources)
        if baseline > 0:
            sources_sum += baseline

        # Get actual value from user input (with adjustment applied for final)
        calc_val = calculated_stats.get(stat_key, 0)
        adj_val = data.manual_adjustments.get(stat_key, 0)
        final_val = calc_val + adj_val
        actual_val = st.session_state.actual_stats.get(stat_key, final_val)

        # Calculate differences
        diff_agg_vs_src = agg_value - sources_sum
        diff_actual_vs_agg = actual_val - agg_value

        # Determine status for aggregate vs sources
        if abs(diff_agg_vs_src) < 0.01:
            status = "✅"
        elif abs(diff_agg_vs_src) < 1:
            status = "⚠️"  # Minor difference (rounding)
        else:
            status = "❌"
            has_mismatch = True

        validation_rows.append({
            "Stat": display_name,
            "Actual (input)": f"{actual_val:,.1f}",
            "aggregate_stats": f"{agg_value:,.1f}",
            "get_stat_sources": f"{sources_sum:,.1f}",
            "Agg vs Src": f"{diff_agg_vs_src:+,.1f}",
            "Actual vs Agg": f"{diff_actual_vs_agg:+,.1f}",
            "Status": status,
        })

    # Show summary
    if has_mismatch:
        st.error("❌ Mismatches found! The two functions are calculating different values.")
    else:
        st.success("✅ All stats match between aggregate_stats and get_stat_sources!")

    # Display validation table
    st.dataframe(validation_rows, use_container_width=True, hide_index=True)

    # Detailed breakdown for mismatched stats
    st.markdown("---")
    st.markdown("### Detailed Breakdown for Mismatched Stats")

    for stat_key, display_name, is_mult, baseline in validation_stats:
        agg_value = raw_stats.get(stat_key, 0)
        if baseline > 0:
            agg_value += baseline

        sources = get_stat_sources(stat_key, raw_stats, current_job_class)
        sources_sum = sum(v for _, v in sources)
        if baseline > 0:
            sources_sum += baseline

        # Get actual value
        calc_val = calculated_stats.get(stat_key, 0)
        adj_val = data.manual_adjustments.get(stat_key, 0)
        final_val = calc_val + adj_val
        actual_val = st.session_state.actual_stats.get(stat_key, final_val)

        diff_agg_vs_src = agg_value - sources_sum
        diff_actual_vs_agg = actual_val - agg_value

        if abs(diff_agg_vs_src) >= 1:  # Show details for mismatches
            with st.expander(f"❌ {display_name}: Agg vs Src = {diff_agg_vs_src:+,.1f}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown(f"**Actual (input):** {actual_val:,.1f}")
                    st.caption("What you entered")

                with col2:
                    st.markdown(f"**aggregate_stats:** {agg_value:,.1f}")
                    if baseline > 0:
                        st.caption(f"(includes baseline: {baseline})")

                with col3:
                    st.markdown(f"**get_stat_sources:** {sources_sum:,.1f}")
                    if baseline > 0:
                        st.caption(f"(includes baseline: {baseline})")

                st.markdown("**Sources breakdown:**")
                if sources:
                    for source_name, value in sources:
                        st.write(f"- {source_name}: {value:,.1f}")
                else:
                    st.write("- (no sources found)")

                st.markdown(f"**Missing from sources (agg - src):** {diff_agg_vs_src:+,.1f}")
                st.markdown(f"**Actual vs aggregate (actual - agg):** {diff_actual_vs_agg:+,.1f}")

# ============================================================================
# STAT AGGREGATOR VALIDATION - New unified stat tracking
# ============================================================================

with st.expander("🔬 **Debug: StatAggregator Validation** (compare new unified class)"):
    st.markdown("""
    This section validates the new `StatAggregator` class against:
    1. **aggregate_stats()** - the current DPS calculation function
    2. **Actual (input)** - your actual in-game stats

    When StatAggregator matches aggregate_stats(), we can safely replace the old functions.
    """)

    try:
        from utils.stat_aggregator import populate_from_user_data, StatAggregator

        # Populate StatAggregator from user data
        stat_agg = populate_from_user_data(data, job_class=current_job_class)

        # Stats to validate
        sa_validation_stats = [
            (f"{_main_stat}_flat", f"{_main_stat_display} (Flat)", 0),
            (f"{_main_stat}_pct", f"{_main_stat_display} %", 0),
            ("attack_flat", "Attack (Flat)", 0),
            ("attack_pct", "Attack %", 0),
            ("damage_pct", "Damage %", 0),
            ("boss_damage", "Boss Damage %", 0),
            ("normal_damage", "Normal Dmg %", 0),
            ("crit_rate", "Crit Rate %", BASE_CRIT_RATE),
            ("crit_damage", "Crit Damage %", BASE_CRIT_DMG),
            ("min_dmg_mult", "Min Dmg Mult %", BASE_MIN_DMG),
            ("max_dmg_mult", "Max Dmg Mult %", BASE_MAX_DMG),
            ("skill_damage", "Skill Damage %", 0),
            ("basic_attack_damage", "Basic Attack Dmg %", 0),
            ("damage_amp", "Damage Amp %", 0),
            # Skill level bonuses
            ("skill_1st_bonus", "1st Job Skill Lvl", 0),
            ("skill_2nd_bonus", "2nd Job Skill Lvl", 0),
            ("skill_3rd_bonus", "3rd Job Skill Lvl", 0),
            ("skill_4th_bonus", "4th Job Skill Lvl", 0),
            ("all_skills_bonus", "All Skills", 0),
        ]

        sa_rows = []
        sa_has_mismatch = False

        for stat_key, display_name, baseline in sa_validation_stats:
            # Get value from StatAggregator (raw_total, no baseline)
            sa_raw = stat_agg.get(stat_key, include_baseline=False)
            sa_with_baseline = sa_raw + baseline

            # Get value from aggregate_stats (also no baseline, we add it)
            agg_value = raw_stats.get(stat_key, 0)
            agg_with_baseline = agg_value + baseline

            # Get actual value from user input
            calc_val = calculated_stats.get(stat_key, 0)
            adj_val = data.manual_adjustments.get(stat_key, 0)
            final_val = calc_val + adj_val
            actual_val = st.session_state.actual_stats.get(stat_key, final_val)

            # Calculate differences
            diff_sa_vs_agg = sa_with_baseline - agg_with_baseline
            diff_actual_vs_sa = actual_val - sa_with_baseline

            # Determine status
            if abs(diff_sa_vs_agg) < 0.01:
                status = "✅"
            elif abs(diff_sa_vs_agg) < 1:
                status = "⚠️"
            else:
                status = "❌"
                sa_has_mismatch = True

            sa_rows.append({
                "Stat": display_name,
                "Actual (input)": f"{actual_val:,.1f}",
                "StatAggregator": f"{sa_with_baseline:,.1f}",
                "aggregate_stats": f"{agg_with_baseline:,.1f}",
                "SA vs Agg": f"{diff_sa_vs_agg:+,.1f}",
                "Actual vs SA": f"{diff_actual_vs_sa:+,.1f}",
                "Status": status,
            })

        # Summary
        if sa_has_mismatch:
            st.error("❌ StatAggregator doesn't match aggregate_stats! Check source tracking logic.")
        else:
            st.success("✅ StatAggregator matches aggregate_stats! Safe to migrate.")

        # Display table
        st.dataframe(sa_rows, use_container_width=True, hide_index=True)

        # Detailed breakdown for mismatches or selected stat
        st.markdown("---")
        st.markdown("### Source Breakdown from StatAggregator")

        stat_options = [f"{name} ({key})" for key, name, _ in sa_validation_stats]
        selected = st.selectbox("Select stat to view sources:", stat_options, key="sa_breakdown_select")

        if selected:
            # Parse selection back to stat key
            selected_key = sa_validation_stats[stat_options.index(selected)][0]
            selected_baseline = sa_validation_stats[stat_options.index(selected)][2]

            sources = stat_agg.get_sources(selected_key)
            sa_raw = stat_agg.get(selected_key, include_baseline=False)
            agg_value = raw_stats.get(selected_key, 0)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**StatAggregator Sources:**")
                if sources:
                    running = 0.0
                    for source_name, value in sources:
                        running += value
                        st.write(f"- **{source_name}:** +{value:,.1f} → {running:,.1f}")
                    if selected_baseline > 0:
                        st.write(f"- **Baseline:** +{selected_baseline:,.0f} → {running + selected_baseline:,.1f}")
                else:
                    st.write("(no sources)")
                st.markdown(f"**Total:** {sa_raw + selected_baseline:,.1f}")

            with col2:
                st.markdown("**get_stat_sources() Sources:**")
                old_sources = get_stat_sources(selected_key, raw_stats, current_job_class)
                if old_sources:
                    running = 0.0
                    for source_name, value in old_sources:
                        running += value
                        st.write(f"- **{source_name}:** +{value:,.1f} → {running:,.1f}")
                    if selected_baseline > 0:
                        st.write(f"- **Baseline:** +{selected_baseline:,.0f} → {running + selected_baseline:,.1f}")
                else:
                    st.write("(no sources)")
                st.markdown(f"**Total (agg):** {agg_value + selected_baseline:,.1f}")

            # Show diff if any
            diff = (sa_raw + selected_baseline) - (agg_value + selected_baseline)
            if abs(diff) >= 0.01:
                st.warning(f"**Difference:** {diff:+,.1f}")

                # Try to identify missing/extra sources
                sa_source_names = set(s[0] for s in sources)
                old_source_names = set(s[0] for s in old_sources)

                only_in_sa = sa_source_names - old_source_names
                only_in_old = old_source_names - sa_source_names

                if only_in_sa:
                    st.markdown(f"**Only in StatAggregator:** {', '.join(only_in_sa)}")
                if only_in_old:
                    st.markdown(f"**Only in get_stat_sources:** {', '.join(only_in_old)}")

    except Exception as e:
        import traceback
        st.error(f"Error running StatAggregator validation: {e}")
        st.code(traceback.format_exc())
