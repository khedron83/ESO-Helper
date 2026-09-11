@echo off
REM Builds a Windows onedir package of ESO Helper (eso-build-manager + Grimoire).
REM Run this from anywhere, on the Windows machine ESO itself runs on -- PyInstaller
REM does not cross-compile, so this can't be built from Linux/macOS for a Windows target.
REM
REM Usage: packaging\win\build.bat

setlocal
cd /d "%~dp0..\.."

if not exist .venv (
    echo Creating virtual environment...
    py -3.11 -m venv .venv || python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r eso-build-manager\requirements.txt
pip install -r Grimoire\requirements.txt
pip install pyinstaller

echo Building...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
pyinstaller packaging\eso-helper.spec --noconfirm

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Done -- dist\eso-helper\eso-helper.exe
endlocal
