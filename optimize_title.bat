@echo off
REM Windows batch script for title optimization
REM Usage: optimize_title.bat "original title" "search_term1" ["search_term2"] ["search_term3"]

if "%1"=="" (
    echo Usage: optimize_title.bat "original title" "search_term1" ["search_term2"] ["search_term3"]
    echo.
    echo Examples:
    echo   optimize_title.bat "LED Light Bulb 60W" "outdoor lighting"
    echo   optimize_title.bat "Purity Eyeglass Cleaner Kit" "refill" "spray" "lens cleaner"
    pause
    exit /b 1
)

python optimize_title_cli.py %*
pause
