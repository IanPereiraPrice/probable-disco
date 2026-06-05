"""
Unit tests for Equipment class bidirectional base/amplified conversion.

Uses verified data from default_character.csv:
- Hat: ★17, base_attack=2686, sub_crit_rate=5.6, etc.
- Necklace: ★19, is_special=True, damage_pct=68.5, etc.

Tests:
1. Main Amplify rates match STARFORCE_TABLE
2. Sub Amplify rates match STARFORCE_TABLE
3. Base → Amplified conversion
4. Amplified → Base conversion (for OCR)
5. get_stats() returns correct StatBlock
"""
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import unittest
from equipment import Equipment, get_amplify_multiplier, STARFORCE_TABLE


class TestAmplifyRates(unittest.TestCase):
    """Verify amplification rates match STARFORCE_TABLE."""

    def test_main_amplify_star_0(self):
        """★0 should have 1.0x multiplier (no amplification)."""
        rate = get_amplify_multiplier(0, is_sub=False)
        self.assertEqual(rate, 1.0)

    def test_main_amplify_star_17(self):
        """★17 main amplify should be 1 + 4.00 = 5.00x (verified from table)."""
        # Stage 16 → 17 shows main_amplify_after = 4.00
        rate = get_amplify_multiplier(17, is_sub=False)
        self.assertAlmostEqual(rate, 5.0, places=2)

    def test_main_amplify_star_18(self):
        """★18 main amplify should be 1 + 4.50 = 5.50x."""
        rate = get_amplify_multiplier(18, is_sub=False)
        self.assertAlmostEqual(rate, 5.5, places=2)

    def test_main_amplify_star_19(self):
        """★19 main amplify should be 1 + 5.00 = 6.00x."""
        rate = get_amplify_multiplier(19, is_sub=False)
        self.assertAlmostEqual(rate, 6.0, places=2)

    def test_sub_amplify_star_17(self):
        """★17 sub amplify should be 1 + 0.70 = 1.70x (stage 16 completed)."""
        rate = get_amplify_multiplier(17, is_sub=True)
        self.assertAlmostEqual(rate, 1.7, places=2)

    def test_sub_amplify_star_18(self):
        """★18 sub amplify should be 1 + 0.80 = 1.80x (stage 17 completed)."""
        rate = get_amplify_multiplier(18, is_sub=True)
        self.assertAlmostEqual(rate, 1.8, places=2)

    def test_sub_amplify_star_19(self):
        """★19 sub amplify should be 1 + 0.90 = 1.90x (stage 18 completed)."""
        rate = get_amplify_multiplier(19, is_sub=True)
        self.assertAlmostEqual(rate, 1.9, places=2)


class TestEquipmentBaseToAmplified(unittest.TestCase):
    """Test base → amplified conversion using default_character data."""

    def test_hat_attack_amplification(self):
        """
        Hat ★17: base_attack=2686
        Expected amplified: 2686 * 5.0 = 13430
        """
        equip = Equipment(slot='hat', stars=17)
        equip.set_base('attack', 2686)
        amplified = equip.get_amplified('attack')
        self.assertAlmostEqual(amplified, 13430, delta=10)

    def test_hat_sub_crit_rate_amplification(self):
        """
        Hat ★17: sub_crit_rate=5.6 (base)
        Sub amplify at ★17 = 1.7x
        Expected amplified: 5.6 * 1.7 = 9.52
        """
        equip = Equipment(slot='hat', stars=17)
        equip.set_base('crit_rate', 5.6)
        amplified = equip.get_amplified('crit_rate')
        self.assertAlmostEqual(amplified, 9.52, delta=0.1)

    def test_necklace_damage_pct_amplification(self):
        """
        Necklace ★19: special_stat_value=68.5 (damage_pct, base)
        Sub amplify at ★19 = 1.9x
        Expected amplified: 68.5 * 1.9 = 130.15
        """
        equip = Equipment(slot='necklace', stars=19, is_special=True)
        equip.set_base('damage_pct', 68.5)
        amplified = equip.get_amplified('damage_pct')
        self.assertAlmostEqual(amplified, 130.15, delta=1.0)

    def test_top_attack_amplification(self):
        """
        Top ★18: base_attack=3974
        Main amplify at ★18 = 5.5x
        Expected amplified: 3974 * 5.5 = 21857
        """
        equip = Equipment(slot='top', stars=18)
        equip.set_base('attack', 3974)
        amplified = equip.get_amplified('attack')
        self.assertAlmostEqual(amplified, 21857, delta=10)


class TestEquipmentAmplifiedToBase(unittest.TestCase):
    """Test amplified → base conversion (for OCR data input)."""

    def test_hat_attack_reverse(self):
        """
        If we observe 13430 amplified attack on a ★17 hat,
        base should be ~2686.
        """
        equip = Equipment(slot='hat', stars=17)
        equip.set_amplified('attack', 13430)
        base = equip.get_base('attack')
        self.assertAlmostEqual(base, 2686, delta=2)

    def test_necklace_damage_pct_reverse(self):
        """
        If we observe 130.15% damage on a ★19 necklace (amplified),
        base should be ~68.5%.
        """
        equip = Equipment(slot='necklace', stars=19, is_special=True)
        equip.set_amplified('damage_pct', 130.15)
        base = equip.get_base('damage_pct')
        self.assertAlmostEqual(base, 68.5, delta=0.5)

    def test_round_trip_conversion(self):
        """Setting base then getting amplified then setting as amplified should give same base."""
        equip = Equipment(slot='gloves', stars=17)
        original_base = 2944

        equip.set_base('attack', original_base)
        amplified = equip.get_amplified('attack')

        equip2 = Equipment(slot='gloves', stars=17)
        equip2.set_amplified('attack', amplified)
        recovered_base = equip2.get_base('attack')

        self.assertAlmostEqual(recovered_base, original_base, delta=0.1)


