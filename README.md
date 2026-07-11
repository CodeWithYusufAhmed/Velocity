# Velocity 🏎️

A **free, open-source** Android game + social voice platform: a shared multiplayer
lucky wheel with virtual coins that can **never** be bought, sold, cashed out, or
transferred — plus live voice rooms ("Tables"), friends, and direct messages.

## Why Velocity exists

Real-money "lucky wheel" apps take money from people every day. Velocity recreates
the fun — the shared wheel, the voice-room hangouts — with coins that are worthless
by design. No store, no ads, no in-app purchases, ever. The wheel's odds favor the
**player** (~113.6% return-to-player on every slot), the math is public, and every
round is provably fair.

The app even shows you how much real money you did **not** spend.

## Monorepo layout

```
velocity/
├── server/    # Python 3.12, FastAPI, uvicorn — game engine, social API, WebSockets
├── android/   # Kotlin 2.x, Jetpack Compose (Material 3) — the app
├── admin/     # Server-rendered admin dashboard (Jinja2, served by FastAPI)
├── deploy/    # docker-compose (Postgres 16 + LiveKit + Redis), systemd, cloudflared
├── LICENSE    # MIT
└── README.md
```

## Quick start (development)

### Infrastructure (Docker)

```bash
cd deploy
cp .env.example .env      # fill in values
docker compose up -d      # Postgres 16 + Redis + LiveKit
```

### Server

```bash
cd server
python -m venv .venv
.venv\Scripts\activate    # Windows   |   source .venv/bin/activate  # Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/health
```

### Android

Open `android/` in Android Studio, or:

```bash
cd android
gradlew.bat assembleDebug
```

## Fair play, in the open

- Every slot on the wheel has an identical ~113.6% RTP — the house always loses.
- Rounds use a commit-reveal scheme: the SHA-256 commitment of the server seed is
  published **before** betting closes; the seed is revealed with the result and any
  past round can be re-verified in the app or via a public endpoint.

## Legal

Velocity is a fan-made free game and is not affiliated with, sponsored, or endorsed
by any car manufacturer. All brand names are property of their respective owners.
Nothing of monetary value can be wagered, won, or purchased in Velocity.

## Future work

- Optional end-to-end encryption for direct messages
- Email verification at registration
- Profile pictures
- Gifts (coin/cosmetic only — never monetary)

## License

MIT — see [LICENSE](LICENSE).
