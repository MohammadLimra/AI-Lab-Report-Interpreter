#!/bin/bash

# Pre-check: verify if Python can import the app successfully and print any tracebacks
echo "Pre-checking Flask app imports..."
python -u -c "import app"

# Start the Flask Backend Server using Gunicorn on dynamic $PORT (fallback to 7860)
echo "Starting Flask App..."
gunicorn --preload --bind 0.0.0.0:${PORT:-7860} app:app

