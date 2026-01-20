#!/bin/bash
set -e

# Run migrations
alembic upgrade head

# Start application
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python -m contact_svc.main
