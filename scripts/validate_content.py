#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AUTHORING_ROOT = ROOT / "data" / "authoring"
RUNTIME_ROOT = ROOT / "data" / "runtime"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
ALLOWED_SKILL_KINDS = {"knowledge", "social", "physical", "survival", "magic", "will"}


class ValidationError(Exception):
	pass


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Validate authoring datasets and write normalized runtime JSON."
	)
	parser.add_argument(
		"--check-only",
		action="store_true",
		help="Validate datasets without writing runtime files.",
	)
	return parser.parse_args()


def ensure(condition: bool, message: str) -> None:
	if not condition:
		raise ValidationError(message)


def load_json(path: Path) -> Any:
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except FileNotFoundError as error:
		raise ValidationError(f"Missing required file: {path}") from error
	except json.JSONDecodeError as error:
		raise ValidationError(f"Invalid JSON in {path}: {error}") from error


def write_json(path: Path, payload: Any) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_id(value: Any, context: str) -> str:
	ensure(isinstance(value, str), f"{context} must be a string id.")
	ensure(ID_PATTERN.match(value) is not None, f"{context} must be snake_case: {value!r}")
	return value


def expect_object(value: Any, context: str) -> dict[str, Any]:
	ensure(isinstance(value, dict), f"{context} must be an object.")
	return value


def expect_list(value: Any, context: str) -> list[Any]:
	ensure(isinstance(value, list), f"{context} must be an array.")
	return value


def ensure_known_keys(
	data: dict[str, Any],
	required: set[str],
	allowed: set[str],
	context: str,
) -> None:
	missing = sorted(required - data.keys())
	extra = sorted(set(data.keys()) - allowed)
	ensure(not missing, f"{context} is missing required keys: {missing}")
	ensure(not extra, f"{context} has unsupported keys: {extra}")


