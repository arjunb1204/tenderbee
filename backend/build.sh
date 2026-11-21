#!/usr/bin/env bash
# Exit on error
set -o errexit

# Navigate to backend directory if executed from repo root
if [ -d "backend" ]; then
  cd backend
fi

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
