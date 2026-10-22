using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using Protocol.Tk495;
using Server;
using Shared;

static class BagProbe
{
    private sealed class Output : IOutbound
    {
        public string Remote => "R24_PUBLIC_CONTAINER_FIXTURE";
        public int Capacity => int.MaxValue;
        public int QueueDepth => 0;
        public byte[]? Prompt;
        public int Generation;
        public bool Send(byte[] frame)
        {
            if (TkPacket.TryParse(frame, out var packet, out _) && packet.Opcode == ServerOp.NpcDialog)
            {
                Prompt = TkCrypt.Crypt(packet.Body, packet.Increment, TkCrypt.LoginKey);
                Generation++;
            }
            return true;
        }
        public void Close() { }
    }

    private static readonly List<object> Checks = new();
    private static bool Failed;
    private static Session S = null!;
    private static Output O = null!;
    private static CharacterStore Store = null!;
    private static World W = null!;
    private static string State = "";
    private static int Number;
    private sealed record BagCase(int Id, int Content, uint Capacity, int Shell);
    // Independent literal source table from the byte-checked RTK scripts and Items.csv;
    // expected outcomes never read RecoveredItemContent's implementation rules.
    private static readonly BagCase[] Cases = {
        new(17024,13009,500,17013),new(17025,13053,500,17013),new(17026,13049,500,17013),
        new(17027,13010,500,17013),new(17028,13052,500,17013),new(17029,13011,100,17013),
        new(17030,13050,100,17013),new(17031,13046,100,17013),new(17032,13013,100,17013),
        new(17033,13051,100,17013),new(17034,13047,100,17013),new(17035,13001,125,17012),
        new(17036,13020,125,17022),new(17037,13021,125,17022),new(17038,13022,125,17022),
        new(17039,13033,125,17022),new(17040,13040,150,17020),new(17041,13014,100,17015),
        new(17042,13015,100,17015),new(17043,10015,100,17018),new(17044,10041,100,17018),
        new(17045,10011,100,17018),new(17046,10027,60,17018),new(17047,13018,110,17021),
        new(17048,13017,110,17021),new(17049,10068,50,17017),new(17050,10069,50,17017),
        new(17051,10067,50,17017),new(17052,10071,50,17017),new(17053,10070,50,17017),
        new(17054,10072,50,17017),new(17055,13048,500,17013)
    };
    private static readonly HashSet<int> CoveredBags = new(), CoveredShells = new();
    private static Character Live => CharacterStore.Deserialize(S.CaptureOfflineCharacterJson());
    private static void Check(string name, bool ok, object? detail = null)
    {
        Checks.Add(new { name, status = ok ? "PASS" : "FAIL", observed = detail });
        Failed |= !ok;
    }
    private static void Act(byte opcode, byte[] body)
    {
        var action = S.ExecuteOfflineAction(
            () => S.Receive(TkPacket.Build(opcode, 0, TkCrypt.Crypt(body, 0, TkCrypt.LoginKey))), _ => { });
        if (!action.Committed) throw new Exception("Original action was not committed: " + action.Error);
    }
    private static void Init(Action<Character> setup, bool atBank = false)
    {
        if (S is not null) { S.StopOffline(); S.EndEmbeddedSessionAsync().GetAwaiter().GetResult(); }
        O = new();
        string folder = Path.Combine(State, "case" + ++Number);
        Directory.CreateDirectory(folder);
        Store = CharacterStore.ForDatabase(Path.Combine(folder, "legacy"), Path.Combine(folder, "probe.db"));
        var bank = atBank ? Content.Npcs.First(npc => npc.Enabled && npc.Bank) : null;
        ushort mapId = bank?.Map ?? 0;
        var map = Content.Maps[mapId];
        var c = new Character
        {
            SchemaVersion = Character.CurrentSchemaVersion, Id = W.AllocatePlayerId(), Name = "bag" + Number,
            Map = mapId, MapXs = map.Xs, MapYs = map.Ys,
            X = bank?.X ?? 50, Y = bank is null ? (ushort)50 : (ushort)Math.Min(map.Ys - 1, bank.Y + 1),
            Level = 99, Mark = 5, Sex = 0, Might = 240, Hp = 50000, MaxHp = 50000,
            Mp = 20000, MaxMp = 20000, Coins = 1000000
        };
        setup(c);
        S = new Session(O, 2005, Store, W, c);
        S.EnableOfflineLifecycle(); S.EnableOfflinePersistence(); W.EnterMap(S, c.Map);
        if (!S.OfflineFlush("Synthetic container and material fixture only").Committed)
            throw new Exception("Initial fixture save did not commit.");
    }
    private static string[] Options()
    {
        var prompt = O.Prompt;
        if (prompt is null || prompt[0] != 2) return Array.Empty<string>();
        int at = 23 + BinaryPrimitives.ReadUInt16BigEndian(prompt.AsSpan(21));
        int count = prompt[at++];
        var options = new List<string>();
        for (int i = 0; i < count; i++)
        {
            int length = prompt[at++];
            options.Add(Encoding.ASCII.GetString(prompt, at, length)); at += length;
        }
        return options.ToArray();
    }
    private static void Use(int slot = 0)
    {
        O.Prompt = null;
        Act(ClientOp.UseItem, new[] { (byte)(slot + 1) });
    }
    private static void Pick(string option)
    {
        var options = Options(); int index = Array.IndexOf(options, option) + 1;
        if (index == 0) throw new Exception("Missing dialog option '" + option + "': " + string.Join("|", options));
        var body = new byte[12]; body[0] = 2; body[8] = 2; body[10] = (byte)index;
        Act(ClientOp.NpcDialog, body);
    }
    private static void Input(string text)
    {
        var bytes = Encoding.ASCII.GetBytes(text);
        var body = new byte[11 + bytes.Length]; body[0] = 4; body[8] = 2; body[10] = (byte)bytes.Length;
        bytes.CopyTo(body, 11); Act(ClientOp.NpcDialog, body);
    }
    private static void Cancel(bool input = false)
    {
        var body = new byte[12]; body[0] = input ? (byte)4 : (byte)2;
        body[8] = input ? (byte)0 : (byte)2;
        Act(ClientOp.NpcDialog, body);
    }
    private static int Count(int id) => Live.Inventory.Where(item => item.ItemId == id).Sum(item => item.Amount);
    private static uint Stored(int id) => Live.Inventory.Single(item => item.ItemId == id).Dura;
    private static string Inventory()
    {
        var live = Live;
        return JsonSerializer.Serialize(new { live.MaxInv, items = live.Inventory.OrderBy(item => item.Slot)
            .Select(item => new { item.Slot, item.ItemId, item.Amount, item.Dura, item.Owner,
                item.CustomName, item.Repair, item.Protected }) });
    }
    private static void Save(string label)
    {
        string expected = S.CaptureOfflineCharacterJson();
        Check(label + "_sqlite_commit", S.OfflineFlush(label).Committed
            && Store.ReadOfflineSnapshot(Live.Name)?.CharacterJson == expected);
    }
    private static void Reopen(string label)
    {
        string expectedInventory = Inventory(), user = Live.Name;
        S.StopOffline(); S.EndEmbeddedSessionAsync().GetAwaiter().GetResult();
        var loaded = Store.Load(user).Character ?? throw new Exception("Saved character could not be loaded.");
        O = new(); S = new Session(O, 2005, Store, W, loaded);
        S.EnableOfflineLifecycle(); S.EnableOfflinePersistence(); W.EnterMap(S, loaded.Map);
        Check(label + "_fresh_session_from_sqlite", Inventory() == expectedInventory);
    }
    private static void Speak(string text)
    {
        byte[] message = Encoding.ASCII.GetBytes(text);
        Act(ClientOp.Chat, new[] { (byte)0, (byte)message.Length }.Concat(message).ToArray());
    }
    private static void Transfer(string operation, int amount)
    {
        Use(); Pick(operation); Input(amount.ToString(System.Globalization.CultureInfo.InvariantCulture));
    }
    private static void Tracer()
    {
        // Independent source facts: amber_bag17024 contains amber13009, maxDura500,
        // and is an empty portable container when its actual instance Dura is0.
        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1, 0), new InvItem(1, 13009, 10) });
        Use();
        bool menu = Options().Contains("Add materials") && Options().Contains("Remove materials");
        Check("empty_typed_amber_bag_opens_real_add_remove_menu", menu, Options());
        if (!menu) return;
        Pick("Add materials"); Input("5");
        var actual = Live;
        Check("deposit_moves_five_ambers_into_existing_instance_dura",
            actual.Inventory.Single(x => x.ItemId == 17024).Dura == 5
            && actual.Inventory.Where(x => x.ItemId == 13009).Sum(x => x.Amount) == 5
            && actual.MaxInv == 27, actual.Inventory.Select(x => new { x.ItemId, x.Amount, x.Dura }));
        string expected = S.CaptureOfflineCharacterJson();
        Check("deposit_survives_actual_sqlite_roundtrip",
            S.OfflineFlush("Container deposit").Committed
            && Store.ReadOfflineSnapshot(actual.Name)?.CharacterJson == expected);
    }
    private static void ContainerCase(BagCase bag)
    {
        Init(c => c.Inventory = new() { new InvItem(0, bag.Id, 1, 0), new InvItem(1, bag.Content, 10) }, atBank: true);
        Transfer("Add materials", 5);
        bool added = Count(bag.Id) == 1 && Stored(bag.Id) == 5 && Count(bag.Content) == 5 && Live.MaxInv == 27;
        Check("source_container_deposit_" + bag.Id, added);
        if (!added) return;
        CoveredBags.Add(bag.Id);
        Transfer("Remove materials", 2);
        Check("source_container_partial_withdraw_" + bag.Id, Stored(bag.Id) == 3 && Count(bag.Content) == 7);
        Transfer("Remove materials", 3);
        Check("emptying_converts_same_slot_to_source_shell_" + bag.Id,
            Count(bag.Id) == 0 && Count(bag.Shell) == 1 && Stored(bag.Shell) == 0
            && Live.Inventory.Single(item => item.ItemId == bag.Shell).Slot == 0 && Count(bag.Content) == 10);
        Use(); Pick("Add materials"); Pick(Content.ItemById(bag.Content)!.Name); Input("4");
        bool filled = Count(bag.Id) == 1 && Stored(bag.Id) == 4 && Count(bag.Shell) == 0
            && Count(bag.Content) == 6 && Live.Inventory.Single(item => item.ItemId == bag.Id).Slot == 0;
        Check("source_shell_selects_exact_quality_" + bag.Id, filled);
        if (filled) CoveredShells.Add(bag.Shell);
        Save("filled_" + bag.Id); Reopen("filled_" + bag.Id);
        string beforeDrop = Inventory();
        Act(ClientOp.DropItem, new byte[] { 1, 1 });
        if (Content.ItemById(bag.Id)!.NoDrop)
            Check("original_no_drop_preserves_container_" + bag.Id, Inventory() == beforeDrop);
        else
        {
            Check("source_droppable_container_leaves_inventory_" + bag.Id, Count(bag.Id) == 0);
            Act(ClientOp.Pickup, new byte[] { 0 });
            Check("source_droppable_container_pickup_preserves_count_" + bag.Id, Stored(bag.Id) == 4);
        }
        string name = Content.ItemById(bag.Id)!.Name;
        Speak("take my " + name);
        bool banked = Count(bag.Id) == 0 && Live.BankItems.Any(item => item.ItemId == bag.Id && item.Dura == 4);
        Check("original_spoken_bank_deposit_preserves_dura_" + bag.Id, banked);
        if (!banked) return;
        Save("banked_" + bag.Id); Reopen("banked_" + bag.Id);
        Speak("give my " + name + " back");
        Check("original_spoken_bank_withdraw_preserves_dura_" + bag.Id,
            Count(bag.Id) == 1 && Stored(bag.Id) == 4 && Live.BankItems.All(item => item.ItemId != bag.Id));
        Transfer("Remove materials", 1);
        Check("reopened_and_withdrawn_container_remains_usable_" + bag.Id,
            Stored(bag.Id) == 3 && Count(bag.Content) == 7);
        Save("reused_" + bag.Id);
        Init(c => c.Inventory = new() { new InvItem(0, bag.Id, 1, bag.Capacity - 1), new InvItem(1, bag.Content, 2) });
        string boundary = Inventory(); Transfer("Add materials", 2);
        Check("source_capacity_overflow_refuses_entire_deposit_" + bag.Id, Inventory() == boundary,
            new { source_capacity = bag.Capacity, stored = Stored(bag.Id) });
        Transfer("Add materials", 1);
        Check("source_capacity_exact_last_unit_is_accepted_" + bag.Id,
            Stored(bag.Id) == bag.Capacity && Count(bag.Content) == 1);
        string exactlyFull = Inventory(); Use(); Pick("Add materials"); Input("1");
        Check("source_capacity_full_container_refuses_extra_unit_" + bag.Id, Inventory() == exactlyFull);
    }
    private static void EdgeCases()
    {
        foreach (string quantity in new[] { "0", "-1", "abc", "2147483647", "99999999999999999999" })
        {
            Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10) });
            string before = Inventory(); Use(); Pick("Add materials"); Input(quantity);
            Check("invalid_or_unfillable_amount_keeps_every_instance_" + quantity, Inventory() == before);
        }
        foreach (bool input in new[] { false, true })
        {
            Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10) });
            string before = Inventory(); Use(); if (input) Pick("Add materials"); Cancel(input);
            Check("cancel_" + (input ? "amount" : "menu") + "_is_lossless", Inventory() == before);
        }
        foreach (uint stored in new uint[] { 0, 499, 500 })
        {
            Init(c => c.Inventory = new() { new InvItem(0, 17024, 1, stored), new InvItem(1, 13009, 10) });
            string before = Inventory(); Use(); Pick(stored == 0 ? "Remove materials" : "Add materials");
            if (stored == 499) Input("2");
            Check("empty_full_or_over_capacity_refusal_" + stored, Inventory() == before);
        }
        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 1) });
        string insufficient = Inventory(); Transfer("Add materials", 2);
        Check("insufficient_material_does_not_partially_deposit", Inventory() == insufficient);

        Init(c => { c.MaxInv = 2; c.Inventory = new() { new InvItem(0, 17024, 1, 5), new InvItem(1, 13001, 1) }; });
        string full = Inventory(); Transfer("Remove materials", 5);
        Check("full_inventory_withdraw_keeps_filled_container_and_shell_identity", Inventory() == full);

        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1, 5), new InvItem(1, 13009, 99) });
        int totalBefore=Count(13009)+(int)Stored(17024);Transfer("Remove materials",1);
        Check("offline_99_limit_spills_without_losing_material_or_contents",Count(13009)==100&&Stored(17024)==4
            &&Live.Inventory.Where(i=>i.ItemId==13009).OrderBy(i=>i.Slot).Select(i=>i.Amount).SequenceEqual(new[]{99,1})
            &&Count(13009)+(int)Stored(17024)==totalBefore);

        foreach (string metadata in new[] { "name", "owner", "dura", "protection", "repair" })
        {
            Init(c =>
            {
                var material = new InvItem(1, 13009, 10);
                if (metadata == "name") material.CustomName = "preserve me";
                if (metadata == "owner") material.Owner = "anotherplayer";
                if (metadata == "dura") material.Dura = 7;
                if (metadata == "protection") material.Protected = 1;
                if (metadata == "repair") material.Repair = 1;
                c.Inventory = new() { new InvItem(0, 17024, 1), material };
            });
            string before = Inventory(); Use(); Pick("Add materials");
            Check("material_" + metadata + "_metadata_is_not_destroyed_by_storage", Inventory() == before);
        }
        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1) { Owner = "anotherplayer" }, new InvItem(1, 13009, 10) });
        string owned = Inventory(); Use();
        Check("another_players_container_cannot_be_used", Inventory() == owned && O.Prompt is null);

        Init(c => c.Inventory = new()
        {
            new InvItem(0, 17024, 1), new InvItem(1, 13009, 5),
            new InvItem(2, 13009, 5) { CustomName = "preserve named half" }
        });
        string mixed = Inventory(); Transfer("Add materials", 10);
        Check("mixed_plain_and_named_materials_do_not_partially_deposit", Inventory() == mixed);

        Init(c => c.Inventory = new()
        {
            new InvItem(0, 17024, 1), new InvItem(1, 13009, 10),
            new InvItem(2, 17025, 1), new InvItem(3, 13053, 10)
        });
        Use(); Pick("Add materials"); Act(ClientOp.UseItem, new byte[] { 3 }); Input("5");
        Check("second_container_use_does_not_orphan_first_amount_prompt",
            Stored(17024) == 5 && Count(13009) == 5 && Stored(17025) == 0 && Count(13053) == 10);
        string once = Inventory(); Input("5");
        Check("duplicate_completed_amount_reply_cannot_duplicate_materials", Inventory() == once);

        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10), new InvItem(2, 13001, 1) });
        Use(); Pick("Add materials"); Act(ClientOp.ChangePos, new byte[] { 0, 1, 3 });
        string swapped = Inventory(); Input("5");
        Check("stale_amount_reply_after_real_slot_swap_keeps_every_instance", Inventory() == swapped);

        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10) });
        Use(); Pick("Add materials"); Act(ClientOp.DropItem, new byte[] { 2, 1 });
        Check("original_droppable_material_is_actually_dropped", Count(13009) == 0);
        Input("5"); Check("stale_amount_after_material_drop_does_not_fabricate_contents", Stored(17024) == 0);
        Act(ClientOp.Pickup, new byte[] { 0 });
        Check("actual_pickup_returns_dropped_material_without_duplication", Count(13009) == 10 && Stored(17024) == 0);

        Init(c => c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10), new InvItem(2, 15001, 1) });
        Use(); Pick("Add materials"); Act(ClientOp.UseItem, new byte[] { 3 });
        Check("original_mount_use_changes_state_while_amount_is_pending", Live.Mounted);
        string mounted = Inventory(); Input("5");
        Check("mounted_stale_reply_does_not_transfer_materials", Inventory() == mounted && Stored(17024) == 0);

        Init(c => { c.Hp = 0; c.Inventory = new() { new InvItem(0, 17024, 1), new InvItem(1, 13009, 10) }; });
        string dead = Inventory(); Use();
        Check("dead_character_cannot_start_container_transfer", Inventory() == dead && O.Prompt is null);

        var amberVariants = Cases.Where(bag => bag.Shell == 17013).ToArray();
        Init(c =>
        {
            c.Inventory.Add(new InvItem(0, 17013, 1));
            for (int i = 0; i < amberVariants.Length; i++)
                c.Inventory.Add(new InvItem((byte)(i + 1), amberVariants[i].Content, 2));
        });
        Use(); Pick("Add materials");
        Check("amber_shell_first_quality_page_is_bounded", Options().Length <= 9 && Options().Contains("Next page"), Options());
        Pick("Next page");
        Check("amber_shell_second_quality_page_is_bounded", Options().Length <= 9 && Options().Contains("Previous page"), Options());
        Pick(Content.ItemById(13048)!.Name); Input("1");
        Check("paged_shell_quality_selects_well_crafted_dark_amber_exactly",
            Count(17055) == 1 && Stored(17055) == 1 && Count(13048) == 1
            && amberVariants.Where(bag => bag.Content != 13048).All(bag => Count(bag.Content) == 2));
    }
    private static void RunAll()
    {
        foreach (var bag in Cases)
            try { ContainerCase(bag); }
            catch (Exception error) { Check("container_execution_" + bag.Id, false, error.ToString()); }
        Check("all_32_source_container_ids_executed", CoveredBags.Count == 32, CoveredBags.OrderBy(id => id));
        Check("all_8_source_empty_shell_ids_executed", CoveredShells.Count == 8, CoveredShells.OrderBy(id => id));
        EdgeCases();
    }
    private static int Main(string[] args)
    {
        Environment.SetEnvironmentVariable("P1998_GAME_DATA", args[0]);
        Environment.SetEnvironmentVariable("P1998_STATE", State = args[1]);
        Directory.CreateDirectory(State);
        try
        {
            Content.Load(); NpcScript.Load(Path.Combine(args[0], "npc_dialog.lua"));
            var clock = new GameClock(); clock.Resume(); W = new World(clock);
            if (args.Length > 3 && args[3] == "all") RunAll(); else Tracer();
        }
        catch (Exception error) { Check("execution", false, error.ToString()); }
        finally { if (S is not null) { S.StopOffline(); S.EndEmbeddedSessionAsync().GetAwaiter().GetResult(); } }
        File.WriteAllText(args[2], JsonSerializer.Serialize(new
        {
            status = Failed ? "FAIL" : "PASS_PUBLIC_CONTAINER_USE_TRANSFER_AND_SAVE", checks = Checks,
            unique_container_ids = CoveredBags.Count, unique_empty_shell_ids = CoveredShells.Count,
            physical_android = "NOT_RUN",
            fixture = "Synthetic prerequisites only; actual Session.Receive/ExecuteOfflineAction and CharacterStore SQLite boundaries. No private invocation or mocks."
        }, new JsonSerializerOptions { WriteIndented = true }));
        return Failed ? 1 : 0;
    }
}
