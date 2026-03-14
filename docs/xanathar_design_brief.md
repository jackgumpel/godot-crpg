# Xanathar-Inspired Design Brief

This note turns broad ideas from *Xanathar's Guide to Everything* into CRPG-ready systems for `godot-crpg`.

Use this as inspiration and structure. Do not copy source text into the game.

## Source quality

- The local PDF at `/home/jackgumpel/Desktop/628552380-Xanathar-s-Guide-to-Everything.pdf` is damaged.
- A Ghostscript repair could only recover 51 pages, and command-line text extraction returned mostly viewer headers.
- Because of that, this brief is based on verified section listings and summaries rather than direct extraction from the local file.

## High-value sections for this project

### This Is Your Life

Use this as the model for background generation, not as a player-facing questionnaire dump.

- Generate short origin packets for companions and notable NPCs.
- Build each packet from a few tags: origin, family pressure, formative event, debt, rival, secret.
- Surface only the pieces that matter in dialogue checks, banter, and quest hooks.

CRPG implementation:

- Create an `origin_profile` resource for important characters.
- Let origin tags unlock or modify dialogue lines.
- Use one hidden tag as a future reveal or betrayal lever.

### Tool Proficiencies

This is one of the best fits for a text-heavy CRPG.

- Treat tools as contextual capability tags, not separate minigames.
- Combine a core stat with a tool tag to unlock richer choices.
- Let tools change the shape of success, not just the chance of success.

CRPG implementation:

- Example: `Lore + Calligrapher's Supplies` reveals forged seals.
- Example: `Resolve + Smith's Tools` lets the player brace a failing mechanism.
- Example: `Insight + Disguise Kit` spots a staged identity instead of merely lying better.

System rule:

- Prefer `stat + tag` checks over isolated skill checks.
- Return different outcomes for `success`, `partial`, and `failure-with-information`.

### Random Encounters

Use these as structured travel scenes, not filler combat.

- Build encounter decks per region.
- Favor encounters that change state: rumor learned, faction noticed, supplies lost, site discovered, escort obligation created.
- Keep only a minority as direct combat starters.

CRPG implementation:

- Each travel encounter should resolve in under three choices.
- Every encounter should write at least one flag, journal entry, or map marker.
- Encounters should be reusable with different states depending on prior flags.

Recommended encounter types:

- road omen
- social interruption
- broken landmark
- faction patrol
- weather hazard
- courier dead-drop
- false refuge

### Traps Revisited

This maps cleanly to Pillars-style scripted interactions.

- Use traps as scenes with readable clues, escalating pressure, and multiple response paths.
- Reserve instant punishment for obvious recklessness.
- The best trap scenes ask for observation, planning, and role-based responses.

CRPG implementation:

- Build "complex trap" scenes as short multi-step sequences.
- Each step should expose a clue, raise pressure, or open a new response.
- Different party tags should create different safe solutions.

Good trap structure:

1. Telegraph danger.
2. Let the player inspect.
3. Present at least three solution angles.
4. Apply a consequence that changes future play, not only hit points.

Example consequences:

- route collapsed
- noise alerted watchers
- relic damaged
- companion shaken
- faction trust reduced

### Downtime Activities

This is one of the strongest long-term systems for a narrative CRPG.

- Treat downtime as a city or camp phase between field operations.
- Each downtime action should advance a clock, spend a resource, and risk complications.
- Complications are what make downtime feel authored rather than menu-driven.

CRPG implementation:

- Start with four actions: gather rumors, recover, work a contact, research.
- Add one complication table per settlement tier.
- Track rival progress during downtime so the world moves while the party rests.

Minimum downtime outputs:

- new lead
- temporary buff
- debt or obligation
- vendor access
- faction reaction
- quest timer advancement

### Character Names

This is low effort and high value.

- Use culture-specific naming pools for Forgotten Realms flavor.
- Assign naming conventions by settlement, faction, and ancestry.
- Keep a generated reserve list for taverns, guards, scribes, smugglers, and pilgrims.

CRPG implementation:

- Store name pools in data files, not hardcoded scenes.
- Generate full names plus a short descriptor for journal readability.

## What to build from this first

These are the best immediate systems for the prototype:

1. `scripted_interaction` data model for text scenes with flags, checks, and outcomes.
2. `travel_event` deck for roadside encounters.
3. `downtime_action` model for camp or town phases.
4. `npc_origin_profile` model for companions and quest givers.

## Immediate design rules

- Every text scene must change state.
- Prefer layered outcomes over binary pass/fail.
- Reward preparation, tools, and prior knowledge.
- Keep combat optional in many encounter types.
- Use journal updates as concrete progression, not flavor only.

## Next build targets

1. Add a second roadside scene that branches differently if `rune_phrase_known` or `daggerford_archivist_lead` is set.
2. Add a simple travel deck system that can pull one encounter from a region list.
3. Add a camp screen with one downtime action and one complication.
4. Add one companion profile whose origin tag changes a scene response.
