extends Node
var volume:=0.65
var last_sequence:=0
var played: Array=[]
var missing: Dictionary={}
var players: Array[AudioStreamPlayer]=[]
func _ready() -> void:
	for i in range(8):
		var player:=AudioStreamPlayer.new();add_child(player);players.append(player)
func consume(events: Array) -> void:
	for event in events:
		var seq:=int(event.sequence)
		if seq<=last_sequence:continue
		last_sequence=seq
		var path:="res://audio/%d.wav" %int(event.sound)
		if not ResourceLoader.exists(path):missing[str(event.sound)]=true;continue
		if volume<=0:continue
		var player: AudioStreamPlayer=players[seq%players.size()]
		player.stream=load(path);player.volume_db=linear_to_db(maxf(0.0001,volume*float(event.volume)/100));player.play()
		played.append({"sequence":seq,"sound":int(event.sound),"mix_rate":AudioServer.get_mix_rate()})
		if played.size()>128:played.pop_front()
func stop_all() -> void:
	for player in players:player.stop()
