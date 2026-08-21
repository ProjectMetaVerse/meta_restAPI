from __future__ import annotations

import json
from pathlib import Path

from meta_api.main import create_app

app = create_app()
document = app.openapi()
Path("openapi.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
paths = document["paths"]
assert "/api/v1/health" in paths
assert "/api/v1/ready" in paths
assert "/api/v1/events" in paths
assert "/api/v1/events/{event_id}" in paths
print(f"OpenAPI {document['openapi']} with {len(paths)} paths")
print("paths:", ", ".join(sorted(paths)))
