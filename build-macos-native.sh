#!/usr/bin/env bash
# OpenCore Studio — sync sources into the .app and compile the Cocoa/WebKit wrapper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="${SCRIPT_DIR}/macos-dist/OpenCore Studio.app"
APP_ROOT="${APP_PATH}/Contents/Resources/app"
SWIFT_SOURCE="${SCRIPT_DIR}/macos-native/main.swift"
TARGET_BIN="${APP_PATH}/Contents/MacOS/OpenCoreStudioNative"
INFO_PLIST="${APP_PATH}/Contents/Info.plist"

echo "=========================================================="
echo " Building OpenCore Studio.app"
echo "=========================================================="

if ! command -v swiftc &>/dev/null; then
    echo "Error: swiftc not found. Install Xcode Command Line Tools:"
    echo "  xcode-select --install"
    exit 1
fi

mkdir -p "${APP_ROOT}" "${APP_PATH}/Contents/MacOS"

echo "--> Syncing engine, UI, and bundled data into the app…"
rsync -a --delete \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    "${SCRIPT_DIR}/engine/" "${APP_ROOT}/engine/"
rsync -a --delete \
    --exclude '.DS_Store' \
    "${SCRIPT_DIR}/static/" "${APP_ROOT}/static/"
rsync -a --delete \
    --exclude 'cache/' \
    --exclude 'builds/' \
    --exclude 'backups/' \
    --exclude '__pycache__/' \
    --exclude '.DS_Store' \
    "${SCRIPT_DIR}/data/" "${APP_ROOT}/data/"
cp "${SCRIPT_DIR}/app.py" "${APP_ROOT}/app.py"

if command -v /usr/libexec/PlistBuddy &>/dev/null; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleExecutable OpenCoreStudioNative" "${INFO_PLIST}" 2>/dev/null \
        || /usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string OpenCoreStudioNative" "${INFO_PLIST}"
fi

echo "--> Compiling Swift (Cocoa + WebKit)…"
swiftc -O \
    -framework Cocoa \
    -framework WebKit \
    "${SWIFT_SOURCE}" \
    -o "${TARGET_BIN}"

chmod +x "${TARGET_BIN}"

echo "--> Ad-hoc signing and clearing quarantine…"
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "${APP_PATH}" 2>/dev/null || true
fi
xattr -cr "${APP_PATH}" 2>/dev/null || true

echo "=========================================================="
echo " BUILD SUCCESSFUL"
echo " ${APP_PATH}"
echo " Double-click the app, or: open \"${APP_PATH}\""
echo "=========================================================="
