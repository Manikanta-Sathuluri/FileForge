@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
py src\app.py
if errorlevel 1 pause
