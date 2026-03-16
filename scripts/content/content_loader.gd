extends RefCounted


const SKILLS_PATH := "res://data/runtime/skills.json"
const STATE_REGISTRY_PATH := "res://data/runtime/state_registry.json"


static func load_json_resource(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("Missing JSON resource: %s" % path)
		return {}

	var source := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(source)
	if parsed is Dictionary:
		return parsed

	push_error("Expected a top-level JSON object in %s" % path)
	return {}


static func load_skill_labels(path: String = SKILLS_PATH) -> Dictionary:
	var data := load_json_resource(path)
	var labels: Dictionary = {}
	var skills_by_id: Dictionary = data.get("skills_by_id", {})
	for skill_id in skills_by_id.keys():
		var skill_data: Dictionary = skills_by_id.get(skill_id, {})
		labels[skill_id] = String(skill_data.get("label", String(skill_id).capitalize()))
	return labels


static func load_state_defaults(path: String = STATE_REGISTRY_PATH) -> Dictionary:
	var data := load_json_resource(path)
	var defaults := {
		"flags": {},
		"counters": {},
		"quest_states": {},
	}

	var flags_by_id: Dictionary = data.get("flags_by_id", {})
	for flag_id in flags_by_id.keys():
		var flag_data: Dictionary = flags_by_id.get(flag_id, {})
		defaults["flags"][flag_id] = bool(flag_data.get("default", false))

	var counters_by_id: Dictionary = data.get("counters_by_id", {})
	for counter_id in counters_by_id.keys():
		var counter_data: Dictionary = counters_by_id.get(counter_id, {})
		defaults["counters"][counter_id] = int(counter_data.get("default", 0))

	var quest_states_by_id: Dictionary = data.get("quest_states_by_id", {})
	for quest_state_id in quest_states_by_id.keys():
		var quest_state_data: Dictionary = quest_states_by_id.get(quest_state_id, {})
		defaults["quest_states"][quest_state_id] = String(quest_state_data.get("default", ""))

	return defaults
