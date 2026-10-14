extends RefCounted
## Read only Codex-validated immutable releases. Never execute package code.
var records = {}
var id_map = {}
var assets = {}
var release_root = ""
var version = "legacy-base"
var last_error = {}

func load_directory(root: String) -> bool:
    var path=root.path_join("ACTIVE.json")
    if not FileAccess.file_exists(path):return true
    var pointer=JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(pointer)!=TYPE_DICTIONARY or pointer.get("version",0)!=1 or not str(pointer.get("release_id","")).is_valid_hex_number(false) or str(pointer.release_id).length()!=64:
        last_error={"code":"ACTIVE_FORMAT","file":path};return false
    release_root=root.path_join("releases").path_join(pointer.release_id)
    path=release_root.path_join("release.json")
    if not FileAccess.file_exists(path) or FileAccess.get_sha256(path)!=pointer.sha256:
        last_error={"code":"CONTENT_HASH","file":path};return false
    var parsed=JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(parsed)!=TYPE_DICTIONARY or parsed.get("format","")!="BARAM_RUNTIME_CONTENT" or int(parsed.get("version",0)) not in [1,2]:
        last_error={"code":"CONTENT_VERSION","file":path};return false
    records=parsed.records;id_map=parsed.id_map;assets=parsed.assets;version=pointer.release_id
    var checked={}
    for info in assets.values():
        if checked.has(info.stored_path):continue
        checked[info.stored_path]=true
        var target=release_root.path_join("files").path_join(info.stored_path)
        if not FileAccess.file_exists(target) or FileAccess.get_sha256(target)!=info.sha256:
            last_error={"code":"CONTENT_ASSET_HASH","file":target};return false
    return true

func definition(id: String) -> Dictionary:
    var record=records.get(id_map.get(id,id),{})
    return record.get("runtime_definition",record.get("data",{}).get("runtime_definition",record.get("data",{})))

func by_kind(kind: String) -> Array:
    return records.keys().filter(func(id):return records[id].kind==kind)

func class_title(id: String, rules) -> String:
    return definition(id).get("name",id if id in rules.JOBS else "")

func apply_rules(rules):
    rules.content_version=version
    for id in records:
        var record=records[id]
        var data=definition(id)
        rules.runtime_definitions[id]={"kind":record.kind,"data":data,"provenance_refs":record.get("runtime_provenance_refs",record.get("provenance_refs",[])),"source_mode":record.get("runtime_source_mode",record.get("source_mode","")),"source_commit":record.get("runtime_source_commit",record.get("source_commit",""))}
        var category="spell" if record.kind=="skill" else record.kind
        if category not in ["item","monster","spell","growth","advancement"]:continue
        var current=rules.by_id.get(id,{"id":id,"category":category,"name":data.get("name",id),"job":null,"level":null,"values":{}}).duplicate(true)
        if record.get("operation","")=="propose_patch" or not id.begins_with("wk."):
            # Numeric fields are patched only by the guarded importer; a
            # runtime_definition is separate from preserved source values.
            var raw=record.get("data",{})
            if raw.has("values"):current.values=raw.values.duplicate(true)
        current.name=data.get("name",current.name)
        var values=current.values
        if category=="item":
            if data.has("stats"):values.merge(data.stats,true)
            values["slot"]=data.get("slot",values.get("slot",""))
            values["stack_limit"]=data.get("stack_limit",values.get("stack_limit",99))
            var needs=data.get("requirements",{})
            values.level_required=needs.get("level_min",needs.get("level",values.get("level_required",0)))
            values.strength_required=needs.get("strength_min",needs.get("strength",values.get("strength_required",0)))
            values.advancement_rank_required=int(needs.get("advancement_rank",0))
            values.allowed_jobs=data.get("class_ids",needs.get("class_ids",[])).map(func(c):return class_title(c,rules))
            if data.has("prices"):
                values.vendor_buy_price=data.prices.get("buy",values.get("vendor_buy_price"))
                values.vendor_sell_price=data.prices.get("sell",values.get("vendor_sell_price"))
            values.instance_equipment=data.get("slot","none")!="none"
            values.flags=data.get("flags",{})
            for effect in data.get("use_effects",[]):
                if effect.get("op","")=="heal_hp":values.heal_amount=effect.get("amount",0)
                if effect.get("op","")=="restore_mp":values.restore_mp=effect.get("amount",0)
                if effect.get("op","")=="teleport_safe_return":values.teleport_safe_return=true
            var visual=data.get("visual",{})
            if visual.has("legacy_sprite"):rules.visual_bindings[id]={"slot":values.slot,"sprite":visual.legacy_sprite,"motion":visual.get("motion","sword")}
        elif category=="monster":
            for field in ["hp","mp","armor_class","experience","level","gold"]:
                if data.has(field):values[field]=data[field]
            var attack=data.get("attack",{})
            values.attack_min=attack.get("min",values.get("attack_min"))
            values.attack_max=attack.get("max",values.get("attack_max"))
            values.attack_interval_ms=attack.get("interval_ms",values.get("attack_interval_ms",1200))
            values.attack_range_tiles=attack.get("range_tiles",1);values.attack_kind=attack.get("kind","melee")
            var behavior=data.get("behavior",{})
            for field in ["move_interval_ms","attack_interval_ms","aggro_radius_tiles","leash_radius_tiles","hit_probability"]:
                if behavior.has(field):values[field]=behavior[field]
            values.respawn_interval_ms=data.get("spawn_rules",{}).get("respawn_ms",values.get("respawn_interval_ms"))
        elif category=="spell":
            var learn=data.get("learn",{});var cost=data.get("cost",{})
            values.learn_level=learn.get("level",values.get("learn_level",1));values.learn_money=learn.get("money",learn.get("gold",values.get("learn_money",0)))
            values.cast_mp=cost.get("mp",values.get("cast_mp",0));values.cast_hp=cost.get("hp",values.get("cast_hp",0))
            for field in ["range_tiles","aoe_radius_tiles","cooldown_ms","duration_ms"]:
                if data.has(field):values[field]=data[field]
            var classes=data.get("class_ids",[])
            if not classes.is_empty():current.job=class_title(classes[0],rules)
        elif category=="growth":
            current.job=class_title(data.get("class_id",str(current.job)),rules);current.level=int(data.get("level",current.level))
            for type in ["hp","mp"]:
                var gains=data.get(type+"_gain",{})
                if gains.has("min"):values[type+"_gain_min"]=gains.min
                if gains.has("max"):values[type+"_gain_max_inclusive"]=gains.max
            if data.has("cumulative_exp"):values.cumulative_exp_to_next=int(data.cumulative_exp)+int(data.get("exp_to_next",0))
            if data.has("base_armor_class"):values.base_armor_class=data.base_armor_class
            rules.grow[str(current.job)+":"+str(current.level)]=current
        rules.by_id[id]=current
        var existing=rules.contents.find_custom(func(c):return c.id==id)
        if existing>=0:rules.contents[existing]=current
        else:rules.contents.append(current)
    rules.rebuild_indexes()

