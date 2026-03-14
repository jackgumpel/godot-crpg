#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_VERSION = "2024-11-30"
DEFAULT_MODEL = "prebuilt-layout"
DEFAULT_POLL_INTERVAL = 2.0
USER_AGENT = "godot-crpg-azure-docint/0.1"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Run Azure AI Document Intelligence against one or more PDFs and "
			"write raw JSON plus normalized text/markdown outputs."
		)
	)
	parser.add_argument(
		"inputs",
		nargs="+",
		help="One or more PDF paths to analyze.",
	)
	parser.add_argument(
		"--endpoint",
		default=os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", ""),
		help="Azure Document Intelligence endpoint. Can also come from AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.",
	)
	parser.add_argument(
		"--key",
		default=os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY", ""),
		help="Azure Document Intelligence API key. Can also come from AZURE_DOCUMENT_INTELLIGENCE_KEY.",
	)
	parser.add_argument(
		"--model",
		default=DEFAULT_MODEL,
		help="Model id to use. Defaults to prebuilt-layout.",
	)
	parser.add_argument(
		"--api-version",
		default=DEFAULT_API_VERSION,
		help=f"API version to use. Defaults to {DEFAULT_API_VERSION}.",
	)
	parser.add_argument(
		"--output-dir",
		default="tmp/pdfs/azure_ocr",
		help="Root directory for OCR artifacts.",
	)
	parser.add_argument(
		"--output-format",
		choices=["auto", "text", "markdown"],
		default="auto",
		help="Analyze result content format. Defaults to auto.",
	)
	parser.add_argument(
		"--pages",
		default="",
		help='Optional 1-based page filter, e.g. "1-30,45,50-60".',
	)
	parser.add_argument(
		"--locale",
		default="",
		help='Optional locale hint, e.g. "en-US".',
	)
	parser.add_argument(
		"--poll-interval",
		type=float,
		default=DEFAULT_POLL_INTERVAL,
		help=f"Polling interval in seconds. Defaults to {DEFAULT_POLL_INTERVAL}.",
	)
	parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Overwrite existing result files.",
	)
	return parser.parse_args()


def choose_output_format(model: str, requested: str) -> str:
	if requested != "auto":
		return requested
	return "markdown" if model == "prebuilt-layout" else "text"


def normalize_endpoint(endpoint: str) -> str:
	return endpoint.rstrip("/")


def build_analyze_url(
	endpoint: str,
	model: str,
	api_version: str,
	output_format: str,
	pages: str,
	locale: str,
) -> str:
	path = "/documentintelligence/documentModels/%s:analyze" % urllib.parse.quote(model, safe="")
	query = {
		"api-version": api_version,
		"outputContentFormat": output_format,
	}
	if pages:
		query["pages"] = pages
	if locale:
		query["locale"] = locale
	return "%s%s?%s" % (normalize_endpoint(endpoint), path, urllib.parse.urlencode(query))


def request_json(url: str, key: str, method: str, data: bytes | None = None, content_type: str = "") -> tuple[dict[str, Any], dict[str, str]]:
	headers = {
		"Accept": "application/json",
		"Ocp-Apim-Subscription-Key": key,
		"User-Agent": USER_AGENT,
	}
	if content_type:
		headers["Content-Type"] = content_type

	request = urllib.request.Request(url, data=data, method=method, headers=headers)
	try:
		with urllib.request.urlopen(request) as response:
			body = response.read().decode("utf-8")
			payload = json.loads(body) if body else {}
			return payload, dict(response.headers.items())
	except urllib.error.HTTPError as error:
		error_body = error.read().decode("utf-8", errors="replace")
		raise RuntimeError(
			"Azure request failed: %s %s\n%s" % (error.code, error.reason, error_body)
		) from error


def submit_document(
	endpoint: str,
	key: str,
	model: str,
	api_version: str,
	output_format: str,
	pages: str,
	locale: str,
	document_bytes: bytes,
) -> str:
	url = build_analyze_url(endpoint, model, api_version, output_format, pages, locale)
	_, headers = request_json(
		url,
		key,
		method="POST",
		data=document_bytes,
		content_type="application/octet-stream",
	)
	operation_location = headers.get("operation-location") or headers.get("Operation-Location")
	if not operation_location:
		raise RuntimeError("Azure response did not include an Operation-Location header.")
	return operation_location


