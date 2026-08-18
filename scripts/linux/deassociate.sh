#!/bin/bash
set -e

DESKTOP_FILE="$HOME/.local/share/applications/mdview.desktop"

echo "Removing file associations for CuriousMD on Linux..."

if [ -f "$DESKTOP_FILE" ]; then
    # Remove the MimeType line from the desktop entry
    sed -i '/^MimeType=/d' "$DESKTOP_FILE"
    
    # Update the desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications"
    fi
    
    echo "Successfully deassociated .md files from CuriousMD."
else
    echo "Could not find desktop entry at $DESKTOP_FILE. Is it installed?"
fi
