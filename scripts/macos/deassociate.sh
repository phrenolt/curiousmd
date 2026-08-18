#!/bin/bash
set -e

APP_BUNDLE="$HOME/Applications/CuriousMD.app"
PLIST="$APP_BUNDLE/Contents/Info.plist"

echo "Removing file associations for CuriousMD..."

if [ -f "$PLIST" ]; then
    # Remove the CFBundleDocumentTypes array from the plist
    /usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
    
    # Force LaunchServices to refresh and apply the change immediately
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_BUNDLE"
    
    echo "Successfully deassociated .md and .markdown files from CuriousMD."
else
    echo "Could not find CuriousMD.app at $APP_BUNDLE. Is it installed?"
fi
