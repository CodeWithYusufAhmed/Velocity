# Velocity — Deployment guide (Windows 11 Pro host)

Yusuf's actual setup: ONE Windows 11 PC runs everything — the dev environment
AND the production server. This replaces the Ubuntu guide (DEPLOYMENT.md is
kept for anyone self-hosting on Linux). Same architecture: Docker Desktop for
Postgres + Redis + LiveKit, uvicorn on the host, Cloudflare Tunnel for HTTPS,
router UDP forwarding for voice media.

## 0. Already done during development

- Docker Desktop with the compose stack (`deploy/docker-compose.yml`)
- Python venv at `server\.venv`, migrations applied
- `server\.env` and `deploy\.env` with real secrets

Production deltas below.

## 1. Make Docker and the stack start with Windows

1. Docker Desktop → Settings → General → ✔ **Start Docker Desktop when you sign in**.
2. Settings → Resources → keep defaults (the stack is tiny).
3. The compose services already have `restart: unless-stopped` — they come back
   whenever Docker does.

Note: the PC must stay signed in (or use auto-login) for the server to run 24/7.
Set Power options: **never sleep** (Settings → System → Power → Screen and
sleep → Never when plugged in).

## 2. Run the server as a background task (systemd replacement)

Create `deploy\windows\run-server.cmd` (provided) and register it:

```powershell
# Run once from an ADMIN PowerShell:
schtasks /Create /TN "Velocity Server" /SC ONLOGON /RL LIMITED `
  /TR "D:\Google\Android-App-Voice-Games\velocity\deploy\windows\run-server.cmd"
schtasks /Run /TN "Velocity Server"     # start it now
```

The script waits for Docker, applies migrations, then keeps uvicorn alive
(restarts it if it ever crashes). Logs: `deploy\windows\server.log`.

## 3. Static LAN IP + router forwarding (ASUS AX55) — unchanged

Follow DEPLOYMENT.md §2–3 exactly, but assign the WINDOWS PC's MAC to
192.168.50.10. The three rules again:

| Service         | Protocol | Ports         | → Internal IP  |
|-----------------|----------|---------------|----------------|
| livekit-udp     | UDP      | 50000:50100   | 192.168.50.10  |
| livekit-tcp     | TCP      | 7881          | 192.168.50.10  |
| livekit-turntls | TCP      | 5349          | 192.168.50.10  |

**Windows Firewall** must also allow them (admin PowerShell):

```powershell
New-NetFirewallRule -DisplayName "LiveKit UDP media" -Direction Inbound -Protocol UDP -LocalPort 50000-50100 -Action Allow
New-NetFirewallRule -DisplayName "LiveKit TCP fallback" -Direction Inbound -Protocol TCP -LocalPort 7881,5349 -Action Allow
```

Docker Desktop publishes the container ports on the Windows host, so
router → Windows → container just works.

## 4. LiveKit production config — unchanged

DEPLOYMENT.md §4 (generate secret, copy livekit-prod.yaml over livekit.yaml,
`docker compose up -d`, mirror key/secret into `server\.env`).

## 5. Cloudflare Tunnel on Windows

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create velocity
# copy deploy\cloudflared\config.yml to C:\Users\Yusuf\.cloudflared\config.yml
# and change credentials-file to C:\Users\Yusuf\.cloudflared\velocity.json
cloudflared tunnel route dns velocity velocity.mdyusufahmed.com
cloudflared tunnel route dns velocity livekit.mdyusufahmed.com
cloudflared service install    # runs as a real Windows service, starts on boot
```

Test from your phone on mobile data: `https://velocity.mdyusufahmed.com/health`.

## 6. Nightly backups (Task Scheduler replaces the systemd timer)

`deploy\windows\pg-backup.ps1` (provided) dumps to `D:\velocity-backups`,
keeps 14 days. Register:

```powershell
schtasks /Create /TN "Velocity Backup" /SC DAILY /ST 04:30 /RL LIMITED `
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\Google\Android-App-Voice-Games\velocity\deploy\windows\pg-backup.ps1"
```

Restore: `gzip -d` the file and pipe into
`docker compose exec -T postgres psql -U velocity velocity`.

## 7–10. Bandwidth, app URL, signing, GitHub releases — unchanged

Follow DEPLOYMENT.md §7–10 as written (they were already Windows-side steps).

## Honest caveats of a Windows game server

- Windows Update reboots interrupt the game — set Active Hours, and know the
  round engine resumes automatically after boot (rounds are server-authoritative,
  no state is lost beyond the in-flight round).
- The PC sleeping = server down. "Never sleep" is mandatory.
- If this ever grows, DEPLOYMENT.md is the path to a dedicated Linux box; the
  code is identical.
