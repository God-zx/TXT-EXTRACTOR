#!/bin/bash

echo "Container Started..."
echo "Starting Bot..."

cd /EXTRACTOR || exit

# Run the bot using the module
python -m Extractor
