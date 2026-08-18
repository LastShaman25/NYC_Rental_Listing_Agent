@echo off
rem One-click launcher for the Rental Listing Agent workbench.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_app.ps1"
if errorlevel 1 pause
