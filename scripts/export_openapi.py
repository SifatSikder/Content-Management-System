"""Export the FastAPI OpenAPI schema to a JSON file.

Run via `uv run python scripts/export_openapi.py [output_path]`.

Used by CI to produce an artifact the frontend can consume for typed clients
(Phase 1 Task 1.1.3). Defaults to `openapi.json` at the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repo root importable when this script is invoked as a file path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    app = create_app()
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
