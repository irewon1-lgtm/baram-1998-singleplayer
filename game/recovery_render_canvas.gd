extends "res://main.gd"
## Test-only canvas inherits the production composite renderer unchanged.
var probe

func _ready():pass
func _process(_delta):pass
func _input(_event):pass

func _draw():
    work_assets.begin_frame()
    if probe!=null:probe.draw_probe(self)
