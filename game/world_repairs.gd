extends RefCounted
## Display names and scoped ecology repairs. Source names/IDs remain intact.
const VERSION="ui-hunt-1"
const RABBIT="kr.monster.5ebc87d48996"
const SQUIRREL="kr.monster.bc85d3766325"
const BEGINNER=["field","kr.map.1f61da6322b5","kr.map.785a69f25595","wk.map.region.squirrel"]
const NAMES={
 "town-room-5":"귀여운 재봉집", "town-room-6":"울음 재봉집", "town-room-7":"붉은 모자 전언소",
 "town-room-8":"황혼 주술사의 집", "town-room-9":"새벽 주술사의 집", "town-room-10":"연꽃 예배당",
 "town-room-19":"노을 직조소", "town-room-20":"돌장이의 집", "town-room-28":"백일 상점",
 "town-room-29":"백이 상점", "town-room-30":"백 상점", "town-room-31":"탑 수련장",
 "town-room-36":"강철심장의 집", "town-room-37":"대나무 주막", "town-room-38":"생강 주막",
 "town-room-43":"순이 푸줏간", "town-room-50":"고양이 쉼터", "town-room-70":"여우 갈림길",
 "town-room-80":"고요한 골짜기", "town-room-90":"거미줄 숲", "town-room-121":"점액 들판",
 "town-room-1011":"국내성 모임터", "town-room-3400":"연못 도서관", "wk.map.region.mantis":"사마귀 사냥터",
 "wk.map.facility.4f3fb0743a80":"미확인 시설", "field":"신수 들판", "rabbit_depth":"토끼굴 깊은 길 · 상급"
}

static func open_cell(m: Dictionary, at: Vector2i) -> bool:
    return at.x>=0 and at.y>=0 and at.x<int(m.width) and at.y<int(m.height) and not m.blocked[at.y][at.x]

static func cells_near(m: Dictionary, center: Vector2i, used: Dictionary, minimum: int=2, maximum: int=18) -> Array:
    var cells=[];var seen={center:true};var queue=[center];var i=0
    while i<queue.size() and i<8192:
        var p:Vector2i=queue[i];i+=1
        var distance=absi(p.x-center.x)+absi(p.y-center.y)
        if distance>=minimum and distance<=maximum and open_cell(m,p) and not used.has(p):cells.append(p)
        if distance>=maximum:continue
        for d in [Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]:
            var q=p+d
            if not seen.has(q) and open_cell(m,q) and not used.has(q):seen[q]=true;queue.append(q)
    return cells

