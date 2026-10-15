extends Node2D
## Screen-space mobile HUD; pointer ownership lasts until release/cancellation.
var game
var pointers={}
var targets=[]
var unit=84.0
var safe=Rect2()
var joystick_id=-1
var joystick_origin=Vector2.ZERO
var joystick_tip=Vector2.ZERO
var last_menu=""
var scroll_origin=0
var toast=""
var toast_until=0.0
var hud_portrait
var portrait_key=""
var rows=[] # compatibility with old diagnostic introspection; no strip buttons
var buttons=[]

func initialize(g):
    game=g
    z_index=100
    get_tree().auto_accept_quit=false
    # Android's Back default is independent of desktop close requests.
    # main._notification owns modal dismissal / the pause menu.
    get_tree().quit_on_go_back=false
    layout()

func release_all():
    pointers.clear();joystick_id=-1
    if game!=null:game.direct_direction=-1

func layout():
    var size=get_viewport_rect().size
    var pixels=Vector2(DisplayServer.window_get_size())
    var ratio=size.x/maxf(1,pixels.x)
    unit=maxf(72,48.0*maxf(160,DisplayServer.screen_get_dpi())/160.0*ratio)
    # Device API safe area is in display pixels, then transformed to viewport.
    safe=Rect2(Vector2(16,12),size-Vector2(32,24))
    if OS.get_name()=="Android":
        var area=DisplayServer.get_display_safe_area()
        if area.size.x>0 and area.size.y>0:
            var trans=get_viewport().get_screen_transform().affine_inverse()
            var a=trans*Vector2(area.position);var b=trans*Vector2(area.end)
            safe=safe.intersection(Rect2(a,b-a)).grow(-8)
    targets=[]
    if game.menu!="" or game.continuity_blocked:return
    add_target("status",Rect2(safe.position,Vector2(260,maxf(unit,82))))
    add_target("menu",Rect2(Vector2(safe.end.x-unit,safe.position.y),Vector2.ONE*unit))
    add_target("bag",Rect2(Vector2(safe.end.x-unit*2-10,safe.position.y),Vector2.ONE*unit))
    var center=Vector2(safe.end.x-unit*.65,safe.end.y-unit*.65)
    add_target("attack",Rect2(center-Vector2.ONE*unit*.6,Vector2.ONE*unit*1.2))
    add_target("skill0",Rect2(center+Vector2(-unit*1.72,-unit*.42),Vector2.ONE*unit))
    add_target("skill1",Rect2(center+Vector2(-unit*1.65,-unit*1.65),Vector2.ONE*unit))
    add_target("skill2",Rect2(center+Vector2(-unit*.45,-unit*2.15),Vector2.ONE*unit))
    if not game.player.is_empty():
        var context=context_action()
        if context!="":add_target(context,Rect2(Vector2(safe.end.x-unit*3.25,safe.end.y-unit*1.1),Vector2.ONE*unit))

func add_target(id: String, rect: Rect2):targets.append({"id":id,"rect":rect})

func context_action() -> String:
    if game.maps[game.player.map].npcs.any(func(n):return Vector2i(n.x,n.y).distance_to(game.cell())<=1.5):return "talk"
    if game.loot.any(func(n):return n.map==game.player.map and Vector2i(n.x,n.y).distance_to(game.cell())<=1.1):return "loot"
    return ""

func key(code: int):
    var e=InputEventKey.new();e.keycode=code;e.pressed=true;game._input(e)
    if game.menu!="":game.clear_inputs()

