#!/bin/sh
set -e

python manage.py makemigrations --noinput
python manage.py migrate --fake-initial --noinput

exec python manage.py runserver "0.0.0.0:${PORT:-8000}"