def poll_result(operation_location: str, key: str, poll_interval: float) -> dict[str, Any]:
	while True:
		payload, _ = request_json(operation_location, key, method="GET")
		status = str(payload.get("status", "")).lower()
		if status in {"notstarted", "running"}:
			time.sleep(poll_interval)
			continue
		if status != "succeeded":
			raise RuntimeError("Azure analysis did not succeed: %s" % json.dumps(payload, indent=2))
		return payload


def slugify(value: str) -> str:
	characters: list[str] = []
	for char in value.lower():
		if char.isalnum():
			characters.append(char)
		elif char in {" ", "-", "_", "."}:
			characters.append("_")
	return "".join(characters).strip("_") or "document"


def extract_plain_text(result: dict[str, Any]) -> str:
	analyze_result = result.get("analyzeResult", {})
	pages = analyze_result.get("pages", [])
	page_texts: list[str] = []
	for page in pages:
		line_texts: list[str] = []
		for line in page.get("lines", []):
			content = str(line.get("content", "")).strip()
			if content:
				line_texts.append(content)
		if line_texts:
			page_number = page.get("pageNumber", "?")
			page_texts.append("Page %s\n%s" % (page_number, "\n".join(line_texts)))
	return "\n\n".join(page_texts).strip()


def write_outputs(
	output_root: Path,
	input_path: Path,
	model: str,
	output_format: str,
	request_metadata: dict[str, Any],
	result: dict[str, Any],
	overwrite: bool,
) -> Path:
	document_dir = output_root / slugify(input_path.stem)
	document_dir.mkdir(parents=True, exist_ok=True)

	result_path = document_dir / "result.json"
	request_path = document_dir / "request.json"
	content_extension = "md" if output_format == "markdown" else "txt"
	content_path = document_dir / ("content.%s" % content_extension)
	plain_text_path = document_dir / "plain_text.txt"

	if not overwrite and result_path.exists():
		raise FileExistsError(
			"Result already exists for %s at %s. Re-run with --overwrite."
			% (input_path, result_path)
		)

	result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
	request_path.write_text(json.dumps(request_metadata, indent=2), encoding="utf-8")

	content = str(result.get("analyzeResult", {}).get("content", "")).strip()
	content_path.write_text(content, encoding="utf-8")

	plain_text = extract_plain_text(result)
	plain_text_path.write_text(plain_text, encoding="utf-8")
	return document_dir


def process_file(args: argparse.Namespace, input_path: Path, output_root: Path) -> dict[str, Any]:
	document_bytes = input_path.read_bytes()
	output_format = choose_output_format(args.model, args.output_format)
	operation_location = submit_document(
		endpoint=args.endpoint,
		key=args.key,
		model=args.model,
		api_version=args.api_version,
		output_format=output_format,
		pages=args.pages,
		locale=args.locale,
		document_bytes=document_bytes,
	)
	result = poll_result(operation_location, args.key, args.poll_interval)
	document_dir = write_outputs(
		output_root=output_root,
		input_path=input_path,
		model=args.model,
		output_format=output_format,
		request_metadata={
			"input_path": str(input_path),
			"model": args.model,
			"api_version": args.api_version,
			"output_format": output_format,
			"pages": args.pages,
			"locale": args.locale,
			"operation_location": operation_location,
			"input_bytes": len(document_bytes),
		},
		result=result,
		overwrite=args.overwrite,
	)
	analyze_result = result.get("analyzeResult", {})
	return {
		"input": str(input_path),
		"output_dir": str(document_dir),
		"model": args.model,
		"output_format": output_format,
		"pages_returned": len(analyze_result.get("pages", [])),
		"content_chars": len(str(analyze_result.get("content", ""))),
	}


def main() -> int:
	args = parse_args()
	if not args.endpoint or not args.key:
		print(
			"error: provide --endpoint/--key or set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY",
			file=sys.stderr,
		)
		return 2

	output_root = Path(args.output_dir)
	output_root.mkdir(parents=True, exist_ok=True)

	summaries: list[dict[str, Any]] = []
	failures: list[dict[str, str]] = []
	for raw_input in args.inputs:
		input_path = Path(raw_input)
		if not input_path.exists():
			failures.append({"input": raw_input, "error": "file not found"})
			continue
		try:
			summary = process_file(args, input_path, output_root)
			summaries.append(summary)
			print(json.dumps({"status": "ok", **summary}))
		except Exception as error:  # noqa: BLE001
			failures.append({"input": str(input_path), "error": str(error)})
			print(json.dumps({"status": "error", "input": str(input_path), "error": str(error)}), file=sys.stderr)

	print(json.dumps({"status": "done", "processed": len(summaries), "failed": len(failures)}))
	if failures:
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
