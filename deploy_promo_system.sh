#!/bin/bash

# Deployment script for new promo codes system
# Deploys to server via SSH and runs migrations

echo "🚀 Deploying new promo codes system to server..."

# SSH credentials from user rules
SSH_PASS='trs5m4t1'
SSH_USER='qlknpodo'
SSH_HOST='195.191.24.169'
PROJECT_PATH='/home/qlknpodo/TWC/TwoComms_Site/twocomms'
VENV_PATH='/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate'

echo "📦 Step 1: Git commit and push changes..."
git add .
git commit -m "feat: Complete promo codes system redesign with groups, vouchers, and auth modal"
git push origin main

echo "📡 Step 2: Pulling changes on server and running migrations..."
sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" "bash -lc '
    echo \"🔄 Activating virtual environment...\"
    source $VENV_PATH
    
    echo \"📥 Pulling latest changes from git...\"
    cd $PROJECT_PATH
    git pull
    
    echo \"🗃️ Creating migrations...\"
    python manage.py makemigrations storefront
    
    echo \"⚡ Running migrations...\"
    python manage.py migrate storefront
    
    echo \"🔄 Collecting static files...\"
    python manage.py collectstatic --noinput
    
    echo \"🔥 Restarting application...\"
    touch $PROJECT_PATH/twocomms/wsgi.py
    
    echo \"✅ Deployment completed successfully!\"
'"

echo ""
echo "✨ Promo codes system deployed!"
echo "📊 Summary of changes:"
echo "  ✅ New models: PromoCodeGroup, PromoCodeUsage"
echo "  ✅ Updated PromoCode model with groups and restrictions"
echo "  ✅ Auth modal for guests"
echo "  ✅ Modular views structure (views/promo.py)"
echo "  ✅ Group management admin interface"
echo ""
echo "🔗 Next steps:"
echo "  1. Test promo code application at: https://twocomms.shop/cart/"
echo "  2. Create promo groups at: https://twocomms.shop/admin-panel/promo-groups/"
echo "  3. Manage promo codes at: https://twocomms.shop/admin-panel/promocodes/"
echo ""
