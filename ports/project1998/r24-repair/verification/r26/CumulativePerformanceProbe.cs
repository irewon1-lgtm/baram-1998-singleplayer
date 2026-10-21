using System.Collections;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using P1998.Embedded;
using Server;
using Shared;

// Isolated synthetic growth fixture, not a copy of the user's character or physical-device evidence.
static class CumulativePerformanceProbe
{
    static readonly JsonSerializerOptions Json = new() { WriteIndented = true };
    static T Field<T>(object value, string name) => (T)value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(value)!;
    static object Cache()
    {
        var cache = (IDictionary)typeof(MapData).GetField("Cache", BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
        long cells = cache.Values.Cast<MapData?>().Where(m => m is not null).Sum(m => (long)m!.Xs * m.Ys);
        return new { maps = cache.Count, terrain_cells = cells, minimum_array_bytes = cells * 6 };
    }
    static object WorldSize(World world)
    {
        var data = JsonSerializer.Deserialize<World.OfflineState>(world.CaptureOfflineStateJson())!;
        return new { materialized_maps = data.Population.Maps.Length, creature_maps = data.Creatures!.Maps.Length,
            retained_monsters = data.Creatures.Maps.Sum(m => m.Mobs.Length), floor_items = data.Floor!.Maps.Sum(m => m.Items.Length) };
    }
    static object Memory()
    {
        using var process = Process.GetCurrentProcess(); process.Refresh();
        return new { rss_bytes = process.WorkingSet64, peak_rss_bytes = process.PeakWorkingSet64,
            private_bytes = process.PrivateMemorySize64, managed_bytes = GC.GetTotalMemory(false),
            gc0 = GC.CollectionCount(0), gc1 = GC.CollectionCount(1), gc2 = GC.CollectionCount(2) };
    }
    static async Task<int> Main(string[] a)
    {
        string root = a[1], mode = a[3]; int history = int.Parse(a[4]); byte level = byte.Parse(a[5]);
        var options = new HostOptions(root, a[0], "growthprobe", "Synthetic26!", "growthprobe", mode == "prepare", false);
        if (mode == "prepare")
        {
            var play = await PlaySession.OpenAsync(options);
            var world = Field<World>(play.Host, "_world"); var session = Field<Session>(play.Host, "_session");
            var visited = Field<HashSet<ushort>>(play.Host, "_visitedMaps");
            ushort[] ids = Content.Spawns.Select(s => s.Map).Concat(Content.AreaSpawns.Select(s => s.Map)).Distinct().Order()
                .Where(id => id != play.Model.Map && id != 330 && Content.Maps.ContainsKey(id)).Take(history).ToArray();
            foreach (ushort id in ids) { world.EnterMap(session, id); world.LeaveMap(session, id); visited.Add(id); }
            // Empty historical visits exercise the old eager terrain restore separately from population.
            foreach (ushort id in Content.Maps.Keys.Order().Where(id => id != play.Model.Map && id != 330).Take(history)) visited.Add(id);
            await play.StopAsync();
            var store = new CharacterStore(Path.Combine(root, "chars")); var stored = store.ReadOfflineSnapshot("growthprobe")!;
            var c = CharacterStore.Deserialize(stored.CharacterJson); var map = Content.Maps[330];
            c.Map = 330; c.MapXs = map.Xs; c.MapYs = map.Ys; c.X = 110; c.Y = 139; c.Level = level;
            c.Hp = c.MaxHp = 50000; c.Mp = c.MaxMp = 50000; c.Coins = 123456; c.BankMoney = 654321;
            c.Quests["r26_performance_fixture"] = 7;
            var save = store.SaveOfflineSnapshot(c.Name, CharacterStore.Serialize(c), stored.ExtraJson, stored.RuntimeJson,
                stored.CaptureSequence + 1, stored.Revision);
            if (!save.Committed) throw new IOException(save.Error);
            File.WriteAllText(a[2], JsonSerializer.Serialize(new { status = "PASS_SYNTHETIC_FIXTURE", level, requested_history = history,
                original_materialization_calls = ids.Length, note = "Test fixture stages normal original map populations; no user save is modified and this is not an assertion of natural progression." }, Json));
            return 0;
        }
        var startMemory = Memory(); long allocated = GC.GetTotalAllocatedBytes();
        using var cpu = Process.GetCurrentProcess(); TimeSpan cpuStart = cpu.TotalProcessorTime;
        var cold = Stopwatch.StartNew(); var sessionPlay = await PlaySession.OpenAsync(options); cold.Stop();
        var host = sessionPlay.Host; var worldNow = Field<World>(host, "_world");
        var coldMemory = Memory(); var coldCache = Cache(); var size = WorldSize(worldNow);
        var storeNow = new CharacterStore(Path.Combine(root, "chars")); var initial = storeNow.ReadOfflineSnapshot(options.InternalId)!;
        var originalCharacter = CharacterStore.Deserialize(initial.CharacterJson);
        var current = sessionPlay.Capture(); var terrain = MapData.For((ushort)current.Map)!;
        int direction = Enumerable.Range(0, 4).First(d => !terrain.BlockedMove(current.X + (d == 1 ? 1 : d == 3 ? -1 : 0),
            current.Y + (d == 2 ? 1 : d == 0 ? -1 : 0), d));
        var samples = new List<object>(); var totals = new List<double>();
        int completed = 0, moved = 0; long actionsAllocationStart = GC.GetTotalAllocatedBytes();
        TimeSpan actionsCpu = cpu.TotalProcessorTime; int[] gcStart = { GC.CollectionCount(0), GC.CollectionCount(1), GC.CollectionCount(2) };
        var actionSpan = Stopwatch.StartNew();
        for (int n = 0; n < 160; n++)
        {
            int oldX = sessionPlay.Model.X, oldY = sessionPlay.Model.Y;
            var timer = Stopwatch.StartNew();
            var result = n % 4 == 0 ? await sessionPlay.AttackAsync() : n % 4 == 1 ? await sessionPlay.TurnAsync(direction)
                : await sessionPlay.StepAsync(n % 4 == 2 ? direction : (direction + 2) % 4);
            timer.Stop(); if (!result.Committed) throw new IOException(result.Error); completed++;
            if (oldX != sessionPlay.Model.X || oldY != sessionPlay.Model.Y) moved++;
            totals.Add(timer.Elapsed.TotalMilliseconds);
            if (n % 8 == 7)
            {
                Field<Session>(host, "_session").RunEmbeddedWork(worldNow.TickOffline);
                // CPU/GC observations include settled original ticks, not a clock-sped game claim.
            }
            samples.Add(new { n, elapsed_ms = timer.Elapsed.TotalMilliseconds, action = n % 4 == 0 ? "attack" : n % 4 == 1 ? "turn" : "walk" });
        }
        actionSpan.Stop();
        var actionMemory = Memory(); var after = CharacterStore.Deserialize(host.CharacterJson);
        var stages = host.InputStages.ToArray(); var sessionCpu = cpu.TotalProcessorTime - cpuStart;
        var actionsCpuMs = (cpu.TotalProcessorTime - actionsCpu).TotalMilliseconds;
        long actionAllocation = GC.GetTotalAllocatedBytes() - actionsAllocationStart;
        bool retained = after.Level == level && after.Coins == originalCharacter.Coins && after.BankMoney == originalCharacter.BankMoney
            && after.Quests.GetValueOrDefault("r26_performance_fixture") == 7
            && originalCharacter.Inventory.All(item => after.Inventory.Any(found => JsonSerializer.Serialize(item, new JsonSerializerOptions { IncludeFields = true }) == JsonSerializer.Serialize(found, new JsonSerializerOptions { IncludeFields = true })))
            && JsonSerializer.Serialize(after.Equipment) == JsonSerializer.Serialize(originalCharacter.Equipment)
            && after.Spells.SequenceEqual(originalCharacter.Spells);
        var finalWorld = WorldSize(worldNow); await sessionPlay.StopAsync();
        var committed = storeNow.ReadOfflineSnapshot(options.InternalId)!;
        using var connection = new SqliteConnection("Data Source=" + Path.Combine(root, "project1998.db")); connection.Open();
        using var integrity = connection.CreateCommand(); integrity.CommandText = "PRAGMA integrity_check";
        bool intact = (string?)integrity.ExecuteScalar() == "ok";
        totals.Sort();
        var report = new { status = retained && intact && completed == 160 && moved > 0 ? "PASS_SCOPED_HOST" : "FAIL", level, requested_history = history,
            map = 330, cold_open_ms = cold.Elapsed.TotalMilliseconds, cold_cpu_ms = sessionCpu.TotalMilliseconds - actionsCpuMs,
            coldCache, world = size, final_world = finalWorld, startMemory, coldMemory, actionMemory,
            input = new { completed, moved, actions_wall_ms = actionSpan.Elapsed.TotalMilliseconds, actions_cpu_ms = actionsCpuMs,
                allocated_bytes = actionAllocation, allocated_per_action = actionAllocation / completed,
                gc_collections = Enumerable.Range(0, 3).Select(i => GC.CollectionCount(i) - gcStart[i]).ToArray(),
                median_ms = totals[totals.Count / 2], p95_ms = totals[(int)(totals.Count * .95)], max_ms = totals[^1], samples, stages },
            save = new { character_utf8_bytes = System.Text.Encoding.UTF8.GetByteCount(committed.CharacterJson),
                world_utf8_bytes = System.Text.Encoding.UTF8.GetByteCount(committed.ExtraJson),
                database_bytes = new FileInfo(Path.Combine(root, "project1998.db")).Length, committed.Revision,
                commits_during_actions_and_teardown = committed.Revision - initial.Revision },
            preserved_progress_inventory_equipment_spells = retained, integrity = intact,
            session_allocated_bytes = GC.GetTotalAllocatedBytes() - allocated,
            physical_android = "NOT_RUN", heat = "NOT_RUN", existing_user_profile = "NOT_AVAILABLE_SYNTHETIC_HISTORY_ONLY",
            scope = "Fresh OS process, normal host creation/reopen, same Buya330 coordinate, original input and ticks and FULL SQLite commits. This is an unpaced CPU/latency stress workload, not physical FPS/thermal proof." };
        File.WriteAllText(a[2], JsonSerializer.Serialize(report, Json));
        return retained && intact && moved > 0 ? 0 : 1;
    }
}
