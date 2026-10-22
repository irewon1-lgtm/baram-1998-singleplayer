using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using IO=System.IO;

public partial class Main
{
    private async Task R29Hold(string key,bool cancel=false)
    {
        var point=_hud.Buttons[key].GetGlobalRect().GetCenter();R15Touch(point,true);await InputDelay(650);
        GetViewport().PushInput(new InputEventScreenTouch{Index=0,Position=point,Pressed=false,Canceled=cancel},true);await InputDelay(100);
    }
    private async void BeginR29GameplaySmoke()
    {
        string status="FAIL",error="";
        try
        {
            using var contract=JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root,"ko-contract.json")));string id=contract.RootElement.GetProperty("id").GetString()!;
            await R15Continue(id);await R15Return();
            var store=new CharacterStore(IO.Path.Combine(_root,"state","chars"));var saved=store.ReadOfflineSnapshot(id)!;var c=CharacterStore.Deserialize(saved.CharacterJson);
            c.Map=332;c.MapXs=Server.Content.Maps[332].Xs;c.MapYs=Server.Content.Maps[332].Ys;c.X=14;c.Y=7;c.Level=8;c.ClassName="Mage";
            c.Spells=Server.Content.Spells.Where(s=>!Server.Content.IsOutOfEraSplitTrap(s)).Take(14).Select(s=>s.Id).ToList();
            c.Equipment.Clear();foreach(byte slot in new byte[]{1,3}){var d=Server.Content.Items.First(d=>d.EquipSlot==slot);c.Equipment.Add(new(slot,d.Id,1,d.Durability));}
            R27Check("r29_isolated_original_full_seed",store.SaveOfflineSnapshot(id,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision).Committed);
            await R15Continue(id);await InputDelay(180);var p=_play!;
            R27Check("r29_actual_equipped_weapon_and_shield_have_cells",new byte[]{1,3}.All(slot=>_hud.Buttons.TryGetValue("native-equipment-slot-"+slot,out var b)&&b.IsVisibleInTree()&&b.TooltipText.Contains(KoreanText.Display(p.Capture().Equipment.Single(i=>i.WireSlot==slot).Name))));
            await CaptureScreen("r29-actual-equipment");
            await R27Tap("native-spells");var initial=G4Character(p);var order=initial.Spells.ToArray();
            await R29Hold("native-cast-1");
            R27Check("r29_actual_hold_does_not_cast_or_save",G4Character(p).Spells.SequenceEqual(order)&&G4Character(p).Mp==initial.Mp&&!_hud.ModalOpen);
            await R27Tap("native-cast-3");(order[0],order[2])=(order[2],order[0]);
            await WaitUi(()=>G4Character(p).Spells.SequenceEqual(order),"Actual original swapped spellbook");await InputSettle();
            R27Check("r29_actual_tap_reorders_original_saved_book",G4Character(p).Spells.SequenceEqual(order)&&p.Host.LastSave.Committed);
            R27Check("r29_actual_swap_preserves_mana_coins_inventory",G4Character(p).Mp==initial.Mp&&G4Character(p).Coins==initial.Coins&&G4Character(p).Inventory.Select(i=>(i.ItemId,i.Amount,i.Dura)).SequenceEqual(initial.Inventory.Select(i=>(i.ItemId,i.Amount,i.Dura))));
            await R29Hold("native-cast-1");await R27Tap("native-page-next");await R27Tap("native-cast-12");(order[0],order[11])=(order[11],order[0]);
            await WaitUi(()=>G4Character(p).Spells.SequenceEqual(order),"Cross page original swap");await InputSettle();
            R27Check("r29_actual_cross_page_long_hold_swap",G4Character(p).Spells.SequenceEqual(order));
            await CaptureScreen("r29-actual-skills-page2");
            await R27Tap("native-page-prev");await R29Hold("native-cast-2",true);
            R27Check("r29_actual_canceled_hold_does_not_mutate_book",G4Character(p).Spells.SequenceEqual(order)&&G4Character(p).Mp==initial.Mp);
            await R29Hold("native-cast-1");await R27Tap("menu");await R27Tap("local-close");
            R27Check("r29_menu_cancels_reorder_selection",_hud.FindChild("SpellSortHint",true,false) is Label hint&&!hint.Text.Contains("위치"));
            await R15Return();await R15Continue(id);p=_play!;await InputDelay(200);
            R27Check("r29_actual_order_survives_full_reopen",G4Character(p).Spells.SequenceEqual(order));
            R27Check("r29_actual_original_save_remains_healthy",p.Host.LastSave.Committed&&!p.Faulted&&_fatal.Length==0);
            status="PASS_ACTUAL_TOUCH_ORIGINAL_SPELL_SWAP_CROSS_PAGE_CANCEL_AND_REOPEN";
        }
        catch(Exception e){error=e.ToString();try{await CaptureScreen("r29-failure");}catch(Exception){}}
        AtomicWrite(IO.Path.Combine(_root,"ko-checks.json"),JsonSerializer.Serialize(new{status,checks=_r27Checks,error,physical_android="NOT_RUN"},new JsonSerializerOptions{WriteIndented=true}));
        WriteReport(IO.Path.Combine(_root,"r29-input-result.json"));await End(true);
    }
}
