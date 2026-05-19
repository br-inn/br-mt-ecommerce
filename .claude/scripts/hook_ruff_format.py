"""PostToolUse hook — auto-formats edited Python files in mt-pricing-backend/app/ with ruff."""
import json
import os
import subprocess
import sys

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")
norm = file_path.replace(os.sep, "/")
marker = "mt-pricing-backend/app/"
idx = norm.find(marker)

if idx >= 0 and file_path.endswith(".py"):
    backend_dir = file_path[: idx + len("mt-pricing-backend")]
    subprocess.run(
        ["uv", "run", "ruff", "format", file_path, "--quiet"],
        cwd=backend_dir,
        capture_output=True,
    )
