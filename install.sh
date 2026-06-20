#!/bin/bash
#
# FileWhisper — one-line installer (macOS)
#
#   curl -fsSL https://raw.githubusercontent.com/ishankanodia/server_rag/main/install.sh | bash
#
# What it does:
#   1. Downloads FileWhisper into ~/.filewhisper/app
#   2. Builds an isolated Python environment (no PyTorch — stays small & fast)
#   3. Pre-downloads the local AI models so the first question is instant
#   4. Drops a double-click "FileWhisper" launcher on your Desktop
#
# After this, the user never needs Terminal again — they just double-click.
#
set -e

REPO="ishankanodia/server_rag"
BRANCH="${FILEWHISPER_BRANCH:-main}"
APP_DIR="$HOME/.filewhisper/app"
VENV="$APP_DIR/.venv"
LAUNCHER="$HOME/Desktop/FileWhisper.command"

echo ""
echo "=================================================="
echo "   Installing FileWhisper"
echo "=================================================="
echo ""

# 1. Make sure Python 3 is available (macOS provides it via Command Line Tools).
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is needed but was not found."
  echo "A macOS install window will open — click \"Install\", let it finish,"
  echo "then run this command again."
  xcode-select --install 2>/dev/null || true
  exit 1
fi

# 2. Get the source. FILEWHISPER_SRC lets you install from a local copy (testing);
#    otherwise the latest version is downloaded from GitHub.
echo "-> Downloading FileWhisper..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
if [ -n "$FILEWHISPER_SRC" ]; then
  # Copy local source, excluding bulky/transient dirs.
  ( cd "$FILEWHISPER_SRC" && \
    find . -type d \( -name .git -o -name .venv -o -name node_modules -o -name dist -o -name target \) -prune -o -type f -print \
    | sed 's|^\./||' | while read -r f; do
        mkdir -p "$APP_DIR/$(dirname "$f")"
        cp "$FILEWHISPER_SRC/$f" "$APP_DIR/$f"
      done )
else
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
    | tar xz -C "$APP_DIR" --strip-components=1
fi

# 3. Build an isolated environment and install dependencies (no PyTorch).
echo "-> Setting up (downloads ~400 MB the first time, please wait)..."
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$APP_DIR/requirements.txt"

# 4. Pre-download the local AI models so the first question doesn't stall.
echo "-> Preparing the local AI models..."
"$VENV/bin/python" - <<'PY' || true
try:
    from fastembed import TextEmbedding
    list(TextEmbedding("sentence-transformers/all-MiniLM-L6-v2").embed(["warmup"]))
    print("   embeddings ready")
except Exception as e:
    print("   (embedding warmup skipped:", e, ")")
try:
    from rapidocr_onnxruntime import RapidOCR
    RapidOCR()
    print("   OCR ready")
except Exception as e:
    print("   (OCR warmup skipped:", e, ")")
PY

# 5. Create a double-click launcher on the Desktop.
#    Generated locally, so macOS does NOT quarantine it -> it just opens.
cat > "$LAUNCHER" <<EOF
#!/bin/bash
# Double-click to start FileWhisper. Close this window to stop it.
cd "$APP_DIR"
exec "$VENV/bin/python" -m filewhisper.server_launcher
EOF
chmod +x "$LAUNCHER"

echo ""
echo "=================================================="
echo "   FileWhisper is installed!"
echo "=================================================="
echo ""
echo "  Double-click  \"FileWhisper\"  on your Desktop to start."
echo "  It opens automatically in your web browser."
echo "  (To stop it, just close the small black window.)"
echo ""