class TestEquipmentGetStats(unittest.TestCase):
    """Test get_stats() returns correct StatBlock."""

    def test_basic_stat_block(self):
        """Test that get_stats() returns a StatBlock with correct values."""
        equip = Equipment(slot='hat', stars=17)
        equip.set_base('attack', 2686)
        equip.set_base('max_hp', 14869)
        equip.set_base('crit_rate', 5.6)
        equip.set_base('normal_damage', 5.9)

        stats = equip.get_stats()

        # attack_flat should include amplified main attack
        expected_attack = 2686 * 5.0  # ★17 main amplify
        self.assertAlmostEqual(stats.attack_flat, expected_attack, delta=10)

        # max_hp should be amplified
        expected_hp = 14869 * 5.0
        self.assertAlmostEqual(stats.max_hp, expected_hp, delta=50)

        # crit_rate should be amplified with sub amplify
        expected_cr = 5.6 * 1.7  # ★17 sub amplify = 1.7x
        self.assertAlmostEqual(stats.crit_rate, expected_cr, delta=0.2)

    def test_special_item_stat_block(self):
        """Test special item stats (damage_pct) in StatBlock."""
        equip = Equipment(slot='necklace', stars=19, is_special=True)
        equip.set_base('attack', 2659)
        equip.set_base('damage_pct', 68.5)
        equip.set_base('crit_damage', 8.58)

        stats = equip.get_stats()

        # damage_pct should be amplified
        expected_dmg = 68.5 * 1.9  # ★19 sub amplify = 1.9x
        self.assertAlmostEqual(stats.damage_pct, expected_dmg, delta=1.0)

    def test_stat_block_addition(self):
        """Test that two StatBlocks can be added together."""
        equip1 = Equipment(slot='hat', stars=17)
        equip1.set_base('attack', 2686)
        equip1.set_base('crit_rate', 5.6)

        equip2 = Equipment(slot='top', stars=18)
        equip2.set_base('attack', 3974)
        equip2.set_base('crit_rate', 0)

        stats1 = equip1.get_stats()
        stats2 = equip2.get_stats()

        combined = stats1 + stats2

        expected_attack = (2686 * 5.0) + (3974 * 5.5)
        self.assertAlmostEqual(combined.attack_flat, expected_attack, delta=20)


class TestEquipmentSerialization(unittest.TestCase):
    """Test to_dict() and from_dict() round-trip."""

    def test_to_dict_from_dict_round_trip(self):
        """Equipment should serialize and deserialize correctly."""
        original = Equipment(
            slot='hat',
            name='Zakum Helmet',
            rarity='Normal',
            tier=3,
            stars=17,
            is_special=True,
        )
        original.set_base('attack', 2686)
        original.set_base('max_hp', 14869)
        original.set_base('third_stat', 505)
        original.set_base('crit_rate', 5.6)
        original.set_base('normal_damage', 5.9)
        original.set_base('sub_attack', 2724)
        original.set_base('final_damage', 3.0)  # special stat

        # Serialize
        data = original.to_dict()

        # Deserialize
        restored = Equipment.from_dict(data)

        # Verify all fields match
        self.assertEqual(restored.slot, 'hat')
        self.assertEqual(restored.name, 'Zakum Helmet')
        self.assertEqual(restored.rarity, 'Normal')
        self.assertEqual(restored.tier, 3)
        self.assertEqual(restored.stars, 17)
        self.assertEqual(restored.is_special, True)

        # Verify stats match
        self.assertAlmostEqual(restored.get_base('attack'), 2686, delta=0.1)
        self.assertAlmostEqual(restored.get_base('max_hp'), 14869, delta=0.1)
        self.assertAlmostEqual(restored.get_base('crit_rate'), 5.6, delta=0.01)
        self.assertAlmostEqual(restored.get_base('final_damage'), 3.0, delta=0.01)


class TestConvenienceProperties(unittest.TestCase):
    """Test the convenience properties (base_attack, amplified_attack, etc.)."""

    def test_base_attack_property(self):
        """Test base_attack property getter/setter."""
        equip = Equipment(slot='hat', stars=17)
        equip.base_attack = 2686
        self.assertEqual(equip.base_attack, 2686)

    def test_amplified_attack_property(self):
        """Test amplified_attack property getter/setter."""
        equip = Equipment(slot='hat', stars=17)
        equip.base_attack = 2686
        self.assertAlmostEqual(equip.amplified_attack, 13430, delta=10)

        # Set via amplified
        equip.amplified_attack = 15000
        self.assertAlmostEqual(equip.base_attack, 3000, delta=1)


if __name__ == '__main__':
    unittest.main()
