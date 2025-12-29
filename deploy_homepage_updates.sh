#!/bin/bash

# ELTAN Homepage CMS Deployment Script
# This script applies HomePage model migrations and creates initial data
# Run this on cPanel server after pulling latest code

set -e  # Exit on error

echo "======================================"
echo "ELTAN Homepage CMS Deployment Script"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${YELLOW}Step 1: Activating virtual environment...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${RED}✗ Virtual environment not found!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Setting production environment...${NC}"
export ELTAN_ENV=production
echo -e "${GREEN}✓ ELTAN_ENV set to production${NC}"

echo ""
echo -e "${YELLOW}Step 3: Checking migration status...${NC}"
python manage.py showmigrations core | tail -10

echo ""
echo -e "${YELLOW}Step 4: Applying migrations...${NC}"
python manage.py migrate core --noinput
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migrations applied successfully${NC}"
else
    echo -e "${RED}✗ Migration failed!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 5: Creating/Updating HomePage record...${NC}"
python manage.py shell << 'PYEOF'
from core.models_cms import HomePage

# Check if HomePage exists
existing = HomePage.objects.first()

if not existing:
    print("Creating new HomePage record...")
    homepage = HomePage.objects.create(
        is_active=True,
        hero_badge_text="Professional Membership Organization",
        hero_title="Welcome to ELTAN",
        hero_subtitle="Join us in fostering excellence in English language teaching and learning across Nigeria.",
        hero_cta_text="Get Started",
        hero_cta_link="/subscribe/",
        secondary_cta_text="Learn More",
        secondary_cta_link="#features",

        features_subtitle="What We Offer",
        features_title="Empowering English Language Teachers Across Nigeria",
        features_description="Join Nigeria's premier association for English language teaching professionals. Access exclusive resources, networking opportunities, and professional development programs.",

        content1_subtitle="Professional Growth",
        content1_title="Invest in Your Potential",
        content1_description="<p>Unlock your full potential with ELTAN's comprehensive professional development programs. Access cutting-edge research, attend specialized workshops, and earn certificates that advance your teaching career.</p><p>Our members benefit from exclusive training sessions, mentorship opportunities, and continuous learning resources designed specifically for English language educators.</p>",
        content1_button_text="Explore Benefits",
        content1_button_link="#features",

        content2_subtitle="Community Impact",
        content2_title="Boost Your Career Growth Today",
        content2_description="Join a community of ambitious professionals transforming English language education across Nigeria. Connect with peers, share best practices, and contribute to the advancement of teaching standards nationwide.",
        content2_button_text="Get Started",
        content2_button_link="/register/",

        faq_title="Frequently Asked Questions",
        faq_subtitle="Have questions about our service? We have answers.",

        cta_title="Ready to Transform Your Career?",
        cta_description="Join over 500 professionals who are already benefiting from ELTAN membership. Get access to exclusive resources, networking opportunities, and career advancement tools.",
        cta_button_text="Get Started Today",
        cta_button_link="/register/",
        cta_secondary_button_text="Contact Us",
        cta_secondary_button_link="#contact"
    )
    print(f"✓ HomePage created successfully! ID: {homepage.id}")
    print(f"  - Hero Title: {homepage.hero_title}")
    print(f"  - Is Active: {homepage.is_active}")
else:
    print(f"✓ HomePage already exists (ID: {existing.id})")
    print(f"  - Hero Title: {existing.hero_title}")
    print(f"  - Is Active: {existing.is_active}")
    print("  - You can edit it at /admin/core/homepage/")
PYEOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ HomePage data configured${NC}"
else
    echo -e "${RED}✗ HomePage creation failed!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 6: Collecting static files...${NC}"
python manage.py collectstatic --noinput
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Static files collected${NC}"
else
    echo -e "${YELLOW}⚠ Static files collection had warnings (may be okay)${NC}"
fi

echo ""
echo -e "${YELLOW}Step 7: Restarting application...${NC}"
if [ -d "tmp" ]; then
    touch tmp/restart.txt
    echo -e "${GREEN}✓ Application restart triggered (tmp/restart.txt)${NC}"
else
    mkdir -p tmp
    touch tmp/restart.txt
    echo -e "${GREEN}✓ Created tmp directory and triggered restart${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETED SUCCESSFULLY!${NC}"
echo "======================================"
echo ""
echo "Next Steps:"
echo "1. Visit your website homepage to verify changes"
echo "2. Login to /admin/core/homepage/ to customize content"
echo "3. All homepage sections are now editable from admin panel"
echo ""
echo "Admin Panel Sections:"
echo "  • Hero Section (badge, title, subtitle, CTAs)"
echo "  • Features Section Header"
echo "  • Content Section 1 (Professional Growth)"
echo "  • Content Section 2 (Community Impact)"
echo "  • FAQ Section Header"
echo "  • Final CTA Section"
echo ""