def validate_skills(data: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
	ensure_known_keys(
		data,
		required={"schema_version", "dataset_type", "skills"},
		allowed={"schema_version", "dataset_type", "skills"},
		context="skills registry",
	)
	ensure(data["dataset_type"] == "skills_registry", "skills registry dataset_type must be skills_registry")
	skills = expect_list(data["skills"], "skills registry skills")
	ensure(skills, "skills registry must define at least one skill.")

	skills_by_id: dict[str, Any] = {}
	for index, raw_skill in enumerate(skills, start=1):
		context = f"skills[{index}]"
		skill = expect_object(raw_skill, context)
		ensure_known_keys(
			skill,
			required={"id", "label", "description", "kind"},
			allowed={"id", "label", "description", "kind"},
			context=context,
		)
		skill_id = validate_id(skill["id"], f"{context}.id")
		ensure(skill_id not in skills_by_id, f"Duplicate skill id: {skill_id}")
		ensure(isinstance(skill["label"], str) and skill["label"], f"{context}.label must be a non-empty string.")
		ensure(
			isinstance(skill["description"], str) and skill["description"],
			f"{context}.description must be a non-empty string.",
		)
		ensure(skill["kind"] in ALLOWED_SKILL_KINDS, f"{context}.kind must be one of {sorted(ALLOWED_SKILL_KINDS)}.")
		skills_by_id[skill_id] = {
			"id": skill_id,
			"label": skill["label"],
			"description": skill["description"],
			"kind": skill["kind"],
		}

	return {
		"schema_version": data["schema_version"],
		"dataset_type": "skills_registry_runtime",
		"skills_by_id": skills_by_id,
	}, set(skills_by_id.keys())


def validate_state_registry(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, set[str]]]:
	ensure_known_keys(
		data,
		required={"schema_version", "dataset_type", "flags", "counters", "quest_states"},
		allowed={"schema_version", "dataset_type", "flags", "counters", "quest_states"},
		context="state registry",
	)
	ensure(data["dataset_type"] == "state_registry", "state registry dataset_type must be state_registry")

	flags_by_id: dict[str, Any] = {}
	for index, raw_flag in enumerate(expect_list(data["flags"], "state registry flags"), start=1):
		context = f"flags[{index}]"
		flag = expect_object(raw_flag, context)
		ensure_known_keys(
			flag,
			required={"id", "default", "description"},
			allowed={"id", "default", "description"},
			context=context,
		)
		flag_id = validate_id(flag["id"], f"{context}.id")
		ensure(flag_id not in flags_by_id, f"Duplicate flag id: {flag_id}")
		ensure(isinstance(flag["default"], bool), f"{context}.default must be boolean.")
		ensure(isinstance(flag["description"], str) and flag["description"], f"{context}.description must be a non-empty string.")
		flags_by_id[flag_id] = flag

	counters_by_id: dict[str, Any] = {}
	for index, raw_counter in enumerate(expect_list(data["counters"], "state registry counters"), start=1):
		context = f"counters[{index}]"
		counter = expect_object(raw_counter, context)
		ensure_known_keys(
			counter,
			required={"id", "default", "min", "description"},
			allowed={"id", "default", "min", "description"},
			context=context,
		)
		counter_id = validate_id(counter["id"], f"{context}.id")
		ensure(counter_id not in counters_by_id, f"Duplicate counter id: {counter_id}")
		ensure(isinstance(counter["default"], int), f"{context}.default must be an integer.")
		ensure(isinstance(counter["min"], int), f"{context}.min must be an integer.")
		ensure(counter["default"] >= counter["min"], f"{context}.default must be >= min.")
		ensure(
			isinstance(counter["description"], str) and counter["description"],
			f"{context}.description must be a non-empty string.",
		)
		counters_by_id[counter_id] = counter

	quest_states_by_id: dict[str, Any] = {}
	for index, raw_quest_state in enumerate(expect_list(data["quest_states"], "state registry quest_states"), start=1):
		context = f"quest_states[{index}]"
		quest_state = expect_object(raw_quest_state, context)
		ensure_known_keys(
			quest_state,
			required={"id", "allowed_values", "default", "description"},
			allowed={"id", "allowed_values", "default", "description"},
			context=context,
		)
		quest_state_id = validate_id(quest_state["id"], f"{context}.id")
		ensure(quest_state_id not in quest_states_by_id, f"Duplicate quest_state id: {quest_state_id}")
		allowed_values = expect_list(quest_state["allowed_values"], f"{context}.allowed_values")
		ensure(allowed_values, f"{context}.allowed_values must not be empty.")
		normalized_values: list[str] = []
		for value in allowed_values:
			normalized_values.append(validate_id(value, f"{context}.allowed_values[]"))
		default_value = validate_id(quest_state["default"], f"{context}.default")
		ensure(default_value in normalized_values, f"{context}.default must be included in allowed_values.")
		ensure(
			isinstance(quest_state["description"], str) and quest_state["description"],
			f"{context}.description must be a non-empty string.",
		)
		quest_states_by_id[quest_state_id] = {
			"id": quest_state_id,
			"allowed_values": normalized_values,
			"default": default_value,
			"description": quest_state["description"],
		}

	return {
		"schema_version": data["schema_version"],
		"dataset_type": "state_registry_runtime",
		"flags_by_id": flags_by_id,
		"counters_by_id": counters_by_id,
		"quest_states_by_id": quest_states_by_id,
	}, {
		"flags": set(flags_by_id.keys()),
		"counters": set(counters_by_id.keys()),
		"quest_states": set(quest_states_by_id.keys()),
	}


