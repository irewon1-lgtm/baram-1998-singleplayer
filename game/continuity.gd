extends CanvasLayer
## One email/password login screen; Auth and transactional saves share Supabase.
const State = preload("res://continuity_state.gd")
var state=State.new()
var game
var config={}
var session={}
var panel: Panel
var message: Label
var email: LineEdit
var password: LineEdit
var badge: Label
var busy=false
var playing=false
var resolving=false
var autosave_clock=0.0
var legacy=""
var http: HTTPRequest
var session_path="user://continuity/session.json"

func initialize(g):
    game=g;legacy=g.save_path;layer=80
    http=HTTPRequest.new();http.timeout=15;http.body_size_limit=20000000;add_child(http)
    if FileAccess.file_exists("res://data/cloud_public.json"):
        var c=JSON.parse_string(FileAccess.get_file_as_string("res://data/cloud_public.json"))
        if typeof(c)==TYPE_DICTIONARY and str(c.get("url","")).begins_with("https://") and str(c.get("public_key","")).length()>20:config=c
    var device_path="user://continuity/device.json"
    if FileAccess.file_exists(device_path):
        var d=JSON.parse_string(FileAccess.get_file_as_string(device_path))
        if typeof(d)==TYPE_DICTIONARY:state.device=str(d.get("id",""))
    if state.device=="":state.device=State.uuid();state.atomic(device_path,JSON.stringify({"id":state.device}))
    badge=Label.new();badge.position=Vector2(635,5);badge.size=Vector2(310,32)
    badge.add_theme_font_override("font",game.font);badge.add_theme_font_size_override("font_size",14);add_child(badge)
    var open=Button.new();open.text="계정 이어하기";open.position=Vector2(790,550);open.size=Vector2(160,44)
    open.add_theme_font_override("font",game.font);open.pressed.connect(show_login);add_child(open)
    var exit=Button.new();exit.text="저장하고 나가기";exit.position=Vector2(790,598);exit.size=Vector2(160,36)
    exit.add_theme_font_override("font",game.font);exit.pressed.connect(save_and_exit);add_child(exit)
    if game.mobile:
        open.hide();exit.hide();badge.hide()
    make_login()
    get_tree().auto_accept_quit=false
    if not config.is_empty():
        show_login()
        if FileAccess.file_exists(session_path):
            var s=JSON.parse_string(FileAccess.get_file_as_string(session_path))
            if typeof(s)==TYPE_DICTIONARY:
                session=s
                await resume_login()
    else:badge.text="이 기기에 저장 · 계정 연결 대기"

func make_login():
    panel=Panel.new();panel.position=Vector2(175,105);panel.size=Vector2(610,400);add_child(panel)
    message=Label.new();message.position=Vector2(25,20);message.size=Vector2(560,105);message.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    message.add_theme_font_override("font",game.font);message.add_theme_font_size_override("font_size",18);panel.add_child(message)
    email=LineEdit.new();email.placeholder_text="이메일";email.position=Vector2(65,130);email.size=Vector2(480,46);panel.add_child(email)
    password=LineEdit.new();password.placeholder_text="비밀번호 (10자 이상)";password.secret=true;password.position=Vector2(65,185);password.size=Vector2(480,46);panel.add_child(password)
    var login=Button.new();login.text="로그인 · 이어하기";login.position=Vector2(65,245);login.size=Vector2(480,46);login.add_theme_font_override("font",game.font);login.pressed.connect(login_pressed);panel.add_child(login)
    var offline=Button.new();offline.text="이 기기 저장으로 계속";offline.position=Vector2(65,305);offline.size=Vector2(340,46);offline.add_theme_font_override("font",game.font);offline.pressed.connect(offline_pressed);panel.add_child(offline)
    var close=Button.new();close.text="닫기";close.position=Vector2(425,305);close.size=Vector2(120,46);close.add_theme_font_override("font",game.font)
    close.pressed.connect(func():
        if not busy and (config.is_empty() or playing):panel.hide();game.continuity_blocked=false)
    panel.add_child(close);panel.hide()

