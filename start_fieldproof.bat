@echo off
title FieldProof - start everything
cd /d "%~dp0"
echo.
echo  Starting FieldProof (backend API + dashboard + phone USB link)...
echo.
rem 1) Backend API on port 8000 (own window, keep it open)
start "FieldProof API (keep open)" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
rem 2) Dashboard on port 5173 (own window, keep it open)
start "FieldProof Dashboard (keep open)" cmd /k "cd /d "%~dp0dashboard" && npx vite --host 0.0.0.0 --port 5173"
rem 3) Phone over USB: phone's 127.0.0.1:8000 -> this laptop's port 8000
timeout /t 3 >nul
call "%~dp0usb_connect.bat" nopause
echo.
echo  Dashboard:  http://localhost:5173   (log in as supervisor1 - password in DEMO_LOGINS.txt)
echo  Phone app:  open FieldProof, tap officer1, Log in
echo.
timeout /t 4 >nul
start "" http://localhost:5173
pause
