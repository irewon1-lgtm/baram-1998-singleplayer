extends Node
var loading_layer
var loading_label
var game

# Packaging adapter only. The verified game scene and save schema are unchanged.
# Assets remain external so their bytes and provenance match the Linux release.
func _ready():
    var overrides = {}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts = arg.trim_prefix("--").split("=",true,1)
            overrides[parts[0]] = parts[1]
    var root = OS.get_environment("BARAM_PACKAGE_ROOT")
    if root=="":root=OS.get_executable_path().get_base_dir()
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
        "save":saved,
        "async-startup":true
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
    var trace=OS.get_environment("BARAM_STARTUP_LOG")
    if trace=="":trace=saved.get_base_dir().get_base_dir().get_base_dir().path_join("logs/startup.jsonl")
    folders["startup-log"]=trace
    loading_layer=CanvasLayer.new()
    add_child(loading_layer)
    var backdrop=ColorRect.new()
    backdrop.color=Color(0.055,0.065,0.055)
    backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    loading_layer.add_child(backdrop)
    loading_label=Label.new()
    loading_label.position=Vector2(80,220)
    loading_label.size=Vector2(800,200)
    loading_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    var loading_font=FontFile.new()
    loading_font.data=FileAccess.get_file_as_bytes(folders.assets.path_join("fonts/NotoSansCJK-Regular.ttc"))
    loading_label.add_theme_font_override("font",loading_font)
    loading_label.text="게임을 준비하고 있습니다…"
    loading_label.add_theme_font_size_override("font_size",24)
    loading_layer.add_child(loading_label)
    # Draw the loader before scene instantiation or its rules constructor.
    await get_tree().process_frame
    await get_tree().process_frame
    var request=ResourceLoader.load_threaded_request("res://main.tscn")
    if request!=OK:stop("게임 화면을 읽지 못했습니다. 오류 "+str(request));return
    while ResourceLoader.load_threaded_get_status("res://main.tscn")==ResourceLoader.THREAD_LOAD_IN_PROGRESS:
        await get_tree().process_frame
    if ResourceLoader.load_threaded_get_status("res://main.tscn")!=ResourceLoader.THREAD_LOAD_LOADED:
        stop("게임 화면 파일이 손상되었습니다.");return
    game=ResourceLoader.load_threaded_get("res://main.tscn").instantiate()
    game.options=folders
    game.startup_finished.connect(finished)
    add_child(game)

func _process(_delta):
    if game==null or game.startup_job==null or loading_label==null:return
    var state=game.startup_job.status()
    var count="" if state.total<=0 else "  "+str(state.current)+" / "+str(state.total)
    var titles={"Startup log opened":"시작 준비","Checking game files":"게임 파일 확인","Preparing items and skills":"아이템·기술 준비","Reading maps":"지도 읽기","Preparing maps":"지도 준비","Preparing characters":"캐릭터 준비","Preparing graphics":"그래픽 준비","Preparing text":"글꼴 준비","Reading saved journey":"저장한 여정 확인","Checking original tile records":"원본 타일 확인"}
    var title=titles.get(state.phase,"그래픽 파일 확인" if str(state.phase).begins_with("Checking tile atlas") else state.phase)
    loading_label.text="게임을 준비하고 있습니다…  "+str(int(state.elapsed_ms/1000))+"초\n\n"+title+count

func finished(success: bool):
    if not success:return
    loading_layer.queue_free()
    loading_label=null
    await get_tree().process_frame
    if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
    var path=OS.get_environment("BARAM_READY_FILE")
    if path!="":
        var marker=FileAccess.open(path,FileAccess.WRITE)
        if marker!=null:marker.store_string("READY\n");marker.close()
    print("BARAM_GAME_READY")

func stop(message):
    push_error("WINDOWS_PACKAGE_BOOTSTRAP: "+message)
    if OS.get_name() == "Windows":
        OS.alert(message,"바람의나라 실행 오류")
    get_tree().quit(2)
