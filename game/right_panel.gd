extends Node2D
## One shared, persistent original-asset sidebar. All actions use the live player.
const TABS=["물품","기술","장비","능력치"]
const SLOT_NAMES={"weapon":"무기","body":"갑옷","head":"머리","shield":"방패","left_hand":"왼손","right_hand":"오른손","accessory":"장신구","neck":"목걸이","ring":"반지"}
var game
var tab=0
var selected=0
var scroll=0
var folded=false
var focused=false
var pointers={}
var targets=[]
var row_ids=[]
var preview
var preview_root
var preview_key=""
var preview_texture
var last_error=""
var missing_icons={}

func initialize(owner):
    game=owner;z_index=120
    preview_root=SubViewport.new();preview_root.size=Vector2i(128,150)
    preview_root.transparent_bg=true;preview_root.render_target_update_mode=SubViewport.UPDATE_DISABLED
    add_child(preview_root)
    preview=Node2D.new();preview_root.add_child(preview);preview.draw.connect(draw_preview)
    layout()

func bounds() -> Rect2:
    var size=game.get_viewport_rect().size
    var width=52.0 if folded else clampf(size.x*.315,284,344)
    return Rect2(Vector2(size.x-width,0),Vector2(width,size.y))

func status_rect() -> Rect2:
    var r=bounds();return Rect2(Vector2(r.position.x,r.end.y-188),Vector2(r.size.x,188))

func select_tab(index: int):
    tab=index;selected=0;scroll=0;folded=false;focused=true
    game.menu="";game.clear_inputs();game.event("sidebar_tab",{"tab":TABS[tab]});layout();queue_redraw()

func layout():
    targets=[];row_ids=[]
    if game==null or game.player.is_empty():return
    var r=bounds()
    if folded:
        for i in range(4):targets.append({"id":"tab:"+str(i),"rect":Rect2(r.position+Vector2(2,14+i*58),Vector2(48,54))})
        targets.append({"id":"fold","rect":Rect2(r.position+Vector2(2,260),Vector2(48,54))});return
    for i in range(4):targets.append({"id":"tab:"+str(i),"rect":Rect2(r.position+Vector2(10+(i%2)*(r.size.x-20)/2,12+int(i/2)*46),Vector2((r.size.x-20)/2,44))})
    targets.append({"id":"fold","rect":Rect2(Vector2(r.position.x-36,8),Vector2(36,46))})
    if tab==0:row_ids=game.player.inventory.keys().filter(func(k):return int(game.player.inventory[k])>0)
    elif tab==1:row_ids=game.player.skills.duplicate()
    elif tab==2:
        row_ids=["weapon","body","head","shield"]
        for slot in game.player.get("equipment_slots",{}):
            if slot not in row_ids:row_ids.append(slot)
    selected=clampi(selected,0,maxi(0,row_ids.size()-1))
    var y=214.0 if tab==2 else 112.0
    var bottom=status_rect().position.y-100
    var count=maxi(1,int((bottom-y)/48))
    scroll=clampi(scroll,0,maxi(0,row_ids.size()-count))
    for i in range(scroll,mini(row_ids.size(),scroll+count)):
        targets.append({"id":"row:"+str(i),"rect":Rect2(Vector2(r.position.x+17,y+(i-scroll)*48),Vector2(r.size.x-34,47))})
    if row_ids.size()>count:
        targets.append({"id":"up","rect":Rect2(Vector2(r.position.x+12,bottom-2),Vector2(54,34))})
        targets.append({"id":"down","rect":Rect2(Vector2(r.position.x+70,bottom-2),Vector2(54,34))})
    var action_y=status_rect().position.y-50
    if tab in [0,1,2]:
        targets.append({"id":"primary","rect":Rect2(Vector2(r.position.x+16,action_y),Vector2((r.size.x-40)/2,42))})
        targets.append({"id":"secondary","rect":Rect2(Vector2(r.position.x+24+(r.size.x-40)/2,action_y),Vector2((r.size.x-40)/2,42))})
    targets.append({"id":"map","rect":Rect2(Vector2(r.position.x+12,r.end.y-37),Vector2(82,32))})
    targets.append({"id":"save","rect":Rect2(Vector2(r.position.x+100,r.end.y-37),Vector2(82,32))})
    targets.append({"id":"pause","rect":Rect2(Vector2(r.position.x+188,r.end.y-37),Vector2(r.size.x-200,32))})

