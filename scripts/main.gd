extends Control

const EncounterData = preload("res://scripts/content/encounter_data.gd")
const SKILL_LABELS := {
	"lore": "Lore",
	"resolve": "Resolve",
}

var encounters: Dictionary = {}
var current_encounter_id := "roadside_cairn"

@onready var scene_title: Label = $MarginContainer/Root/Columns/NarrativePanel/Margin/VBox/SceneTitle
@onready var body_text: RichTextLabel = $MarginContainer/Root/Columns/NarrativePanel/Margin/VBox/BodyText
@onready var choices_box: VBoxContainer = $MarginContainer/Root/Columns/NarrativePanel/Margin/VBox/Choices
@onready var restart_button: Button = $MarginContainer/Root/Columns/NarrativePanel/Margin/VBox/RestartButton
@onready var stats_text: RichTextLabel = $MarginContainer/Root/Columns/SidebarPanel/Margin/VBox/StatsText
@onready var journal_text: RichTextLabel = $MarginContainer/Root/Columns/SidebarPanel/Margin/VBox/JournalText


func _ready() -> void:
	encounters = EncounterData.build()
	restart_button.pressed.connect(_restart_vertical_slice)
	_restart_vertical_slice()


func _restart_vertical_slice() -> void:
	GameState.reset_run()
	current_encounter_id = "roadside_cairn"
	_render_current_encounter()


func _render_current_encounter() -> void:
	var encounter: Dictionary = encounters.get(current_encounter_id, {})
	if encounter.is_empty():
		push_error("Unknown encounter id: %s" % current_encounter_id)
		return

	scene_title.text = String(encounter.get("title", "Untitled Encounter"))
	body_text.clear()
	body_text.append_text(String(encounter.get("body", "")))
	_rebuild_choices(encounter.get("choices", []))
	_refresh_sidebar()


func _rebuild_choices(choice_list: Array) -> void:
	for child in choices_box.get_children():
		child.queue_free()

	if choice_list.is_empty():
		var ending_label := Label.new()
		ending_label.text = "No further actions in this slice. Restart to test another branch."
		ending_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		choices_box.add_child(ending_label)
		return

	for choice_data in choice_list:
		var button := Button.new()
		button.text = _format_choice_text(choice_data)
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.pressed.connect(_on_choice_pressed.bind(choice_data))
		choices_box.add_child(button)


func _on_choice_pressed(choice_data: Dictionary) -> void:
	var result: Dictionary = choice_data.get("result", {})
	var check: Dictionary = choice_data.get("check", {})

	if not check.is_empty():
		var skill_name := String(check.get("skill", ""))
		var difficulty := int(check.get("difficulty", 0))
		var skill_value := int(GameState.skills.get(skill_name, 0))
		if skill_value >= difficulty:
			result = choice_data.get("on_success", {})
		else:
			result = choice_data.get("on_failure", {})

	_apply_result(result)


func _apply_result(result: Dictionary) -> void:
	var flag_updates: Dictionary = result.get("flags", {})
	if not flag_updates.is_empty():
		GameState.set_flags(flag_updates)

	var journal_entry := String(result.get("journal", ""))
	if not journal_entry.is_empty():
		GameState.add_journal_entry(journal_entry)

	current_encounter_id = String(result.get("next", current_encounter_id))
	_render_current_encounter()


func _refresh_sidebar() -> void:
	stats_text.clear()
	stats_text.append_text(_build_stats_text())

	journal_text.clear()
	journal_text.append_text(_build_journal_text())


func _build_stats_text() -> String:
	var lines: Array[String] = ["Skills"]
	for skill_id in SKILL_LABELS.keys():
		lines.append("%s: %d" % [SKILL_LABELS[skill_id], int(GameState.skills.get(skill_id, 0))])

	lines.append("")
	lines.append("Flags")

	var flag_keys: Array = GameState.flags.keys()
	flag_keys.sort()
	if flag_keys.is_empty():
		lines.append("None yet.")
	else:
		for flag_key in flag_keys:
			if bool(GameState.flags[flag_key]):
				lines.append("- %s" % String(flag_key).replace("_", " "))

	return "\n".join(lines)


func _build_journal_text() -> String:
	if GameState.journal.is_empty():
		return "No entries yet."

	var lines: Array[String] = []
	for index in range(GameState.journal.size()):
		lines.append("%d. %s" % [index + 1, GameState.journal[index]])
	return "\n\n".join(lines)


func _format_choice_text(choice_data: Dictionary) -> String:
	var base_text := String(choice_data.get("text", "Continue"))
	var check: Dictionary = choice_data.get("check", {})
	if check.is_empty():
		return base_text

	var skill_name := String(check.get("skill", ""))
	var difficulty := int(check.get("difficulty", 0))
	var skill_label := String(SKILL_LABELS.get(skill_name, skill_name.capitalize()))
	var skill_value := int(GameState.skills.get(skill_name, 0))
	return "%s [%s %d/%d]" % [base_text, skill_label, skill_value, difficulty]
