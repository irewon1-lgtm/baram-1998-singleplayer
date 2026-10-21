using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using IO = System.IO;

// Isolated PC input acceptance; never included in the update APK.
public partial class Main
{
    private readonly List<object> _r27Checks = new();
    private void R27Check(string name, bool passed, object? observed = null)
    {
        _r27Checks.Add(new { name, status = passed ? "PASS" : "FAIL", observed });
        if (!passed) throw new InvalidOperationException(name);
    }
    private Label? R27Details => _hud.FindChild("ItemDetailsText", true, false) as Label;
    private async Task R27Tap(string key, int wait = 70, bool mouse = false)
    {
        await WaitUi(() => _hud.Buttons.TryGetValue(key, out var b) && b.IsVisibleInTree() && !b.Disabled, "Touchable " + key);
        var point = _hud.Buttons[key].GetGlobalRect().GetCenter();
        if (mouse) GetViewport().PushInput(new InputEventMouseButton { Position=point,GlobalPosition=point,ButtonIndex=MouseButton.Left,Pressed=true },true);
        else R15Touch(point, true);
        await InputDelay(25);
        if (mouse) GetViewport().PushInput(new InputEventMouseButton { Position=point,GlobalPosition=point,ButtonIndex=MouseButton.Left,Pressed=false },true);
        else R15Touch(point, false);
        await InputDelay(wait);
    }
    private async Task R27Double(string key, bool mouse = false)
    { await R27Tap(key,60,mouse); await R27Tap(key,80,mouse); await InputSettle(); }
    private async void BeginR27InventorySmoke()
    {
        string status = "FAIL", error = "";
        try
        {
            using var contract = JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root,"ko-contract.json")));
            string id = contract.RootElement.GetProperty("id").GetString()!;
            await R15Continue(id); await R15Return();
            var store = new CharacterStore(IO.Path.Combine(_root,"state","chars"));
            var saved = store.ReadOfflineSnapshot(id)!;
            var c = CharacterStore.Deserialize(saved.CharacterJson);
            c.Map=330;c.MapXs=Server.Content.Maps[330].Xs;c.MapYs=Server.Content.Maps[330].Ys;c.X=110;c.Y=137;
            c.Level=8;c.ClassName="Mage";c.Mark=0;c.Sex=0;c.Might=12;c.Will=18;c.Grace=10;
            c.MaxHp=100;c.Hp=50;c.MaxMp=100;c.Mp=20;c.Mounted=false;
            c.Inventory.Clear();c.Equipment.Clear();
            c.Inventory.Add(new InvItem(0,102,1,357));
            c.Inventory.Add(new InvItem(1,10001,3));
            c.Inventory.Add(new InvItem(2,46001,1,4567));
            var gated = Server.Content.Items.First(d=>d.IsEquip && d.Level>c.Level && d.PathId==0 && d.Sex>=2);
            c.Inventory.Add(new InvItem(3,gated.Id,1,gated.Durability));
            for(byte slot=4;slot<12;slot++) c.Inventory.Add(new InvItem(slot,10002+slot,1));
            var result=store.SaveOfflineSnapshot(id,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision);
            R27Check("synthetic_fixture_committed_only_to_isolated_copy",result.Committed);
            await R15Continue(id);await InputDelay(200);var p=_play!;
            await R27Tap("native-inventory");
            string before=p.Host.CharacterJson;
            await R27Tap("native-item-1");
            R27Check("single_bag_tap_does_not_open_action_modal",!_hud.ModalOpen,new{_hud.ModalOpen});
            R27Check("single_bag_tap_shows_immediate_durability_and_requirements",R27Details is{ } details&&details.IsVisibleInTree()&&details.Text.Contains("357")&&details.Text.Contains("1,000")&&details.Text.Contains("필요 레벨"),R27Details?.Text);
            R27Check("inspection_does_not_mutate_character",before==p.Host.CharacterJson);
            await CaptureScreen("r27-single-inspection");
            await InputDelay(450);await R27Double("native-item-1");
            await WaitUi(()=>p.Capture().Equipment.Any(i=>i.BaseName==Server.Content.ItemById(102)!.Name),"Double touch equip");
            R27Check("double_touch_equips_original_instance_once",G4Character(p).Equipment.Single(i=>i.ItemId==102).Dura==357&&!_hud.ModalOpen);
            await R27Tap("native-item-2");
            R27Check("food_single_touch_only_inspects",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==3);
            R27Check("food_effect_matches_original_use_script_data",R27Details?.Text.Contains("HP 5 회복")==true,R27Details?.Text);
            await InputDelay(450);await R27Double("native-item-2");
            R27Check("double_touch_eats_exactly_one",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2&&!_hud.ModalOpen);
            await R27Tap("native-item-3");await InputDelay(450);await R27Tap("native-item-3");
            R27Check("weapon_inspection_shows_bonuses_and_actual_worn_comparison",R27Details?.Text.Contains("최대 HP +10")==true&&R27Details.Text.Contains("현재 장비와 비교")&&R27Details.Text.Contains("4,567"),R27Details?.Text);
            R27Check("slow_two_touches_do_not_activate",G4Character(p).Inventory.Any(i=>i.ItemId==46001));
            await R27Tap("native-item-2");await R27Tap("native-item-3");
            R27Check("different_item_touch_does_not_activate",G4Character(p).Inventory.Any(i=>i.ItemId==46001)&&G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            await InputDelay(450);await R27Double("native-item-3",true);
            R27Check("desktop_double_click_equips_and_returns_old_instance",G4Character(p).Equipment.Any(i=>i.ItemId==46001&&i.Dura==4567)&&G4Character(p).Inventory.Any(i=>i.ItemId==102&&i.Dura==357));
            await R27Tap("native-item-4");await InputDelay(450);await R27Double("native-item-4");
            R27Check("level_gate_still_refuses_without_consuming",G4Character(p).Inventory.Any(i=>i.ItemId==gated.Id)&&G4Character(p).Equipment.Any(i=>i.ItemId==46001));
            // The staff is now equipped; its previous bag slot is correctly absent.
            // Inspect the returned wooden saber to compare it with that equipped staff.
            await R27Tap("native-item-1");await CaptureScreen("r27-equipped-comparison");
            await R27Tap("native-item-2");await R27Tap("native-spells");await R27Tap("native-inventory");await R27Tap("native-item-2");
            R27Check("panel_change_cancels_pending_pair",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            await R27Tap("native-page-next");await R27Tap("native-page-prev");await R27Tap("native-item-2");
            R27Check("page_change_cancels_pending_pair",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            var point=_hud.Buttons["native-item-2"].GetGlobalRect().GetCenter();
            R15Touch(point,true);GetViewport().PushInput(new InputEventScreenDrag{Index=0,Position=point+new Vector2(18,0),Relative=new Vector2(18,0)},true);R15Touch(point+new Vector2(18,0),false);
            await R27Tap("native-item-2");
            R27Check("drag_cancels_pending_pair",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            _hud.Notification((int)Main.NotificationApplicationFocusOut);await R27Tap("native-item-2");
            R27Check("focus_loss_cancels_pending_pair",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            point=_hud.Buttons["native-item-2"].GetGlobalRect().GetCenter();
            R15Touch(point,true);await InputDelay(500);R15Touch(point,false);await R27Tap("native-item-2");
            R27Check("long_hold_followed_by_one_tap_does_not_eat",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            await R27Tap("menu");await R27Tap("local-close");await R27Tap("native-item-2");
            R27Check("menu_closing_does_not_complete_old_double_tap",G4Character(p).Inventory.Single(i=>i.ItemId==10001).Amount==2);
            await R27Tap("save");await InputSettle();
            string final=p.Host.CharacterJson;await R15Return();await R15Continue(id);p=_play!;
            R27Check("normal_reopen_preserves_equipment_food_durability_and_progress",p.Host.CharacterJson==final&&G4Character(p).Equipment.Any(i=>i.ItemId==46001&&i.Dura==4567)&&G4Character(p).Level==8);
            R27Check("original_commits_and_runtime_remain_healthy",p.Host.LastSave.Committed&&!p.Faulted&&_fatal.Length==0);
            status="PASS_SCOPED_ACTUAL_TOUCH_MOUSE_ITEM_DETAILS_ACTIVATION_AND_SAVE";
        }
        catch(Exception e){error=e.ToString();try{await CaptureScreen("r27-failure");}catch(Exception){}}
        AtomicWrite(IO.Path.Combine(_root,"ko-checks.json"),JsonSerializer.Serialize(new{status,checks=_r27Checks,error,physical_android="NOT_RUN",scope="Actual Godot input on isolated synthetic copy, original Session actions and FULL SQLite."},new JsonSerializerOptions{WriteIndented=true}));
        WriteReport(IO.Path.Combine(_root,"r27-input-result.json"));await End(true);
    }
}
