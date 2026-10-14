extends SceneTree
## Isolated level-30 fixtures are calculation setup, NEVER natural-play progress.
const Rules=preload("res://rules.gd")
const Store=preload("res://save_store.gd")
func _initialize():
    var destination=""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--out="):destination=arg.trim_prefix("--out=")
    if destination=="":quit(2);return
    var rules=Rules.new();var store=Store.new()
    for job in range(4):
        var p=rules.new_player(Rules.JOBS[job],"자료통합검증")
        rules.award_xp(p,rules.threshold(p.job,29))
        p.gold=1000000
        p.validation_fixture="CONTROLLED_LEVEL30_NOT_NATURAL_PLAYTHROUGH"
        p.hp=maxi(1,int(p.hp_max)/2)
        for c in rules.contents:
            if c.category!="spell" or c.job!=p.job or c.values.get("learn_level")==null or float(c.values.learn_level)>30:continue
            for key in c.values:
                if key.begins_with("learn_materials."):
                    var title=key.trim_prefix("learn_materials.").trim_suffix(".quantity")
                    p.inventory[title]=int(p.inventory.get(title,0))+int(c.values[key])
        var path=destination.path_join("skills-"+str(job)+".json")
        if FileAccess.file_exists(path):push_error("Existing fixture preserved: "+path);quit(2);return
        if not store.write_state(path,{"player":p,"world":{},"loot":[],"rng_state":str(rules.rng.state)}):quit(2);return
        print("CREATED_CONTROLLED_FIXTURE "+p.job+" "+path)
    quit()
