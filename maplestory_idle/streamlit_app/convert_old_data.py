"""
Convert old CSV data files to new Streamlit app format.
Run this script to migrate data from the old tkinter app.
"""
import csv
import os

# Paths to old data files
OLD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)))

# Output path
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "users")

def convert_old_data(username: str = "quarts"):
    """Convert all old CSV files to new format."""
    rows = []
    rows.append(['section', 'key', 'subkey', 'value'])

    # =========================================================================
    # Character Settings
    # =========================================================================
    char_file = os.path.join(OLD_DATA_DIR, "character_settings_save.csv")
    if os.path.exists(char_file):
        print(f"Reading {char_file}")
        with open(char_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                setting = row['setting']
                value = row['value']
                if setting == 'character_level':
                    rows.append(['character', 'level', '', value])
                elif setting == 'all_skills':
                    rows.append(['character', 'all_skills', '', value])
                elif setting == 'combat_mode':
                    rows.append(['character', 'combat_mode', '', value])

    # Default chapter
    rows.append(['character', 'chapter', '', 'Chapter 27'])

    # =========================================================================
    # Equipment Items
    # =========================================================================
    equip_file = os.path.join(OLD_DATA_DIR, "equipment_save.csv")
    if os.path.exists(equip_file):
        print(f"Reading {equip_file}")
        with open(equip_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slot = row['slot']
                # Map old fields to new format
                rows.append(['equipment', slot, 'name', row.get('name', slot.title())])
                rows.append(['equipment', slot, 'rarity', row.get('rarity', 'normal')])
                rows.append(['equipment', slot, 'tier', row.get('tier', '1')])
                rows.append(['equipment', slot, 'stars', row.get('stars', '0')])
                rows.append(['equipment', slot, 'is_special', row.get('is_special', 'False')])
                rows.append(['equipment', slot, 'base_attack', row.get('base_attack', '0')])
                rows.append(['equipment', slot, 'base_max_hp', row.get('base_hp', '0')])
                rows.append(['equipment', slot, 'base_third_stat', row.get('base_third', '0')])
                rows.append(['equipment', slot, 'sub_boss_damage', row.get('boss_dmg', '0')])
                rows.append(['equipment', slot, 'sub_normal_damage', row.get('normal_dmg', '0')])
                rows.append(['equipment', slot, 'sub_crit_rate', row.get('crit_rate', '0')])
                rows.append(['equipment', slot, 'sub_crit_damage', row.get('crit_dmg', '0')])
                rows.append(['equipment', slot, 'sub_attack_flat', row.get('attack_flat', '0')])
                rows.append(['equipment', slot, 'sub_skill_1st', row.get('skill_1st', '0')])
                rows.append(['equipment', slot, 'sub_skill_2nd', row.get('skill_2nd', '0')])
                rows.append(['equipment', slot, 'sub_skill_3rd', row.get('skill_3rd', '0')])
                rows.append(['equipment', slot, 'sub_skill_4th', row.get('skill_4th', '0')])
                rows.append(['equipment', slot, 'special_stat_type', row.get('special_stat_type', 'damage_pct')])
                rows.append(['equipment', slot, 'special_stat_value', row.get('special_stat_value', '0')])

    # =========================================================================
    # Equipment Potentials
    # =========================================================================
    pot_file = os.path.join(OLD_DATA_DIR, "..", "potentials_save.csv")
    if os.path.exists(pot_file):
        print(f"Reading {pot_file}")
        with open(pot_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slot = row['slot']
                pot_type = row['pot_type']  # 'regular' or 'bonus'

                if pot_type == 'regular':
                    rows.append(['potential', slot, 'tier', row.get('tier', 'legendary')])
                    rows.append(['potential', slot, 'regular_pity', row.get('pity', '0')])
                    rows.append(['potential', slot, 'line1_stat', row.get('line1_stat', '')])
                    rows.append(['potential', slot, 'line1_value', row.get('line1_value', '0')])
                    rows.append(['potential', slot, 'line2_stat', row.get('line2_stat', '')])
                    rows.append(['potential', slot, 'line2_value', row.get('line2_value', '0')])
                    rows.append(['potential', slot, 'line3_stat', row.get('line3_stat', '')])
                    rows.append(['potential', slot, 'line3_value', row.get('line3_value', '0')])
                elif pot_type == 'bonus':
                    rows.append(['potential', slot, 'bonus_tier', row.get('tier', 'legendary')])
                    rows.append(['potential', slot, 'bonus_pity', row.get('pity', '0')])
                    rows.append(['potential', slot, 'bonus_line1_stat', row.get('line1_stat', '')])
                    rows.append(['potential', slot, 'bonus_line1_value', row.get('line1_value', '0')])
                    rows.append(['potential', slot, 'bonus_line2_stat', row.get('line2_stat', '')])
                    rows.append(['potential', slot, 'bonus_line2_value', row.get('line2_value', '0')])
                    rows.append(['potential', slot, 'bonus_line3_stat', row.get('line3_stat', '')])
                    rows.append(['potential', slot, 'bonus_line3_value', row.get('line3_value', '0')])

    # =========================================================================
    # Hero Power Lines
    # =========================================================================
    hp_file = os.path.join(OLD_DATA_DIR, "hero_power_save.csv")
    if os.path.exists(hp_file):
        print(f"Reading {hp_file}")
        with open(hp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slot = int(row['slot'])
                line_id = f"line{slot}"
                rows.append(['hero_power_line', line_id, 'stat', row.get('stat_type', '')])
                rows.append(['hero_power_line', line_id, 'value', row.get('value', '0')])
                rows.append(['hero_power_line', line_id, 'tier', row.get('tier', 'common')])
                rows.append(['hero_power_line', line_id, 'locked', row.get('is_locked', 'False')])

    # =========================================================================
    # Hero Power Passives
    # =========================================================================
    hpp_file = os.path.join(OLD_DATA_DIR, "hero_power_passive_save.csv")
    if os.path.exists(hpp_file):
        print(f"Reading {hpp_file}")
        with open(hpp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stat_type = row['stat_type']
                level = row['level']
                rows.append(['hero_power_passive', stat_type, '', level])

    # =========================================================================
    # Maple Rank
    # =========================================================================
    mr_file = os.path.join(OLD_DATA_DIR, "maple_rank_save.csv")
    if os.path.exists(mr_file):
        print(f"Reading {mr_file}")
        with open(mr_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stat = row['stat']
                value = row['value']
                # Main stats go to maple_rank section
                if stat in ['current_stage', 'main_stat_level', 'special_main_stat_points']:
                    if stat == 'special_main_stat_points':
                        rows.append(['maple_rank', 'special_main_stat', '', value])
                    else:
                        rows.append(['maple_rank', stat, '', value])
                else:
                    # Stat levels go to maple_rank_stat section
                    rows.append(['maple_rank_stat', stat, '', value])

    # =========================================================================
    # Companions
    # =========================================================================
    comp_file = os.path.join(OLD_DATA_DIR, "companions_save.csv")
    if os.path.exists(comp_file):
        print(f"Reading {comp_file}")
        with open(comp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            slot_mapping = {
                'Main': 0, 'Sub 1': 1, 'Sub 2': 2, 'Sub 3': 3,
                'Sub 4': 4, 'Sub 5': 5, 'Sub 6': 6
            }
            for row in reader:
                row_type = row['type']
                key = row['key']

                if row_type == 'inventory':
                    level = row.get('level', '0')
                    rows.append(['companion_level', key, '', level])
                elif row_type == 'equipped':
                    slot_name = row.get('slot', '')
                    if slot_name in slot_mapping:
                        slot_idx = slot_mapping[slot_name]
                        rows.append(['equipped_companion', str(slot_idx), '', key])

    # =========================================================================
    # Weapons
    # =========================================================================
    weap_file = os.path.join(OLD_DATA_DIR, "weapons_save.csv")
    if os.path.exists(weap_file):
        print(f"Reading {weap_file}")
        with open(weap_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            equipped_idx = None
            for idx, row in enumerate(reader):
                rarity = row.get('rarity', 'normal')
                tier = row.get('tier', '1')
                level = row.get('level', '1')
                is_equipped = row.get('is_equipped', 'False')

                rows.append(['weapon_inv', str(idx), 'rarity', rarity])
                rows.append(['weapon_inv', str(idx), 'tier', tier])
                rows.append(['weapon_inv', str(idx), 'level', level])

                if is_equipped.lower() == 'true':
                    equipped_idx = idx

            if equipped_idx is not None:
                rows.append(['equipped_weapon', 'index', '', str(equipped_idx)])

    # =========================================================================
    # Artifacts
    # =========================================================================
    art_file = os.path.join(OLD_DATA_DIR, "artifacts_save.csv")
    if os.path.exists(art_file):
        print(f"Reading {art_file}")
        with open(art_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                art_key = row['artifact_key']
                stars = row.get('awakening_stars', '0')
                slot = row.get('equipped_slot', '-1')

                # Always add to inventory
                rows.append(['artifact_inventory', art_key, 'stars', stars])
                rows.append(['artifact_inventory', art_key, 'pot1', row.get('pot1_stat', '')])
                rows.append(['artifact_inventory', art_key, 'pot1_val', row.get('pot1_value', '0')])
                rows.append(['artifact_inventory', art_key, 'pot1_tier', row.get('pot1_tier', '')])
                rows.append(['artifact_inventory', art_key, 'pot2', row.get('pot2_stat', '')])
                rows.append(['artifact_inventory', art_key, 'pot2_val', row.get('pot2_value', '0')])
                rows.append(['artifact_inventory', art_key, 'pot2_tier', row.get('pot2_tier', '')])
                rows.append(['artifact_inventory', art_key, 'pot3', row.get('pot3_stat', '')])
                rows.append(['artifact_inventory', art_key, 'pot3_val', row.get('pot3_value', '0')])
                rows.append(['artifact_inventory', art_key, 'pot3_tier', row.get('pot3_tier', '')])

                # If equipped (slot >= 0), add to equipped slots
                if int(slot) >= 0:
                    slot_key = f"slot{slot}"
                    rows.append(['artifact_equipped', slot_key, 'artifact', art_key])
                    rows.append(['artifact_equipped', slot_key, 'pot1', row.get('pot1_stat', '')])
                    rows.append(['artifact_equipped', slot_key, 'pot1_val', row.get('pot1_value', '0')])
                    rows.append(['artifact_equipped', slot_key, 'pot2', row.get('pot2_stat', '')])
                    rows.append(['artifact_equipped', slot_key, 'pot2_val', row.get('pot2_value', '0')])
                    rows.append(['artifact_equipped', slot_key, 'pot3', row.get('pot3_stat', '')])
                    rows.append(['artifact_equipped', slot_key, 'pot3_val', row.get('pot3_value', '0')])

    # =========================================================================
    # Equipment Sets
    # =========================================================================
    sets_file = os.path.join(OLD_DATA_DIR, "equipment_sets_save.csv")
    if os.path.exists(sets_file):
        print(f"Reading {sets_file}")
        with open(sets_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                set_type = row['type']
                value = row['value']
                rows.append(['equipment_sets', set_type, '', value])

    # =========================================================================
    # Manual Adjustments
    # =========================================================================
    adj_file = os.path.join(OLD_DATA_DIR, "manual_adjustments_save.csv")
    if os.path.exists(adj_file):
        print(f"Reading {adj_file}")
        with open(adj_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stat = row['stat']
                adjustment = row['adjustment']
                rows.append(['manual_adj', stat, '', adjustment])

    # =========================================================================
    # Write output file
    # =========================================================================
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"{username.lower()}_data.csv")

    print(f"\nWriting {len(rows)-1} rows to {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

    print(f"Done! Data exported to {output_file}")
    return output_file


if __name__ == "__main__":
    convert_old_data("quarts")
