extends RefCounted


static func build() -> Dictionary:
	return {
		"roadside_cairn": {
			"title": "Roadside Cairn",
			"body": "Rain needles across the trade road as you find a low cairn wrapped in old prayer-cords. One stone has been carved with neat, deliberate runes. Another sits loose enough to suggest a hidden latch beneath it.",
			"choices": [
				{
					"text": "Study the runes for a pattern.",
					"check": {"skill": "lore", "difficulty": 2},
					"on_success": {
						"next": "rune_success",
						"journal": "The cairn's runes hide a passphrase used by dead-drop couriers: 'Dawn remembers'.",
						"flags": {"rune_phrase_known": true}
					},
					"on_failure": {
						"next": "rune_failure",
						"journal": "The weather smears the runes before you can fully map the pattern."
					}
				},
				{
					"text": "Force the loose stone and test the latch.",
					"check": {"skill": "resolve", "difficulty": 2},
					"on_success": {
						"next": "vault_open",
						"journal": "You force the latch with raw leverage and break the seal the hard way.",
						"flags": {"vault_forced": true, "vault_opened": true}
					},
					"on_failure": {
						"next": "bruised_knuckles",
						"journal": "The stone shifts, but not enough. Your hands pay for the attempt."
					}
				},
				{
					"text": "Mark the cairn on your map and leave it for later.",
					"result": {
						"next": "camp_note",
						"journal": "You mark the cairn on your map for a return trip with better light and tools.",
						"flags": {"cairn_marked": true}
					}
				}
			]
		},
		"rune_success": {
			"title": "The Phrase Beneath the Weather",
			"body": "The chisel marks repeat in a courier's cipher. Once you see the pattern, the meaning is plain enough: speak the phrase, then press the western stone.",
			"choices": [
				{
					"text": "Whisper 'Dawn remembers' and press the stone.",
					"result": {
						"next": "vault_open",
						"journal": "The latch yields as if it has been waiting for the words all season.",
						"flags": {"vault_opened": true}
					}
				},
				{
					"text": "Memorize the passphrase and withdraw.",
					"result": {
						"next": "camp_note",
						"journal": "You leave with the phrase committed to memory and the site still undisturbed.",
						"flags": {"cairn_marked": true}
					}
				}
			]
		},
		"rune_failure": {
			"title": "Smudged Meaning",
			"body": "Whatever certainty lived in the runes is gone with the rain. You can keep testing the site by instinct, or back off before you damage something valuable.",
			"choices": [
				{
					"text": "Try the latch anyway.",
					"result": {
						"next": "bruised_knuckles"
					}
				},
				{
					"text": "Leave and update your notes.",
					"result": {
						"next": "camp_note",
						"journal": "You note that the cairn likely conceals a mechanism, but the cipher needs a cleaner read.",
						"flags": {"cairn_marked": true}
					}
				}
			]
		},
		"bruised_knuckles": {
			"title": "Stone Wins",
			"body": "The loose slab bites back. There is a mechanism here, but brute force alone is not enough to solve it quickly.",
			"choices": [
				{
					"text": "Step back and read the runes instead.",
					"result": {
						"next": "roadside_cairn"
					}
				},
				{
					"text": "Cut your losses and leave.",
					"result": {
						"next": "camp_note",
						"journal": "You retreat from the cairn with a better sense of its stubborn construction.",
						"flags": {"cairn_marked": true}
					}
				}
			]
		},
		"vault_open": {
			"title": "Courier Cache",
			"body": "The western stone folds inward and reveals a narrow compartment. Inside are waxed notes, a broken signet, and a route ledger naming an archivist in Daggerford as the final recipient.",
			"choices": [
				{
					"text": "Take the ledger and add the archivist lead to your journal.",
					"result": {
						"next": "journal_complete",
						"journal": "Recovered a route ledger pointing to an archivist in Daggerford. This is enough to start a proper quest thread.",
						"flags": {"daggerford_archivist_lead": true, "quest_archivist_started": true}
					}
				},
				{
					"text": "Reseal the cache after a quick look.",
					"result": {
						"next": "camp_note",
						"journal": "You leave the ledger in place for now, but note the archivist's name and destination.",
						"flags": {"daggerford_archivist_lead": true}
					}
				}
			]
		},
		"journal_complete": {
			"title": "Quest Seed Logged",
			"body": "This slice ends with a concrete lead, a journal update, and a quest-state flag. From here the next scene could move to a world map, camp, or city hub conversation.",
			"choices": []
		},
		"camp_note": {
			"title": "Leave It For Later",
			"body": "You step back onto the road with the cairn entered into your notes. This branch ends cleanly without advancing the quest, but the site remains available for a later return.",
			"choices": []
		}
	}
