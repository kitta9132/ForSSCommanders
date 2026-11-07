@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%install-wowsmod.ps1"
set "RESOLVER=%SCRIPT_DIR%tools\resolve-wows-build.ps1"
set "GAMEROOT=C:\Program Files (x86)\Steam\steamapps\common\World of Warships"
if defined WOWS_GAME_ROOT set "GAMEROOT=%WOWS_GAME_ROOT%"
set "REQUESTED_BUILD=%WOWS_BUILD%"
set "BUILD="
set "DRYRUN="
set "WITHATM="

if /I "%~1"=="--dry-run" set "DRYRUN=-DryRun"
if /I "%~1"=="-dryrun" set "DRYRUN=-DryRun"
if /I "%~1"=="/dry-run" set "DRYRUN=-DryRun"
if /I "%~2"=="--dry-run" set "DRYRUN=-DryRun"

if /I "%~1"=="--with-atm" set "WITHATM=-WithAtm"
if /I "%~2"=="--with-atm" set "WITHATM=-WithAtm"

if /I "%~1"=="--restore-atm" (
  if not exist "%SCRIPT_DIR%restore-atm.bat" (
    echo [ERROR] restore-atm.bat was not found next to this .bat.
    goto :failed
  )
  call "%SCRIPT_DIR%restore-atm.bat" %2
  exit /b %ERRORLEVEL%
)

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

echo WowsExtractor installer for WoWS build %BUILD%
echo Target: %GAMEROOT%\bin\%BUILD%
if defined WITHATM (
  echo ATM mode: keep ^(explicit --with-atm^) - ATM load files will not be moved.
) else (
  echo ATM mode: disable - ATM-only files will be moved out of the load paths if present.
)
echo.

if not exist "%PS1%" (
  echo [ERROR] install-wowsmod.ps1 was not found next to this .bat.
  echo [ERROR] Keep both files in the same folder.
  goto :failed
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Build "%BUILD%" -GameRoot "%GAMEROOT%" %DRYRUN% %WITHATM%
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" goto :failed_rc

echo.
if defined DRYRUN (
  echo Dry run completed. No files were written.
) else (
  echo Installation completed successfully.
)
echo.
pause
exit /b 0

:failed_rc
echo.
echo [ERROR] Installation did not complete. Exit code: %RC%
echo [ERROR] No success was reported. Review the messages above.
echo.
pause
exit /b %RC%

:failed
echo.
pause
exit /b 1
