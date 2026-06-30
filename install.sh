#!/bin/bash

# Ensure script stops on errors
set -e

# Setup absolute paths
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MDVIEW_SCRIPT="$APP_DIR/mdview.py"
ICON_PATH="$APP_DIR/md_icon.png"

echo "Installing CuriousMD..."

# 1. Setup alias and autocomplete in ~/.bashrc
BASHRC="$HOME/.bashrc"

if ! grep -q "alias md=" "$BASHRC"; then
    echo "" >> "$BASHRC"
    echo "# CuriousMD alias and autocomplete" >> "$BASHRC"
    echo "alias md='python3 \"$MDVIEW_SCRIPT\"'" >> "$BASHRC"
    echo "complete -f -X '!*.md' -o plusdirs md" >> "$BASHRC"
    echo "Added 'md' alias to ~/.bashrc"
else
    echo "Alias 'md' already exists in ~/.bashrc. Skipping."
fi

# 2. Setup Desktop Entry
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/mdview.desktop"

cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=CuriousMD
Comment=Local Markdown viewer and editor
Exec=python3 "$MDVIEW_SCRIPT" %f
Icon=$ICON_PATH
Terminal=false
Categories=Utility;TextEditor;
MimeType=text/markdown;
EOF

chmod +x "$DESKTOP_FILE"

# Update desktop database if the command is available
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_DIR"
fi

echo "Created desktop entry at $DESKTOP_FILE"

echo ""
echo "CuriousMD installation complete!"
echo "Please run 'source ~/.bashrc' or open a new terminal to use the 'md' command."