func activate(id: String):
    match id:
        "status":game.clear_inputs();game.menu="status"
        "bag":game.open_inventory()
        "menu":key(KEY_ESCAPE)
        "attack":game.navigation.attack_selected()
        "skill0","skill1","skill2":
            var slot=int(id.right(1));game.navigation.cancel();game.cast_skill(slot)
            toast=game.rules.display_name(str(game.player.hotbar[slot]));toast_until=game.clock+1.5
        "talk":game.navigation.cancel();game.interact()
        "loot":game.navigation.cancel();game.pickup()
        "close":key(KEY_ESCAPE)
        "skills":game.menu="";key(KEY_K)
        "equipment":game.menu="";key(KEY_O)
        "map":game.world_map_view.open()
        "account":game.clear_inputs();game.continuity.show_login()
        "save":game.save_game()
        "exit":game.clear_inputs();game.continuity.save_and_exit()
        "resume":game.menu="";game.clear_inputs()
        _:
            if id.begins_with("row:"):game.selected=int(id.trim_prefix("row:"))
            elif id.begins_with("key:"):key(int(id.trim_prefix("key:")))
    queue_redraw()

func center_for(code: int) -> Vector2:
    var id={KEY_I:"bag",KEY_ESCAPE:"menu",KEY_SPACE:"attack",KEY_1:"skill0",KEY_2:"skill1",KEY_3:"skill2"}.get(code,"")
    for target in targets:
        if target.id==id:return target.rect.get_center()
    return Vector2(-1,-1)

func _input(event):
    if game==null or not game.startup_ready or game.menu=="creation" or game.continuity_blocked:return
    if game.menu=="world_map":return # Native map controls own their touches and drags.
    if event is InputEventScreenTouch:
        get_viewport().set_input_as_handled()
        if event.pressed:pointer_down(event.index,event.position)
        else:pointer_up(event.index,event.position,event.canceled)
    elif event is InputEventScreenDrag:
        get_viewport().set_input_as_handled();pointer_move(event.index,event.position)
    elif event is InputEventMouseButton:
        get_viewport().set_input_as_handled()
        if event.device==InputEvent.DEVICE_ID_EMULATION:return
        if event.button_index==MOUSE_BUTTON_LEFT:
            if event.pressed:pointer_down(-100,event.position)
            else:pointer_up(-100,event.position,false)
        elif game.menu!="" and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
            scroll_origin=clampi(scroll_origin+(-1 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1),0,maxi(0,game.choices.size()-visible_rows()))
    elif event is InputEventMouseMotion and pointers.has(-100):
        get_viewport().set_input_as_handled();pointer_move(-100,event.position)

func pointer_down(id: int, at: Vector2):
    var hit=""
    for target in targets:
        if target.rect.has_point(at):hit=target.id;break
    pointers[id]={"start":at,"at":at,"hit":hit,"menu":game.menu,"map":game.player.map,"camera":game.camera(),"drag":false}
    if hit=="attack":activate(hit)

func pointer_move(id: int, at: Vector2):
    if not pointers.has(id):return
    var p=pointers[id];p.at=at
    var threshold=maxf(10,unit*.14)
    if p.start.distance_to(at)>threshold:p.drag=true
    if p.menu!=game.menu:pointers.erase(id);return
    if game.menu!="":
        if p.drag:
            var offset=int((p.start.y-at.y)/maxf(unit*.65,52))
            if offset!=0:scroll_origin=clampi(scroll_origin+offset,0,maxi(0,game.choices.size()-visible_rows()));p.start=at
        return
    if p.hit!="":
        # Moving off a combat button immediately releases that pointer only.
        var inside=false
        for t in targets:
            if t.id==p.hit and t.rect.has_point(at):inside=true
        if not inside:pointers.erase(id)
        return
    if p.drag and joystick_id==-1 and p.start.x<get_viewport_rect().size.x*.43 and p.start.y>get_viewport_rect().size.y*.48:
        joystick_id=id;joystick_origin=p.start;game.navigation.cancel()
    if id==joystick_id:
        var diff=at-joystick_origin;joystick_tip=joystick_origin+diff.limit_length(unit*.7)
        game.direct_direction=game.Facing.toward(Vector2i(diff)) if diff.length()>threshold else -1

