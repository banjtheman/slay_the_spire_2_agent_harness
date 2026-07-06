#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR_DIR="$ROOT/.vendor"
CLI_ANYTHING_DIR="$VENDOR_DIR/CLI-Anything"
BRIDGE_PATCH="$ROOT/patches/cli-anything-sts2-bridge-compat.patch"
GAME_ROOT="${STS2_GAME_ROOT:-$HOME/Library/Application Support/Steam/steamapps/common/Slay the Spire 2}"
GAME_DATA_DIR="${STS2_GAME_DATA_DIR:-$GAME_ROOT/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v dotnet >/dev/null 2>&1; then
  echo "ERROR: dotnet not found. Install .NET 9 SDK first." >&2
  exit 1
fi

if ! dotnet --list-sdks | awk '{ split($1, version, "."); if (version[1] >= 9) found=1 } END { exit found ? 0 : 1 }'; then
  echo "ERROR: .NET 9 SDK or newer is required to build STS2_Bridge." >&2
  echo "Install with: brew install --cask dotnet-sdk" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "ERROR: Python 3.10+ is required for cli-anything-sts2. Found $PYTHON_VERSION at $PYTHON_BIN." >&2
  echo "Try: PYTHON_BIN=/path/to/python ./scripts/setup_live_bridge.sh" >&2
  exit 1
fi

if [ ! -d "$GAME_DATA_DIR" ]; then
  echo "ERROR: STS2 game data directory not found:" >&2
  echo "  $GAME_DATA_DIR" >&2
  echo "Set STS2_GAME_DATA_DIR to override." >&2
  exit 1
fi

mkdir -p "$VENDOR_DIR"

if [ ! -d "$CLI_ANYTHING_DIR/.git" ]; then
  git clone --depth 1 https://github.com/HKUDS/CLI-Anything.git "$CLI_ANYTHING_DIR"
elif [ -n "$(git -C "$CLI_ANYTHING_DIR" status --porcelain)" ]; then
  echo "Local CLI-Anything changes detected; skipping git pull."
else
  git -C "$CLI_ANYTHING_DIR" pull --ff-only
fi

HARNESS_DIR="$CLI_ANYTHING_DIR/slay_the_spire_ii/agent-harness"

if [ -f "$BRIDGE_PATCH" ]; then
  if git -C "$CLI_ANYTHING_DIR" apply --reverse --check "$BRIDGE_PATCH" >/dev/null 2>&1; then
    echo "✓ Bridge compatibility fixes already applied."
  elif git -C "$CLI_ANYTHING_DIR" apply --check "$BRIDGE_PATCH" >/dev/null 2>&1; then
    echo "Applying bridge compatibility fixes..."
    git -C "$CLI_ANYTHING_DIR" apply "$BRIDGE_PATCH"
  else
    echo "ERROR: Could not apply bundled bridge compatibility fixes:" >&2
    echo "  $BRIDGE_PATCH" >&2
    echo "The upstream bridge may have changed. Inspect $CLI_ANYTHING_DIR and update the patch." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" -m pip install -e "$HARNESS_DIR"

(
  cd "$HARNESS_DIR/bridge/plugin"
  STS2_GAME_DATA_DIR="$GAME_DATA_DIR" DOTNET_ROLL_FORWARD=Minor ./build.sh
)

(
  cd "$HARNESS_DIR/bridge/install"
  ./install_bridge.sh "$GAME_ROOT"
)

cat <<EOF

Live bridge files installed.

Next:
  1. Launch Slay the Spire 2 from Steam.
  2. Enable STS2_Bridge in the game mod manager.
  3. Verify:
       python3 -m live_bridge doctor
       python3 -m live_bridge state

EOF
