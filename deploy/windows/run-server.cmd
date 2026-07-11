@echo off
rem Velocity server keep-alive (registered as the "Velocity Server" scheduled task).
cd /d D:\Google\Android-App-Voice-Games\velocity\server

rem Wait for the Docker engine (up to ~2 minutes after login)
set tries=0
:waitdocker
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" info >nul 2>&1 && goto dockerup
set /a tries+=1
if %tries% geq 24 goto dockerup
timeout /t 5 /nobreak >nul
goto waitdocker
:dockerup

cd /d D:\Google\Android-App-Voice-Games\velocity\deploy
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose up -d

cd /d D:\Google\Android-App-Voice-Games\velocity\server
.venv\Scripts\alembic.exe upgrade head >> ..\deploy\windows\server.log 2>&1

:serve
echo [%date% %time%] starting uvicorn >> ..\deploy\windows\server.log
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> ..\deploy\windows\server.log 2>&1
echo [%date% %time%] uvicorn exited, restarting in 5s >> ..\deploy\windows\server.log
timeout /t 5 /nobreak >nul
goto serve
