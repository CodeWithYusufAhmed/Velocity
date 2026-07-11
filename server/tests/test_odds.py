from decimal import Decimal

from app.game.odds import SLOTS, slot_probabilities, uniform_rtp


def test_eight_slots_with_spec_multipliers() -> None:
    assert [m for _, _, m in SLOTS] == [5, 5, 5, 5, 10, 15, 25, 45]
    assert [p for p, _, _ in SLOTS] == list(range(8))


def test_probabilities_sum_to_one() -> None:
    assert abs(sum(slot_probabilities()) - 1) < Decimal("1e-20")


def test_rtp_is_uniform_and_player_favored() -> None:
    r = uniform_rtp()
    # ~113.6% — every slot identical, always above 100% (never a house edge).
    assert Decimal("1.1359") < r < Decimal("1.1361")
    for p, (_, _, m) in zip(slot_probabilities(), SLOTS):
        assert abs(p * (m + 1) - r) < Decimal("1e-20")


def test_spec_probabilities_match_prompt() -> None:
    probs = [float(p) for p in slot_probabilities()]
    expected = [0.18933, 0.18933, 0.18933, 0.18933, 0.10327, 0.07100, 0.04369, 0.02470]
    for got, want in zip(probs, expected):
        assert abs(got - want) < 5e-5
