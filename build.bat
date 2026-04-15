@echo off
title Building Recorder EXE (Python 3.12 Strict)

echo ============================================
echo     Packaging Recorder (Python 3.12)
echo ============================================

REM ---- CONFIG ----
set SCRIPT_NAME=recorder.py
set EXE_NAME=Recorder

REM ---- LOCATE PYTHON 3.12 ----
echo Detecting Python 3.12...

for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do (
    set PY312=%%P
)

if "%PY312%"=="" (
    echo.
    echo ERROR: Python 3.12 not found.
    echo Install Python 3.12 or ensure "py -3.12" works.
    pause
    exit /b
)

echo Found Python 3.12 at:
echo     %PY312%
echo.

REM ---- CLEAN OLD BUILDS ----
echo Cleaning old build folders...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM ---- CHECK PYINSTALLER UNDER PYTHON 3.12 ----
echo Checking PyInstaller for Python 3.12...

"%PY312%" -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not installed for Python 3.12.
    echo Installing now...
    "%PY312%" -m pip install pyinstaller
)

REM ---- BUILD EXE ----
echo Running PyInstaller with Python 3.12...

"%PY312%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%EXE_NAME%" ^
    "%SCRIPT_NAME%"

echo.
echo ============================================
echo   Build complete!
echo   EXE located in: dist\%EXE_NAME%.exe
echo ============================================
pause
