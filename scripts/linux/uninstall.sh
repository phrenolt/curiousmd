#!/bin/bash

# Ensure script stops on errors
set -e

echo "Uninstalling CuriousMD..."

# 1. Remove Desktop Entry
DESKTOP_FILE="$HOME/.local/share/applications/mdview.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "Removed desktop entry ($DESKTOP_FILE)"
    
    # Update desktop database if the command is available
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications"
    fi
else
    echo "Desktop entry not found, skipping."
fi

# 2. Remove alias and autocomplete from ~/.bashrc
BASHRC="$HOME/.bashrc"
if [ -f "$BASHRC" ]; then
    # Create a backup just in case
    cp "$BASHRC" "${BASHRC}.bak"
    
    # Remove the comment line
    sed -i '/# CuriousMD alias and autocomplete/d' "$BASHRC"
    
    # Remove the alias line
    sed -i '/alias md=.*mdview\.py/d' "$BASHRC"
    
    # Remove the autocomplete line using grep -v to avoid sed escaping complexities
    grep -v "complete -f -X '!*.md' -o plusdirs md" "$BASHRC" > "${BASHRC}.tmp"
    mv "${BASHRC}.tmp" "$BASHRC"
    
    echo "Removed 'md' alias and autocomplete from ~/.bashrc"
else
    echo "~/.bashrc not found, skipping."
fi

echo ""
echo "CuriousMD uninstallation complete!"
echo "Please run 'unalias md' in your current terminal to remove the alias immediately, or restart your terminal."
