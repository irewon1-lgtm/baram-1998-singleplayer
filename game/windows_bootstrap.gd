extends Node

# Packaging adapter only. The verified game scene and save schema are unchanged.
# Assets remain external so their bytes and provenance match the Linux release.
func _ready():
    var overrides = {}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts = arg.trim_prefix("--").split("=",true,1)
            overrides[parts[0]] = parts[1]
    var root = OS.get_executable_path().get_base_dir()
    if OS.get_name() != "Windows":
        # Explicitly labeled Linux PCK verification, never a Windows PASS.
        root = str(overrides.get("package-root",root))
    var saved = str(overrides.get("save",""))
    if saved == "":
        if OS.get_name() != "Windows":
            stop("Linux package verification requires an isolated --save path.")
            return
        var local = OS.get_environment("LOCALAPPDATA")
        if local == "" or not local.is_absolute_path():
            stop("Windows 저장 폴더를 찾지 못했습니다. 기존 저장은 변경하지 않았습니다.")
            return
        saved = local.path_join("BaramSinglePlayer/saves/v2/character.json")
    if not saved.is_absolute_path():
        stop("저장 경로는 절대 경로여야 합니다. 기존 저장은 변경하지 않았습니다.")
        return
    var folders = {
        "assets":root.path_join("private_assets"),
        "content":root.path_join("private_content"),
        "save":saved
    }
    var required = [
        folders.assets.path_join("actors.json"),
        folders.assets.path_join("fonts/NotoSansCJK-Regular.ttc"),
        folders.assets.path_join("source_maps/world.json"),
        folders.content.path_join("ACTIVE.json")
    ]
    for member in required:
        if not FileAccess.file_exists(member):
            stop("게임 파일이 없습니다. ZIP 전체를 압축 해제한 뒤 실행하세요.\n"+member)
            return
    var folder_error = DirAccess.make_dir_recursive_absolute(saved.get_base_dir())
    if folder_error != OK:
        stop("저장 폴더를 만들지 못했습니다. 기존 저장은 변경하지 않았습니다.\n"+saved.get_base_dir())
        return
    var scene = load("res://main.tscn").instantiate()
    scene.options = folders
    add_child(scene)

func stop(message):
    push_error("WINDOWS_PACKAGE_BOOTSTRAP: "+message)
    if OS.get_name() == "Windows" and DisplayServer.get_name() != "headless":
        OS.alert(message,"바람의나라 실행 오류")
    get_tree().quit(2)
