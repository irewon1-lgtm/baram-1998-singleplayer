extends SceneTree
## Controlled interpreter/reference checks only; never whole-gameplay PASS.
const Rules=preload("res://rules.gd")
const Registry=preload("res://content_registry.gd")
const Effects=preload("res://effect_runtime.gd")
const Precision=preload("res://precision.gd")
var options={}
var report={"scope":"READ_ONLY_CONTENT_LOAD_AND_CONTROLLED_EFFECT_INTERPRETER_NOT_GUI_GAMEPLAY","checks":[]}
var content=Registry.new()
var rules=Rules.new()

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    call_deferred("run")

func record(id: String, errors: Array, tested: int, details={}):
    report.checks.append({"id":id,"result":"PASS" if errors.is_empty() else "FAIL","tested":tested,"errors":errors,"details":details})
    print("CONTRACT "+id+" "+("PASS" if errors.is_empty() else "FAIL")+" "+str(tested))

func typed(id: String,kind: String) -> bool:
    return content.records.has(id) and content.records[id].kind==kind

func run():
    if not content.load_directory(options.content):record("immutable-release-and-assets",[content.last_error],0);finish();return
    report.content_version=content.version
    report.source_sha256={}
    for path in ["rules.gd","core_actions.gd","content_registry.gd","effect_runtime.gd","precision.gd","main.gd"]:report.source_sha256[path]=FileAccess.get_sha256("res://"+path)
    report.ran_at_utc=Time.get_datetime_string_from_system(true)
    record("immutable-release-and-assets",[],content.assets.size())
    content.apply_rules(rules)
    var errors=[];var apply_errors=[];var modes={};var counts={};var applied_count=0
    for id in content.records:counts[content.records[id].kind]=int(counts.get(content.records[id].kind,0))+1
    report.definition_counts=counts
    for id in content.by_kind("skill"):
        var spec=content.definition(id)
        var compiled=Effects.compile_skill(spec)
        var result=Effects.validate(compiled)
        if not result.ok:
            errors.append({"id":id,"error":result});apply_errors.append({"id":id,"error":"NOT_RUN_INVALID_COMPILE"});continue
        if compiled.is_empty():
            errors.append({"id":id,"error":"EMPTY_EFFECTS"});apply_errors.append({"id":id,"error":"NOT_RUN_EMPTY_EFFECTS"});continue
        var p=rules.new_player("전사","감사 전용")
        p.hp_max=1000000;p.hp=500000;p.mp_max=1000000;p.mp=500000
        if compiled.any(func(effect):return effect.type=="revive"):p.hp=0
        var target={"id":"audit-target","hp":1000000,"hp_max":1000000,"mp":1000000,"mp_max":1000000,"statuses":{},"spec":{"values":{"armor_class":0}}}
        var applied=Effects.apply(rules.actions,p,[target],compiled)
        applied_count+=1
        if not applied.ok:apply_errors.append({"id":id,"error":applied})
        for move in applied.get("movement",[]):
            var mode=move.get("mode","");modes[mode]=int(modes.get(mode,0))+1
            if mode not in ["inspect_item","local_message","directional_town_gate","home_city","revival_npc","safe_region_entry","adjacent_enemy"] and move.get("map","")=="":apply_errors.append({"id":id,"error":"UNKNOWN_MOVEMENT","mode":mode})
        for ingredient in spec.get("learn",{}).get("consume",[]):
            if not typed(ingredient.item_id,"item"):errors.append({"id":id,"error":"LEARN_ITEM_MISSING","item":ingredient.item_id})
    record("all-skills-compile-and-validate",errors,content.by_kind("skill").size())
    record("all-skills-controlled-effects-accepted",apply_errors,applied_count,{"movement_modes":modes,"defined_skills":content.by_kind("skill").size(),"normal_cast_and_animation":"NOT_RUN"})
    errors=[];var services={}
    for id in content.by_kind("npc"):
        var spec=content.definition(id)
        for service in spec.get("services",[]):
            var kind=service.get("type","");services[kind]=int(services.get(kind,0))+1
            if kind not in ["shop","quest","quests","trainer","skill","skills","learn_skills","experience_exchange","recipe_book","repair","revive","advancement","travel","teleport","enhancement","heal","rest","dialogue"]:errors.append({"id":id,"error":"UNKNOWN_SERVICE","service":kind})
            for pair in [["shop_id","shop"],["recipe_id","recipe"],["economy_id","economy"]]:
                if service.has(pair[0]) and not typed(service[pair[0]],pair[1]):errors.append({"id":id,"error":"SERVICE_REFERENCE","field":pair[0],"value":service[pair[0]]})
            for pair in [["skill_ids","skill"],["quest_ids","quest"],["recipe_ids","recipe"],["advancement_ids","advancement"],["map_ids","map"]]:
                for ref in service.get(pair[0],[]):
                    if not typed(ref,pair[1]):errors.append({"id":id,"error":"SERVICE_REFERENCE","field":pair[0],"value":ref})
        for node in spec.get("dialogue",[]):
            if typeof(node)!=TYPE_DICTIONARY:continue
            for choice in node.get("choices",[]):
                if choice.get("close",false):continue
                var index=int(choice.get("service_index",-1))
                if index<0 or index>=spec.get("services",[]).size():errors.append({"id":id,"error":"DIALOGUE_SERVICE_INDEX","index":index})
    record("all-NPC-services-and-dialogue-references",errors,content.by_kind("npc").size(),{"service_types":services})
    errors=[]
    for id in content.by_kind("monster"):
        var group=content.definition(id).get("drop_group_id","")
        if not typed(group,"drop_group"):errors.append({"id":id,"error":"DROP_GROUP_MISSING","value":group})
    for id in content.by_kind("drop_group"):
        var spec=content.definition(id)
        var result=Precision.draw(rules.rng,spec.mode,spec.rolls)
        if not result.ok:errors.append({"id":id,"error":result.error})
        for roll in spec.rolls:
            if roll.get("item_id","")!="" and not typed(roll.item_id,"item"):errors.append({"id":id,"error":"DROP_ITEM_MISSING","value":roll.item_id})
    record("all-monster-drop-groups-and-roll-references",errors,content.by_kind("drop_group").size())
    errors=[];var objectives={};var rewards={}
    for id in content.by_kind("quest"):
        var spec=content.definition(id)
        for objective in spec.get("objectives",[]):
            var kind=objective.get("type","");objectives[kind]=int(objectives.get(kind,0))+1
            if kind not in ["collect","kill","talk"]:errors.append({"id":id,"error":"OBJECTIVE_EVENT_NOT_EMITTED","value":kind})
            var field={"collect":"item_id","kill":"monster_id","talk":"npc_id"}.get(kind,"")
            var expected={"collect":"item","kill":"monster","talk":"npc"}.get(kind,"")
            if field!="" and not typed(objective.get(field,objective.get("target_id","")),expected):errors.append({"id":id,"error":"OBJECTIVE_REFERENCE","objective":objective})
            if objective.has("map_id") and not typed(objective.map_id,"map"):errors.append({"id":id,"error":"OBJECTIVE_MAP_MISSING"})
        for prior in spec.get("prerequisites",[]):
            if not typed(prior,"quest"):errors.append({"id":id,"error":"PREREQUISITE_MISSING","value":prior})
        for reward in spec.get("rewards",[]):
            if typeof(reward)!=TYPE_DICTIONARY:errors.append({"id":id,"error":"REWARD_FORMAT"});continue
            var kind=reward.get("type","");rewards[kind]=int(rewards.get(kind,0))+1
            if kind not in ["gold","experience","item","advancement"]:errors.append({"id":id,"error":"REWARD_UNKNOWN","value":kind})
            if kind=="item" and not typed(reward.get("item_id",""),"item"):errors.append({"id":id,"error":"REWARD_ITEM_MISSING"})
            if kind=="advancement" and not typed(reward.get("advancement_id",""),"advancement"):errors.append({"id":id,"error":"REWARD_ADVANCEMENT_MISSING"})
    record("all-quest-objective-events-and-reward-references",errors,content.by_kind("quest").size(),{"objective_types":objectives,"reward_types":rewards,"all_quest_playthrough":"NOT_RUN"})
    errors=[]
    for id in content.by_kind("recipe"):
        var spec=content.definition(id)
        if not Precision.valid_ratio(spec.get("success_ratio",{})):errors.append({"id":id,"error":"RECIPE_RATIO"})
        for output in spec.get("outputs",[])+spec.get("consume",[]):
            if not typed(output.get("item_id",""),"item"):errors.append({"id":id,"error":"RECIPE_ITEM_REFERENCE","value":output.get("item_id","")})
    record("all-recipe-input-output-references",errors,content.by_kind("recipe").size())
    finish()

func finish():
    report.result="FAIL" if report.checks.any(func(c):return c.result=="FAIL") else "PASS"
    report.gameplay_result="NOT_RUN"
    var file=FileAccess.open(options.out,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
    quit(0 if report.result=="PASS" else 2)
