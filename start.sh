#!/bin/bash
cd "$(dirname "$0")"
echo "Starting OZAS Digital Banking Server (port 8000)..."
echo "Dashboard: http://localhost:8000/dashboard"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
