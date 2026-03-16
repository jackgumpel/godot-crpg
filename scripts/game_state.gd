extends Node

const ContentLoader = preload("res://scripts/content/content_loader.gd")

var skills: Dictionary = {}
var flags: Dictionary = {}
var counters: Dictionary = {}
var quest_states: Dictionary = {}
var journal: Array[String] = []


func _ready() -> void:
	reset_run()


func reset_run() -> void:
	var state_defaults := ContentLoader.load_state_defaults()
	skills = {
		"lore": 2,
		"resolve": 1,
	}
	flags = state_defaults.get("flags", {}).duplicate(true)
	counters = state_defaults.get("counters", {}).duplicate(true)
	quest_states = state_defaults.get("quest_states", {}).duplicate(true)
	journal.clear()
	add_journal_entry("A half-burned charter mentions a courier cairn east of the river.")


func add_journal_entry(entry: String) -> void:
	if entry.is_empty():
		return
	journal.append(entry)


func set_flags(values: Dictionary) -> void:
	for key in values.keys():
		flags[key] = values[key]


func add_counters(values: Dictionary) -> void:
	for key in values.keys():
		counters[key] = int(counters.get(key, 0)) + int(values[key])


func set_quest_states(values: Dictionary) -> void:
	for key in values.keys():
		quest_states[key] = values[key]
