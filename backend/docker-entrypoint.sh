#!/bin/sh
set -e

# Headed Chromium (HEADED=true) needs an X display, which a Railway container lacks.
# Start a virtual framebuffer and point DISPLAY at it. The Django server — and every
# child it spawns, including the pytest runner — inherits this DISPLAY, so headed
# browser launches render into Xvfb instead of dying with "Missing X server or $DISPLAY".
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

python manage.py makemigrations --noinput
python manage.py migrate --fake-initial --noinput

exec python manage.py runserver "0.0.0.0:${PORT:-8000}"
