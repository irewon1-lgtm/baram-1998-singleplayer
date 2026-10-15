extends CanvasLayer
## Thirteen large multitouch targets; contextual commands reuse keyboard input.
## The 960x640 PC game view is preserved above the Android control strip.
var game
var held={}
var buttons=[]
var rows=[]
var last_menu=""

func key(code: int):
    if game.continuity_blocked or not game.startup_ready:return
    if code==0:
        if game.continuity!=null:game.continuity.save_and_exit()
        return
    if code==KEY_O and game.menu=="inventory":key(KEY_ESCAPE)
    var e=InputEventKey.new();e.keycode=code;e.pressed=true;game._input(e)

func center_for(code: int) -> Vector2:
    for row in rows:
        if row.key==code and row.button.visible:return row.button.position+Vector2(64,64)
    return Vector2(-1,-1)

func initialize(g):
    game=g;layer=30
    get_viewport().content_scale_size=Vector2i(960,1060)
    var specs=[
        ["↑",KEY_UP,Vector2(140,660)],["←",KEY_LEFT,Vector2(4,796)],
        ["↓",KEY_DOWN,Vector2(140,796)],["→",KEY_RIGHT,Vector2(276,796)],
        ["기술1",KEY_1,Vector2(420,650)],["기술2",KEY_2,Vector2(556,650)],["기술3",KEY_3,Vector2(692,650)],
        ["공격",KEY_SPACE,Vector2(420,786)],["대화",KEY_ENTER,Vector2(556,786)],["줍기",KEY_G,Vector2(692,786)],
        ["가방",KEY_I,Vector2(420,922)],["기술",KEY_K,Vector2(556,922)],["메뉴",KEY_ESCAPE,Vector2(692,922)]
    ]
    for spec in specs:
        var control=TouchScreenButton.new();control.position=spec[2]
        var shape=RectangleShape2D.new();shape.size=Vector2(128,128);control.shape=shape;control.shape_centered=true
        var image=Image.create(128,128,false,Image.FORMAT_RGBA8);image.fill(Color(.16,.19,.16,.96))
        control.texture_normal=ImageTexture.create_from_image(image)
        image=Image.create(128,128,false,Image.FORMAT_RGBA8);image.fill(Color(.32,.36,.22,.96))
        control.texture_pressed=ImageTexture.create_from_image(image)
        var label=Label.new();label.text=spec[0];label.position=Vector2(4,42);label.size=Vector2(120,44);label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
        label.add_theme_font_override("font",game.font);label.add_theme_font_size_override("font_size",26);control.add_child(label)
        var row={"button":control,"label":label,"key":spec[1],"default":spec[0],"default_key":spec[1]}
        control.pressed.connect(func():held[row.key]=true;key(row.key))
        control.released.connect(func():held.erase(row.key))
        add_child(control);buttons.append(control);rows.append(row)
    update_menu()

func update_menu():
    var commands=[]
    match game.menu:
        "creation":commands=[["전사",KEY_1],["도적",KEY_2],["주술사",KEY_3],["도사",KEY_4],["시작",KEY_ENTER]]
        "pause":commands=[["계속",KEY_ENTER],["저장종료",0]]
        "shop":commands=[["구매",KEY_ENTER],["판매",KEY_V],["수리",KEY_R],["요리",KEY_C],["휴식",KEY_H],["닫기",KEY_ESCAPE]]
        "inventory":commands=[["장착",KEY_ENTER],["사용",KEY_U],["장비",KEY_O],["닫기",KEY_ESCAPE]]
        "equipment":commands=[["장착",KEY_ENTER],["해제",KEY_X],["강화",KEY_N],["닫기",KEY_ESCAPE]]
        "skills","trainer":commands=[["기술1",KEY_1],["기술2",KEY_2],["기술3",KEY_3],["확인",KEY_ENTER],["닫기",KEY_ESCAPE]]
        "":pass
        _:commands=[["확인",KEY_ENTER],["닫기",KEY_ESCAPE]]
    for i in range(4,rows.size()):
        var row=rows[i];var n=i-4
        row.button.visible=game.menu=="" or n<commands.size()
        row.key=row.default_key if game.menu=="" else commands[n][1] if n<commands.size() else -1
        row.label.text=row.default if game.menu=="" else commands[n][0] if n<commands.size() else ""
    last_menu=game.menu
    held.clear()

func _process(_delta):
    if game==null:return
    if game.menu!=last_menu:update_menu()
    if game.continuity_blocked or game.menu!="":held.clear();return
    for code in held:
        if code in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT]:game.move_player({KEY_UP:0,KEY_LEFT:1,KEY_DOWN:2,KEY_RIGHT:3}[code])
        elif code==KEY_SPACE:game.begin_attack()

func _notification(what):
    if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:held.clear()
