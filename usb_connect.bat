@echo off
title FieldProof - phone USB link
rem Run this again whenever you unplug / re-plug the phone cable.
set ADB="%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
echo.
echo  Phones connected:
%ADB% devices
%ADB% reverse tcp:8000 tcp:8000
echo.
echo  USB link active: the phone app now talks to this laptop through the cable.
echo  (If it says "no devices", unlock the phone and tap "Allow USB debugging".)
echo.
if /i not "%1"=="nopause" pause
