extends Node
## CI-only native platform/file-format test, explicitly not cloud sync.
var checks=[]
func check(ok: bool, name: String):
    checks.append({"name":name,"status":"PASS" if ok else "FAIL"})
    print("MOBILE_CHECK "+name+" "+("PASS" if ok else "FAIL"))
func tap(game,point: Vector2,index=1):
    var press=InputEventScreenTouch.new();press.index=index;press.position=point;press.pressed=true
    Input.parse_input_event(press)
    await get_tree().create_timer(.08).timeout
    var release=InputEventScreenTouch.new();release.index=index;release.position=point;release.pressed=false
    Input.parse_input_event(release)
    await get_tree().create_timer(.25).timeout
func run(game,mode,directory):
    DirAccess.make_dir_recursive_absolute(directory)
    if mode=="mobile-pc-seed":
        check(game.menu=="creation","PC_creation_screen")
        game.name_edit.text="이어하기시험";game.name_edit.release_focus()
        var e=InputEventKey.new();e.keycode=KEY_ENTER;e.pressed=true;game._input(e)
        check(not game.player.is_empty() and game.save_game(),"PC_normal_character_saved")
    elif mode=="mobile-pc-resume":
        var expected=JSON.parse_string(FileAccess.get_file_as_string(game.options.expected))
        check(game.save_loaded,"PC_fresh_process_loaded_Android_save")
        check(game.player.name==expected.name and [game.player.x,game.player.y]==expected.after,"PC_restores_Android_changed_position_and_same_character")
        check(expected.before!=expected.after,"Android_actually_changed_progress")
    else:
        check(OS.get_name()=="Android","actual_Android_process")
        check(game.save_loaded,"Android_loaded_PC_save")
        check(game.touch_controls!=null and game.touch_controls.buttons.size()>=16,"touch_buttons_created")
        var before=[game.player.x,game.player.y]
        var moved=false
        for d in range(4):
            if game.free_cell(game.player.map,game.cell()+game.DIRECTIONS[d],"",d):
                await tap(game,[Vector2(115,680),Vector2(45,750),Vector2(115,750),Vector2(185,750)][d])
                moved=[game.player.x,game.player.y]!=before
                if moved:break
        check(moved,"actual_screen_touch_moves_character")
        await tap(game,Vector2(345,750))
        check(game.menu=="inventory","actual_screen_touch_opens_bag")
        await tap(game,Vector2(555,750))
        check(game.menu=="","actual_screen_touch_closes_menu")
        check(game.save_game(),"Android_saved_shared_schema2")
        await RenderingServer.frame_post_draw
        var frame=game.get_viewport().get_texture().get_image()
        check(not frame.is_empty() and frame.save_png(directory.path_join("android-frame.png"))==OK,"Android_rendered_frame")
        var report={"status":"PASS" if checks.all(func(c):return c.status=="PASS") else "FAIL", "checks":checks,
            "platform":OS.get_name(),"scope":"NATIVE_EMULATOR_FILE_TRANSPORT_NOT_CLOUD_NOT_GALAXY", "name":game.player.name,"before":before,"after":[game.player.x,game.player.y]}
        var f=FileAccess.open(directory.path_join("mobile-report.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report));f.close()
        print("BARAM_MOBILE_RESULT "+JSON.stringify(report))
        await get_tree().create_timer(12).timeout
    var result={"status":"PASS" if checks.all(func(c):return c.status=="PASS") else "FAIL","checks":checks,"platform":OS.get_name(),"scope":"FILE_TRANSPORT_NOT_DEPLOYED_CLOUD"}
    var f=FileAccess.open(directory.path_join(mode+"-report.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result));f.close()
    print("BARAM_FORMAT_RESULT "+JSON.stringify(result))
    get_tree().quit(0 if result.status=="PASS" else 1)
