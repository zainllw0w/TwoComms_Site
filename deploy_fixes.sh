#!/bin/bash
# Deployment script for audit fixes
# Run this script to deploy all fixes to production server

set -e  # Exit on error

echo "🚀 Starting deployment of audit fixes..."
echo ""

# Server credentials
SERVER_USER="qlknpodo"
SERVER_HOST="195.191.24.169"
SERVER_PASSWORD="trs5m4t1"
PROJECT_PATH="/home/qlknpodo/TWC/TwoComms_Site/twocomms"
VENV_PATH="/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13"

echo "📦 Step 1: Pulling latest code from repository..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git fetch origin
git checkout fix-audit-errors-f88J2
git pull origin fix-audit-errors-f88J2
echo "✅ Code updated successfully"
ENDSSH

echo ""
echo "📚 Step 2: Installing new dependencies (django-ratelimit)..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
pip install -r requirements.txt
echo "✅ Dependencies installed"
ENDSSH

echo ""
echo "🔄 Step 3: Running Django migrations (if any)..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
python manage.py migrate --noinput
echo "✅ Migrations completed"
ENDSSH

echo ""
echo "📦 Step 4: Collecting static files..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
python manage.py collectstatic --noinput
echo "✅ Static files collected"
ENDSSH

echo ""
echo "🔄 Step 5: Restarting application..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
# Touch passenger_wsgi.py to restart the application
touch /home/qlknpodo/TWC/TwoComms_Site/twocomms/passenger_wsgi.py
echo "✅ Application restarted"
ENDSSH

echo ""
echo "🧹 Step 6: Clearing Django cache..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_HOST" << 'ENDSSH'
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
python manage.py shell << 'PYTHON'
from django.core.cache import cache
cache.clear()
print("✅ Cache cleared")
PYTHON
ENDSSH

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Summary of deployed fixes:"
echo "  ✅ Performance: Optimized product_detail view (N+1 queries fixed)"
echo "  ✅ Security: SECRET_KEY now mandatory in production"
echo "  ✅ Security: Redis password authentication support added"
echo "  ✅ Security: Rate limiting middleware (100 req/min per IP)"
echo "  ✅ Security: Removed @csrf_exempt from user-facing endpoints"
echo "  ✅ Code Quality: Removed all console.log statements"
echo ""
echo "🔍 Next steps:"
echo "  1. Check server logs: tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/django.log"
echo "  2. Test the site: https://twocomms.shop"
echo "  3. Monitor performance and errors"
echo ""
echo "⚠️  Important: Make sure to set REDIS_PASSWORD in environment variables if using Redis with password"

