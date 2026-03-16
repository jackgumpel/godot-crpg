extends RefCounted

const ContentLoader = preload("res://scripts/content/content_loader.gd")
const ENCOUNTER_PATH := "res://data/runtime/encounters/roadside_cairn.json"

static func build() -> Dictionary:
	return ContentLoader.load_json_resource(ENCOUNTER_PATH)