func merge_world(world: Dictionary) -> Dictionary:
    var result=world.duplicate(true)
    var map_ids={}
    for id in by_kind("map"):
        var definition_data=definition(id)
        if not definition_data.has("layout_acquisition"):continue
        # A shared layout is NOT a shared gameplay identity. Keep established
        # scene/save IDs; Work-authored roles own separate permanent map IDs.
        map_ids[id]=id
    for id in by_kind("map"):
        var alias=definition(id).get("variant_group","")
        if alias!="":map_ids[id]=map_ids.get(alias,alias)
    result["map_aliases"]=map_ids
    for id in by_kind("map"):
        var data=definition(id)
        if data.get("variant_active",true)==false:continue
        if not data.has_all(["width","height","layers","collision","entry"]):continue
        var layout={};var shared={}
        if data.has("layout_acquisition"):
            var info=assets.get(id,{})
            if info.is_empty():last_error={"code":"MAP_LAYOUT_NOT_ACQUIRED","content_id":id};continue
            layout=JSON.parse_string(FileAccess.get_file_as_string(release_root.path_join("files").path_join(info.stored_path)))
            var objects=layout.get("objects_acquisition",{"bundle_id":data.layout_acquisition.bundle_id,"member":layout.get("objects_member","")})
            var format_key="bundle_file:"+objects.bundle_id+":"+str(objects.member)
            info=assets.get(format_key,{})
            if info.is_empty():last_error={"code":"MAP_OBJECT_FORMAT_MISSING","content_id":id};continue
            shared=JSON.parse_string(FileAccess.get_file_as_string(release_root.path_join("files").path_join(info.stored_path)))
            result["work_draw_order"]=shared.draw_order
        var ground=[];var blocked=[];var collision=[];var decorations=[]
        if not layout.is_empty():
            var tables=shared.tile_tables
            for y in range(int(data.height)):
                var row=[];var walls=[];var masks=[]
                for x in range(int(data.width)):
                    var index=y*int(data.width)+x;var word=int(layout.layers.ground[index]);var sheet=tables.B if word>=int(tables.B.base) else tables.A
                    var frame=word-int(sheet.base)
                    row.append(str(sheet.sheet_asset_id)+"#"+str(frame) if frame>=0 and frame<int(sheet.count) else "")
                    var mask=int(layout.collision_masks[index]);masks.append(mask);walls.append(mask==15)
                    var object_id=int(layout.layers.objects[index])
                    if object_id>0 and object_id<shared.objects.size():
                        var object=shared.objects[object_id]
                        for part in range(object.frames.size()):
                            if object.frames[part]==null:continue # original empty column segment; keep part offset
                            decorations.append({"x":x,"y":y-part,"anchor_y":y,"tile":str(tables.C.sheet_asset_id)+"#"+str(int(object.frames[part])),"object_id":object_id,"column_part":part})
                ground.append(row);blocked.append(walls);collision.append(masks)
        else:
            ground=data.layers.get("ground",[]);blocked=data.collision
            decorations=data.layers.get("decorations",[])
        var scene_id=map_ids.get(id,id)
        var m={"id":scene_id,"definition_id":id,"name":data.name,"width":data.width,"height":data.height,"ground":ground,"blocked":blocked,
            "entry":data.entry,"portals":data.get("portals",[]).duplicate(true),"spawns":[],"npcs":[],"decorations":data.layers.get("decorations",[]),
            "kind":data.get("kind","field"),"source_kind":records[id].get("source_mode","")}
        m.decorations=decorations
        if not collision.is_empty():m.collision_masks=collision
        if data.has("layout_acquisition"):m.original_map_id=data.layout_acquisition.source_original_map_id
        for portal in m.portals:
            portal.target=map_ids.get(portal.get("destination_map_id",portal.get("target","")),portal.get("destination_map_id",portal.get("target","")))
            portal.entry=portal.get("destination_xy",portal.get("entry",[]))
            portal.label=definition(portal.get("destination_map_id","")).get("name",portal.target)
            portal.id=portal.get("placement_id",portal.get("id",""))
        for spawn in data.get("spawns",[]):
            var positions=spawn.get("spawn_cells",[[spawn.x,spawn.y]]).duplicate(true)
            var limit=int(spawn.get("max_live",1));var radius=int(spawn.get("radius_tiles",2))
            for y in range(maxi(0,int(spawn.y)-radius),mini(int(data.height),int(spawn.y)+radius+1)):
                for x in range(maxi(0,int(spawn.x)-radius),mini(int(data.width),int(spawn.x)+radius+1)):
                    if positions.size()>=limit:break
                    if not blocked[y][x] and [x,y] not in positions:positions.append([x,y])
            for count in range(mini(limit,positions.size())):
                var s=spawn.duplicate(true);s.kind=s.get("monster_id",s.get("kind",""));s.id=str(s.get("placement_id",id+"/spawn/"+str(m.spawns.size())))+"/"+str(count)
                s.x=positions[count][0];s.y=positions[count][1];m.spawns.append(s)
        for placement in data.get("npc_placements",[]):
            var n=placement.duplicate(true);var nid=n.get("npc_id",n.get("id",""));var spec=definition(nid)
            if spec.get("identity_variants",{}).get("active",true)==false:continue
            n.definition_id=nid;n.id=n.get("placement_id",n.get("id",id+"/npc/"+str(m.npcs.size())));n.name=spec.get("name",nid)
            n.kind=spec.get("visual",{}).get("asset_id","teacher");n.role="work_services";n.services=spec.get("services",[]);n.dialogue=spec.get("dialogue",[])
            m.npcs.append(n)
        var index=result.maps.find_custom(func(old):return old.id==scene_id)
        if index>=0:result.maps[index]=m
        else:result.maps.append(m)
    if map_ids.has("wk.map.city.goguryeo"):
        var home=result.home
        var origin_index=result.maps.find_custom(func(m):return m.id==home.map)
        var target_index=result.maps.find_custom(func(m):return m.id=="wk.map.city.goguryeo")
        if origin_index>=0 and target_index>=0:
            var origin=result.maps[origin_index];var target=result.maps[target_index]
            # Minimal Codex integration link, separate from read-only Work
            # definitions. Preserve all old portals, NPCs and saved geography.
            var from=bridge_cell(origin,home.entry);var to=bridge_cell(target,target.entry)
            origin.portals.append({"id":"codex.bridge.Work","x":from.x,"y":from.y,"target":target.id,"entry":target.entry,"label":"추가 지역 길목","trigger":"interact","source_kind":"CODEX_INTEGRATION_BRIDGE"})
            target.portals.append({"id":"codex.bridge.legacy","x":to.x,"y":to.y,"target":home.map,"entry":home.entry,"label":"기존 고구려 마을","trigger":"interact","source_kind":"CODEX_INTEGRATION_BRIDGE"})
    return result

func bridge_cell(map: Dictionary, entry: Array) -> Vector2i:
    for radius in range(2,7):
        for y in range(maxi(0,int(entry[1])-radius),mini(int(map.height),int(entry[1])+radius+1)):
            for x in range(maxi(0,int(entry[0])-radius),mini(int(map.width),int(entry[0])+radius+1)):
                var cell=Vector2i(x,y)
                if map.blocked[y][x] or cell.distance_to(Vector2i(entry[0],entry[1]))<2:continue
                if map.npcs.any(func(n):return cell.distance_to(Vector2i(n.x,n.y))<=1.5):continue
                if map.portals.any(func(p):return cell.distance_to(Vector2i(p.x,p.y))<=1.5):continue
                return cell
    return Vector2i(entry[0],entry[1])