func action(id: String):
    if id.begins_with("tab:"):select_tab(int(id.trim_prefix("tab:")));return
    focused=true
    if id=="fold":folded=not folded;game.clear_inputs()
    elif id.begins_with("row:"):selected=int(id.trim_prefix("row:"))
    elif id in ["up","down"]:scroll=clampi(scroll+(-1 if id=="up" else 1),0,maxi(0,row_ids.size()-1))
    elif id in ["primary","secondary"]:perform(id=="secondary")
    elif id=="map":game.menu="map";game.selected=0;game.choices=game.world.maps.map(func(m):return m.id);game.clear_inputs()
    elif id=="save":game.save_game()
    elif id=="pause":game.clear_inputs();game.menu="pause"
    layout();queue_redraw()

func perform(secondary: bool=false):
    if row_ids.is_empty():return
    var id=str(row_ids[selected]);var p=game.player
    if tab==0:
        var item=game.rules.item(id)
        if secondary or not game.rules.actions.is_gear(id):
            if item.get("teleport_safe_return",false):
                var result=game.rules.actions.use_return_item(p,id,game.world.home)
                if result.ok:game.transition(game.world.home.map,game.world.home.entry)
                game.notice("귀환했습니다." if result.ok else "사용 조건을 확인하세요.")
            else:
                var ok=game.rules.consume(p,id);game.notice("물품을 사용했습니다." if ok else "사용할 수 없는 물품입니다.")
        else:
            var ok=game.rules.equip(p,id);game.notice("장착했습니다." if ok else "레벨·직업·힘 등 착용 조건을 확인하세요.")
        game.event("sidebar_item",{"id":id,"secondary":secondary,"equipped":p.equipped})
    elif tab==1:
        if secondary:
            var slot=selected%3;p.hotbar[slot]=id;game.notice("단축키 "+str(slot+1)+"에 지정했습니다.")
        else:game.cast_known_skill(id)
    elif tab==2:
        if secondary:
            var instance=p.equipment_slots.get(id,"")
            if instance=="":game.notice("이 슬롯은 비어 있습니다.");return
            var gear=p.equipment_instances[instance]
            p.extensions["optional_enhancement"]=true;game.enhancement_instance=instance
            game.menu="enhancement";game.selected=0
            game.choices=game.content.by_kind("enhancement").filter(func(rule):return gear.definition_id in game.content.definition(rule).get("applicable_item_ids",[]))
            game.event("extension_opt_in",{"extension":"optional_enhancement","original_rule":false})
            if game.choices.is_empty():game.notice("이 장비에 전달된 강화 규칙이 없습니다.")
            return
        if not p.equipment_slots.has(id):game.notice("이 슬롯은 비어 있습니다.");return
        var result=game.rules.actions.unequip(p,id)
        game.notice("장비를 해제했습니다." if result.ok else "이 슬롯은 비어 있습니다.")
        game.event("sidebar_unequip",{"slot":id,"result":result})
    layout()

func _input(event):
    if game==null or not game.startup_ready or game.player.is_empty() or game.continuity_blocked:return
    var touch=event is InputEventScreenTouch
    var mouse=event is InputEventMouseButton
    if mouse and event.device==InputEvent.DEVICE_ID_EMULATION:return
    if touch or mouse:
        var at=event.position;var inside=bounds().has_point(at)
        for target in targets:
            if target.id=="fold" and target.rect.has_point(at):inside=true
        var index=event.index if touch else -100
        if mouse and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN] and inside:
            if event.pressed:scroll+=-1 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1;layout()
            get_viewport().set_input_as_handled();return
        if mouse and event.button_index!=MOUSE_BUTTON_LEFT:return
        if event.pressed and inside:
            var hit=""
            for target in targets:
                if target.rect.has_point(at):hit=target.id;break
            pointers[index]={"at":at,"hit":hit,"drag":false};game.clear_inputs();get_viewport().set_input_as_handled();return
        if not event.pressed and pointers.has(index):
            var pointer=pointers[index];pointers.erase(index)
            if not pointer.drag and not (touch and event.canceled):
                for target in targets:
                    if target.id==pointer.hit and target.rect.has_point(at):action(target.id);break
            get_viewport().set_input_as_handled();return
        if event.pressed and not inside:focused=false
    elif event is InputEventScreenDrag or event is InputEventMouseMotion:
        var index=event.index if event is InputEventScreenDrag else -100
        if pointers.has(index):
            var pointer=pointers[index];var dy=event.position.y-pointer.at.y
            if absf(dy)>=18:
                pointer.drag=true;scroll+=-1 if dy>0 else 1;pointer.at=event.position;layout()
            get_viewport().set_input_as_handled()
    elif event is InputEventKey and event.pressed and not event.echo and focused and game.menu=="":
        var key=event.keycode
        if key==KEY_ESCAPE:focused=false;get_viewport().set_input_as_handled();return
        if key in [KEY_UP,KEY_DOWN]:
            selected=clampi(selected+(-1 if key==KEY_UP else 1),0,maxi(0,row_ids.size()-1));scroll=maxi(0,selected-2);layout()
        elif key==KEY_N and tab==2:perform(true)
        elif key==KEY_E and tab==2:game.notice("물품에서 장비를 선택한 뒤 E로 장착합니다. X: 해제, N: 강화")
        elif key in [KEY_ENTER,KEY_E,KEY_U,KEY_X]:perform(key==KEY_U)
        elif tab==1 and key in [KEY_1,KEY_2,KEY_3] and not row_ids.is_empty():game.player.hotbar[key-KEY_1]=row_ids[selected]
        else:return
        get_viewport().set_input_as_handled()

