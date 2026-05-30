#!/bin/bash
# Deploy script for finance subdomain
set -e

export SSHPASS='Trs5m4t1zxcvqwer!twc'

sshpass -e ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
    source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
    cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

    echo \"=== Fetching latest code ===\"
    git fetch origin main
    git reset --hard origin/main

    echo \"=== Merging migrations ===\"
    python manage.py makemigrations --merge --noinput

    echo \"=== Running migrations ===\"
    python manage.py migrate finance

    echo \"=== Collecting static files ===\"
    python manage.py collectstatic --noinput

    echo \"=== Restarting application ===\"
    touch /home/qlknpodo/TWC/TwoComms_Site/twocomms/tmp/restart.txt

    echo \"=== Deploy completed successfully ===\"
'"
