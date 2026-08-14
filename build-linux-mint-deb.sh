#!/usr/bin/env bash
# Build a Linux Mint/Ubuntu .deb package from this source directory.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-0.1.0}"
PACKAGE_NAME="airi-vietnamese-speech"
OUTPUT_DIR="$ROOT_DIR/dist"
OUTPUT_FILE="$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}_all.deb"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "dpkg-deb is required. Run this on Linux Mint, Ubuntu, or Debian." >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/airi-vietnamese-speech-deb.XXXXXX")"
trap 'rm -rf "$STAGING_DIR"' EXIT
APP_DIR="$STAGING_DIR/opt/airi-vietnamese-speech"
DEBIAN_DIR="$STAGING_DIR/DEBIAN"

mkdir -p "$APP_DIR" "$DEBIAN_DIR" "$STAGING_DIR/usr/bin" "$STAGING_DIR/usr/share/applications" "$OUTPUT_DIR"
cp "$ROOT_DIR/launcher.py" "$ROOT_DIR/requirements.txt" "$ROOT_DIR/README.md" "$APP_DIR/"
cp -R "$ROOT_DIR/server" "$ROOT_DIR/ui" "$ROOT_DIR/scripts" "$APP_DIR/"
find "$APP_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$APP_DIR" -type f -name '*.pyc' -delete
chmod 755 "$APP_DIR/scripts/start_linux.sh"

cat > "$DEBIAN_DIR/control" <<EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-venv, python3-gi, gir1.2-webkit2-4.0 | gir1.2-webkit2-4.1, ffmpeg, espeak-ng
Maintainer: Local User <local@localhost>
Description: Local Vietnamese speech app for AIRI
 AIRI Vietnamese Speech provides TTS, voice cloning, and STT in a local desktop UI.
EOF

cat > "$STAGING_DIR/usr/bin/airi-vietnamese-speech" <<'EOF'
#!/usr/bin/env bash
exec /opt/airi-vietnamese-speech/scripts/start_linux.sh "$@"
EOF
chmod 755 "$STAGING_DIR/usr/bin/airi-vietnamese-speech"

cat > "$STAGING_DIR/usr/share/applications/airi-vietnamese-speech.desktop" <<'EOF'
[Desktop Entry]
Name=AIRI Vietnamese Speech
Comment=Local Vietnamese TTS, voice cloning, and STT for AIRI
Exec=airi-vietnamese-speech
Terminal=false
Type=Application
Categories=AudioVideo;Utility;
EOF

dpkg-deb --build "$STAGING_DIR" "$OUTPUT_FILE"
echo "Built: $OUTPUT_FILE"
