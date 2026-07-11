# Velocity — Deployment guide (Ubuntu desktop, Ryzen 7 5800X)

The whole stack runs on one PC: FastAPI (game/API/WS), Postgres + Redis + LiveKit
in Docker, Cloudflare Tunnel for HTTPS, and a router UDP port-forward for voice
media. Follow top to bottom.

## 1. Prepare the box

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv git docker.io docker-compose-v2
sudo usermod -aG docker yusuf   # log out/in after this
git clone https://github.com/<you>/velocity ~/velocity
cd ~/velocity/server
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fill in REAL values (below)
cd ~/velocity/deploy && cp .env.example .env   # strong POSTGRES_PASSWORD
```

`server/.env` production values:
- `DATABASE_URL` with the Postgres password from `deploy/.env`
- `JWT_SECRET`: `openssl rand -hex 32`
- `ADMIN_PASSWORD`: long and unique — it guards /admin
- `GOOGLE_OAUTH_CLIENT_ID`: the Web client ID
- `LIVEKIT_URL=wss://livekit.mdyusufahmed.com` and the prod key/secret (step 4)

## 2. Static LAN IP for the PC (ASUS AX55)

1. Open http://router.asus.com → log in.
2. **LAN → DHCP Server → Manually Assigned IP** ("DHCP 手動割当"): enable,
   pick the PC's MAC from the dropdown, assign **192.168.50.10**, Apply.
3. Reboot the PC's network (`sudo dhclient -r && sudo dhclient`) and confirm
   `ip a` shows 192.168.50.10.

## 3. Router port forwarding (voice media — the ONLY forwarded ports)

Cloudflare Tunnel carries everything HTTP/WebSocket, so ports 80/443/8000 stay
CLOSED. WebRTC media cannot use the tunnel and needs:

ASUS AX55: **WAN → Virtual Server / Port Forwarding → Add profile**, one per row:

| Service name    | Protocol | External port | Internal port | Internal IP    |
|-----------------|----------|---------------|---------------|----------------|
| livekit-udp     | UDP      | 50000:50100   | 50000:50100   | 192.168.50.10  |
| livekit-tcp     | TCP      | 7881          | 7881          | 192.168.50.10  |
| livekit-turntls | TCP      | 5349          | 5349          | 192.168.50.10  |

Apply. (The colon syntax `50000:50100` is how the AX55 expresses a range.)

- **UDP 50000–50100**: primary WebRTC media path.
- **TCP 7881**: fallback for players whose networks block UDP.
- **TCP 5349 (TURN/TLS)**: last-resort relay for hard NATs; only needed because
  `turn.enabled: true` in livekit-prod.yaml.

## 4. LiveKit production config

```bash
cd ~/velocity/deploy
openssl rand -hex 32     # → the API secret
# edit livekit/livekit-prod.yaml: replace the key line with
#   velocity_prod: <that secret>
cp livekit/livekit-prod.yaml livekit/livekit.yaml
docker compose up -d
```
Put the same pair in `server/.env`:
`LIVEKIT_API_KEY=velocity_prod`, `LIVEKIT_API_SECRET=<that secret>`.

## 5. Cloudflare Tunnel (HTTPS, no open ports)

```bash
# Cloudflare dashboard: add site mdyusufahmed.com (free plan), update nameservers.
curl -L https://pkg.cloudflare.com/cloudflared-stable-linux-amd64.deb -o cf.deb && sudo dpkg -i cf.deb
cloudflared tunnel login
cloudflared tunnel create velocity
mkdir -p ~/.cloudflared && cp ~/velocity/deploy/cloudflared/config.yml ~/.cloudflared/
cloudflared tunnel route dns velocity velocity.mdyusufahmed.com
cloudflared tunnel route dns velocity livekit.mdyusufahmed.com
sudo cloudflared service install   # runs as systemd, starts on boot
```
Test: `https://velocity.mdyusufahmed.com/health` from your phone's mobile data.

## 6. systemd services + nightly backups

```bash
sudo cp ~/velocity/deploy/systemd/velocity.service /etc/systemd/system/
sudo cp ~/velocity/deploy/systemd/velocity-backup.{service,timer} /etc/systemd/system/
chmod +x ~/velocity/deploy/backup/pg_backup.sh
sudo systemctl daemon-reload
sudo systemctl enable --now velocity velocity-backup.timer
systemctl status velocity          # should be active; /health returns ok
```
Backups land in `~/velocity-backups/` (14 days kept).
Restore: `gunzip -c velocity-DATE.sql.gz | docker compose exec -T postgres psql -U velocity velocity`

## 7. Bandwidth / capacity

Each listener ≈ 32 kbps of UPLOAD per speaking participant they hear. Rule of
thumb: `upload_Mbps × 1000 / 32 ≈ max concurrent listener-streams`. Measure
your upload at fast.com and set **max tables / max listeners** in /admin
accordingly (e.g. 10 Mbps up ≈ ~300 listener-streams total — plenty).

## 8. Point the app at production

In `android/app/build.gradle.kts` set
`SERVER_BASE_URL = "https://velocity.mdyusufahmed.com"` for the release build.
(HTTPS via the tunnel — remember to remove `usesCleartextTraffic` from the
manifest for release, or gate it to debug with a manifest overlay.)

## 9. Signed release APK

```powershell
# ONE TIME, on the Windows PC — then BACK THE FILE UP (cloud + USB). Losing it
# means you can never update the app for existing installs.
& "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe" -genkeypair -v `
  -keystore velocity-release.jks -alias velocity -keyalg RSA -keysize 4096 -validity 10000
```
Create `android/keystore.properties` (gitignored):
```
storeFile=C:/path/to/velocity-release.jks
storePassword=...
keyAlias=velocity
keyPassword=...
```
The app build reads it automatically (see app/build.gradle.kts signingConfigs).
Build: `.\gradlew.bat assembleRelease` → `app/build/outputs/apk/release/app-release.apk`.
Also add the release keystore's SHA-1 as a second Android OAuth client in
Google Cloud Console (same package name) or Google Sign-In will fail in release.

## 10. GitHub release automation

`.github/workflows/release.yml` builds and attaches the APK to a GitHub Release
whenever you push a tag like `v1.0.0`. Add repo secrets first:
`KEYSTORE_BASE64` (`base64 -w0 velocity-release.jks`), `KEYSTORE_PASSWORD`,
`KEY_ALIAS`, `KEY_PASSWORD`.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

## v1.0.0 checklist

- [ ] deploy/.env + server/.env: real secrets, never committed
- [ ] LiveKit prod key/secret rotated from dev values
- [ ] Static LAN IP + 3 port-forward rules verified from OUTSIDE (mobile data)
- [ ] /health via tunnel OK; wheel plays end-to-end over the internet
- [ ] Two phones on different networks can hear each other in a Table
- [ ] /admin reachable, dashboard password strong, your account is_admin
- [ ] Nightly backup timer fired once (`systemctl list-timers`, file exists)
- [ ] Release APK signed, installed clean, Google Sign-In works (release SHA-1!)
- [ ] Buy Me a Coffee URL replaced in AboutScreen.kt
- [ ] About screen copy approved by Yusuf
- [ ] GitHub repo public, Actions secrets set, v1.0.0 tag → Release with APK
