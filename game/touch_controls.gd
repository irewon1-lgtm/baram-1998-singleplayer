extends CanvasLayer
## TouchScreenButton supports simultaneous move + attack. All commands call
## existing keyboard handlers. PC layout and keyboard mappings stay intact.
var game
var held={}
var buttons=[]

func key(code: int):
    if game.continuity_blocked or not game.startup_ready:return
    var e=InputEventKey.new();e.keycode=code;e.pressed=true;game._input(e)

func initialize(g):
    game=g;layer=30
    if OS.get_name()!="Android" and not game.options.has("touch-test"):return
    # The existing 960x640 game is unchanged. Add a dedicated control strip.
    get_viewport().content_scale_size=Vector2i(960,860)
    var specs=[
        ["↑",KEY_UP,Vector2(85,650)],["←",KEY_LEFT,Vector2(15,720)],["↓",KEY_DOWN,Vector2(85,720)],["→",KEY_RIGHT,Vector2(155,720)],
        ["공격",KEY_SPACE,Vector2(825,650)],["대화·확인",KEY_ENTER,Vector2(720,720)],["줍기",KEY_G,Vector2(825,720)],
        ["기술1",KEY_1,Vector2(300,650)],["기술2",KEY_2,Vector2(405,650)],["기술3",KEY_3,Vector2(510,650)],
        ["가방",KEY_I,Vector2(300,720)],["기술목록",KEY_K,Vector2(405,720)],["닫기",KEY_ESCAPE,Vector2(510,720)],
        ["대상",KEY_TAB,Vector2(615,650)],["사용",KEY_U,Vector2(615,720)],["판매",KEY_V,Vector2(720,650)]
    ]
    for spec in specs:
        var control=TouchScreenButton.new();control.position=spec[2]
        var shape=RectangleShape2D.new();shape.size=Vector2(90,60);control.shape=shape;control.shape_centered=false
        var image=Image.create(90,60,false,Image.FORMAT_RGBA8);image.fill(Color(.16,.19,.16,.95))
        control.texture_normal=ImageTexture.create_from_image(image)
        control.pressed.connect(func():held[spec[1]]=true;key(spec[1]))
        control.released.connect(func():held.erase(spec[1]))
        add_child(control);buttons.append(control)
        var label=Label.new();label.text=spec[0];label.position=Vector2(3,12);label.size=Vector2(84,40);label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
        label.add_theme_font_override("font",game.font);label.add_theme_font_size_override("font_size",17);control.add_child(label)
    var exit=Button.new();exit.text="저장하고 나가기";exit.position=Vector2(695,795);exit.size=Vector2(220,50);exit.add_theme_font_override("font",game.font)
    exit.pressed.connect(func():game.continuity.save_and_exit());add_child(exit)

func _process(_delta):
    if game==null or game.continuity_blocked or game.menu!="":held.clear();return
    for code in held:
        if code in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT]:game.move_player({KEY_UP:0,KEY_LEFT:1,KEY_DOWN:2,KEY_RIGHT:3}[code])
        elif code==KEY_SPACE:game.begin_attack()

func _notification(what):
    if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:held.clear()
