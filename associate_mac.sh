#!/bin/bash
set -e

APP_BUNDLE="$HOME/Applications/CuriousMD.app"
PLIST="$APP_BUNDLE/Contents/Info.plist"

echo "Adding file associations for CuriousMD..."

if [ -f "$PLIST" ]; then
    # Clear existing associations if any to avoid duplicates or errors
    /usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
    
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes array" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0 dict" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions array" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:0 string md" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:1 string markdown" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeName string Markdown Document" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Editor" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:LSHandlerRank string Alternate" "$PLIST"

    # Force LaunchServices to register the new file association
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_BUNDLE"
    
    echo "Successfully associated .md and .markdown files with CuriousMD."
else
    echo "Could not find CuriousMD.app at $APP_BUNDLE. Please run install_mac.sh first."
fi