func pointer_up(id: int, at: Vector2, canceled: bool):
    if not pointers.has(id):return
    var p=pointers[id];pointers.erase(id)
    if id==joystick_id:joystick_id=-1;game.direct_direction=-1;return
    if canceled or p.menu!=game.menu or p.drag:return
    if p.hit!="":
        if p.hit=="attack":return
        for target in targets:
            if target.id==p.hit and target.rect.has_point(at):activate(p.hit);return
    elif game.menu=="" and p.map==game.player.map:game.navigation.tap(at+(p.camera-game.camera())*game.STEP)

func _process(_delta):
    if game==null:return
    if last_menu!=game.menu:
        release_all();scroll_origin=0;last_menu=game.menu
    layout()
    if game.continuity_blocked:release_all()
    elif game.menu=="":
        for p in pointers.values():
            if p.hit=="attack":game.navigation.attack_selected();break
    queue_redraw()

func panel(rect: Rect2, color=Color(.06,.08,.075,.87), radius=14):
    var style=StyleBoxFlat.new();style.bg_color=color;style.border_color=Color(.65,.56,.34,.75)
    style.set_border_width_all(1);style.set_corner_radius_all(radius);style.draw(get_canvas_item(),rect)

func text(value: String, at: Vector2, size=20, color=Color(.94,.9,.76), width=-1.0):
    draw_string(game.font,at,value,HORIZONTAL_ALIGNMENT_LEFT,width,size,color)

func glyph(id: String, at: Vector2, scale: float, color=Color(.94,.86,.63)):
    var w=scale*.22
    if id=="bag":
        draw_rect(Rect2(at-Vector2(w,w*.65),Vector2(w*2,w*1.6)),color,false,3)
        draw_arc(at-Vector2(0,w*.65),w*.6,PI,TAU,16,color,3)
    elif id in ["attack","equipment"]:
        draw_line(at+Vector2(-w,w),at+Vector2(w,-w),color,5)
        draw_line(at+Vector2(-w,w*.15),at+Vector2(-w*.15,w),color,4)
        draw_line(at+Vector2(w,-w),at+Vector2(w*.3,-w),color,3)
    elif id=="menu":
        for y in [-1,0,1]:draw_line(at+Vector2(-w,y*w*.7),at+Vector2(w,y*w*.7),color,3)
    elif id=="close":
        draw_line(at-Vector2.ONE*w,at+Vector2.ONE*w,color,3);draw_line(at+Vector2(-w,w),at+Vector2(w,-w),color,3)
    elif id.begins_with("skill"):
        var slot=int(id.right(1));var points=PackedVector2Array()
        for i in range(9):
            var angle=i*TAU/8-PI/2;points.append(at+Vector2(cos(angle),sin(angle))*w*(1 if i%2==0 else .4))
        draw_polyline(points,color,3)
        if slot==1:draw_arc(at,w*1.3,0,TAU,24,color,2)
        elif slot==2:draw_line(at-Vector2(w*1.35,0),at+Vector2(w*1.35,0),color,3)
    elif id=="talk":
        draw_rect(Rect2(at-Vector2(w,w*.7),Vector2(w*2,w*1.4)),color,false,2);draw_line(at+Vector2(-w*.5,w*.7),at+Vector2(-w*.8,w*1.1),color,3)
    elif id=="loot":
        draw_arc(at,w*.7,0,TAU,16,color,3);draw_line(at+Vector2(0,-w*1.4),at,color,3)