static func apply(world: Dictionary) -> Dictionary:
    if world.get("repair_version","")==VERSION:return world
    var maps={};var unknown=RegEx.new();unknown.compile("[A-Za-z?]")
    var names={}
    for m in world.maps:
        maps[m.id]=m
        var original=str(m.get("name",""));var title=str(NAMES.get(m.id,original))
        for suffix in [" · 北米地形", " · 북미지형 대체"," · 북미 지형 대체"," · 원본 지형"," · 원본 실내"]:title=title.replace(suffix,"")
        var provisional=NAMES.has(m.id) and m.id!="field" and m.id!="rabbit_depth"
        if title.strip_edges()=="" or unknown.search(title)!=null:
            title="미확인 지역 "+str(absi(str(m.id).hash())%100000);provisional=true
        m.display_name_ko=title+(" (임시)" if provisional else "")
        m.display_name_status="PROVISIONAL_TRANSLATION" if provisional else "EXISTING_KOREAN_LABEL"
        names[original]=m.display_name_ko
    for m in world.maps:
        for p in m.portals:
            if not p.has("source_label"):p.source_label=p.get("label","")
            var target=world.get("map_aliases",{}).get(p.target,p.target)
            p.label=maps[target].display_name_ko if maps.has(target) else "연결 확인 중"
        for n in m.npcs:
            for node in n.get("dialogue",[]):
                if typeof(node)!=TYPE_DICTIONARY:continue
                if node.has("text"):
                    for old in names:
                        if unknown.search(old)!=null:node.text=node.text.replace(old,names[old])
    # Keep all authored variant IDs and stats. Only their beginner placement moves.
    var veteran=maps.get("rabbit_depth",{});var moved=[]
    var veteran_used={}
    if not veteran.is_empty():
        for s in veteran.spawns:veteran_used[Vector2i(s.x,s.y)]=true
        for p in veteran.portals:veteran_used[Vector2i(p.x,p.y)]=true
    var veteran_cells=cells_near(veteran,Vector2i(veteran.entry[0],veteran.entry[1]),veteran_used,6,40) if not veteran.is_empty() else []
    for id in BEGINNER:
        if not maps.has(id):continue
        var m=maps[id];var keep=[]
        for s in m.spawns:
            if s.kind in ["rabbit","squirrel",RABBIT,SQUIRREL]:keep.append(s)
            elif not veteran_cells.is_empty():
                var p:Vector2i=veteran_cells.pop_front();s.x=p.x;s.y=p.y
                veteran.spawns.append(s);moved.append({"spawn":s.id,"from":id,"to":veteran.id})
            else:keep.append(s) # never delete unplaceable content
        m.spawns=keep
        var used={}
        for n in m.npcs:used[Vector2i(n.x,n.y)]=true
        for p in m.portals:used[Vector2i(p.x,p.y)]=true
        for s in m.spawns:used[Vector2i(s.x,s.y)]=true
        var points=cells_near(m,Vector2i(m.entry[0],m.entry[1]),used,3,12)
        for kind in [RABBIT,SQUIRREL]:
            var count=m.spawns.filter(func(s):return s.kind==kind or s.kind==("rabbit" if kind==RABBIT else "squirrel")).size()
            for index in range(maxi(0,4-count)):
                if points.is_empty():break
                var p:Vector2i=points.pop_front()
                m.spawns.append({"id":"repair.spawn."+id+"."+kind+"."+str(index),"kind":kind,"x":p.x,"y":p.y,"placement_basis":"SCOPED_BEGINNER_REPAIR"})
    # Authored, visible normal exit by the starting square; no guide teleport.
    if maps.has("village") and maps.has("field"):
        var town=maps.village;var field=maps.field
        var start=Vector2i(world.start.entry[0],world.start.entry[1]);var town_used={}
        for n in town.npcs:town_used[Vector2i(n.x,n.y)]=true
        for p in town.portals:town_used[Vector2i(p.x,p.y)]=true
        var doors=cells_near(town,start,town_used,4,8)
        if not doors.is_empty():
            var gate:Vector2i=doors[0]
            var field_used={}
            for n in field.npcs:field_used[Vector2i(n.x,n.y)]=true
            for p in field.portals:field_used[Vector2i(p.x,p.y)]=true
            for s in field.spawns:field_used[Vector2i(s.x,s.y)]=true
            var entries=cells_near(field,Vector2i(field.entry[0],field.entry[1]),field_used,0,6)
            if not entries.is_empty():
                var back:Vector2i=entries[0]
                town.portals.append({"id":"repair.portal.town.field","x":gate.x,"y":gate.y,"target":"field","entry":[back.x,back.y],"trigger":"interact","label":field.display_name_ko,"source_kind":"AUTHORED_BEGINNER_CONNECTION"})
                field.portals.append({"id":"repair.portal.field.town","x":back.x,"y":back.y,"target":"village","entry":[start.x,start.y],"trigger":"interact","label":town.display_name_ko,"source_kind":"AUTHORED_BEGINNER_CONNECTION"})
                world.beginner_gate={"map":"village","x":gate.x,"y":gate.y,"label":field.display_name_ko}
    world.repair_version=VERSION;world.beginner_relocations=moved
    return world
