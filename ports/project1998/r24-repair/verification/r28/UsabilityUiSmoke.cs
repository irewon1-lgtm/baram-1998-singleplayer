using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using IO=System.IO;
public partial class Main
{
    private async Task R28Press(Control control)
    {var p=control.GetGlobalRect().GetCenter();R15Touch(p,true);await InputDelay(30);R15Touch(p,false);await InputDelay(100);await InputSettle();}
    private async Task R28Swipe(Vector2 delta,bool canceled=false)
    {
        var start=_hud.Buttons.Values.First(b=>b.Name.ToString().StartsWith("native-item-")&&b.IsVisibleInTree()).GetGlobalRect().GetCenter()+new Vector2(0,4);
        var scale=_hud.NativeOverlay.GetGlobalTransformWithCanvas().Scale;var end=start+delta*scale;
        R15Touch(start,true);await InputDelay(35);
        GetViewport().PushInput(new InputEventScreenDrag{Index=0,Position=end,Relative=end-start},true);await InputDelay(35);
        GetViewport().PushInput(new InputEventScreenTouch{Index=0,Position=end,Pressed=false,Canceled=canceled},true);await InputDelay(160);
    }
    private async void BeginR28UsabilitySmoke()
    {
        string status="FAIL",error="";
        try
        {
            using var contract=JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root,"ko-contract.json")));string id=contract.RootElement.GetProperty("id").GetString()!;
            await R15Continue(id);await R15Return();var store=new CharacterStore(IO.Path.Combine(_root,"state","chars"));
            var saved=store.ReadOfflineSnapshot(id)!;var c=CharacterStore.Deserialize(saved.CharacterJson);
            c.Map=332;c.MapXs=Server.Content.Maps[332].Xs;c.MapYs=Server.Content.Maps[332].Ys;c.X=14;c.Y=7;c.Level=8;c.ClassName="Mage";c.Coins=10000;c.MaxHp=100;c.Hp=80;c.MaxMp=100;c.Mp=50;
            c.Inventory.Clear();c.Equipment.Clear();c.Inventory.Add(new(0,10009,98));c.Inventory.Add(new(1,10009,2));c.Inventory.Add(new(2,102,2,357){Protected=2});
            var filler=Server.Content.Items.Where(i=>i.Type==0&&i.Id!=10009).Take(12).ToArray();
            for(byte n=3;n<15;n++)c.Inventory.Add(new(n,filler[n-3].Id,1));
            R27Check("r28_seed_isolated_character",store.SaveOfflineSnapshot(id,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision).Committed);
            await R15Continue(id);await InputDelay(200);var p=_play!;
            var npc=p.Capture().Creatures.First(n=>n.X==14&&n.Y==5);_hud.SelectedTarget=npc.Id;
            await R27Tap("talk");await WaitUi(()=>p.Capture().Dialog?.Kind==2,"Original inn root");await InputDelay(160);
            var menu=p.Capture().Dialog!;int buy=Array.IndexOf(menu.Options,"Buy")+1;
            R27Check("r28_real_npc_root_contains_buy",buy>0,new{menu.Text,menu.Options});
            await R27Tap("dialog-menu-"+buy);await InputDelay(180);
            bool category = p.Capture().Dialog is {Kind:2};
            string[] previousOptions = p.Capture().Dialog?.Options ?? menu.Options;
            if(category)await R27Tap("dialog-menu-1");
            await WaitUi(()=>p.Capture().Shop is not null,"Original buy grid");await InputDelay(130);
            uint coins=G4Character(p).Coins;int stock=G4Character(p).Inventory.Sum(i=>i.Amount);
            await R27Tap("shop-cancel");await InputDelay(180);
            R27Check("r28_shop_close_returns_previous_npc_menu_without_retalking",p.Capture().Dialog is{Kind:2} root&&root.EntityId==npc.Id&&root.Options.SequenceEqual(previousOptions),p.Capture().Dialog);
            R27Check("r28_back_does_not_buy_or_duplicate_items",G4Character(p).Coins==coins&&G4Character(p).Inventory.Sum(i=>i.Amount)==stock);
            await R27Tap("dialog-menu-"+(category?1:Array.IndexOf(p.Capture().Dialog!.Options,"Buy")+1));await InputDelay(130);
            GetViewport().PushInput(new InputEventKey{Keycode=Key.Escape,Pressed=true},true);await InputDelay(250);await InputSettle();
            R27Check("r28_system_back_from_shop_returns_parent",p.Capture().Dialog is {Kind:2} back && back.Options.SequenceEqual(previousOptions));
            if(category){await R27Tap("dialog-cancel");await InputDelay(150);R27Check("r28_back_from_category_returns_npc_root",p.Capture().Dialog?.Options.Contains("Buy")==true);}
            GetViewport().PushInput(new InputEventKey{Keycode=Key.Escape,Pressed=true},true);await InputDelay(200);await InputSettle();
            R27Check("r28_back_from_root_exits_normally",p.Capture().Dialog is null&&p.Capture().Shop is null);
            var held=G4Character(p);R27Check("r28_entry_compacts_100_acorns_to_99_and_1",held.Inventory.Where(i=>i.ItemId==10009).OrderBy(i=>i.Slot).Select(i=>i.Amount).SequenceEqual(new[]{99,1}));
            R27Check("r28_same_equipment_state_preserved_in_one_slot",held.Inventory.Single(i=>i.ItemId==102) is{Amount:2,Dura:357,Protected:2});
            await R27Tap("native-inventory");string before=p.Host.CharacterJson;
            await R28Swipe(new(-60,0));R27Check("r28_swipe_left_next_page",_hud.FindChild("BagPageIndicator",true,false) is Label next&&next.Text.StartsWith("2 /"));
            await R28Swipe(new(60,0));R27Check("r28_swipe_right_previous_page",_hud.FindChild("BagPageIndicator",true,false) is Label previous&&previous.Text.StartsWith("1 /"));
            R27Check("r28_swipe_never_uses_eats_or_equips",p.Host.CharacterJson==before);
            await R28Swipe(new(-60,0),true);R27Check("r28_canceled_swipe_stays_on_page",((Label)_hud.FindChild("BagPageIndicator",true,false)).Text.StartsWith("1 /"));
            await R28Swipe(new(0,60));R27Check("r28_vertical_drag_does_not_turn_page",((Label)_hud.FindChild("BagPageIndicator",true,false)).Text.StartsWith("1 /"));
            await R28Swipe(new(60,0));R27Check("r28_first_page_swipe_is_bounded",((Label)_hud.FindChild("BagPageIndicator",true,false)).Text.StartsWith("1 /"));
            await R27Tap("native-item-1");R27Check("r28_single_item_tap_still_inspects_without_modal",R27Details?.IsVisibleInTree()==true&&!_hud.ModalOpen);
            await R28Swipe(new(-60,0));await R28Swipe(new(60,0));await R27Tap("native-item-1");
            R27Check("r28_swipe_resets_pending_double_tap",G4Character(p).Inventory.Where(i=>i.ItemId==10009).Sum(i=>i.Amount)==100);
            R27Check("r28_stack_label_is_not_duplicated_count",_hud.Buttons["native-item-1"].Text.Contains("×99")&&!_hud.Buttons["native-item-1"].Text.Contains("(99)"),_hud.Buttons["native-item-1"].Text);
            await CaptureScreen("r28-bag-swipe-stacks");
            await R27Tap("area-map");await WaitUi(()=>_hud.FindChild("AreaRouteText",true,false) is Label l&&!l.Text.Contains("읽는 중"),"Detailed map ready");await InputDelay(200);
            R27Check("r28_map_shows_current_region_and_coordinates",_hud.FindChild("CurrentRegionLocation",true,false) is Label location&&location.Text.Contains("부여")&&location.Text.Contains("14, 7"),((Label)_hud.FindChild("CurrentRegionLocation",true,false)).Text);
            R27Check("r28_detailed_map_is_drawn",_hud.FindChild("DetailedAreaMap",true,false) is Control canvas&&canvas.IsVisibleInTree());
            await R27Tap("area-city");await WaitUi(()=>_hud.FindChild("AreaRouteText",true,false) is Label l&&!l.Text.Contains("읽는 중"),"Buya city ready");await InputDelay(200);
            var search=(LineEdit)_hud.FindChild("AreaSearch",true,false);search.Text="주술사";await R27Tap("area-search");
            var mage=_hud.FindChildren("area-place-*","Button",true,false).OfType<Button>().First(b=>b.Text.Contains("주술사")&&b.Text.Contains("("));await R28Press(mage);
            await WaitUi(()=>((Label)_hud.FindChild("AreaRouteText",true,false)).Text.Contains("문 →"),"Resolved actual first entrance",20);
            string route=((Label)_hud.FindChild("AreaRouteText",true,false)).Text;
            R27Check("r28_mage_guild_has_real_entrance_and_route",route.Contains("주술사")&&route.Contains("문 →")&&route.Contains("("),route);
            await CaptureScreen("r28-buya-mage-map");
            R27Check("r28_map_browse_does_not_teleport_or_spend_items",p.Capture().Map==332&&p.Capture().X==14&&p.Capture().Y==7&&G4Character(p).Coins==coins);
            var exitPlans=Server.Content.Warps.Where(w=>w.Key.m==332&&w.Value.m==330).Select(w=>new{w.Key.x,w.Key.y,plan=ClientNavigation.Plan(p.Capture(),w.Key.x,w.Key.y)}).ToArray();
            AtomicWrite(IO.Path.Combine(_root,"r28-exit-plans.json"),JsonSerializer.Serialize(exitPlans));
            AtomicWrite(IO.Path.Combine(_root,"r28-map-layout.json"),JsonSerializer.Serialize(_hud.FindChildren("*","Control",true,false).OfType<Control>().Where(n=>n.IsVisibleInTree()&&(n.Name.ToString().StartsWith("area-")||n.Name=="DetailedAreaMap")).Select(n=>new{name=n.Name.ToString(),rect=n.GetGlobalRect().ToString(),minimum=n.GetCombinedMinimumSize().ToString()})));
            await R27Tap("area-walk");await WaitUi(()=>p.Capture().Map==330,"Guide route walks through the real tavern exit",20);await InputSettle();
            var arrived=p.Capture();await InputDelay(450);
            R27Check("r28_guide_walk_uses_original_exit_and_stops_on_map_transition",p.Capture().Map==330&&p.Capture().X==arrived.X&&p.Capture().Y==arrived.Y&&!_hud.ModalOpen,new{arrived.Map,arrived.X,arrived.Y});
            await R27Tap("area-map");await InputDelay(200);await R27Tap("area-overview");await CaptureScreen("r28-local-overview");await R27Tap("area-close");
            await R15Return();saved=store.ReadOfflineSnapshot(id)!;c=CharacterStore.Deserialize(saved.CharacterJson);
            var lua=Server.Content.Npcs.First(n=>n.Key=="LaptevNpc"&&n.Enabled);c.Map=lua.Map;c.MapXs=Server.Content.Maps[lua.Map].Xs;c.MapYs=Server.Content.Maps[lua.Map].Ys;c.X=lua.X;c.Y=(ushort)(lua.Y+1);
            R27Check("r28_lua_fixture_saved_without_touching_other_characters",store.SaveOfflineSnapshot(id,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision).Committed);
            await R15Continue(id);p=_play!;await InputDelay(180);var weaver=p.Capture().Creatures.First(n=>n.X==lua.X&&n.Y==lua.Y);_hud.SelectedTarget=weaver.Id;
            await R27Tap("talk");await InputDelay(150);var luaRoot=p.Capture().Dialog!;
            await R27Tap("dialog-menu-"+(Array.IndexOf(luaRoot.Options,"Joy of Weaving")+1));await InputDelay(150);string first=p.Capture().Dialog!.Text;
            await R27Tap("dialog-next");await InputDelay(100);R27Check("r28_lua_second_page_has_previous_button",p.Capture().Dialog?.Previous==true);
            await R27Tap("dialog-previous");await InputDelay(100);R27Check("r28_previous_revisits_text_without_replaying_rewards",p.Capture().Dialog?.Text==first&&G4Character(p).Coins==coins);
            await R27Tap("dialog-cancel");await InputDelay(150);R27Check("r28_lua_close_returns_parent_without_retalking",p.Capture().Dialog?.Options.Contains("Joy of Weaving")==true);
            await R27Tap("dialog-cancel");await InputDelay(100);
            string final=p.Host.CharacterJson;await R15Return();await R15Continue(id);p=_play!;
            R27Check("r28_stacks_and_instance_state_survive_restart",G4Character(p).Inventory.Where(i=>i.ItemId==10009).Sum(i=>i.Amount)==100&&G4Character(p).Inventory.Single(i=>i.ItemId==102) is{Amount:2,Dura:357,Protected:2});
            R27Check("r28_original_full_commits_still_healthy",p.Host.LastSave.Committed&&!p.Faulted&&_fatal.Length==0);
            status="PASS_SCOPED_R28_ACTUAL_NPC_BACK_SWIPE_STACK_MAP_AND_REOPEN";
        }
        catch(Exception e){error=e.ToString();try{await CaptureScreen("r28-failure");}catch(Exception){}}
        AtomicWrite(IO.Path.Combine(_root,"ko-checks.json"),JsonSerializer.Serialize(new{status,checks=_r27Checks,error,physical_android="NOT_RUN"},new JsonSerializerOptions{WriteIndented=true}));
        WriteReport(IO.Path.Combine(_root,"r28-input-result.json"));await End(true);
    }
}
