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
    if typeof(parsed)!=TYPE_DICTIONARY or parsed.get("format","")!="BARAM_RUNTIME_CONTENT" or parsed.get("version",0)!=1:
        last_error={"code":"CONTENT_VERSION","file":path};return false
    records=parsed.records;id_map=parsed.id_map;assets=parsed.assets;version=pointer.release_id
    for info in assets.values():
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
        rules.runtime_definitions[id]={"kind":record.kind,"data":data,"provenance_refs":record.get("provenance_refs",[]),"source_mode":record.get("source_mode",""),"source_commit":record.get("source_commit","")}
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
            values.allowed_jobs=data.get("class_ids",needs.get("class_ids",[])).map(func(c):return class_title(c,rules))
            if data.has("prices"):
                values.vendor_buy_price=data.prices.get("buy",values.get("vendor_buy_price"))
                values.vendor_sell_price=data.prices.get("sell",values.get("vendor_sell_price"))
            values.instance_equipment=data.get("flags",{}).get("instance_equipment",values.get("instance_equipment",false))
            var visual=data.get("visual",{})
            if visual.has("legacy_sprite"):rules.visual_bindings[id]={"slot":values.slot,"sprite":visual.legacy_sprite,"motion":visual.get("motion","sword")}
        elif category=="monster":
            for field in ["hp","mp","armor_class","experience","level","gold"]:
                if data.has(field):values[field]=data[field]
            var attack=data.get("attack",{})
            values.attack_min=attack.get("min",values.get("attack_min"))
            values.attack_max=attack.get("max",values.get("attack_max"))
            var behavior=data.get("behavior",{})
            for field in ["move_interval_ms","attack_interval_ms","aggro_radius_tiles","leash_radius_tiles","hit_probability"]:
                if behavior.has(field):values[field]=behavior[field]
            values.respawn_interval_ms=data.get("spawn_rules",{}).get("respawn_ms",values.get("respawn_interval_ms"))
        elif category=="spell":
            var learn=data.get("learn",{});var cost=data.get("cost",{})
            values.learn_level=learn.get("level",values.get("learn_level",1));values.learn_money=learn.get("gold",values.get("learn_money",0))
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
            if data.has("cumulative_exp"):values.cumulative_exp_to_next=data.cumulative_exp
            if data.has("base_armor_class"):values.base_armor_class=data.base_armor_class
            rules.grow[str(current.job)+":"+str(current.level)]=current
        rules.by_id[id]=current
        var existing=rules.contents.find_custom(func(c):return c.id==id)
        if existing>=0:rules.contents[existing]=current
        else:rules.contents.append(current)
    rules.rebuild_indexes()

func merge_world(world: Dictionary) -> Dictionary:
    var result=world.duplicate(true)
    for id in by_kind("map"):
        var data=definition(id)
        if not data.has_all(["width","height","layers","collision","entry"]):continue
        var ground=data.layers.get("ground",[]) if typeof(data.layers)==TYPE_DICTIONARY else []
        var m={"id":id,"name":data.name,"width":data.width,"height":data.height,"ground":ground,"blocked":data.collision,
            "entry":data.entry,"portals":data.get("portals",[]).duplicate(true),"spawns":[],"npcs":[],"decorations":data.layers.get("decorations",[]),
            "kind":data.get("kind","field"),"source_kind":records[id].get("source_mode","")}
        for spawn in data.get("spawns",[]):
            var s=spawn.duplicate(true);s.kind=s.get("monster_id",s.get("kind",""));s.id=s.get("id",id+"/spawn/"+str(m.spawns.size()));m.spawns.append(s)
        for placement in data.get("npc_placements",[]):
            var n=placement.duplicate(true);var nid=n.get("npc_id",n.get("id",""));var spec=definition(nid)
            n.definition_id=nid;n.id=n.get("id",id+"/npc/"+str(m.npcs.size()));n.name=spec.get("name",nid)
            n.kind=spec.get("visual",{}).get("asset_id","teacher");n.role="work_services";n.services=spec.get("services",[]);n.dialogue=spec.get("dialogue",[])
            m.npcs.append(n)
        var index=result.maps.find_custom(func(old):return old.id==id)
        if index>=0:result.maps[index]=m
        else:result.maps.append(m)
    return result
