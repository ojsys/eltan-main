@echo off
REM Script to easily switch between development and production environments
REM Usage: set_env.bat [development|production]

if "%1"=="" (
    echo Usage: set_env.bat [development^|production]
    echo.
    echo Example:
    echo   set_env.bat development
    echo   set_env.bat production
    exit /b 1
)

set ENV=%1

if NOT "%ENV%"=="development" if NOT "%ENV%"=="production" (
    echo Error: Environment must be 'development' or 'production'
    exit /b 1
)

REM Set the environment variable
set ELTAN_ENV=%ENV%

REM Copy the appropriate .env file
if exist ".env.%ENV%" (
    copy /Y ".env.%ENV%" .env >nul
    echo [OK] Copied .env.%ENV% to .env
) else (
    echo [WARNING] .env.%ENV% file not found
)

REM Display current configuration
echo.
echo Environment Configuration:
echo =========================
echo ELTAN_ENV: %ELTAN_ENV%
echo Settings Module: eltanweb.settings.%ENV%
echo.

if "%ENV%"=="development" (
    echo Development Mode Active:
    echo   - Database: SQLite
    echo   - Debug: Enabled
    echo   - Paystack: Test keys
    echo   - Email: Console backend
    echo.
    echo Run: python manage.py runserver
) else (
    echo Production Mode Active:
    echo   - Database: MySQL ^(check .env^)
    echo   - Debug: Disabled
    echo   - Paystack: Live keys
    echo   - Email: SMTP backend
    echo.
    echo Remember to:
    echo   1. Verify .env has correct MySQL credentials
    echo   2. Run: python manage.py migrate
    echo   3. Run: python manage.py collectstatic
)

echo.
