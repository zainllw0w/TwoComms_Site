#!/bin/bash
###############################################################################
# MIGRATION VERIFICATION SCRIPT
# Автоматична перевірка міграції views на production/staging сервері
#
# Usage: bash verify_migration.sh
###############################################################################

set -e

echo "🔍 =========================================="
echo "   MIGRATION VERIFICATION SCRIPT"
echo "   TwoComms E-commerce Platform"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

###############################################################################
# 1. CHECK DJANGO ENVIRONMENT
###############################################################################

echo "📋 Step 1: Checking Django environment..."

if [ ! -f "manage.py" ]; then
    echo -e "${RED}❌ manage.py not found! Are you in the correct directory?${NC}"
    echo "   Current dir: $(pwd)"
    echo "   Expected: /path/to/twocomms/"
    exit 1
fi

echo -e "${GREEN}✅ Django project found${NC}"
((PASSED++))

###############################################################################
# 2. CHECK PYTHON IMPORTS
###############################################################################

echo ""
echo "📋 Step 2: Checking Python imports..."

python3 << 'PYTHON_SCRIPT'
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
    import django
    django.setup()
    
    print("✅ Django setup successful")
    
    # Test imports
    from storefront import views
    print("✅ storefront.views imported successfully")
    
    # Test critical functions
    critical_functions = [
        'home', 'cart', 'checkout', 'order_create', 
        'monobank_webhook', 'admin_panel', 'favorites_list',
        'debug_media', 'register_view_new', 'dev_grant_admin'
    ]
    
    missing = []
    for func in critical_functions:
        if not hasattr(views, func):
            missing.append(func)
    
    if missing:
        print(f"❌ Missing functions: {', '.join(missing)}")
        sys.exit(1)
    else:
        print(f"✅ All {len(critical_functions)} critical functions available")
    
    # Test module count
    module_count = len([x for x in dir(views) if not x.startswith('_')])
    print(f"✅ Total exported names: {module_count}")
    
    sys.exit(0)
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All imports successful${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Import test failed${NC}"
    ((FAILED++))
fi

###############################################################################
# 3. CHECK FILE STRUCTURE
###############################################################################

echo ""
echo "📋 Step 3: Checking file structure..."

EXPECTED_MODULES=(
    "storefront/views/__init__.py"
    "storefront/views/utils.py"
    "storefront/views/auth.py"
    "storefront/views/catalog.py"
    "storefront/views/product.py"
    "storefront/views/cart.py"
    "storefront/views/checkout.py"
    "storefront/views/monobank.py"
    "storefront/views/wholesale.py"
    "storefront/views/admin.py"
    "storefront/views/stores.py"
    "storefront/views/dropship.py"
    "storefront/views/profile.py"
    "storefront/views/static_pages.py"
    "storefront/views/api.py"
    "storefront/views/debug.py"
)

MISSING_FILES=()

for module in "${EXPECTED_MODULES[@]}"; do
    if [ ! -f "$module" ]; then
        MISSING_FILES+=("$module")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All ${#EXPECTED_MODULES[@]} modules present${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Missing modules:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    ((FAILED++))
fi

###############################################################################
# 4. RUN DJANGO CHECKS
###############################################################################

echo ""
echo "📋 Step 4: Running Django system checks..."

python3 manage.py check --deploy 2>&1 | head -50

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Django checks passed${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  Django checks have warnings${NC}"
    ((WARNINGS++))
fi

###############################################################################
# 5. CHECK FOR LINTER ERRORS
###############################################################################

echo ""
echo "📋 Step 5: Checking for linter errors..."

if command -v flake8 &> /dev/null; then
    LINT_OUTPUT=$(flake8 storefront/views/ --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1 || true)
    
    if [ -z "$LINT_OUTPUT" ]; then
        echo -e "${GREEN}✅ No critical linter errors${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  Linter warnings found:${NC}"
        echo "$LINT_OUTPUT"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠️  flake8 not installed, skipping linter check${NC}"
    ((WARNINGS++))
fi

###############################################################################
# 6. CHECK URLS.PY
###############################################################################

echo ""
echo "📋 Step 6: Checking URL patterns..."

# Count URL patterns that use views.*
URL_COUNT=$(grep -c "views\." storefront/urls.py 2>/dev/null || echo "0")

if [ "$URL_COUNT" -gt 100 ]; then
    echo -e "${GREEN}✅ Found $URL_COUNT URL patterns using views.*${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  Only found $URL_COUNT URL patterns${NC}"
    ((WARNINGS++))
fi

###############################################################################
# 7. PERFORMANCE CHECK (если есть siege или ab)
###############################################################################

echo ""
echo "📋 Step 7: Performance check (optional)..."

if command -v curl &> /dev/null; then
    # Simple response time check
    echo "Testing home page response time..."
    
    # Start time
    START=$(date +%s%N)
    
    # Make request
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
    
    # End time
    END=$(date +%s%N)
    
    # Calculate duration in ms
    DURATION=$(( (END - START) / 1000000 ))
    
    if [ "$STATUS" == "200" ]; then
        echo -e "${GREEN}✅ Home page responded in ${DURATION}ms${NC}"
        
        if [ $DURATION -lt 500 ]; then
            echo "   ⚡ Performance: EXCELLENT"
        elif [ $DURATION -lt 1000 ]; then
            echo "   👍 Performance: GOOD"
        else
            echo "   ⚠️  Performance: NEEDS OPTIMIZATION"
        fi
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  Server not running or returned status: $STATUS${NC}"
        echo "   Skipping performance check"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠️  curl not available, skipping performance check${NC}"
    ((WARNINGS++))
fi

###############################################################################
# SUMMARY
###############################################################################

echo ""
echo "=========================================="
echo "           VERIFICATION SUMMARY"
echo "=========================================="
echo ""

TOTAL=$((PASSED + FAILED + WARNINGS))

echo -e "✅ Passed:   ${GREEN}$PASSED${NC} / $TOTAL"
echo -e "❌ Failed:   ${RED}$FAILED${NC} / $TOTAL"
echo -e "⚠️  Warnings: ${YELLOW}$WARNINGS${NC} / $TOTAL"
echo ""

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL CHECKS PASSED! Migration is SUCCESSFUL! 🎉${NC}"
    exit 0
elif [ $FAILED -eq 0 ]; then
    echo -e "${YELLOW}✅ Checks passed with warnings. Review above.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please review above.${NC}"
    exit 1
fi