def validate_source_documents(data: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
	ensure_known_keys(
		data,
		required={"schema_version", "dataset_type", "documents"},
		allowed={
			"schema_version",
			"dataset_type",
			"documents",
		},
		context="source documents",
	)
	ensure(data["dataset_type"] == "source_documents", "source documents dataset_type must be source_documents")

	documents_by_id: dict[str, Any] = {}
	for index, raw_document in enumerate(expect_list(data["documents"], "source documents documents"), start=1):
		context = f"documents[{index}]"
		document = expect_object(raw_document, context)
		ensure_known_keys(
			document,
			required={"id", "title", "source_pdf", "ocr_status"},
			allowed={
				"id",
				"title",
				"source_pdf",
				"ocr_status",
				"ocr_content_path",
				"ocr_plain_text_path",
				"ocr_manifest_path",
				"notes",
			},
			context=context,
		)
		document_id = validate_id(document["id"], f"{context}.id")
		ensure(document_id not in documents_by_id, f"Duplicate document id: {document_id}")
		ensure(isinstance(document["title"], str) and document["title"], f"{context}.title must be a non-empty string.")
		source_pdf = ROOT / str(document["source_pdf"])
		ensure(source_pdf.exists(), f"{context}.source_pdf does not exist: {document['source_pdf']}")
		ocr_status = document["ocr_status"]
		ensure(ocr_status in {"pending_ocr", "ocr_complete"}, f"{context}.ocr_status is invalid: {ocr_status}")
		if ocr_status == "ocr_complete":
			for key in ("ocr_content_path", "ocr_plain_text_path", "ocr_manifest_path"):
				ensure(key in document, f"{context}.{key} is required when ocr_status is ocr_complete.")
				artifact_path = ROOT / str(document[key])
				ensure(artifact_path.exists(), f"{context}.{key} does not exist: {document[key]}")
		documents_by_id[document_id] = document

	return {
		"schema_version": data["schema_version"],
		"dataset_type": "source_documents_runtime",
		"documents_by_id": documents_by_id,
	}, set(documents_by_id.keys())


def validate_source_refs(
	source_refs: Any,
	document_ids: set[str],
	context: str,
) -> list[dict[str, Any]]:
	normalized: list[dict[str, Any]] = []
	for index, raw_ref in enumerate(expect_list(source_refs, f"{context}.source_refs"), start=1):
		ref_context = f"{context}.source_refs[{index}]"
		source_ref = expect_object(raw_ref, ref_context)
		ensure_known_keys(
			source_ref,
			required={"document_id", "page_start", "page_end"},
			allowed={"document_id", "page_start", "page_end", "section_title", "confidence", "import_notes"},
			context=ref_context,
		)
		document_id = validate_id(source_ref["document_id"], f"{ref_context}.document_id")
		ensure(document_id in document_ids, f"{ref_context}.document_id is unknown: {document_id}")
		page_start = source_ref["page_start"]
		page_end = source_ref["page_end"]
		ensure(isinstance(page_start, int) and page_start >= 1, f"{ref_context}.page_start must be >= 1.")
		ensure(isinstance(page_end, int) and page_end >= page_start, f"{ref_context}.page_end must be >= page_start.")
		confidence = source_ref.get("confidence")
		if confidence is not None:
			ensure(isinstance(confidence, (int, float)), f"{ref_context}.confidence must be numeric.")
			ensure(0 <= float(confidence) <= 1, f"{ref_context}.confidence must be between 0 and 1.")
		normalized.append(source_ref)
	return normalized


def validate_result(
	result: Any,
	node_ids: set[str],
	state_ids: dict[str, set[str]],
	context: str,
) -> dict[str, Any]:
	result_object = expect_object(result, context)
	ensure_known_keys(
		result_object,
		required={"next"},
		allowed={"next", "journal_add", "set_flags", "add_counters", "set_quest_states", "end_encounter"},
		context=context,
	)
	next_id = validate_id(result_object["next"], f"{context}.next")
	ensure(next_id in node_ids, f"{context}.next references unknown node: {next_id}")
	journal_add = result_object.get("journal_add")
	if journal_add is not None:
		ensure(isinstance(journal_add, str) and journal_add, f"{context}.journal_add must be a non-empty string.")

	set_flags = result_object.get("set_flags", {})
	ensure(isinstance(set_flags, dict), f"{context}.set_flags must be an object.")
	for flag_id, flag_value in set_flags.items():
		validate_id(flag_id, f"{context}.set_flags key")
		ensure(flag_id in state_ids["flags"], f"{context}.set_flags references unknown flag: {flag_id}")
		ensure(isinstance(flag_value, bool), f"{context}.set_flags[{flag_id}] must be boolean.")

	add_counters = result_object.get("add_counters", {})
	ensure(isinstance(add_counters, dict), f"{context}.add_counters must be an object.")
	for counter_id, delta in add_counters.items():
		validate_id(counter_id, f"{context}.add_counters key")
		ensure(counter_id in state_ids["counters"], f"{context}.add_counters references unknown counter: {counter_id}")
		ensure(isinstance(delta, int), f"{context}.add_counters[{counter_id}] must be integer.")

	set_quest_states = result_object.get("set_quest_states", {})
	ensure(isinstance(set_quest_states, dict), f"{context}.set_quest_states must be an object.")
	for quest_state_id, quest_value in set_quest_states.items():
		validate_id(quest_state_id, f"{context}.set_quest_states key")
		ensure(
			quest_state_id in state_ids["quest_states"],
			f"{context}.set_quest_states references unknown quest state: {quest_state_id}",
		)
		validate_id(quest_value, f"{context}.set_quest_states[{quest_state_id}]")

	return result_object


def validate_encounter(
	data: dict[str, Any],
	skill_ids: set[str],
	state_ids: dict[str, set[str]],
	document_ids: set[str],
) -> dict[str, Any]:
	ensure_known_keys(
		data,
		required={"schema_version", "dataset_type", "encounter_set_id", "entry_node_id", "nodes"},
		allowed={"schema_version", "dataset_type", "encounter_set_id", "entry_node_id", "nodes"},
		context="encounter set",
	)
	ensure(data["dataset_type"] == "encounter_set", "encounter dataset_type must be encounter_set")
	encounter_set_id = validate_id(data["encounter_set_id"], "encounter_set_id")
	entry_node_id = validate_id(data["entry_node_id"], "entry_node_id")
	raw_nodes = expect_list(data["nodes"], "encounter nodes")
	ensure(raw_nodes, "encounter must contain at least one node.")

	node_ids: set[str] = set()
	for index, raw_node in enumerate(raw_nodes, start=1):
		node = expect_object(raw_node, f"nodes[{index}]")
		node_id = validate_id(node.get("id"), f"nodes[{index}].id")
		ensure(node_id not in node_ids, f"Duplicate encounter node id: {node_id}")
		node_ids.add(node_id)
	ensure(entry_node_id in node_ids, f"entry_node_id references unknown node: {entry_node_id}")

	nodes_by_id: dict[str, Any] = {}
	for index, raw_node in enumerate(raw_nodes, start=1):
		context = f"nodes[{index}]"
		node = expect_object(raw_node, context)
		ensure_known_keys(
			node,
			required={"id", "title", "body", "choices"},
			allowed={"id", "title", "body", "choices", "tags", "source_refs"},
			context=context,
		)
		node_id = validate_id(node["id"], f"{context}.id")
		ensure(isinstance(node["title"], str) and node["title"], f"{context}.title must be a non-empty string.")
		ensure(isinstance(node["body"], str) and node["body"], f"{context}.body must be a non-empty string.")

		tags: list[str] = []
		if "tags" in node:
			for tag in expect_list(node["tags"], f"{context}.tags"):
				tags.append(validate_id(tag, f"{context}.tags[]"))

		source_refs: list[dict[str, Any]] = []
		if "source_refs" in node:
			source_refs = validate_source_refs(node["source_refs"], document_ids, context)

		choices = expect_list(node["choices"], f"{context}.choices")
		choice_ids: set[str] = set()
		normalized_choices: list[dict[str, Any]] = []
		for choice_index, raw_choice in enumerate(choices, start=1):
			choice_context = f"{context}.choices[{choice_index}]"
			choice = expect_object(raw_choice, choice_context)
			ensure_known_keys(
				choice,
				required={"id", "text"},
				allowed={"id", "text", "result", "check", "ui_tags"},
				context=choice_context,
			)
			choice_id = validate_id(choice["id"], f"{choice_context}.id")
			ensure(choice_id not in choice_ids, f"Duplicate choice id in node {node_id}: {choice_id}")
			choice_ids.add(choice_id)
			ensure(isinstance(choice["text"], str) and choice["text"], f"{choice_context}.text must be a non-empty string.")

			has_result = "result" in choice
			has_check = "check" in choice
			ensure(has_result != has_check, f"{choice_context} must define exactly one of result or check.")

			normalized_choice: dict[str, Any] = {
				"id": choice_id,
				"text": choice["text"],
			}

			if "ui_tags" in choice:
				ui_tags: list[str] = []
				for tag in expect_list(choice["ui_tags"], f"{choice_context}.ui_tags"):
					ui_tags.append(validate_id(tag, f"{choice_context}.ui_tags[]"))
				normalized_choice["ui_tags"] = ui_tags

			if has_result:
				normalized_choice["result"] = validate_result(
					choice["result"],
					node_ids=node_ids,
					state_ids=state_ids,
					context=f"{choice_context}.result",
				)
			else:
				check = expect_object(choice["check"], f"{choice_context}.check")
				ensure_known_keys(
					check,
					required={"skill", "difficulty", "on_success", "on_failure"},
					allowed={"skill", "difficulty", "hint_text", "on_success", "on_failure"},
					context=f"{choice_context}.check",
				)
				skill_id = validate_id(check["skill"], f"{choice_context}.check.skill")
				ensure(skill_id in skill_ids, f"{choice_context}.check.skill is unknown: {skill_id}")
				difficulty = check["difficulty"]
				ensure(isinstance(difficulty, int) and difficulty >= 0, f"{choice_context}.check.difficulty must be >= 0.")
				normalized_check: dict[str, Any] = {
					"skill": skill_id,
					"difficulty": difficulty,
					"on_success": validate_result(
						check["on_success"],
						node_ids=node_ids,
						state_ids=state_ids,
						context=f"{choice_context}.check.on_success",
					),
					"on_failure": validate_result(
						check["on_failure"],
						node_ids=node_ids,
						state_ids=state_ids,
						context=f"{choice_context}.check.on_failure",
					),
				}
				if "hint_text" in check:
					ensure(
						isinstance(check["hint_text"], str) and check["hint_text"],
						f"{choice_context}.check.hint_text must be a non-empty string.",
					)
					normalized_check["hint_text"] = check["hint_text"]
				normalized_choice["check"] = normalized_check

			normalized_choices.append(normalized_choice)

		normalized_node: dict[str, Any] = {
			"id": node_id,
			"title": node["title"],
			"body": node["body"],
			"choices": normalized_choices,
		}
		if tags:
			normalized_node["tags"] = tags
		if source_refs:
			normalized_node["source_refs"] = source_refs
		nodes_by_id[node_id] = normalized_node

	return {
		"schema_version": data["schema_version"],
		"dataset_type": "encounter_set_runtime",
		"encounter_set_id": encounter_set_id,
		"entry_node_id": entry_node_id,
		"nodes": nodes_by_id,
	}


def main() -> int:
	args = parse_args()

	try:
		skills_runtime, skill_ids = validate_skills(
			expect_object(load_json(AUTHORING_ROOT / "skills.json"), "data/authoring/skills.json")
		)
		state_runtime, state_ids = validate_state_registry(
			expect_object(load_json(AUTHORING_ROOT / "state_registry.json"), "data/authoring/state_registry.json")
		)
		source_documents_runtime, document_ids = validate_source_documents(
			expect_object(load_json(AUTHORING_ROOT / "source_documents.json"), "data/authoring/source_documents.json")
		)

		encounter_outputs: list[tuple[Path, dict[str, Any]]] = []
		for encounter_path in sorted((AUTHORING_ROOT / "encounters").glob("*.json")):
			encounter_data = expect_object(load_json(encounter_path), str(encounter_path))
			encounter_runtime = validate_encounter(
				encounter_data,
				skill_ids=skill_ids,
				state_ids=state_ids,
				document_ids=document_ids,
			)
			encounter_outputs.append((encounter_path, encounter_runtime))
	except ValidationError as error:
		print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
		return 1

	if not args.check_only:
		write_json(RUNTIME_ROOT / "skills.json", skills_runtime)
		write_json(RUNTIME_ROOT / "state_registry.json", state_runtime)
		write_json(RUNTIME_ROOT / "source_documents.json", source_documents_runtime)
		for encounter_path, encounter_runtime in encounter_outputs:
			write_json(RUNTIME_ROOT / "encounters" / encounter_path.name, encounter_runtime)

	print(
		json.dumps(
			{
				"status": "ok",
				"check_only": args.check_only,
				"encounter_files": [path.name for path, _ in encounter_outputs],
				"skills": sorted(skill_ids),
				"documents": sorted(document_ids),
			}
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