func _draw():
    if game==null or game.menu=="creation" or game.player.is_empty() or game.continuity_blocked:return
    if game.menu=="world_map":return
    if game.menu!="":draw_modal();return
    var p=game.player
    for target in targets:
        var id=target.id;var rect:Rect2=target.rect
        if id=="status":
            panel(rect);var a=rect.position
            draw_circle(a+Vector2(32,31),20,Color(.32,.33,.25,.9))
            update_portrait()
            if hud_portrait!=null:
                var size=Vector2(hud_portrait.get_size());size*=minf(38/size.x,44/size.y)
                draw_texture_rect(hud_portrait,Rect2(a+Vector2(32,31)-size/2,size),false)
            else:
                draw_circle(a+Vector2(32,25),7,Color(.8,.7,.48));draw_arc(a+Vector2(32,41),12,PI,TAU,12,Color(.8,.7,.48),4)
            text(p.name+"  Lv."+str(p.level),a+Vector2(61,25),18)
            for i in range(2):
                var r=Rect2(a+Vector2(62,38+i*18),Vector2(180,11))
                draw_rect(r,Color(.02,.03,.04,.9))
                var value=float(p.hp)/maxf(1,p.hp_max) if i==0 else float(p.mp)/maxf(1,p.mp_max)
                draw_rect(Rect2(r.position,Vector2(r.size.x*value,r.size.y)),Color(.7,.23,.17) if i==0 else Color(.24,.46,.73))
            continue
        var shade=Color(.08,.10,.09,.74)
        var color=Color(.95,.86,.60)
        var cooldown=0.0;var unavailable=false
        if id.begins_with("skill"):
            var title=str(p.hotbar[int(id.right(1))]);cooldown=float(p.cooldowns.get(title,0))
            unavailable=title=="" or cooldown>0 or game.cast_elapsed>=0 or game.attack_elapsed>=0
            if title!="":unavailable=unavailable or int(p.mp)<int(game.rules.value_or(game.rules.skill(p,title),"cast_mp",0))
            if unavailable:color=Color(.55,.57,.54,.7)
        draw_circle(rect.get_center(),rect.size.x*.47,shade)
        draw_arc(rect.get_center(),rect.size.x*.47,0,TAU,36,Color(.72,.61,.36,.8),2)
        glyph(id,rect.get_center(),rect.size.x,color)
        if cooldown>0:
            draw_circle(rect.get_center(),rect.size.x*.44,Color(0,0,0,.42));text(str(snappedf(cooldown,.1)),rect.get_center()+Vector2(-15,7),20)
    var location=game.maps[p.map].name
    text(location,Vector2(get_viewport_rect().size.x*.5-game.font.get_string_size(location,HORIZONTAL_ALIGNMENT_LEFT,-1,19).x/2,safe.position.y+25),19)
    if game.selected_target!="" and game.entities.has(game.selected_target):
        var e=game.entities[game.selected_target]
        if e.alive and e.map==p.map:
            var at=game.screen_point(e.x,e.y)-Vector2(0,16)
            draw_arc(at,24,0,TAU,24,Color(1,.65,.22),2)
    if joystick_id>=0:
        draw_circle(joystick_origin,unit*.74,Color(.12,.16,.14,.36));draw_arc(joystick_origin,unit*.74,0,TAU,32,Color(.85,.8,.6,.5),2)
        draw_circle(joystick_tip,unit*.3,Color(.75,.71,.54,.65))
    if game.clock<toast_until:text(toast,Vector2(safe.end.x-unit*3.3,safe.end.y-unit*2.3),18)
    if not game.log_lines.is_empty():text(str(game.log_lines.back()),Vector2(safe.position.x+16,safe.end.y-unit*2.2),16,Color(.95,.91,.75,.9),get_viewport_rect().size.x*.52)

func modal_rect() -> Rect2:
    var size=get_viewport_rect().size
    return Rect2(Vector2(maxf(safe.position.x,(size.x-760)/2),safe.position.y+8),Vector2(minf(760,safe.size.x),safe.size.y-16))

func visible_rows() -> int:return maxi(2,int((modal_rect().size.y-210)/(maxf(52,unit*.65))))

func update_portrait():
    var p=game.player
    var gear=p.get("equipment_instances",{}).get(p.get("equipment_slots",{}).get("head",""),{})
    var key_value=p.job+":"+str(gear.get("definition_id",""))
    if portrait_key==key_value:return
    portrait_key=key_value;hud_portrait=null
    var classes=game.content.by_kind("class").filter(func(id):return game.content.definition(id).get("name","")==p.job)
    if classes.is_empty():return
    var head=game.content.definition(classes[0]).get("visual",{}).get("head_asset_id","")
    head=game.rules.runtime_definitions.get(gear.get("definition_id",""),{}).get("data",{}).get("visual",{}).get("equipment_asset_id",head)
    var frame=game.work_assets.frame_index(head,"walk_unarmed",2,100)
    if frame>=0:hud_portrait=game.work_assets.icon(head,frame)

