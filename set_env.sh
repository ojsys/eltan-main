#!/bin/bash
# Script to easily switch between development and production environments
# Usage: source set_env.sh [development|production]

if [ -z "$1" ]; then
    echo "Usage: source set_env.sh [development|production]"
    echo ""
    echo "Example:"
    echo "  source set_env.sh development"
    echo "  source set_env.sh production"
    exit 1
fi

ENV=$1

if [ "$ENV" != "development" ] && [ "$ENV" != "production" ]; then
    echo "Error: Environment must be 'development' or 'production'"
    exit 1
fi

# Set the environment variable
export ELTAN_ENV=$ENV

# Copy the appropriate .env file
if [ -f ".env.$ENV" ]; then
    cp ".env.$ENV" .env
    echo "✓ Copied .env.$ENV to .env"
else
    echo "⚠ Warning: .env.$ENV file not found"
fi

# Display current configuration
echo ""
echo "Environment Configuration:"
echo "========================="
echo "ELTAN_ENV: $ELTAN_ENV"
echo "Settings Module: eltanweb.settings.$ENV"
echo ""

if [ "$ENV" == "development" ]; then
    echo "Development Mode Active:"
    echo "  - Database: SQLite"
    echo "  - Debug: Enabled"
    echo "  - Paystack: Test keys"
    echo "  - Email: Console backend"
    echo ""
    echo "Run: python manage.py runserver"
else
    echo "Production Mode Active:"
    echo "  - Database: MySQL (check .env)"
    echo "  - Debug: Disabled"
    echo "  - Paystack: Live keys"
    echo "  - Email: SMTP backend"
    echo ""
    echo "Remember to:"
    echo "  1. Verify .env has correct MySQL credentials"
    echo "  2. Run: python manage.py migrate"
    echo "  3. Run: python manage.py collectstatic"
fi

echo ""
