extends Node

var skills: Dictionary = {}
var flags: Dictionary = {}
var journal: Array[String] = []


func _ready() -> void:
	reset_run()


func reset_run() -> void:
	skills = {
		"lore": 2,
		"resolve": 1,
	}
	flags.clear()
	journal.clear()
	add_journal_entry("A half-burned charter mentions a courier cairn east of the river.")


func add_journal_entry(entry: String) -> void:
	if entry.is_empty():
		return
	journal.append(entry)


func set_flags(values: Dictionary) -> void:
	for key in values.keys():
		flags[key] = values[key]