func modal_button(id: String, title: String, rect: Rect2):
    add_target(id,rect);panel(rect,Color(.19,.22,.17,.95),9)
    text(title,rect.position+Vector2(14,rect.size.y*.5+7),18,Color(.96,.9,.72),rect.size.x-20)

func draw_modal():
    targets=[]
    draw_rect(get_viewport_rect(),Color(0,0,0,.46))
    var r=modal_rect();panel(r,Color(.07,.09,.08,.97))
    var headings={"status":"캐릭터 정보","inventory":"가방","pause":"메뉴","equipment":"장비","skills":"배운 기술","trainer":"기술 수련","shop":"물품 거래","dialogue":"대화","services":"NPC 서비스","travel":"길 안내","map":"지도","world_map":"지도","job_selection":"직업 선택","compass":"비영사천문","quests":"의뢰와 보상","advancement":"승급","recipe":"재료 제작","experience_exchange":"경험치 교환","enhancement":"장비 강화","save_error":"저장 오류 · 원본 보존"}
    text(headings.get(game.menu,game.menu),r.position+Vector2(25,40),25)
    var close=Rect2(Vector2(r.end.x-unit-8,r.position.y+4),Vector2.ONE*unit)
    add_target("close",close);glyph("close",close.get_center(),unit)
    if not game.log_lines.is_empty():text(str(game.log_lines.back()),r.position+Vector2(28,73),16,Color(.85,.8,.64),r.size.x-56)
    if game.menu=="status":
        var p=game.player;var y=r.position.y+102
        for line in [p.name+" · "+p.job+" · 레벨 "+str(p.level),"체력  %d / %d     마력  %d / %d"%[p.hp,p.hp_max,p.mp,p.mp_max],"경험치  %s     금전  %d전"%[str(float(p.xp2)/2),p.gold],"힘  %d     사냥  %d"%[p.strength,p.kills],"무기  "+game.rules.display_name(p.equipped) if p.equipped!="" else "무기  맨손","옷  "+game.rules.display_name(p.get("armor_equipped",""))]:
            text(line,Vector2(r.position.x+28,y),21);y+=45
        modal_button("equipment","장비 보기",Rect2(Vector2(r.position.x+28,r.end.y-unit-20),Vector2(170,unit)))
        modal_button("skills","기술 보기",Rect2(Vector2(r.position.x+210,r.end.y-unit-20),Vector2(170,unit)))
        return
    if game.menu=="pause":
        var entries=[["resume","계속하기"],["map","지도"],["skills","기술"],["equipment","장비"],["save","저장"],["account","계정 이어하기"],["exit","저장하고 나가기"]]
        var button_width=(r.size.x-68)/2
        var button_height=minf(unit,maxf(48,(r.size.y-180)/4-10))
        for i in range(entries.size()):
            modal_button(entries[i][0],entries[i][1],Rect2(r.position+Vector2(28+(i%2)*(button_width+12),96+int(i/2)*(button_height+10)),Vector2(button_width,button_height)))
        text("버전  "+game.store.game_build.left(12),Vector2(r.position.x+28,r.end.y-48),16)
        if game.continuity!=null:text(game.continuity.badge.text,Vector2(r.position.x+28,r.end.y-22),16)
        return
    if game.menu=="dialogue":
        var paragraphs=PackedStringArray()
        for line in game.choices.slice(scroll_origin):paragraphs.append(str(line))
        draw_multiline_string(game.font,r.position+Vector2(28,120),"\n\n".join(paragraphs),HORIZONTAL_ALIGNMENT_LEFT,r.size.x-56,21,maxi(1,int((r.size.y-150)/28)),Color(.94,.9,.76))
        return
    var row_h=maxf(52,unit*.65);var count=visible_rows()
    for i in range(scroll_origin,mini(game.choices.size(),scroll_origin+count)):
        var choice=game.choices[i];var id=str(choice);var title=game.rules.display_name(id)
        if game.menu=="services":title=choice.get("name",choice.get("type","서비스"))
        elif game.menu=="equipment":title=game.rules.display_name(game.player.equipment_instances[id].definition_id)+" +"+str(int(game.player.equipment_instances[id].enhancement_level))
        elif game.menu=="travel":title=game.maps[game.world.get("map_aliases",{}).get(id,id)].name
        if game.menu=="inventory":title+="  ×"+str(game.player.inventory.get(id,0))
        elif game.menu=="quests":title+=" · "+{"ACTIVE":"진행 중","CLAIMED":"보상 받음"}.get(game.player.quest_progress.get(id,{}).get("state",""),"접수 가능")
        elif game.menu=="shop":
            var price=int(game.rules.value_or(game.rules.item(id),"vendor_buy_price",5))
            for offer in game.npc.get("work_offers",[]):
                if offer.get("item_id","")==id:price=int(offer.get("price_gold",offer.get("buy_price",offer.get("price",price))))
            title+=" · %d전 · 보유 %d"%[price,int(game.player.inventory.get(id,0))]
        var row=Rect2(r.position+Vector2(22,92+(i-scroll_origin)*row_h),Vector2(r.size.x-44,row_h-3))
        add_target("row:"+str(i),row)
        if game.selected==i:panel(row,Color(.28,.27,.15,.95),6)
        text(title,row.position+Vector2(16,row_h*.5+7),20,Color(.94,.9,.76),row.size.x-32)
    var commands=[]
    match game.menu:
        "inventory":commands=[[KEY_ENTER,"장착"],[KEY_U,"사용"]]
        "equipment":commands=[[KEY_ENTER,"장착"],[KEY_X,"해제"],[KEY_N,"강화"]]
        "shop":commands=[[KEY_ENTER,"구매"],[KEY_V,"판매"],[KEY_R,"수리"],[KEY_C,"요리"],[KEY_H,"휴식"]]
        "skills","trainer":commands=[[KEY_1,"슬롯 1"],[KEY_2,"슬롯 2"],[KEY_3,"슬롯 3"]]
        "dialogue","map":pass
        _:commands=[[KEY_ENTER,"확인"]]
    if game.menu=="trainer":commands.append([KEY_ENTER,"습득"])
    var width=(r.size.x-44)/maxi(1,commands.size())
    for i in range(commands.size()):modal_button("key:"+str(commands[i][0]),commands[i][1],Rect2(Vector2(r.position.x+22+i*width,r.end.y-unit-18),Vector2(width-6,unit)))
    var detail=""
    if game.choices.is_empty():text("표시할 항목이 없습니다.",r.position+Vector2(35,130),20)
    elif game.menu=="inventory":
        var it=game.rules.item(str(game.choices[game.selected]))
        detail="공격 %d~%d · 방어 %d · 필요 힘 %d"%[int(game.rules.value_or(it,"damage_min",0)),int(game.rules.value_or(it,"damage_max",0)),int(game.rules.value_or(it,"armor_class",0)),int(game.rules.value_or(it,"strength_required",0))]
    elif game.menu in ["skills","trainer"]:
        var id=str(game.choices[game.selected]);var s=game.rules.skill(game.player,id)
        detail="%s · 마력 %d"%[game.rules.display_name(id),int(game.rules.value_or(s,"cast_mp",0))]
        if game.menu=="trainer":detail+=" · Lv.%d · %s전"%[int(game.rules.value_or(s,"learn_level",0)),str(s.get("learn_money","미확정"))]
    elif game.menu=="services" and not game.npc.get("dialogue",[]).is_empty():detail=game.npc.dialogue[0].get("text","")
    if detail!="":text(detail,Vector2(r.position.x+28,r.end.y-unit-34),17,Color(.94,.9,.76),r.size.x-56)
    if game.choices.size()>count:text("↕",Vector2(r.end.x-25,r.end.y-unit-34),18)

func _notification(what):
    if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:release_all()
