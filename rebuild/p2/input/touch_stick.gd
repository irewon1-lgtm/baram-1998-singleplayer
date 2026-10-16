extends Control
## One finger drags a transient stick; a stationary tap remains world navigation.
signal direction_changed(direction: Vector2i)
signal tapped(position: Vector2)
var finger := -1
var origin := Vector2.ZERO
var point := Vector2.ZERO
var dragging := false
var direction := Vector2i.ZERO
const RADIUS := 44.0
const DEADZONE := 12.0

func _ready() -> void:
	mouse_filter=Control.MOUSE_FILTER_STOP
	gui_input.connect(_event)

func cancel() -> void:
	finger=-1;dragging=false;direction=Vector2i.ZERO
	direction_changed.emit(direction);queue_redraw()

func _set_point(value: Vector2) -> void:
	point=value
	var offset:=point-origin
	if offset.length()>DEADZONE: dragging=true
	var next:=Vector2i.ZERO
	if dragging and offset.length()>DEADZONE:
		next=Vector2i(signi(int(offset.x)),0) if absf(offset.x)>=absf(offset.y) else Vector2i(0,signi(int(offset.y)))
	if next!=direction: direction=next;direction_changed.emit(direction)
	queue_redraw()

func _event(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed and finger<0:
			finger=event.index;origin=event.position;point=origin;dragging=false
		elif not event.pressed and event.index==finger:
			var tap:=not dragging;var at: Vector2=event.position
			cancel()
			if tap: tapped.emit(at)
		accept_event()
	elif event is InputEventScreenDrag and event.index==finger:
		_set_point(event.position);accept_event()
	elif event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT:
		# Android's emulated mouse must not duplicate the real touch tap.
		if event.device==InputEvent.DEVICE_ID_EMULATION: return
		if event.pressed and finger<0: finger=-2;origin=event.position;point=origin;dragging=false
		elif not event.pressed and finger==-2:
			var tap:=not dragging;var at: Vector2=event.position;cancel()
			if tap: tapped.emit(at)
		accept_event()
	elif event is InputEventMouseMotion and finger==-2:
		_set_point(event.position);accept_event()

func _draw() -> void:
	if not dragging: return
	draw_circle(origin,RADIUS,Color(0.15,0.09,0.03,0.23))
	draw_arc(origin,RADIUS,0,TAU,48,Color(0.94,0.79,0.52,0.42),2,true)
	draw_circle(origin+(point-origin).limit_length(RADIUS),17,Color(0.94,0.79,0.52,0.48))
