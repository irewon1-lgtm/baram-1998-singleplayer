extends ScrollContainer
## Real parchment rows, shared selection API; no ItemList skin substitution.
signal item_selected(index: int)
var rows: VBoxContainer
var entries: Array = []
var selected := -1
var item_count: int:
	get: return entries.size()
var fixed_icon_size := Vector2i(28,28)

func _init() -> void:
	horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	rows = VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rows.add_theme_constant_override("separation",2)
	add_child(rows)

func clear() -> void:
	for child in rows.get_children():
		rows.remove_child(child); child.queue_free()
	entries.clear(); selected=-1

func add_item(title: String, icon: Texture2D = null) -> void:
	var index := entries.size()
	var button := Button.new()
	button.text = String.chr(97+index)+":  "+title
	button.icon=icon; button.expand_icon=true
	button.add_theme_constant_override("icon_max_width",28)
	button.custom_minimum_size=Vector2(0,38)
	button.alignment=HORIZONTAL_ALIGNMENT_LEFT
	button.toggle_mode=true; button.focus_mode=Control.FOCUS_NONE
	var normal:=StyleBoxFlat.new();normal.bg_color=Color(0.5,0.3,0.12,0.04)
	normal.content_margin_left=5;normal.content_margin_right=3
	button.add_theme_stylebox_override("normal",normal)
	var hover:=normal.duplicate();hover.bg_color=Color(0.5,0.3,0.12,0.17)
	button.add_theme_stylebox_override("hover",hover)
	button.add_theme_color_override("font_color",Color("302012"))
	button.add_theme_color_override("font_pressed_color",Color("fff3ca"))
	button.pressed.connect(func(): select(index); item_selected.emit(index))
	rows.add_child(button)
	entries.append({"button":button,"metadata":null})

func set_item_metadata(index: int, value: Variant) -> void:
	entries[index].metadata=value

func get_item_metadata(index: int) -> Variant:
	return entries[index].metadata

func set_item_tooltip(index: int, title: String) -> void:
	entries[index].button.tooltip_text=title

func get_selected_items() -> PackedInt32Array:
	return PackedInt32Array([selected]) if selected>=0 and selected<entries.size() else PackedInt32Array()

func select(index: int) -> void:
	selected=index
	for i in range(entries.size()): entries[i].button.set_pressed_no_signal(i==index)
