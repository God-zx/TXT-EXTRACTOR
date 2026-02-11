#!/bin/bash

echo "Container Started..."
echo "Starting Web + Bot..."

cd /EXTRACTOR || exit

python app.py
