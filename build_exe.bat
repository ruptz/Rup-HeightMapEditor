@echo off
setlocal

rem Build a standalone exe for HeightMap Editor
rem Requires Python and dependencies installed

set SCRIPT=height_tool_gui.py
set APPNAME=HeightMapEditor
set ICON=OZyXBv0.ico

rem Clean previous build outputs
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist %APPNAME%.spec del %APPNAME%.spec

rem Use PyInstaller to build a single-file GUI exe with icon
pyinstaller --noconfirm ^
  --name %APPNAME% ^
  --onefile ^
  --windowed ^
  --icon %ICON% ^
  --add-data %ICON%;. ^
  %SCRIPT%

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo Build complete. Find exe in dist\%APPNAME%.exe
endlocal
