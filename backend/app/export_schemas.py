"""Write the API's OpenAPI document and the study guide JSON Schema for the web app.

    python -m app.export_schemas ../frontend/lib/schema

The web app generates its TypeScript types from these two files (npm run gen:types).
"""

import json
import sys
from pathlib import Path

from app.main import create_app
from app.schemas.study_guide import StudyGuideContent


def main(out: str) -> None:
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    openapi = create_app().openapi()
    guide = StudyGuideContent.model_json_schema(by_alias=True, mode="serialization")
    for name, doc in (("openapi.json", openapi), ("study-guide.schema.json", guide)):
        (target / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print(f"wrote {target / name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../frontend/lib/schema")
