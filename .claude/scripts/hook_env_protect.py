"""PreToolUse hook — blocks accidental edits to .env secrets files."""
import json
import os
import sys

BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.deploy",
    ".env.production",
    ".env.staging",
    ".env.prod",
    ".env.test",
    ".env.production.local",
    ".env.development.local",
    ".env.test.local",
}

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")
if os.path.basename(file_path) in BLOCKED_NAMES:
    print(
        f"[env-protect] BLOCKED: '{file_path}' is a secrets file — edit it outside Claude Code.",
        file=sys.stderr,
    )
    sys.exit(1)
