#!/bin/bash
set -e

echo "Starting Backend Container..."
echo "Current Directory: $(pwd)"
echo "Listing files:"
ls -la

echo "Checking .env file exists..."
if [ -f .env ]; then
    echo ".env file found."
else
    echo "ERROR: .env file NOT found!"
fi

echo "Starting Uvicorn..."
# Exec into uvicorn to replace the shell process
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
