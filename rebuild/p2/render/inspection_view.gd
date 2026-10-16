extends PanelContainer
## No stand-in map, sprite, icon or sound. Render only verified content later.
var message: Label

func _ready() -> void:
	message = Label.new()
	message.text = "G0 BLOCKED\n한국 지도·캐릭터·효과·음향 원본 미수신\n\n원본 바이트와 의존성 검증 뒤 표시합니다."
	message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	message.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(message)
