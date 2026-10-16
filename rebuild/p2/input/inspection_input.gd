extends RefCounted
## Called only by _unhandled_input: UI-consumed events cannot reach this adapter.
var state: RefCounted

func _init(shared_state: RefCounted) -> void:
	state = shared_state

func consume(event: InputEvent) -> bool:
	if event is InputEventKey and not event.echo:
		var action := ""
		match event.physical_keycode:
			KEY_LEFT: action = "left"
			KEY_RIGHT: action = "right"
			KEY_UP: action = "up"
			KEY_DOWN: action = "down"
			KEY_SPACE: action = "inspect_action"
		if not action.is_empty():
			if event.pressed:
				state.held_actions[action] = true
			else:
				state.held_actions.erase(action)
			return true
	return false
