@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "RESOLVER=%SCRIPT_DIR%tools\resolve-wows-build.ps1"
set "GAMEROOT=C:\Program Files (x86)\Steam\steamapps\common\World of Warships"
if defined WOWS_GAME_ROOT set "GAMEROOT=%WOWS_GAME_ROOT%"
set "REQUESTED_BUILD=%WOWS_BUILD%"
set "BUILD="

if not exist "%RESOLVER%" (
  echo [ERROR] tools\resolve-wows-build.ps1 was not found next to this .bat.
  echo [ERROR] Keep the tools folder next to the .bat files.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%B in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%RESOLVER%" -GameRoot "%GAMEROOT%" -Build "%REQUESTED_BUILD%"`) do set "BUILD=%%B"
if not defined BUILD (
  echo [ERROR] Could not resolve the WoWS build.
  echo [ERROR] Read the messages above. Set WOWS_BUILD only if you know the installed build.
  pause
  exit /b 1
)

set "MODDIR=%GAMEROOT%\bin\%BUILD%\res_mods\PnFMods\WowsExtractor"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%SCRIPT_DIR%tools\serve_map.py" --mod-dir "%MODDIR%" %*
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.10 or newer not found.
  ) else (
    python "%SCRIPT_DIR%tools\serve_map.py" --mod-dir "%MODDIR%" %*
  )
)
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
