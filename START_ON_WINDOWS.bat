@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo  MediaFlow Studio - Windows Launcher
echo ========================================
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo ERROR: FFmpeg was not found in PATH.
  echo Install FFmpeg from https://ffmpeg.org/download.html
  pause
  exit /b 1
)
where ffprobe >nul 2>&1
if errorlevel 1 (
  echo ERROR: ffprobe was not found in PATH.
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m mediaflow.gui
  if errorlevel 1 pause
  exit /b %errorlevel%
)
where python >nul 2>&1
if not errorlevel 1 (
  python -m mediaflow.gui
  if errorlevel 1 pause
  exit /b %errorlevel%
)
echo ERROR: Python 3.10+ is needed. https://python.org/downloads
pause
exit /b 1
