extends RefCounted
## Shared inspection state, containing no reconstructed historical defaults.
var active_panel := 0
var input_generation := 0
var held_actions: Dictionary = {}
var equipment: Dictionary = {}
var original_input_status := "BLOCKED_MISSING_PRIVATE_BYTES"
var profile_id := "P2_INFRASTRUCTURE_ONLY"

func switch_panel(index: int) -> void:
	assert(index >= 0 and index < 4)
	active_panel = index

func clear_input() -> void:
	held_actions.clear()
	input_generation += 1
