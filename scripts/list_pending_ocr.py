#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DOCUMENTS_PATH = ROOT / "data" / "authoring" / "source_documents.json"


def main() -> int:
	data = json.loads(SOURCE_DOCUMENTS_PATH.read_text(encoding="utf-8"))
	jobs: list[dict[str, str]] = []
	for document in data.get("documents", []):
		if document.get("ocr_status") != "pending_ocr":
			continue
		source_pdf = str(document["source_pdf"])
		jobs.append(
			{
				"document_id": str(document["id"]),
				"title": str(document["title"]),
				"source_pdf": source_pdf,
				"recommended_command": (
					f"python3 scripts/azure_docint_ocr.py --model prebuilt-layout --chunk-size 5 --resume \"{source_pdf}\""
				),
			}
		)
	print(json.dumps({"status": "ok", "pending_jobs": jobs}, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
