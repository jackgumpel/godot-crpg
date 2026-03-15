#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
import shutil

DEFAULT_API_VERSION = "2024-11-30"
DEFAULT_MODEL = "prebuilt-layout"
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_REQUEST_TIMEOUT = 60.0
DEFAULT_MAX_POLL_ERRORS = 12
USER_AGENT = "godot-crpg-azure-docint/0.1"


class TransientAzureError(Exception):
	def __init__(self, message: str, wait_seconds: float | None = None) -> None:
		super().__init__(message)
		self.wait_seconds = wait_seconds


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
		"--chunk-size",
		type=int,
		default=0,
		help=(
			"Automatically split a PDF into fixed-size page chunks and OCR them "
			"sequentially. Ignored when --pages is set."
		),
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
		"--request-timeout",
		type=float,
		default=DEFAULT_REQUEST_TIMEOUT,
		help=f"HTTP request timeout in seconds. Defaults to {DEFAULT_REQUEST_TIMEOUT}.",
	)
	parser.add_argument(
		"--max-poll-errors",
		type=int,
		default=DEFAULT_MAX_POLL_ERRORS,
		help=(
			"Maximum number of transient submission or polling errors to tolerate before failing. "
			f"Defaults to {DEFAULT_MAX_POLL_ERRORS}."
		),
	)
	parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Overwrite existing result files.",
	)
	parser.add_argument(
		"--resume",
		action="store_true",
		help="Skip chunks that already have saved outputs on disk.",
	)
	parser.add_argument(
		"--merge-inputs",
		action="store_true",
		help="Merge the processed or resumed outputs for all provided inputs in order.",
	)
	parser.add_argument(
		"--merge-name",
		default="",
		help="Optional name for the merged output directory when --merge-inputs is set.",
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


def is_transient_error(error: BaseException) -> bool:
	if isinstance(error, urllib.error.HTTPError):
		return error.code in {408, 409, 429, 500, 502, 503, 504}
	if isinstance(error, urllib.error.URLError):
		reason = error.reason
		if isinstance(reason, (TimeoutError, socket.timeout, ssl.SSLError, ConnectionResetError)):
			return True
		reason_text = str(reason).lower()
		return "eof occurred in violation of protocol" in reason_text or "timed out" in reason_text
	return isinstance(error, (TimeoutError, socket.timeout, ssl.SSLError, ConnectionResetError))


def request_json(
	url: str,
	key: str,
	method: str,
	data: bytes | None = None,
	content_type: str = "",
	request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> tuple[dict[str, Any], dict[str, str]]:
	headers = {
		"Accept": "application/json",
		"Ocp-Apim-Subscription-Key": key,
		"User-Agent": USER_AGENT,
	}
	if content_type:
		headers["Content-Type"] = content_type

	request = urllib.request.Request(url, data=data, method=method, headers=headers)
	try:
		with urllib.request.urlopen(request, timeout=request_timeout) as response:
			body = response.read().decode("utf-8")
			payload = json.loads(body) if body else {}
			return payload, dict(response.headers.items())
	except urllib.error.HTTPError as error:
		error_body = error.read().decode("utf-8", errors="replace")
		if error.code in {408, 409, 429, 500, 502, 503, 504}:
			retry_after = error.headers.get("Retry-After") if error.headers else None
			wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else None
			raise TransientAzureError(
				"Azure request failed: %s %s\n%s" % (error.code, error.reason, error_body),
				wait_seconds=wait_seconds,
			) from error
		raise RuntimeError(
			"Azure request failed: %s %s\n%s" % (error.code, error.reason, error_body)
		) from error
	except urllib.error.URLError as error:
		if is_transient_error(error):
			raise TransientAzureError(str(error)) from error
		raise
	except (TimeoutError, socket.timeout, ssl.SSLError, ConnectionResetError) as error:
		raise TransientAzureError(str(error)) from error


def submit_document(
	endpoint: str,
	key: str,
	model: str,
	api_version: str,
	output_format: str,
	pages: str,
	locale: str,
	document_bytes: bytes,
	request_timeout: float,
) -> str:
	url = build_analyze_url(endpoint, model, api_version, output_format, pages, locale)
	_, headers = request_json(
		url,
		key,
		method="POST",
		data=document_bytes,
		content_type="application/octet-stream",
		request_timeout=request_timeout,
	)
	operation_location = headers.get("operation-location") or headers.get("Operation-Location")
	if not operation_location:
		raise RuntimeError("Azure response did not include an Operation-Location header.")
	return operation_location


def poll_result(
	operation_location: str,
	key: str,
	poll_interval: float,
	request_timeout: float,
	max_poll_errors: int,
) -> dict[str, Any]:
	transient_error_count = 0
	while True:
		try:
			payload, _ = request_json(
				operation_location,
				key,
				method="GET",
				request_timeout=request_timeout,
			)
			transient_error_count = 0
		except TransientAzureError as error:
			transient_error_count += 1
			if transient_error_count > max_poll_errors:
				raise RuntimeError(
					"Azure polling exceeded transient error budget (%d): %s"
					% (max_poll_errors, error)
				) from error
			time.sleep(error.wait_seconds or poll_interval)
			continue
		except Exception as error:  # noqa: BLE001
			if not is_transient_error(error):
				raise
			transient_error_count += 1
			if transient_error_count > max_poll_errors:
				raise RuntimeError(
					"Azure polling exceeded transient error budget (%d): %s"
					% (max_poll_errors, error)
				) from error
			time.sleep(poll_interval)
			continue
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


def build_document_slug(input_path: Path, pages: str) -> str:
	base_slug = slugify(input_path.stem)
	if not pages:
		return base_slug
	return "%s__pages_%s" % (base_slug, slugify(pages))


def parse_pages_spec(pages: str) -> list[tuple[int, int]]:
	ranges: list[tuple[int, int]] = []
	for raw_part in pages.split(","):
		part = raw_part.strip()
		if not part:
			continue
		if "-" in part:
			start_text, end_text = part.split("-", 1)
			start = int(start_text)
			end = int(end_text)
		else:
			start = int(part)
			end = start
		if start < 1 or end < start:
			raise ValueError("Invalid page range: %s" % part)
		ranges.append((start, end))
	return ranges


def run_command(command: list[str]) -> None:
	result = subprocess.run(command, capture_output=True, text=True, check=False)
	if result.returncode != 0:
		raise RuntimeError(
			"Command failed (%s): %s"
			% (" ".join(command), result.stderr.strip() or result.stdout.strip())
		)


def prepare_upload_path(input_path: Path, pages: str, output_root: Path) -> tuple[Path, str]:
	if not pages or input_path.suffix.lower() != ".pdf":
		return input_path, pages
	if not shutil.which("pdfseparate") or not shutil.which("pdfunite"):
		return input_path, pages

	chunk_slug = build_document_slug(input_path, pages)
	chunk_root = output_root / "_upload_chunks" / chunk_slug
	chunk_root.mkdir(parents=True, exist_ok=True)
	chunk_path = chunk_root / ("%s.pdf" % chunk_slug)
	if chunk_path.exists():
		return chunk_path, ""

	chunk_pages: list[Path] = []
	for index, (start, end) in enumerate(parse_pages_spec(pages), start=1):
		pattern = chunk_root / ("range_%02d_page-%%03d.pdf" % index)
		run_command(
			[
				"pdfseparate",
				"-f",
				str(start),
				"-l",
				str(end),
				str(input_path),
				str(pattern),
			]
		)
		chunk_pages.extend(sorted(chunk_root.glob("range_%02d_page-*.pdf" % index)))

	if not chunk_pages:
		raise RuntimeError("No PDF pages were extracted for range %s." % pages)

	run_command(["pdfunite", *[str(path) for path in chunk_pages], str(chunk_path)])
	return chunk_path, ""


def get_pdf_page_count(input_path: Path) -> int:
	result = subprocess.run(
		["pdfinfo", str(input_path)],
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode != 0:
		raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "pdfinfo failed")
	for line in result.stdout.splitlines():
		if line.startswith("Pages:"):
			return int(line.split(":", 1)[1].strip())
	raise RuntimeError("Could not determine page count for %s" % input_path)


def build_chunk_ranges(total_pages: int, chunk_size: int) -> list[str]:
	if chunk_size < 1:
		raise ValueError("chunk_size must be at least 1")
	ranges: list[str] = []
	start = 1
	while start <= total_pages:
		end = min(start + chunk_size - 1, total_pages)
		ranges.append("%d-%d" % (start, end))
		start = end + 1
	return ranges


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
	output_format: str,
	pages: str,
	request_metadata: dict[str, Any],
	result: dict[str, Any],
	overwrite: bool,
) -> Path:
	document_dir = output_root / build_document_slug(input_path, pages)
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


def saved_output_matches_request(
	document_dir: Path,
	input_path: Path,
	model: str,
	output_format: str,
	pages: str,
) -> bool:
	request_path = document_dir / "request.json"
	if not request_path.exists():
		return False

	request_metadata = json.loads(request_path.read_text(encoding="utf-8"))
	saved_pages = str(request_metadata.get("requested_pages", request_metadata.get("pages", "")))
	return (
		str(request_metadata.get("input_path", "")) == str(input_path)
		and str(request_metadata.get("model", "")) == model
		and str(request_metadata.get("output_format", "")) == output_format
		and saved_pages == pages
	)


def build_summary_from_saved_output(
	output_root: Path,
	input_path: Path,
	model: str,
	output_format: str,
	pages: str,
) -> dict[str, Any]:
	document_dir = output_root / build_document_slug(input_path, pages)
	result_path = document_dir / "result.json"
	if not result_path.exists() or not saved_output_matches_request(
		document_dir,
		input_path,
		model,
		output_format,
		pages,
	):
		raise FileNotFoundError(result_path)
	result = json.loads(result_path.read_text(encoding="utf-8"))
	analyze_result = result.get("analyzeResult", {})
	return {
		"input": str(input_path),
		"output_dir": str(document_dir),
		"model": model,
		"output_format": output_format,
		"pages_returned": len(analyze_result.get("pages", [])),
		"content_chars": len(str(analyze_result.get("content", ""))),
	}


def write_merged_outputs(
	output_root: Path,
	output_name: str,
	chunk_summaries: list[dict[str, Any]],
) -> Path:
	merged_dir = output_root / slugify(output_name)
	merged_dir.mkdir(parents=True, exist_ok=True)

	if not chunk_summaries:
		raise RuntimeError("No chunk summaries were provided for merge.")

	output_format = str(chunk_summaries[0]["output_format"])
	content_extension = "md" if output_format == "markdown" else "txt"
	merged_content_path = merged_dir / ("content.%s" % content_extension)
	merged_plain_text_path = merged_dir / "plain_text.txt"
	manifest_path = merged_dir / "manifest.json"

	merged_content_parts: list[str] = []
	merged_plain_text_parts: list[str] = []
	for summary in chunk_summaries:
		chunk_dir = Path(str(summary["output_dir"]))
		chunk_content_path = chunk_dir / ("content.%s" % content_extension)
		chunk_plain_text_path = chunk_dir / "plain_text.txt"
		if chunk_content_path.exists():
			merged_content_parts.append(chunk_content_path.read_text(encoding="utf-8").strip())
		if chunk_plain_text_path.exists():
			merged_plain_text_parts.append(chunk_plain_text_path.read_text(encoding="utf-8").strip())

	merged_content_path.write_text(
		"\n\n".join(part for part in merged_content_parts if part),
		encoding="utf-8",
	)
	merged_plain_text_path.write_text(
		"\n\n".join(part for part in merged_plain_text_parts if part),
		encoding="utf-8",
	)
	manifest_path.write_text(json.dumps(chunk_summaries, indent=2), encoding="utf-8")
	return merged_dir


def process_file(args: argparse.Namespace, input_path: Path, output_root: Path) -> dict[str, Any]:
	upload_path, submitted_pages = prepare_upload_path(input_path, args.pages, output_root)
	output_format = choose_output_format(args.model, args.output_format)
	document_dir = output_root / build_document_slug(input_path, args.pages)
	has_mismatched_saved_output = (
		(document_dir / "result.json").exists()
		and not saved_output_matches_request(
			document_dir,
			input_path,
			args.model,
			output_format,
			args.pages,
		)
	)
	if args.resume and not args.overwrite:
		try:
			return build_summary_from_saved_output(
				output_root=output_root,
				input_path=input_path,
				model=args.model,
				output_format=output_format,
				pages=args.pages,
			)
		except FileNotFoundError:
			pass
	if not args.endpoint or not args.key:
		raise RuntimeError(
			"No saved output found for %s and Azure credentials are not set."
			% input_path
		)

	document_bytes = upload_path.read_bytes()
	submit_error_count = 0
	while True:
		try:
			operation_location = submit_document(
				endpoint=args.endpoint,
				key=args.key,
				model=args.model,
				api_version=args.api_version,
				output_format=output_format,
				pages=submitted_pages,
				locale=args.locale,
				document_bytes=document_bytes,
				request_timeout=args.request_timeout,
			)
			break
		except TransientAzureError as error:
			submit_error_count += 1
			if submit_error_count > args.max_poll_errors:
				raise RuntimeError(
					"Azure submission exceeded transient error budget (%d): %s"
					% (args.max_poll_errors, error)
				) from error
			time.sleep(error.wait_seconds or args.poll_interval)
	result = poll_result(
		operation_location,
		args.key,
		args.poll_interval,
		args.request_timeout,
		args.max_poll_errors,
	)
	document_dir = write_outputs(
		output_root=output_root,
		input_path=input_path,
		output_format=output_format,
		pages=args.pages,
		request_metadata={
			"input_path": str(input_path),
			"upload_path": str(upload_path),
			"model": args.model,
			"api_version": args.api_version,
			"output_format": output_format,
			"requested_pages": args.pages,
			"submitted_pages": submitted_pages,
			"locale": args.locale,
			"operation_location": operation_location,
			"input_bytes": len(document_bytes),
		},
		result=result,
		overwrite=args.overwrite or has_mismatched_saved_output,
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


def process_input(args: argparse.Namespace, input_path: Path, output_root: Path) -> dict[str, Any]:
	if args.chunk_size > 0 and not args.pages and input_path.suffix.lower() == ".pdf":
		total_pages = get_pdf_page_count(input_path)
		chunk_ranges = build_chunk_ranges(total_pages, args.chunk_size)
		chunk_summaries: list[dict[str, Any]] = []
		for index, page_range in enumerate(chunk_ranges, start=1):
			print(
				json.dumps(
					{
						"status": "chunk_start",
						"input": str(input_path),
						"chunk_index": index,
						"chunk_count": len(chunk_ranges),
						"pages": page_range,
					}
				),
				flush=True,
			)
			chunk_args = argparse.Namespace(**vars(args))
			chunk_args.pages = page_range
			chunk_summary = process_file(chunk_args, input_path, output_root)
			chunk_summaries.append(chunk_summary)
			print(
				json.dumps(
					{
						"status": "chunk_ok",
						"input": str(input_path),
						"chunk_index": index,
						"chunk_count": len(chunk_ranges),
						"pages": page_range,
						"output_dir": chunk_summary["output_dir"],
						"pages_returned": chunk_summary["pages_returned"],
						"content_chars": chunk_summary["content_chars"],
					}
				),
				flush=True,
			)
		merged_dir = write_merged_outputs(
			output_root,
			"%s__merged" % slugify(input_path.stem),
			chunk_summaries,
		)
		return {
			"input": str(input_path),
			"output_dir": str(merged_dir),
			"model": args.model,
			"output_format": chunk_summaries[0]["output_format"],
			"chunk_count": len(chunk_summaries),
			"pages_returned": sum(int(summary["pages_returned"]) for summary in chunk_summaries),
			"content_chars": sum(int(summary["content_chars"]) for summary in chunk_summaries),
		}
	return process_file(args, input_path, output_root)


def main() -> int:
	args = parse_args()
	if (not args.endpoint or not args.key) and not args.resume:
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
			summary = process_input(args, input_path, output_root)
			summaries.append(summary)
			print(json.dumps({"status": "ok", **summary}))
		except Exception as error:  # noqa: BLE001
			failures.append({"input": str(input_path), "error": str(error)})
			print(json.dumps({"status": "error", "input": str(input_path), "error": str(error)}), file=sys.stderr)

	if args.merge_inputs and summaries and not failures:
		merge_name = args.merge_name or "merged_inputs"
		merged_dir = write_merged_outputs(output_root, merge_name, summaries)
		print(
			json.dumps(
				{
					"status": "merged",
					"output_dir": str(merged_dir),
					"input_count": len(summaries),
					"merge_name": merge_name,
				}
			)
		)

	print(json.dumps({"status": "done", "processed": len(summaries), "failed": len(failures)}))
	if failures:
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
