#!/usr/bin/env python3
"""
MapleStory Idle - Interactive Calculator
=========================================
CLI tool for damage calculations and stat comparisons.

Usage:
    python -m maplestory_idle.calculator
    
Or:
    python calculator.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .constants import (
    DAMAGE_AMP_DIVISOR,
    HEX_MULTIPLIER_PER_STACK,
    ENEMY_DEFENSE_VALUES,
    BOWMASTER_FD_SOURCES,
)


@dataclass
class CharacterState:
    """Current character stats for calculations."""
    
    # DEX
    dex_flat_pool: int = 18700
    dex_percent: float = 1.265
    str_flat: int = 200
    
    # Damage %
    damage_percent_base: float = 4.841
    hex_stacks: int = 3
    
    # Damage Amp
    damage_amp: float = 23.2
    
    # Final Damage
    fd_sources: Dict[str, float] = field(default_factory=lambda: {
        "bottom": 0.13, "guild": 0.10, "extreme_archery": 0.217
    })
    mortal_blow_active: bool = False
    fire_flower_targets: int = 0
    
    # Critical
    critical_rate: float = 1.119
    critical_damage: float = 1.845
    book_of_ancient: bool = True
    
    # Defense Pen
    def_pen_sources: List[float] = field(default_factory=lambda: [0.424, 0.19, 0.165])
    
    # Damage types
    boss_damage: float = 0.645
    normal_damage: float = 1.258
    
    # Attack
    base_attack: int = 50000
    
    def get_total_dex(self) -> float:
        return self.dex_flat_pool * (1 + self.dex_percent)
    
    def get_damage_percent(self) -> float:
        return self.damage_percent_base * (HEX_MULTIPLIER_PER_STACK ** self.hex_stacks)
    
    def get_final_damage(self) -> float:
        sources = dict(self.fd_sources)
        if self.mortal_blow_active:
            sources["mortal_blow"] = 0.144
        if self.fire_flower_targets > 0:
            sources["fire_flower"] = min(self.fire_flower_targets, 10) * 0.012
        mult = 1.0
        for fd in sources.values():
            mult *= (1 + fd)
        return mult - 1
    
    def get_defense_pen(self) -> float:
        remaining = 1.0
        for ied in self.def_pen_sources:
            remaining *= (1 - ied)
        return 1 - remaining
    
    def get_crit_damage(self) -> float:
        cd = self.critical_damage
        if self.book_of_ancient:
            cd += self.critical_rate * 0.36
        return cd
    
    def calculate_damage(self, enemy_def: float = 0.752, vs_boss: bool = True) -> float:
        """Calculate total damage against an enemy."""
        stat_prop = (self.get_total_dex() * 0.01) + (self.str_flat * 0.0025)
        damage_type = self.boss_damage if vs_boss else self.normal_damage
        
        damage = self.base_attack
        damage *= (1 + stat_prop)
        damage *= (1 + self.get_damage_percent() + damage_type)
        damage *= (1 + self.damage_amp / DAMAGE_AMP_DIVISOR)
        damage *= (1 + self.get_final_damage())
        damage *= (1 + self.get_crit_damage())
        damage /= (1 + enemy_def * (1 - self.get_defense_pen()))
        
        return damage


def print_stat_summary(state: CharacterState):
    """Print current stat summary."""
    print("\n" + "=" * 60)
    print("CHARACTER STAT SUMMARY")
    print("=" * 60)
    print(f"Total DEX:           {state.get_total_dex():,.0f}")
    print(f"Damage %:            {state.get_damage_percent() * 100:.1f}%")
    print(f"Damage Amp:          {state.damage_amp:.1f}%")
    print(f"Final Damage:        {state.get_final_damage() * 100:.1f}%")
    print(f"Defense Pen:         {state.get_defense_pen() * 100:.1f}%")
    print(f"Crit Damage:         {state.get_crit_damage() * 100:.1f}%")
    print(f"Boss Damage:         {state.boss_damage * 100:.1f}%")
    print("=" * 60)


def compare_stat_change(state: CharacterState, stat: str, amount: float) -> Dict:
    """Compare damage before/after a stat change."""
    before = state.calculate_damage()
    
    # Make a copy and modify
    import copy
    new_state = copy.deepcopy(state)
    
    if stat == "dex_flat":
        new_state.dex_flat_pool += int(amount)
    elif stat == "dex_percent":
        new_state.dex_percent += amount
    elif stat == "damage_percent":
        new_state.damage_percent_base += amount
    elif stat == "damage_amp":
        new_state.damage_amp += amount
    elif stat == "final_damage":
        new_state.fd_sources["added"] = amount
    elif stat == "def_pen":
        new_state.def_pen_sources.append(amount)
    elif stat == "crit_damage":
        new_state.critical_damage += amount
    elif stat == "boss_damage":
        new_state.boss_damage += amount
    
    after = new_state.calculate_damage()
    change_pct = (after / before - 1) * 100
    
    return {
        "before": before,
        "after": after,
        "change": after - before,
        "change_pct": change_pct,
    }


def main():
    """Interactive calculator main loop."""
    state = CharacterState()
    
    print("\n" + "=" * 60)
    print("MAPLESTORY IDLE - DAMAGE CALCULATOR")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("1. View current stats")
        print("2. Calculate damage vs enemy")
        print("3. Compare stat change")
        print("4. Toggle buffs")
        print("5. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "1":
            print_stat_summary(state)
            
        elif choice == "2":
            print("\nKnown locations:")
            for i, (loc, def_val) in enumerate(ENEMY_DEFENSE_VALUES.items(), 1):
                print(f"  {i}. {loc} (Def: {def_val})")
            
            loc_choice = input("Select location (or enter defense value): ").strip()
            try:
                if loc_choice.isdigit() and 1 <= int(loc_choice) <= len(ENEMY_DEFENSE_VALUES):
                    enemy_def = list(ENEMY_DEFENSE_VALUES.values())[int(loc_choice) - 1]
                else:
                    enemy_def = float(loc_choice)
            except:
                enemy_def = 0.752
            
            is_boss = input("Is boss? (y/n): ").lower() == "y"
            damage = state.calculate_damage(enemy_def, is_boss)
            print(f"\nDamage: {damage:,.0f}")
            
        elif choice == "3":
            print("\nStats to compare:")
            print("  1. dex_flat (+1000)")
            print("  2. dex_percent (+0.10 = 10%)")
            print("  3. damage_percent (+0.10 = 10%)")
            print("  4. final_damage (+0.10 = 10%)")
            print("  5. def_pen (+0.10 = 10%)")
            print("  6. crit_damage (+0.10 = 10%)")
            
            stat_choice = input("Choose stat: ").strip()
            amount = float(input("Amount to add: ").strip())
            
            stat_map = {
                "1": "dex_flat", "2": "dex_percent", "3": "damage_percent",
                "4": "final_damage", "5": "def_pen", "6": "crit_damage"
            }
            stat = stat_map.get(stat_choice, "damage_percent")
            
            result = compare_stat_change(state, stat, amount)
            print(f"\nBefore: {result['before']:,.0f}")
            print(f"After:  {result['after']:,.0f}")
            print(f"Change: +{result['change']:,.0f} ({result['change_pct']:+.2f}%)")
            
        elif choice == "4":
            print(f"\nMortal Blow: {'ON' if state.mortal_blow_active else 'OFF'}")
            print(f"Fire Flower Targets: {state.fire_flower_targets}")
            print(f"Hex Stacks: {state.hex_stacks}")
            
            toggle = input("Toggle (m=mortal, f=flower, h=hex): ").strip().lower()
            if toggle == "m":
                state.mortal_blow_active = not state.mortal_blow_active
            elif toggle == "f":
                state.fire_flower_targets = int(input("Targets (0-10): "))
            elif toggle == "h":
                state.hex_stacks = int(input("Stacks (0-3): "))
            
        elif choice == "5":
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
