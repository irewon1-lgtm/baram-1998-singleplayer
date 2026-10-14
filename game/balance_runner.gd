extends SceneTree
const Rules = preload("res://rules.gd")
const Store = preload("res://save_store.gd")
var rules = Rules.new()
var store = Store.new()
var folder = ""
var report_path = ""
var checks = []
var observed = {}
var world = {}
var only = []

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--report="): report_path = arg.trim_prefix("--report=")
        if arg.begins_with("--private="): folder = arg.trim_prefix("--private=")
        if arg.begins_with("--only="): only = arg.trim_prefix("--only=").split(",")
    call_deferred("run")

func verify(condition: bool, description: String):
    checks.append({"condition":description,"result":"PASS" if condition else "FAIL"})

func player(job: String = "전사") -> Dictionary:
    return rules.new_player(job,"계산검증")

func save_roundtrip(p: Dictionary, name: String) -> bool:
    var path = folder.path_join(name+".json")
    var s = {"player":p,"world":{},"rng_state":str(rules.rng.state)}
    if not store.write_state(path,s):
        print("SAVE_CHECK write failed: "+path)
        return false
    var loaded = store.read_state(path)
    if loaded.is_empty():
        print("SAVE_CHECK read rejected: "+path)
        return false
    for key in ["level","hp","hp_max","mp","mp_max","xp2","gold","inventory","equipped","rng_state"]:
        if p[key] != loaded.player[key]:
            print("SAVE_CHECK mismatch "+key+" original="+str(p[key])+" loaded="+str(loaded.player[key]))
            return false
    return true

