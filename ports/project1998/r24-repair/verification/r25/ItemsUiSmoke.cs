using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using System.Text.RegularExpressions;
using IO = System.IO;

// Test-only partial: copied into an isolated desktop build, never the update APK.
public partial class Main
{
    private async Task R24Pick(string option)
    {
        await WaitUi(() => _play?.Capture().Dialog is { Kind: 2 } d && d.Options.Contains(option)
            && _hud.Buttons.TryGetValue("dialog-menu-1", out var b) && b.IsVisibleInTree(), "Rendered choice: " + option);
        var menu = _play!.Capture().Dialog!;
        await R15Hud("dialog-menu-" + (Array.IndexOf(menu.Options, option) + 1));
    }
    private async Task R24ClosePages()
    {
        for (int n = 0; n < 8 && _play!.Capture().Dialog is not null; n++)
        {
            var d = _play.Capture().Dialog!;
            if (d.Kind == 2) throw new InvalidOperationException("Unexpected open menu");
            await R15Hud(d.Next ? "dialog-next" : "dialog-cancel");
        }
        await WaitUi(() => _play!.Capture().Dialog is null, "Dialog did not close");
    }
    private async Task R24Use(int id)
    {
        int wire = G4Character(_play!).Inventory.First(i => i.ItemId == id).Slot + 1;
        await R15Hud("native-inventory");
        await R15Hud("native-item-" + wire);
        await R15Hud("use-" + wire);
    }
    private async Task R24Npc()
    {
        await R16TouchMuseumGuide(_play!, 360);
        await WaitUi(() => _hud.Buttons.TryGetValue("dialog-menu-1", out var b) && b.IsVisibleInTree(), "NPC menu presentation");
    }
    private void R24Vocabulary()
    {
        using var rules = JsonDocument.Parse(Godot.FileAccess.GetFileAsString("res://r24-translations.json"));
        KoCheck("r24_exact_70_new_translation_rules", rules.RootElement.GetArrayLength() == 70);
        foreach (var row in rules.RootElement.EnumerateArray())
        {
            string source = row.GetProperty("Source").GetString()!, target = row.GetProperty("Target").GetString()!;
            var names = row.GetProperty("Names").EnumerateArray().Select(v => v.GetInt32()).ToHashSet();
            int count = Regex.Matches(source, @"\{(\d+)\}").Select(m => int.Parse(m.Groups[1].Value) + 1).DefaultIfEmpty(0).Max();
            object[] values = Enumerable.Range(0, count).Select(i => (object)(names.Contains(i) ? "Cat" : (197 + i * 101).ToString())).ToArray();
            object[] expected = values.Select(v => v.Equals("Cat") ? (object)"고양이" : v).ToArray();
            string input = string.Format(System.Globalization.CultureInfo.InvariantCulture, source, values);
            string answer = string.Format(System.Globalization.CultureInfo.InvariantCulture, target, expected);
            string actual = KoreanText.Display(input);
            KoCheck("r24_translation_" + source, actual == answer && !actual.Contains('\ufffd'), new { input, answer, actual });
        }
        foreach (var item in Server.RecoveredItemContent.All.Items)
        {
            string raw = Server.Content.ItemById(item.Id)!.Name, display = KoreanText.Display(raw);
            KoCheck("r24_item_name_" + item.Id, !Regex.IsMatch(display, "[A-Za-z]{2,}")
                && !display.Contains('\ufffd') && display.Any(c => c >= '가' && c <= '힣'), new { raw, display });
        }
    }
    private async void BeginR24ItemsUiSmoke()
    {
        try
        {
            KoWrite("RUNNING");
            using var contract = JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root, "ko-contract.json")));
            string id = contract.RootElement.GetProperty("id").GetString()!;
            await R15Continue(id);
            KoCheck("r24_old_save_opens_byte_identically_before_test_fixture", R15Hash(_play!.Host.CharacterJson)
                == contract.RootElement.GetProperty("character_sha256").GetString());
            await R15Return();
            var store = new CharacterStore(IO.Path.Combine(_root, "state", "chars"));
            var saved = store.ReadOfflineSnapshot(id)!;
            var c = CharacterStore.Deserialize(saved.CharacterJson);
            var npc = Server.Content.NpcById(360)!;
            var map = Server.Content.Maps[npc.Map];
            c.Map = npc.Map; c.MapXs = map.Xs; c.MapYs = map.Ys; c.X = npc.X; c.Y = (ushort)(npc.Y + 1);
            c.Level = 99; c.Mark = 3; c.Might = 240; c.Grace = 100; c.Will = 100;
            c.Hp = c.MaxHp = 80000; c.Mp = c.MaxMp = 40000; c.Coins = 2000000; c.Mounted = false;
            c.RecoveredMountItemId = c.RecoveredFaceItemId = c.RecoveredHairItemId = c.RecoveredBeardItemId = c.RecoveredWeaponSkinId = c.RecoveredSkinBaseItemId = 0;
            c.Inventory.Clear(); c.Equipment.Clear();
            c.Equipment.Add(new InvItem(1, 46001, 1) { Dura = Server.Content.ItemById(46001)!.Durability });
            int[] seeded = { 17024, 17477, 17544, 18051, 16001, 4001, 99, 13009, 102 };
            for (byte n = 0; n < seeded.Length; n++) c.Inventory.Add(new InvItem(n, seeded[n], n == 7 ? 12 : 1));
            var receipt = store.SaveOfflineSnapshot(id, CharacterStore.Serialize(c), saved.ExtraJson, saved.RuntimeJson, saved.CaptureSequence + 1, saved.Revision);
            KoCheck("r24_synthetic_preconditions_only_in_isolated_copy", receipt.Committed,
                new { synthetic = "NPC360 position, level99, coins2000000, weapon and eight test item/material stacks; no natural progression or user-save modification claimed" });
            await R15Continue(id); var p = _play!;
            R24Vocabulary();
            await R24Npc(); await R24Pick("Recovered special items"); await KoPicture("r24-special-categories");
            await R24Pick("Mount items"); await KoPicture("r24-special-offers");
            string offer = p.Capture().Dialog!.Options.First(x => x.Contains("[item 15001]", StringComparison.Ordinal));
            uint coins = G4Character(p).Coins;
            await R24Pick(offer); await KoPicture("r24-buy-confirmation"); await R24Pick("Buy"); await R24ClosePages();
            KoCheck("r24_actual_shop_touch_buys_exact_mount_and_debits_once", G4Character(p).Inventory.Any(i => i.ItemId == 15001)
                && G4Character(p).Coins == coins - Server.RecoveredItemContent.Find(15001)!.Price);
            await R24Use(15001); KoCheck("r24_native_inventory_mount", G4Character(p).Mounted && p.Capture().Cosmetics.MountItemId == 15001);
            await KoPicture("r24-riding"); await R24Use(15001); KoCheck("r24_native_inventory_dismount", !G4Character(p).Mounted);
            await R24Use(17024); await R24Pick("Add materials");
            await WaitUi(() => p.Capture().Dialog?.Kind == 4 && _hud.FindChild("DialogInput", true, false) is LineEdit, "Container amount input");
            ((LineEdit)_hud.FindChild("DialogInput", true, false)).Text = "7";
            await KoPicture("r24-bag-amount"); await R15Hud("dialog-input");
            KoCheck("r24_native_container_deposit_keeps_total_material", G4Character(p).Inventory.Single(i => i.ItemId == 17024).Dura == 7
                && G4Character(p).Inventory.Single(i => i.ItemId == 13009).Amount == 5);
            await R24Use(17024); await R24Pick("Remove materials");
            await WaitUi(() => p.Capture().Dialog?.Kind == 4 && _hud.FindChild("DialogInput", true, false) is LineEdit, "Container withdrawal input");
            ((LineEdit)_hud.FindChild("DialogInput", true, false)).Text = "3"; await R15Hud("dialog-input");
            KoCheck("r24_native_container_withdrawal_keeps_total_material", G4Character(p).Inventory.Single(i => i.ItemId == 17024).Dura == 4
                && G4Character(p).Inventory.Single(i => i.ItemId == 13009).Amount == 8);
            foreach (int cosmetic in new[] {17477, 17544, 18051})
            {
                await R24Use(cosmetic); await KoPicture("r24-apply-" + cosmetic); await R24Pick("Apply");
                KoCheck("r24_actual_confirm_consumes_one_" + cosmetic, G4Character(p).Inventory.All(i => i.ItemId != cosmetic));
                await KoPicture("r24-applied-" + cosmetic);
            }
            await R24Use(16001); KoCheck("r24_native_weapon_overlay_uses_original_weapon", G4Character(p).RecoveredWeaponSkinId == 16001
                && G4Character(p).Equipment.Single(i => i.Slot == 1).ItemId == 46001);
            await KoPicture("r24-weapon-overlay");
            // Switch the actual weapon through the existing inventory GUI. The old skin is bound to
            // its previous item and must disappear from both captured presentation consumers.
            int saberWire=G4Character(p).Inventory.Single(i=>i.ItemId==102).Slot+1;
            await R15Hud("native-inventory");await R15Hud("native-item-"+saberWire);await R15Hud("equip-"+saberWire);
            KoCheck("r25_weapon_change_deactivates_previous_item_bound_skin",p.Capture().Cosmetics.WeaponIcon<0&&G4Character(p).Equipment.Single(i=>i.Slot==1).ItemId==102);
            await R24Use(16001);await R24Use(16001);
            KoCheck("r25_skin_can_be_applied_to_current_weapon",p.Capture().Cosmetics.WeaponSkinId==16001&&G4Character(p).RecoveredSkinBaseItemId==102);
            await R15Hud("native-equipment");await KoPicture("r25-native-blade-field-and-equipment");

            await R24Use(4001); await KoPicture("r24-map-guide"); await R24ClosePages();
            KoCheck("r24_guide_does_not_bypass_travel", p.Capture().Map == npc.Map);
            await R24Use(99); KoCheck("r24_detector_stays_in_inventory", G4Character(p).Inventory.Any(i => i.ItemId == 99));
            await R24Npc(); await R24Pick("Remove beard");
            KoCheck("r24_npc_shaves_beard", G4Character(p).RecoveredBeardItemId == 0);
            await R15Hud("save"); KoCheck("r24_manual_save_commits", p.Host.LastSave.Committed);
            string expectedHash = R15Hash(p.Host.CharacterJson);
            await R15Return(); await R15Continue(id); p = _play!;
            KoCheck("r24_reopen_exact_character_with_container_and_cosmetics", R15Hash(p.Host.CharacterJson) == expectedHash);
            KoCheck("r24_reopen_keeps_new_appearance_and_container", G4Character(p).RecoveredHairItemId == 17477
                && G4Character(p).RecoveredFaceItemId == 18051 && G4Character(p).RecoveredWeaponSkinId == 16001
                && G4Character(p).Inventory.Single(i => i.ItemId == 17024).Dura == 4);
            await KoPicture("r24-reopened"); KoCheck("r24_host_and_art_have_no_fault", !p.Faulted && _fatal.Length == 0 && _art.Missing.Count == 0);
            await R15Return();
            // Preserve the valid, closed UI save before the separate death test creates an
            // intentionally profile-less account. The public backup validator must reject
            // that later mixed fixture; it must not be weakened to make this test pass.
            string backup = IO.Path.Combine(_root, "r25-before-death-ui.zip");
            OfflineBackupStore.Create(_root, backup);
            KoCheck("r25_public_backup_captures_closed_actual_ui_save_before_isolated_death_fixture", IO.File.Exists(backup));
            await KoDeathMenuFixture(); KoWrite("PASS_SCOPED_R25_ACTUAL_UI_INPUT_SAVE_AND_REVIVE"); GetTree().Quit(0);
        }
        catch (Exception e)
        {
            KoWrite("FAIL", e); try { await KoPicture("failure"); } catch (Exception) { }
            GD.PushError(e.ToString()); GetTree().Quit(1);
        }
    }
}