func show_login():
    if busy:return
    game.clear_inputs()
    panel.show();game.continuity_blocked=true
    message.text="같은 이메일과 비밀번호로 PC·폰·태블릿을 이어합니다.\n처음 로그인하면 계정이 만들어집니다. 캐릭터는 하나만 사용합니다."
    if config.is_empty():message.text="계정 저장 서비스 연결 대기입니다. 현재 기기 저장과 기존 파일은 그대로 사용할 수 있습니다."

func report(code: String):
    badge.text={"OK":"서버 저장 확인 완료","NETWORK":"동기화 대기 · 이 기기에 보존","BUSY":"다른 기기에서 동기화 후 종료하세요","UPDATE_REQUIRED":"게임 업데이트 필요 · 저장 보존","CONFLICT_PRESERVED":"저장 충돌 · 양쪽 사본 보존","AUTH":"로그인이 필요합니다"}.get(code,code)
    message.text=badge.text

func request(endpoint: String, body: Dictionary, authorized=true) -> Dictionary:
    var headers=PackedStringArray(["Content-Type: application/json","apikey: "+str(config.public_key)])
    if authorized:
        if session.get("access_token","")=="":return {"status":"AUTH"}
        headers.append("Authorization: Bearer "+str(session.access_token))
    var error=http.request(str(config.url)+endpoint,headers,HTTPClient.METHOD_POST,JSON.stringify(body))
    if error!=OK:return {"status":"NETWORK"}
    var r=await http.request_completed
    if r[0]!=HTTPRequest.RESULT_SUCCESS:return {"status":"NETWORK"}
    var doc=JSON.parse_string(r[3].get_string_from_utf8())
    if int(r[1])>=200 and int(r[1])<300 and typeof(doc)==TYPE_DICTIONARY:return doc
    return {"status":"AUTH" if int(r[1]) in [400,401,403,422,429] else "NETWORK","http":int(r[1])}

func remember() -> bool:
    # These are the player's runtime tokens in OS-private app data, never app
    # credentials in a package/repository. Passwords are never persisted/logged.
    if not state.atomic(session_path,JSON.stringify(session)):return false
    if OS.get_name()!="Windows":FileAccess.set_unix_permissions(session_path,FileAccess.UNIX_READ_OWNER|FileAccess.UNIX_WRITE_OWNER)
    return true

func refresh() -> bool:
    if session.get("refresh_token","")=="":return false
    var r=await request("/auth/v1/token?grant_type=refresh_token",{"refresh_token":session.refresh_token},false)
    if not r.has("access_token"):return false
    session=r
    return remember()

func save_rpc(name: String, body: Dictionary) -> Dictionary:
    var r=await request("/rest/v1/rpc/"+name,body)
    if r.get("status")=="AUTH" and await refresh():r=await request("/rest/v1/rpc/"+name,body)
    return r

func login_pressed():
    if busy or config.is_empty():return
    if playing:message.text="현재 계정의 저장하고 나가기를 먼저 완료하세요.";return
    busy=true
    var body={"email":email.text.strip_edges().to_lower(),"password":password.text}
    if body.email=="" or body.password.length()<10:message.text="이메일과 10자 이상 비밀번호를 입력하세요.";busy=false;return
    var r=await request("/auth/v1/token?grant_type=password",body,false)
    if not r.has("access_token") and r.get("http")==400:
        r=await request("/auth/v1/signup",body,false)
    body.password="";password.text=""
    if not r.has("access_token"):report("AUTH");message.text="로그인하지 못했습니다. 이메일·비밀번호와 네트워크를 확인하세요.";busy=false;return
    session=r
    if not remember():report("LOCAL_SESSION_FAILED");busy=false;return
    busy=false
    await open_account()

func resume_login():
    busy=true
    var refreshed=await refresh()
    busy=false
    if refreshed:await open_account()
    else:report("NETWORK")

