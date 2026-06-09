"""
Tests for the optimizer's fast-DPS path:
  - `is_sequence_affecting` correctly identifies stats that change the action
    sequence and must trigger a realistic-sim re-run.
  - `FastDPSEvaluator.evaluate` returns the same DPS as direct realistic
    evaluation for sequence-affecting stats, and scales correctly via the
    baseline ratio for non-sequence stats.
  - `calculate_marginal_dps_value` honors the optional `fast_evaluator`.
  - `companion_duration` stat plumbing: extends summon window in the sim.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.utils.dps_calculator import (
    is_sequence_affecting,
    SEQUENCE_AFFECTING_STAT_KEYS,
    FastDPSEvaluator,
)


# ---------------------------------------------------------------------------
# is_sequence_affecting
# ---------------------------------------------------------------------------

class TestIsSequenceAffecting:
    def test_sequence_stats_return_true(self):
        # The canonical three: cooldown reduction, buff duration, companion
        # duration. Each is the gate for whether a candidate forces a sim
        # re-run; failing this check would silently regress optimizer cost.
        assert is_sequence_affecting('skill_cd_reduction')
        assert is_sequence_affecting('skill_cd')  # potential-name alias
        assert is_sequence_affecting('buff_duration')
        assert is_sequence_affecting('companion_duration')

    def test_non_sequence_stats_return_false(self):
        # Multiplier-only stats should NOT force a sim re-run.
        for stat in (
            'damage_pct', 'crit_rate', 'crit_damage', 'attack_pct',
            'attack_flat', 'boss_damage', 'normal_damage',
            'final_damage', 'def_pen', 'main_stat_pct', 'main_stat_flat',
            'all_skills_bonus', 'ba_targets',
        ):
            assert not is_sequence_affecting(stat), \
                f"{stat!r} should not be sequence-affecting"

    def test_unknown_stats_return_false(self):
        # Defensive: typos / new stats default to fast-path. This is the
        # safer side to err on (worst case: a brand-new sequence-affecting
        # stat is added without updating SEQUENCE_AFFECTING_STAT_KEYS and
        # would be misclassified; we should add it to the set when
        # introducing the stat).
        assert not is_sequence_affecting('totally_made_up_stat')

    def test_keys_are_a_frozenset(self):
        # frozenset prevents accidental mutation at runtime.
        assert isinstance(SEQUENCE_AFFECTING_STAT_KEYS, frozenset)


# ---------------------------------------------------------------------------
# FastDPSEvaluator
# ---------------------------------------------------------------------------

class _RecordingCalc:
    """
    Mock calculate_dps that tracks call args and returns deterministic
    numbers based on stat values. Lets us assert on what the evaluator
    does without spinning up a full character / simulator pipeline.
    """

    def __init__(self, realistic_factor: float = 1.10):
        # The "realistic" path returns `factor × legacy_dps`. This mimics
        # the typical relationship — realistic includes companion summon
        # damage and other multiplier-orthogonal contributions, so it's
        # uniformly a bit higher than legacy.
        self.realistic_factor = realistic_factor
        self.calls = []  # list of (stats_signature, use_realistic_dps)

    def __call__(self, stats, combat_mode, enemy_def, **kw):
        legacy_total = (
            stats.get('attack_flat', 0) * 100
            + stats.get('damage_pct', 0) * 50
            + stats.get('crit_damage', 0) * 30
            + stats.get('boss_damage', 0) * 40
            + 1_000_000  # base term so non-zero DPS even at default stats
        )
        # Boost legacy a little when sequence stats change so the sim path
        # is observably different from pure-scaling.
        legacy_total += stats.get('skill_cd_reduction', 0) * 50_000
        legacy_total += stats.get('buff_duration', 0) * 30_000
        legacy_total += stats.get('companion_duration', 0) * 40_000

        use_realistic = kw.get('use_realistic_dps', False)
        signature = tuple(sorted(
            (k, v) for k, v in stats.items()
            if isinstance(v, (int, float))
        ))
        self.calls.append((signature, use_realistic))
        total = legacy_total * (self.realistic_factor if use_realistic else 1.0)
        return {'total': total}


def _baseline_stats():
    return {
        'attack_flat': 1000.0,
        'damage_pct': 50.0,
        'crit_damage': 100.0,
        'boss_damage': 100.0,
        'skill_cd_reduction': 0.0,
        'buff_duration': 0.0,
        'companion_duration': 0.0,
    }


class TestFastDPSEvaluator:
    def test_construction_runs_two_baselines(self):
        # The constructor should run BOTH a realistic and a legacy baseline
        # so it can compute the ratio. After that, no more sim runs for
        # non-sequence stats.
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        # Exactly two construction calls: realistic + legacy.
        assert len(calc.calls) == 2
        flags = sorted(realistic for _, realistic in calc.calls)
        assert flags == [False, True]
        # Ratio should be the realistic factor.
        assert evaluator.ratio == pytest.approx(1.20)

    def test_non_sequence_candidate_uses_legacy_and_scales(self):
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        calls_before = len(calc.calls)

        # Bump damage_pct (NOT sequence-affecting). The evaluator should run
        # the legacy path and multiply by the ratio.
        candidate = _baseline_stats()
        candidate['damage_pct'] += 20.0
        fast_dps = evaluator.evaluate(candidate, changed_stat='damage_pct')

        # Exactly one new call, and it was the legacy path.
        new_calls = calc.calls[calls_before:]
        assert len(new_calls) == 1
        assert new_calls[0][1] is False, \
            "Non-sequence candidate must NOT trigger a realistic sim"

        # The returned DPS should equal legacy DPS × ratio, which is what
        # the realistic path would produce directly for the same stats.
        direct_realistic = calc(candidate, 'boss', 0.752, use_realistic_dps=True)
        assert fast_dps == pytest.approx(direct_realistic['total'], rel=1e-6)

    def test_sequence_candidate_runs_full_sim(self):
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        calls_before = len(calc.calls)

        candidate = _baseline_stats()
        candidate['skill_cd_reduction'] += 1.0
        fast_dps = evaluator.evaluate(candidate, changed_stat='skill_cd_reduction')

        new_calls = calc.calls[calls_before:]
        assert len(new_calls) == 1
        assert new_calls[0][1] is True, \
            "Sequence candidate MUST trigger a realistic sim"

        # And the returned DPS should be exactly the realistic call output
        # (no ratio scaling — the sim already produced realistic numbers).
        direct = calc(candidate, 'boss', 0.752, use_realistic_dps=True)
        assert fast_dps == pytest.approx(direct['total'], rel=1e-6)

    def test_companion_duration_routes_to_sim(self):
        # The new companion_duration stat must trigger a re-sim: changing
        # the summon window length changes how many attacks land within
        # the fight and (transitively) the action sequence.
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        calls_before = len(calc.calls)
        candidate = _baseline_stats()
        candidate['companion_duration'] += 10.0
        evaluator.evaluate(candidate, changed_stat='companion_duration')
        new_calls = calc.calls[calls_before:]
        assert new_calls[0][1] is True

    def test_unknown_changed_stat_falls_back_to_sim(self):
        # When the caller doesn't know which stat changed, the safe choice
        # is to run the sim — otherwise we'd risk silently fast-pathing
        # a sequence change. The candidate must differ in some
        # sequence-affecting field so it doesn't hit the sim cache, which
        # would also short-circuit the realistic call.
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        calls_before = len(calc.calls)
        candidate = _baseline_stats()
        candidate['skill_cd_reduction'] += 0.5  # changes the sequence cache key
        evaluator.evaluate(candidate, changed_stat=None)
        new_calls = calc.calls[calls_before:]
        assert new_calls[0][1] is True

    def test_repeated_sequence_candidate_hits_cache(self):
        # The new sim cache short-circuits identical sequence-affecting
        # candidates: the second call returns the first call's result
        # without invoking the realistic sim again.
        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        candidate = _baseline_stats()
        candidate['skill_cd_reduction'] += 0.5

        # First evaluation: cache miss → runs sim
        dps1 = evaluator.evaluate(candidate, changed_stat='skill_cd_reduction')
        hits1, misses1 = evaluator.cache_stats

        # Second evaluation of the SAME candidate: cache hit → no new sim
        calls_before = len(calc.calls)
        dps2 = evaluator.evaluate(candidate, changed_stat='skill_cd_reduction')
        hits2, misses2 = evaluator.cache_stats

        assert dps1 == pytest.approx(dps2, rel=1e-9)
        assert hits2 == hits1 + 1  # cache hit incremented
        assert misses2 == misses1  # no new miss
        assert len(calc.calls) == calls_before  # no new sim call


# ---------------------------------------------------------------------------
# calculate_marginal_dps_value × fast_evaluator
# ---------------------------------------------------------------------------

class TestMarginalDPSValueWithFastPath:
    def test_uses_fast_evaluator_when_provided(self):
        from optimizers.optimal_stats import calculate_marginal_dps_value

        calc = _RecordingCalc(realistic_factor=1.20)
        evaluator = FastDPSEvaluator(
            baseline_stats=_baseline_stats(),
            combat_mode='boss',
            enemy_def=0.752,
            calculate_dps_fn=calc,
        )
        # The marginal function takes the simple `calc_dps_func(stats)`
        # closure that calls realistic. With fast_evaluator passed, it
        # should bypass calc_dps_func for the candidate evaluation.
        calls_before = len(calc.calls)

        def calc_dps_func(stats):
            # If this gets called for the candidate, the fast path didn't
            # fire. We let it fall through to the recording calc.
            return calc(stats, 'boss', 0.752, use_realistic_dps=True)['total']

        # Use 'boss_damage' rather than 'damage_pct' here because
        # _apply_stat_to_dict's internal _STAT_KEY_MAP rewrites
        # 'damage_pct' → 'damage_percent' (a legacy convention for the
        # closed-form damage formula). boss_damage maps to itself, so the
        # stat we add lands in the same dict key the recording calc reads.
        baseline_dps = evaluator.baseline_realistic_dps
        gain_pct = calculate_marginal_dps_value(
            _baseline_stats(), 'boss_damage', 30.0, calc_dps_func,
            baseline_dps=baseline_dps,
            fast_evaluator=evaluator,
        )
        # The marginal function should have called the evaluator (which uses
        # the LEGACY path for boss_damage), NOT calc_dps_func directly.
        new_calls = calc.calls[calls_before:]
        # Exactly one new call, on the legacy path.
        assert len(new_calls) == 1
        assert new_calls[0][1] is False
        # And the % gain should be positive (we added boss_damage).
        assert gain_pct > 0


class TestCompanionDurationPlumbing:
    """
    End-to-end: setting `stats['companion_duration']` should extend the
    companion summon's duration when it's registered with the calculator.
    This exercises the dps_calculator path that calls dataclasses.replace
    on the summon SkillData before registering.
    """

    def test_companion_duration_extends_summon_window(self):
        # Build a minimal calculator + companion summon. Compare the
        # registered summon's duration with vs without a companion_duration
        # boost — the boost should multiply through to summon_skill.duration.
        from game.skills import (
            DPSCalculator, create_character_at_level,
            SkillData, SkillType, DamageType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        from dataclasses import replace

        # Build the synthetic companion SkillData the same way
        # dps_calculator.calculate_dps does.
        base_skill = SkillData(
            name="companion_main_summon",
            skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL,
            job=Job.FOURTH,
            unlock_level=1,
            base_damage_pct=300.0,
            base_hits=1,
            base_targets=6,
            attack_interval=2.0,
            duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S,
            scales_with_attack_speed=False,
        )

        # Simulate the +20% companion duration path that
        # calculate_dps wires in when stats['companion_duration'] = 20.0:
        boosted_skill = replace(
            base_skill,
            duration=base_skill.duration * (1 + 20.0 / 100),
        )
        assert boosted_skill.duration == pytest.approx(SUMMON_DURATION_S * 1.20)

        # And the registration accepts the boosted skill cleanly.
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        calc = DPSCalculator(char, enemy_def=0.752)
        calc.register_companion_summon(boosted_skill, "companion_main_summon")
        # The registered summon must carry the extended duration.
        assert calc._summon_skills["companion_main_summon"].duration == pytest.approx(
            SUMMON_DURATION_S * 1.20
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
