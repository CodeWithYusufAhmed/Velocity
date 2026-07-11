# Nightly Postgres backup (registered as the "Velocity Backup" scheduled task).
$ErrorActionPreference = "Stop"
$backupDir = "D:\velocity-backups"
New-Item -ItemType Directory -Force $backupDir | Out-Null
$stamp = Get-Date -Format yyyy-MM-dd
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
Set-Location "D:\Google\Android-App-Voice-Games\velocity\deploy"

$out = "$backupDir\velocity-$stamp.sql"
& $docker compose exec -T postgres pg_dump -U velocity velocity | Out-File $out -Encoding utf8
Compress-Archive -Path $out -DestinationPath "$out.zip" -Force
Remove-Item $out

# keep 14 days
Get-ChildItem $backupDir -Filter "velocity-*.sql.zip" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    Remove-Item -Confirm:$false
"backup ok: velocity-$stamp.sql.zip"
