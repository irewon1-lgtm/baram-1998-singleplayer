extends Node
func _ready():
    if not ProjectSettings.load_resource_pack("res://runtime.pck"):
        OS.alert("게임 데이터를 읽지 못했습니다. 앱 파일을 확인하세요.","바람의나라")
        get_tree().quit(2);return
    var scene=load("res://main.tscn").instantiate()
    scene.options={"assets":"res://private_assets","content":"res://private_content"}
    # Generated only for a separately identified emulator verification build.
    if OS.is_debug_build() and FileAccess.file_exists("res://data/mobile_probe.json"):
        if not ProjectSettings.load_resource_pack("res://verification.pck"):get_tree().quit(2);return
        var probe=JSON.parse_string(FileAccess.get_file_as_string("res://data/mobile_probe.json"))
        if typeof(probe)!=TYPE_DICTIONARY:get_tree().quit(2);return
        scene.options.merge(probe,true)
        if FileAccess.file_exists("res://data/initial_save.json"):
            DirAccess.make_dir_recursive_absolute(str(scene.options.save).get_base_dir())
            if not FileAccess.file_exists(scene.options.save):
                var file=FileAccess.open(scene.options.save,FileAccess.WRITE)
                file.store_buffer(FileAccess.get_file_as_bytes("res://data/initial_save.json"));file.close()
    add_child(scene)
