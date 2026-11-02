@echo off
setlocal
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0tools\serve_map.py" %*
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.10 or newer not found.
  ) else (
    python "%~dp0tools\serve_map.py" %*
  )
)
pause
