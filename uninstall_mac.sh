#!/bin/bash
set -e
echo "Uninstalling CuriousMD from macOS..."

# 1. Remove macOS App bundle
APP_BUNDLE="$HOME/Applications/CuriousMD.app"
if [ -d "$APP_BUNDLE" ]; then
    # Unregister from LaunchServices before deleting
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f -u "$APP_BUNDLE" 2>/dev/null || true
    rm -rf "$APP_BUNDLE"
    echo "Removed $APP_BUNDLE"
fi

# 2. Remove alias from ~/.bashrc and ~/.zshrc
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ]; then
        # BSD sed (macOS default) requires -i '' to edit in-place without backup extension
        sed -i '' '/# CuriousMD alias/d' "$rc" 2>/dev/null || true
        sed -i '' '/alias md=.*mdview\.py/d' "$rc" 2>/dev/null || true
        echo "Cleaned up aliases in $rc"
    fi
done

echo ""
echo "CuriousMD uninstallation complete!"
echo "Please run 'unalias md' or restart your terminal."
