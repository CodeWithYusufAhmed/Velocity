#!/usr/bin/env bash
# Nightly Postgres backup. Keeps 14 days. Installed by velocity-backup.timer.
set -euo pipefail
BACKUP_DIR=/home/yusuf/velocity-backups
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F)
cd /home/yusuf/velocity/deploy
docker compose exec -T postgres pg_dump -U velocity velocity | gzip > "$BACKUP_DIR/velocity-$STAMP.sql.gz"
find "$BACKUP_DIR" -name 'velocity-*.sql.gz' -mtime +14 -delete
echo "backup ok: velocity-$STAMP.sql.gz"
