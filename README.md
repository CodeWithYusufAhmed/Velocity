# Velocity 🏎️

A **free, open-source** Android game + social voice platform: a shared
multiplayer lucky wheel with virtual coins that can **never** be bought, sold,
cashed out, or transferred — plus live voice rooms ("Tables"), friends, and
on-device direct messages.

*(screenshots coming with the v1.0 release)*

## Philosophy — why this exists

Real-money "lucky wheel" apps take money from people every day; the author and
many others have lost real money to them. Velocity recreates everything fun
about those apps — the shared wheel, the countdown, the voice-room hangouts —
and removes the harm:

- **No money, ever.** No store, no ads, no purchases, no cash-out, no coin
  transfers. VIP is earned by playing, never bought.
- **The odds favor YOU.** Every slot returns ~113.6% to players (the exact
  math is in the app's About screen and in `server/app/game/odds.py`). There is
  no house edge — the "house" is a free server that wants you to win.
- **Provably fair.** Every round publishes `SHA256(seed‖round_id)` *before*
  betting closes and reveals the seed with the result. Any round is
  re-verifiable in-app or at `GET /rounds/{id}/verify`.
- **Anti-addiction by design.** A "Money You Didn't Spend" counter, and a
  self-set daily round limit that only takes raises the *next* day.

## What's inside

| Part | Stack |
|------|-------|
| `server/` | Python 3.12, FastAPI, SQLAlchemy 2 async, Postgres 16, commit-reveal RNG, WebSockets, LiveKit tokens, VIP engine, 146 tests |
| `android/` | Kotlin 2.x, Jetpack Compose (Material 3), Hilt, Retrofit, Room (device-only DM history), LiveKit Android SDK |
| `admin/` | Server-rendered Jinja2 dashboard at `/admin` (round monitor, users, odds editor with uniform-RTP guard, tables, reports, capacity) |
| `deploy/` | docker-compose (Postgres+Redis+LiveKit), systemd units, Cloudflare Tunnel config, nightly backups, full self-hosting guide |

## Quick start (development)

```bash
cd deploy && cp .env.example .env && docker compose up -d
cd ../server && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload    # → http://127.0.0.1:8000/health
.venv/bin/python -m pytest tests -q        # 146 passed
.venv/bin/python -m scripts.simulate_rtp   # 1,000,000-round fairness check
```

Android: open `android/` in Android Studio and Run (emulator targets the local
server at `10.0.2.2:8000` out of the box).

## Self-hosting

The whole platform runs on one home PC. The complete walkthrough — Docker,
Cloudflare Tunnel, LiveKit production config, router port-forwarding (with
exact ASUS AX55 steps), systemd, nightly `pg_dump`, signed APK, GitHub release
automation — is in [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md).

## Direct messages & privacy

DM history is stored **only on your device** (Room/SQLite). If you're offline,
messages wait encrypted-in-transit in a server queue and are **deleted the
moment they're delivered** (or purged after 30 days). Reinstalling the app
clears your history — by design, the server has nothing to give back.

## Future work

- Optional end-to-end encryption for DMs
- Email verification at registration
- RNNoise "Studio Noise Removal" (WebRTC noise suppression ships today)
- Gifts — coin/cosmetic only, never monetary

## Legal

Velocity is a fan-made free game and is not affiliated with, sponsored, or
endorsed by any car manufacturer. All brand names are property of their
respective owners. Nothing of monetary value can be wagered, won, or purchased.

## License

MIT — see [LICENSE](LICENSE).
