@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
set ARGS=
:parse
if "%~1"=="" goto run
if /I "%~1"=="--skip-mvp" (
  set ARGS=!ARGS! -SkipMvp
) else if /I "%~1"=="--help" (
  set ARGS=!ARGS! -Help
) else (
  set ARGS=!ARGS! "%~1"
)
shift
goto parse
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_full_regression.ps1" !ARGS!
if errorlevel 1 exit /b 1
exit /b 0
