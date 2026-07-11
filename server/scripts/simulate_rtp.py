"""M3 gate check: simulate 1,000,000 rounds and print measured per-slot RTP.

Bets 1,000 coins on EVERY slot every round, using the exact production RNG
(fresh random seed per round, same selection code the engine runs). Measured
RTP must come out ≈ 113.6% on every slot.

Run:  cd server && .venv\\Scripts\\python -m scripts.simulate_rtp [rounds]
"""

import sys
from decimal import Decimal

from app.game import rng
from app.game.odds import SLOTS, slot_probabilities, uniform_rtp

STAKE = 1_000


def main(rounds: int = 1_000_000) -> None:
    probs = slot_probabilities()
    hits = [0] * len(SLOTS)
    for round_id in range(1, rounds + 1):
        seed = rng.new_server_seed()
        hits[rng.select_slot(seed, round_id, probs)] += 1
        if round_id % 100_000 == 0:
            print(f"  ... {round_id:,} rounds", file=sys.stderr)

    expected = float(uniform_rtp())
    print(f"\nrounds simulated: {rounds:,}   stake per slot per round: {STAKE:,}")
    print(f"theoretical RTP (every slot): {expected:.4%}\n")
    print(f"{'slot':<18}{'mult':>6}{'hits':>10}{'measured p':>13}{'measured RTP':>15}")
    worst = 0.0
    for (pos, name, mult), h, p in zip(SLOTS, hits, probs):
        measured_p = h / rounds
        # Each round: stake lost on 8 slots, (m+1)*stake back on the winner.
        measured_rtp = measured_p * (mult + 1)
        worst = max(worst, abs(measured_rtp - expected))
        print(f"{name:<18}{'x' + str(mult):>6}{h:>10,}{measured_p:>13.5%}{measured_rtp:>15.4%}")

    total_bet = rounds * STAKE * len(SLOTS)
    total_back = sum(h * (m + 1) * STAKE for (_, _, m), h in zip(SLOTS, hits))
    print(f"\noverall: bet {total_bet:,}, returned {total_back:,} "
          f"= {total_back / total_bet:.4%} (players keep the difference)")
    print(f"max per-slot deviation from theory: {worst:.4%}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000)
