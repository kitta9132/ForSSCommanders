@echo off
setlocal EnableExtensions
set "PREFIX=without-atm-b"
if /I "%~1"=="--with-atm" set "PREFIX=with-atm-b"
set "MODDIR=C:\Program Files (x86)\Steam\steamapps\common\World of Warships\bin\13357625\res_mods\PnFMods\WowsExtractor"
echo WowsExtractor recorder - build 13357625
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
