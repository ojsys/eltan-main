#!/bin/bash
# Static Files Debugging Script

echo "=== Checking Static Files Configuration ==="
echo ""

echo "1. Checking if staticfiles directory exists:"
ls -la /home/eltanige/eltanmain/staticfiles/ | head -20
echo ""

echo "2. Checking if static source directory exists:"
ls -la /home/eltanige/eltanmain/static/ 2>/dev/null || echo "static/ directory does NOT exist"
echo ""

echo "3. Checking file count in staticfiles:"
find /home/eltanige/eltanmain/staticfiles -type f | wc -l
echo ""

echo "4. Checking for admin static files:"
ls -la /home/eltanige/eltanmain/staticfiles/admin/ 2>/dev/null | head -10
echo ""

echo "5. Checking permissions:"
ls -ld /home/eltanige/eltanmain/staticfiles
echo ""

echo "6. Checking BASE_DIR path:"
cd /home/eltanige/eltanmain && python3 -c "
from pathlib import Path
BASE_DIR = Path('/home/eltanige/eltanmain')
print(f'BASE_DIR: {BASE_DIR}')
print(f'STATIC_ROOT: {BASE_DIR / \"staticfiles\"}')
print(f'STATICFILES_DIRS: [{BASE_DIR / \"static\"}]')
print(f'static exists: {(BASE_DIR / \"static\").exists()}')
print(f'staticfiles exists: {(BASE_DIR / \"staticfiles\").exists()}')
"
