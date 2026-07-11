from decimal import Decimal

from app.game import rng
from app.game.odds import slot_probabilities


def test_commitment_binds_seed_and_round() -> None:
    seed = rng.new_server_seed()
    c = rng.commitment(seed, 42)
    assert c == rng.commitment(seed, 42)          # deterministic
    assert c != rng.commitment(seed, 43)          # bound to round id
    assert c != rng.commitment(rng.new_server_seed(), 42)  # bound to seed


def test_selection_deterministic_and_in_range() -> None:
    probs = slot_probabilities()
    seed = rng.new_server_seed()
    first = rng.select_slot(seed, 7, probs)
    assert first == rng.select_slot(seed, 7, probs)
    assert 0 <= first < 8


def test_selection_covers_edge_rolls() -> None:
    probs = slot_probabilities()
    # u == ~1 boundary can't escape the table
    assert rng.select_slot("ff" * 32, 1, [Decimal("0.5"), Decimal("0.5")]) in (0, 1)


def test_distribution_roughly_matches_probabilities() -> None:
    """50k rounds: each slot's observed frequency within 15% relative error."""
    probs = slot_probabilities()
    n = 50_000
    hits = [0] * 8
    seed = rng.new_server_seed()
    for i in range(n):
        hits[rng.select_slot(seed, i, probs)] += 1
    for h, p in zip(hits, probs):
        assert abs(h / n - float(p)) / float(p) < 0.15
