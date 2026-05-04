#!/bin/bash
set -e

echo "========================================="
echo "   Python Learning App - First-Time Setup"
echo "========================================="
echo ""
echo "[1/3] Updating package list..."
sudo apt-get update -qq

echo "[2/3] Installing Flask..."
sudo apt-get install -y python3-flask python3-werkzeug python3-itsdangerous python3-blinker

echo "[3/3] Creating data directory..."
mkdir -p data

echo ""
echo "========================================="
echo "   Setup Complete!"
echo "========================================="
echo ""
echo "Now start the app with:"
echo "   python3 app.py"
echo ""
echo "Then open your browser to:"
echo "   http://localhost:5000"
echo ""
