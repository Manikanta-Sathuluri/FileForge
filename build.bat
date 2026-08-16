@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo FileForge 3.2.0 - Windows Release Build
echo ==========================================
echo.

echo [1/4] Installing/updating build dependencies...
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo.
echo [2/4] Cleaning previous build output...
if exist build rmdir /s /q build
if exist dist\FileForge.exe del /q dist\FileForge.exe
if not exist dist mkdir dist

echo.
echo [3/4] Building FileForge.exe...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name FileForge --paths src src\app.py
if errorlevel 1 goto :fail

if not exist dist\FileForge.exe goto :fail

echo.
echo [4/4] Creating SHA-256 checksum...
certutil -hashfile dist\FileForge.exe SHA256 > dist\FileForge.exe.sha256
if errorlevel 1 goto :fail

echo.
echo ==========================================
echo BUILD SUCCESSFUL
echo ==========================================
echo EXE:      %CD%\dist\FileForge.exe
echo SHA-256:  %CD%\dist\FileForge.exe.sha256
echo.
pause
exit /b 0

:fail
echo.
echo ==========================================
echo BUILD FAILED
echo ==========================================
echo Check the error above.
pause
exit /b 1