func execute(t: Dictionary):
    checks = []
    observed = {}
    var id = str(t.test_id)
    var v = t.inputs
    if id.begins_with("XP-") and v.has("threshold"):
        var p = player(v.class_scope)
        p.level = v.current_level
        p.xp2 = int(v.xp_before)*2
        verify(rules.threshold(v.class_scope,int(v.current_level)) == int(v.threshold),"Research threshold agrees with independent expected input")
        rules.award_xp(p,float(v.award))
        observed = {"level":p.level,"xp2":p.xp2}
        verify(int(p.level) == int(t.expected_conditions.level_after),"Cumulative threshold boundary")
    elif id == "XP-FRACTION":
        var p = player()
        for i in range(int(v.kills)):rules.award_xp(p,float(v.monster_xp))
        observed = {"xp2":p.xp2}
        verify(int(p.xp2) == 150,"Ten 7.5 awards retain fractional XP")
    elif id.begins_with("GROWTH-"):
        rules.rng.seed = int(v.random_seed)
        var p = player(v.class_scope)
        while int(p.level) < int(v.target_level):
            var threshold = rules.threshold(p.job,int(p.level))
            rules.award_xp(p,float(threshold)-float(p.xp2)/2.0)
        verify(p.growth_log.size() == 29,"29 actual level-up operations")
        for g in p.growth_log:
            var bounds = rules.growth(g.job,int(g.from))
            verify(int(g.hp_gain)>=int(bounds.hp_gain_min) and int(g.hp_gain)<=int(bounds.hp_gain_max_inclusive)
                and int(g.mp_gain)>=int(bounds.mp_gain_min) and int(g.mp_gain)<=int(bounds.mp_gain_max_inclusive),"Inclusive bounds at level "+str(int(g.from)))
            verify(str(g.job)==("평민" if int(g.from)<5 else str(v.class_scope)),"Peasant/job boundary at level "+str(int(g.from)))
        verify(save_roundtrip(p,id),"Same save module preserves state on disk")
        observed={"level":p.level,"hp":p.hp,"mp":p.mp,"growth_log":p.growth_log}
    elif id == "XP-99-CAP":
        var p = player()
        p.level=99
        rules.award_xp(p,1000000)
        verify(int(p.level)==99 and int(p.xp2)==2000000,"Level 99 cap retains XP bank")
        observed={"level":p.level,"xp2":p.xp2}
    elif id == "INTEGER-LEARN":verify(rules.integer_learn(71.5)==72,"Learning level rounds upward")
    elif id == "INTEGER-AC":verify(rules.integer_armor(-11.5)==-12,"AC rounds downward")
    elif id == "EQUIP-STRENGTH":
        var result=[]
        for strength in [4,5]:
            var p=player()
            p.inventory={"목검":1}
            p.strength=strength
            var old=p.inventory.duplicate(true)
            var ok=rules.equip(p,"목검")
            result.append(ok)
            if not ok:verify(old==p.inventory,"Failed equip does not alter inventory")
        verify(result==[false,true],"Strength 4 fails and 5 succeeds")
        observed={"equip_results":result}
    elif id == "DAMAGE-ARMOR":
        var result=[]
        for a in [100,0,-80,-95]:result.append(rules.damage(100,a))
        verify(result==[200,100,20,5],"Explicit NA replacement formula at four armor boundaries")
        observed={"damage":result,"classification":"NA_REPLACEMENT"}
    elif id == "CAST-RESOURCES":
        var p=player()
        p.mp=20
        p.hp=50
        var ok=rules.cast_resources(p,21,0,1.0,"test")
        verify(not ok and p.mp==20 and p.hp==50 and p.cooldowns.is_empty(),"Resource failure is atomic and cooldown not started")
    elif id == "HEAL-CAP":
        var p=player();p.hp=90;p.hp_max=100
        rules.heal(p,50)
        verify(p.hp==100,"Healing capped at HP maximum")
    elif id in ["LEARN-COST","LEARN-ABORT"]:
        var p=player();p.level=10;p.gold=30;p.inventory={"도토리":70 if id=="LEARN-COST" else 69,"토끼고기":10}
        var ok=rules.learn(p,"누리의기원")
        if id=="LEARN-COST":
            verify(ok and p.gold==0 and p.inventory["도토리"]==0,"Research learning money and acorns deducted")
            verify(int(rules.skill(p,"누리의기원").cast_mp)==5,"Casting MP remains separate from 30 learning money")
        else:verify(not ok and p.gold==30 and p.inventory["도토리"]==69,"Missing one acorn aborts whole transaction")
        observed={"success":ok,"gold":p.gold,"acorns":p.inventory["도토리"],"additional_master_precondition":"10 rabbit meat supplied"}
    elif id == "DROP-10PCT":
        rules.rng.seed=1999
        var p=player();var count=0
        var mon=rules.find_content("monster","서생원")
        for i in range(100000):
            for drop in rules.monster_drops(p,mon.id):
                if drop.item=="산삼":count+=drop.quantity
        verify(count>=9500 and count<=10500,"Actual source-linked monster drop function in 100000 kills")
        observed={"drops":count,"kills":100000}
    elif id == "DROP-ALTERNATIVE":
        rules.rng.seed=2001
        var max_count=0
        for i in range(10000):max_count=maxi(max_count,rules.alternate(["철단도","철검"],0.5).size())
        verify(max_count<=1,"Alternative group never emits both items")
        observed={"group_probability":"DEV_ESTIMATE_0.5","max_group_items":max_count}
    elif id == "TRADE-ROUNDTRIP":
        var p=player();p.gold=1000
        verify(rules.trade(p,"목검",3,20,true) == false,"Single-slot item stack limit is enforced")
        # Arithmetic boundary uses stackable goods; gameplay quantities retain actual limits.
        verify(rules.trade(p,"도토리",3,20,true) and p.gold==940,"Buy three at 20")
        verify(rules.trade(p,"도토리",3,10,false) and p.gold==970,"Sell three at 10")
        var old=p.duplicate(true)
        verify(not rules.trade(p,"도토리",100,20,true) and p==old,"Insufficient funds preserve entire state")
    elif id == "REPAIR-RTK":
        var p=player();p.inventory["목검"]=1;p.durability["목검"]=2000
        verify(rules.repair_cost(20,4000,2000)==5,"RTK replacement repair fee equals 5")
        verify(rules.repair(p,"목검") and p.durability["목검"]==4000 and p.gold==25,"Repair transaction applies fee and full durability")
    elif id == "REPAIR-BOUNDARY":
        var p=player();p.gold=0;p.inventory["목검"]=1;p.durability["목검"]=4000
        verify(rules.repair(p,"목검") and p.gold==0,"Full durability repair costs zero")
        verify(rules.repair_cost(20,0,0)==-1 and not rules.repair(p,"도토리"),"Zero maximum and nonrepairable item rejected")
    elif id == "CRAFT-ATOMIC":
        var p=player();var before=p.duplicate(true)
        verify(not rules.craft(p,{"토끼고기":1},1,"구운토끼고기") and p==before,"Missing ingredient grants/deducts nothing")
    elif id == "PROGRESSION-RESOURCES":
        var materials=world.shop_items
        var sources={}
        for d in rules.drops:
            if d.probability!=null:sources[d.item_name]=true
        var classes=[]
        for job in Rules.JOBS:
            var p=player(job);var learned=0;var trades=0
            # Economic simulation, using actual registered spawn definitions and same transactions.
            var farm=rules.monster("squirrel",world.replacements)
            var kills=0
            while int(p.level)<30:
                rules.reward_kill(p,farm,"squirrel")
                kills+=1
            for c in rules.contents:
                if c.category=="spell" and str(c.job)==job and c.values.get("learn_level")!=null and float(c.values.learn_level)<=30:
                    var obtainable=true
                    for key in c.values:
                        if key.begins_with("learn_materials."):
                            var material=key.trim_prefix("learn_materials.").trim_suffix(".quantity")
                            obtainable=obtainable and (material in materials or sources.has(material))
                            var qty=int(c.values[key])
                            var missing=maxi(0,qty-int(p.inventory.get(material,0)))
                            if missing>0:
                                var price=int(rules.value_or(rules.item(material),"vendor_buy_price",5))
                                while int(p.gold)<missing*price+int(c.values.learn_money):rules.reward_kill(p,farm,"squirrel");kills+=1
                                if rules.trade(p,material,missing,price,true):trades+=1
                    verify(obtainable,"Materials have a registered merchant/drop source: "+job+"/"+c.name)
                    if rules.learn(p,c.name):learned+=1
                    else:verify(false,"Registered skill economic path could not complete: "+c.name)
            verify(p.gold>=0,"No negative gold in "+job)
            for title in ["목도","목검","철단도","철검"]:
                verify(int(rules.value_or(rules.item(title),"strength_required",0))<=int(p.strength),"Required starter equipment strength available: "+title)
            classes.append({"job":job,"level":p.level,"gold":p.gold,"kills_simulated":kills,"learned":learned,"trades":trades})
        observed={"classes":classes,"scope":"REGISTERED_CONTENT_REACHABILITY_AND_SAME_RULES_SIMULATION_NOT_MANUAL_PLAYTHROUGH"}
    else:
        verify(false,"No executor for existing definition")
    return {"test_id":id,"status":"PASS" if checks.all(func(c):return c.result=="PASS") else "FAIL",
            "checks":checks.duplicate(true),"observed":observed.duplicate(true)}

func run():
    world=JSON.parse_string(FileAccess.get_file_as_string("res://data/world.json"))
    var definitions=JSON.parse_string(FileAccess.get_file_as_string("res://data/balance_tests.json"))
    var results=[]
    for t in definitions.tests:
        if not only.is_empty() and t.test_id not in only:continue
        var result=execute(t)
        results.append(result)
        print(result.test_id+" "+result.status)
    var passes=results.filter(func(r):return r.status=="PASS").size()
    var expected_count=37 if only.is_empty() else only.size()
    var report={"status":"PASS_CALCULATION_SIMULATION" if passes==expected_count else "FAIL","executed":results.size(),"pass":passes,
        "fail":results.size()-passes,"results":results,"scope":"SAME_INTERACTIVE_GAME_RULES_NOT_37_MANUAL_SCREEN_PLAYTHROUGHS",
        "rules_sha256":FileAccess.get_sha256("res://rules.gd"),"world_sha256":FileAccess.get_sha256("res://data/world.json"),
        "save_module_sha256":FileAccess.get_sha256("res://save_store.gd")}
    var file=FileAccess.open(report_path,FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"  "))
    file.close()
    quit(0 if passes==expected_count else 1)
