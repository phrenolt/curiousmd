#!/bin/bash

# Ensure script stops on errors
set -e

# Setup absolute paths
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MDVIEW_SCRIPT="$APP_DIR/mdview.py"

echo "Installing CuriousMD for macOS..."

# 1. Setup alias and autocomplete in ~/.bashrc and ~/.zshrc
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ] || [ "$rc" = "$HOME/.zshrc" ]; then
        if ! grep -q "alias md=" "$rc" 2>/dev/null; then
            echo "" >> "$rc"
            echo "# CuriousMD alias" >> "$rc"
            echo "alias md='python3 \"$MDVIEW_SCRIPT\"'" >> "$rc"
            echo "Added 'md' alias to $rc"
        else
            echo "Alias 'md' already exists in $rc"
        fi
    fi
done

# 2. Create macOS .app bundle in user's Applications folder
APP_BUNDLE="$HOME/Applications/CuriousMD.app"
mkdir -p "$HOME/Applications"

# We use an AppleScript wrapper to launch the Python script in a Terminal window.
# This ensures the user has a terminal they can Ctrl+C to stop the local HTTP server.
cat <<EOF > /tmp/curiousmd_launcher.applescript
on run
    tell application "Terminal"
        do script "python3 '$MDVIEW_SCRIPT'"
        activate
    end tell
end run

on open theFiles
    set fileArgs to ""
    repeat with aFile in theFiles
        set fileArgs to fileArgs & " " & quoted form of POSIX path of aFile
    end repeat
    tell application "Terminal"
        do script "python3 '$MDVIEW_SCRIPT' " & fileArgs
        activate
    end tell
end open
EOF

echo "Compiling macOS App Bundle..."
osacompile -o "$APP_BUNDLE" /tmp/curiousmd_launcher.applescript
rm /tmp/curiousmd_launcher.applescript

# 3. Associate .md files by updating the bundle's Info.plist
PLIST="$APP_BUNDLE/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0 dict" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:0 string md" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:1 string markdown" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeName string Markdown Document" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Editor" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:LSHandlerRank string Alternate" "$PLIST"

# Force macOS LaunchServices to register the new file association
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_BUNDLE"

echo ""
echo "CuriousMD installation complete!"
echo "Created macOS App at $APP_BUNDLE and registered .md file association."
echo "Please restart your terminal to use the 'md' command."
