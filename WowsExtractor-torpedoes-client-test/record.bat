@echo off
setlocal EnableExtensions
set "PREFIX=without-atm-b"
if /I "%~1"=="--with-atm" set "PREFIX=with-atm-b"
set "SCRIPT_DIR=%~dp0"
set "RESOLVER=%SCRIPT_DIR%tools\resolve-wows-build.ps1"
set "GAMEROOT=C:\Program Files (x86)\Steam\steamapps\common\World of Warships"
if defined WOWS_GAME_ROOT set "GAMEROOT=%WOWS_GAME_ROOT%"
set "REQUESTED_BUILD=%WOWS_BUILD%"
set "BUILD="

if not exist "%RESOLVER%" (
  echo [ERROR] tools\resolve-wows-build.ps1 was not found next to this .bat.
  echo [ERROR] Keep the tools folder next to the .bat files.
  goto :failed
)

for /f "usebackq delims=" %%B in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%RESOLVER%" -GameRoot "%GAMEROOT%" -Build "%REQUESTED_BUILD%"`) do set "BUILD=%%B"
if not defined BUILD (
  echo [ERROR] Could not resolve the WoWS build.
  echo [ERROR] Read the messages above. Set WOWS_BUILD only if you know the installed build.
  goto :failed
)

set "MODDIR=%GAMEROOT%\bin\%BUILD%\res_mods\PnFMods\WowsExtractor"
echo WowsExtractor recorder - build %BUILD%
echo Start before entering battle. Press Ctrl+C to stop and save.
echo This recorder does not change ATM or game files.
where py >nul 2>nul
if errorlevel 1 goto :python
py -3 "%~dp0tools\record_telemetry.py" --mod-dir "%MODDIR%" --output-dir "%~dp0recordings" --prefix "%PREFIX%"
goto :done
:python
python "%~dp0tools\record_telemetry.py" --mod-dir "%MODDIR%" --output-dir "%~dp0recordings" --prefix "%PREFIX%"
:done
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [ERROR] Recorder exited with code %RC%.
pause
exit /b %RC%

:failed
pause
exit /b 1
