@echo off
setlocal enabledelayedexpansion
title Building Project Manager EXE...

echo.
echo  =============================================
echo   Project Manager - EXE Builder
echo  =============================================
echo.

:: ── Find correct Python ───────────────────────────────────────────────────
set PY=
for %%p in (
    "C:\Users\Francisco\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%p (
        if "!PY!"=="" set PY=%%~p
    )
)
if "!PY!"=="" (
    echo [ERROR] Could not find Python.
    pause & exit /b 1
)
echo  Using Python: !PY!
echo.

:: ── Add Flutter to PATH ───────────────────────────────────────────────────
set PATH=C:\flutter\bin;%PATH%

:: ── Verify Flutter ────────────────────────────────────────────────────────
echo [1/3] Checking Flutter...
where flutter >nul 2>&1
if errorlevel 1 (
    echo [ERROR] flutter not found on PATH.
    pause & exit /b 1
)
echo       Flutter OK.

:: ── Ensure flet is installed ──────────────────────────────────────────────
echo [2/3] Checking flet...
"!PY!" -m pip show flet >nul 2>&1
if errorlevel 1 (
    echo       Installing flet...
    "!PY!" -m pip install flet --quiet
) else (
    echo       flet OK.
)
echo.

:: ── Find flet.exe (installed alongside python) ────────────────────────────
set PYDIR=C:\Users\Francisco\AppData\Local\Programs\Python\Python312
set FLET=!PYDIR!\Scripts\flet.exe

if not exist "!FLET!" (
    echo [ERROR] flet.exe not found at !FLET!
    echo         Try running:  pip install flet  then re-run this script.
    pause & exit /b 1
)

:: ── Build ─────────────────────────────────────────────────────────────────
echo [3/3] Building Windows EXE with flet build...
echo       (first run can take several minutes)
echo.

"!FLET!" build windows ^
    --project "ProjectManager" ^
    --product "Project Manager" ^
    --org com.local ^
    --build-version 1.0.0

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause & exit /b 1
)

echo.
echo  =============================================
echo   Done!
echo   EXE is in:  build\windows\x64\runner\Release\
echo  =============================================
echo.
pause