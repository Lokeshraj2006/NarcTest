@echo off
title FieldProof - create database
echo.
echo  ===============================================================
echo   FieldProof: create the new PostgreSQL database (fieldproof_db)
echo  ===============================================================
echo.
echo  It will ask:  Password for user postgres:
echo  Type your PostgreSQL "postgres" password and press Enter.
echo  (Nothing shows on screen while you type - that is normal.)
echo.
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -p 5433 -c "CREATE DATABASE fieldproof_db OWNER labelguard;"
echo.
echo  If you see "CREATE DATABASE" above, it worked. Go back to Claude and say "done".
echo  If it says "already exists", that is also fine.
echo.
pause