func _process(_delta):
    if game==null:return
    layout();queue_redraw()

func text(value: String, at: Vector2, size: int=17, color=Color(.18,.095,.035), width: float=-1):
    draw_string(game.font,at,value,HORIZONTAL_ALIGNMENT_LEFT,width,size,color)

func draw_preview():
    if game==null or game.player.is_empty():return
    game.draw_player_on(preview,Vector2(64,128))

func update_preview():
    var key=JSON.stringify([game.player.job,game.player.get("equipment_slots",{}),game.player.get("equipped",""),game.player.get("armor_equipped","")])
    if key==preview_key:return
    preview_key=key;preview.queue_redraw();preview_root.render_target_update_mode=SubViewport.UPDATE_ONCE
    preview_texture=preview_root.get_texture()

func button(rect: Rect2, title: String, active: bool=false):
    game.box_on(self,rect,Color(.62,.43,.22) if active else Color(.37,.23,.11))
    draw_string(game.font,rect.position+Vector2(9,rect.size.y*.65),title,HORIZONTAL_ALIGNMENT_LEFT,rect.size.x-14,16,Color(.99,.92,.72))

func _draw():
    if game==null or game.player.is_empty():return
    var r=bounds();game.box_on(self,r,Color(.29,.16,.075))
    if folded:
        for target in targets:button(target.rect,TABS[int(target.id.trim_prefix("tab:"))] if target.id.begins_with("tab:") else "펼침",false)
        return
    var upper=Rect2(r.position+Vector2(7,102),Vector2(r.size.x-14,status_rect().position.y-105))
    var scroll_texture=game.work_assets.icon("wk.asset.kr491.sheet.spellinv",0)
    if scroll_texture!=null:draw_texture_rect(scroll_texture,upper,false)
    else:game.box_on(self,upper,Color(.70,.55,.32))
    for target in targets:
        var id=target.id;var rect:Rect2=target.rect
        if id.begins_with("tab:"):button(rect,TABS[int(id.trim_prefix("tab:"))],tab==int(id.trim_prefix("tab:")))
        elif id=="fold":button(rect,"접기")
        elif id in ["up","down"]:button(rect,"이전" if id=="up" else "다음")
        elif id=="primary":button(rect,["장착·사용","사용","해제",""][tab])
        elif id=="secondary":button(rect,["사용","단축키","강화",""][tab])

        elif id.begins_with("row:"):
            var index=int(id.trim_prefix("row:"));var value=str(row_ids[index])
            if index==selected:draw_rect(rect.grow(-1),Color(.38,.20,.07,.27))
            var title=game.rules.display_name(value)
            var suffix=""
            if tab==0:
                game.icon_on(self,value,rect.position+Vector2(19,23),32)
                var wearing=game.player.equipment_slots.values().any(func(gear_id):return game.player.equipment_instances.get(gear_id,{}).get("definition_id","")==value)
                suffix=" ×"+str(int(game.player.inventory[value]))+(" [착용]" if wearing else "")
                text(title,rect.position+Vector2(42,21),17,Color(.16,.07,.02),rect.size.x-46)
                text(suffix,rect.position+Vector2(42,41),13)
                continue
            elif tab==2:
                var gear=game.player.equipment_instances.get(game.player.equipment_slots.get(value,""),{})
                title=SLOT_NAMES.get(value,"장비")+": "+game.rules.display_name(gear.get("definition_id","")) if not gear.is_empty() else SLOT_NAMES.get(value,"장비")+": 비어 있음"
                if not gear.is_empty():game.icon_on(self,gear.definition_id,rect.position+Vector2(19,23),32)
                text(title,rect.position+Vector2(40,29),16,Color(.16,.07,.02),rect.size.x-44);continue
            text(title,rect.position+Vector2(8,22),17,Color(.16,.07,.02),rect.size.x-16)
            if tab==1:
                var skill=game.rules.skill(game.player,value)
                text("마력 "+str(int(game.rules.value_or(skill,"cast_mp",0)))+" · 대기 "+str(snappedf(float(game.player.cooldowns.get(value,0)),.1))+"초",rect.position+Vector2(8,41),12)
    if tab==2:
        update_preview()
        if preview_texture!=null:draw_texture_rect(preview_texture,Rect2(Vector2(r.position.x+r.size.x/2-48,109),Vector2(96,112)),false)
    elif tab==3:
        var p=game.player;var stats=game.rules.combat_stats(p)
        var lines=[p.name,p.job+" · 레벨 "+str(p.level),"체력 %d / %d"%[p.hp,p.hp_max],"마력 %d / %d"%[p.mp,p.mp_max],"경험치 "+str(float(p.xp2)/2),"금전 "+str(p.gold)+"전","공격 %d ~ %d"%[stats.minimum,stats.maximum],"방어 "+str(game.rules.armor(p)),"힘 "+str(p.strength),"사냥 "+str(p.kills)+"마리"]
        for i in range(lines.size()):text(lines[i],Vector2(r.position.x+30,139+i*26),17)
    elif row_ids.is_empty():text("배운 기술이 없습니다." if tab==1 else "보유 물품이 없습니다.",Vector2(r.position.x+28,155),17)
    if tab==0 and not row_ids.is_empty():
        var visual=game.content.definition(str(row_ids[selected])).get("visual",{})
        var identity=str(visual.get("identity",""))
        if "INFERRED" in identity or "REPLACEMENT" in identity or "UNVERIFIED" in identity:
            text("그림 연결: 추정 자료",Vector2(r.position.x+24,status_rect().position.y-86),12,Color(.49,.14,.05))
        var item=game.rules.item(str(row_ids[selected]));var y=status_rect().position.y-68
        text("공격 %d~%d · 방어 %d"%[int(game.rules.value_or(item,"damage_min",0)),int(game.rules.value_or(item,"damage_max",0)),int(game.rules.value_or(item,"armor_class",0))],Vector2(r.position.x+24,y),13)
    var status=status_rect();game.box_on(self,status,Color(.30,.17,.08))
    var p=game.player;var x=r.position.x+16;var y=status.position.y
    draw_string(game.font,Vector2(x,y+27),p.name+" · "+p.job,HORIZONTAL_ALIGNMENT_LEFT,r.size.x-26,18,Color(.99,.91,.71))
    draw_string(game.font,Vector2(x,y+50),"레벨 %d · 금전 %d전"%[p.level,p.gold],HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color(.99,.91,.71))
    for i in range(2):
        var current=int(p.hp if i==0 else p.mp);var maximum=int(p.hp_max if i==0 else p.mp_max)
        var bar=Rect2(Vector2(x,y+63+i*29),Vector2(r.size.x-32,24))
        draw_rect(bar,Color(.07,.035,.02));draw_rect(Rect2(bar.position,Vector2(bar.size.x*clampf(float(current)/maxi(1,maximum),0,1),24)),Color(.61,.12,.07) if i==0 else Color(.12,.28,.59))
        draw_string(game.font,bar.position+Vector2(8,18),("체력 " if i==0 else "마력 ")+str(current)+" / "+str(maximum),HORIZONTAL_ALIGNMENT_LEFT,-1,14,Color(1,.94,.78))
    draw_string(game.font,Vector2(x,y+139),"경험치 "+str(float(p.xp2)/2),HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color(1,.93,.74))
    for target in targets:
        if target.id in ["map","save","pause"]:button(target.rect,{"map":"지도","save":"저장","pause":"메뉴"}[target.id])