func open_account():
    if busy:return
    busy=true;game.continuity_blocked=true
    var id=str(session.get("user",{}).get("id",""))
    if not state.select_account(id,"schema2:"+game.content.version,state.device):report(state.error);busy=false;return
    var r=await save_rpc("baram_open",{"p_device":state.device,"p_compatibility":state.compatibility})
    if not state.accept_open(r,legacy):report(state.error);busy=false;return
    game.save_path=state.path
    var saved=game.store.read_state(state.path)
    if not saved.is_empty():
        if is_instance_valid(game.creation_controls):game.creation_controls.queue_free()
        game.restore(saved);game.save_loaded=true
    elif game.store.last_status=="MISSING":
        game.player={};game.menu="creation"
        if not is_instance_valid(game.creation_controls):game.setup_creation()
    else:report(game.store.last_status);busy=false;return
    playing=true;game.continuity_blocked=false;panel.hide();report("OK");busy=false

func offline_pressed():
    if busy:return
    if config.is_empty():panel.hide();game.continuity_blocked=false;return
    if state.meta.get("conflict",false):report("CONFLICT_PRESERVED");return
    # Never start an unleased/stale second device while the server is offline.
    if playing:panel.hide();game.continuity_blocked=false;return
    var id=str(session.get("user",{}).get("id",""))
    if not state.select_account(id,"schema2:"+game.content.version,state.device) or not state.meta.get("leased",false) or state.meta.get("conflict",false):report("BUSY");return
    var saved=game.store.read_state(state.path)
    if saved.is_empty():report("NO_LOCAL_SAVE");return
    if is_instance_valid(game.creation_controls):game.creation_controls.queue_free()
    game.save_path=state.path;game.restore(saved);playing=true;panel.hide();game.continuity_blocked=false;report("NETWORK")

func before_local_save() -> bool:
    if not playing:return true
    if not state.mark_dirty():report(state.error);return false
    badge.text="이 기기에 저장 · 서버 전송 전"
    return true

func save_and_exit():
    if busy:return
    busy=true;game.continuity_blocked=true
    if not playing and not config.is_empty():get_tree().quit();return
    # Resolve attacks before snapshotting; no new gameplay input while exiting.
    var limit=Time.get_ticks_msec()+2000
    while (game.attack_elapsed>=0 or game.cast_elapsed>=0) and Time.get_ticks_msec()<limit:
        resolving=true
        await get_tree().create_timer(.05).timeout
        resolving=false
    if not game.player.is_empty() and not game.save_game():report("LOCAL_SAVE_FAILED");busy=false;return
    if not playing:get_tree().quit();return
    var r={}
    if game.player.is_empty():
        r=await save_rpc("baram_release_empty",{"p_device":state.device,"p_compatibility":state.compatibility})
        if r.get("status")=="OK":state.meta.leased=false;state.persist();get_tree().quit();return
    else:
        var body=state.upload_request()
        if not body.is_empty():r=await save_rpc("baram_push",body)
        if not body.is_empty() and state.accept_upload(r):get_tree().quit();return
    panel.show();report(state.error if not state.error in ["OK",""] else str(r.get("status","NETWORK")))
    message.text+="\n이 기기 저장은 보존했습니다. 저장하고 나가기로 다시 전송하거나 기기에 보존하고 종료할 수 있습니다."
    var leave=Button.new();leave.text="기기에 보존하고 종료";leave.position=Vector2(65,355);leave.size=Vector2(480,40);leave.add_theme_font_override("font",game.font);leave.pressed.connect(func():get_tree().quit());panel.add_child(leave)
    busy=false

func _process(delta):
    if game==null or not game.startup_ready or busy or game.continuity_blocked:return
    autosave_clock+=delta
    if autosave_clock>=30 and not game.player.is_empty() and game.attack_elapsed<0 and game.cast_elapsed<0:
        autosave_clock=0;game.save_game()

func _notification(what):
    if game==null or not game.startup_ready:return
    # Mobile Back is owned by main.gd (dismiss modal or open pause).
    # Notifications reach every node; saving/exiting here would also terminate
    # the app after main has correctly dismissed the inventory.
    if what==NOTIFICATION_WM_CLOSE_REQUEST:save_and_exit()
    elif what==NOTIFICATION_WM_GO_BACK_REQUEST and not game.mobile:save_and_exit()
    elif what==NOTIFICATION_APPLICATION_PAUSED or what==NOTIFICATION_APPLICATION_FOCUS_OUT:
        if not game.player.is_empty() and not game.continuity_blocked:game.save_game()
