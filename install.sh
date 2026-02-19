#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=== Openprovider MCP Server — Setup ==="
echo

# --- Find Python 3.10+ ---
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        major="${version%%.*}"
        minor="${version#*.}"
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python 3.10+ is required but not found."
    echo "Install it with: sudo apt install python3 (Ubuntu/Debian) or brew install python (macOS)"
    exit 1
fi

echo "Using $PYTHON ($($PYTHON --version 2>&1))"

# --- Create venv ---
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "Virtual environment already exists."
fi

echo "Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt

# --- Credentials ---
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    echo
    echo "Created .env from .env.example."
    read -rp "Enter your Openprovider username: " op_user
    read -rsp "Enter your Openprovider password: " op_pass
    echo
    if [[ -n "$op_user" && -n "$op_pass" ]]; then
        cat > .env <<EOF
OPENPROVIDER_USERNAME=$op_user
OPENPROVIDER_PASSWORD=$op_pass
EOF
        echo "Credentials saved to .env"
    else
        echo "Skipped — edit .env manually before use."
    fi
    chmod 600 .env
else
    echo ".env already exists, skipping credential setup."
fi

echo
echo "=== Setup complete ==="
echo

# --- Claude Code registration ---
if command -v claude &>/dev/null; then
    echo "Claude Code CLI detected."
    read -rp "Register as MCP server in Claude Code? [Y/n] " register
    register="${register:-Y}"
    if [[ "$register" =~ ^[Yy]$ ]]; then
        claude mcp add -s user -t stdio openprovider -- "$DIR/.venv/bin/python" "$DIR/server.py"
        echo "Registered! The server will be available in your next Claude Code session."
    else
        echo "Skipped. To register manually, run:"
        echo "  claude mcp add -s user -t stdio openprovider -- $DIR/.venv/bin/python $DIR/server.py"
    fi
else
    echo "To use with Claude Code, add this to your MCP config:"
    echo
    echo "  claude mcp add -s user -t stdio openprovider -- $DIR/.venv/bin/python $DIR/server.py"
    echo
    echo "Or add manually to ~/.claude.json under mcpServers:"
    echo
    cat <<SNIPPET
  "openprovider": {
    "type": "stdio",
    "command": "$DIR/.venv/bin/python",
    "args": ["$DIR/server.py"]
  }
SNIPPET
fi
