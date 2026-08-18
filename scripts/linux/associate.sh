#!/bin/bash
set -e

DESKTOP_FILE="$HOME/.local/share/applications/mdview.desktop"

echo "Adding file associations for CuriousMD on Linux..."

if [ -f "$DESKTOP_FILE" ]; then
    # Remove existing MimeType line if it exists to avoid duplicates
    sed -i '/^MimeType=/d' "$DESKTOP_FILE"
    
    # Add the MimeType line to the desktop entry
    echo "MimeType=text/markdown;" >> "$DESKTOP_FILE"
    
    # Update the desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications"
    fi
    
    # Set it as the default handler for markdown files
    if command -v xdg-mime &> /dev/null; then
        xdg-mime default mdview.desktop text/markdown
    fi
    
    echo "Successfully associated .md files with CuriousMD."
else
    echo "Could not find desktop entry at $DESKTOP_FILE. Please run scripts/linux/install.sh first."
fi
