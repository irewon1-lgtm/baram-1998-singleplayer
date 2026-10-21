using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Data.Sqlite;
using Server;
using Shared;

Environment.SetEnvironmentVariable("P1998_GAME_DATA", args[0]); Environment.SetEnvironmentVariable("P1998_STATE", args[1]);
Directory.CreateDirectory(args[1]); Content.Load(); var checks = new List<object>(); bool failed = false;
void Check(string name, bool pass, object? evidence = null) { checks.Add(new { name, status = pass ? "PASS" : "FAIL", evidence }); failed |= !pass; }
long mono = 0; var clock = new GameClock(monotonicMs: () => mono); var world = new World(clock);
world.BindRestoredOfflineOwner("stableowner", 123);
var item = new GroundItem { Id = world.AllocateItemId(), ItemId = Content.ItemByKey("acorn")!.Id, X = 5, Y = 6,
    Amount = 17, Dura = 712, Graphic = 214, CustomName = "continuity fixture", Owner = "stableowner",
    LooterId = 123, LockedUntil = Environment.TickCount64 + 300000, Repair = 2, Protected = 3 };
world.DropItem(4711, item);
var mob = new Mob(world.AllocateMobId(), 1, 8, 9, "continuity", 100) { Hp = 63, HomeX = 8, HomeY = 9,
    OwnerId = 123, TargetId = 123, PoisonOwnerId = 123, PoisonUntil = 1000, Handed = new() { new InvItem(0, item.ItemId, 5) } };
world.AddMob(4711, mob);
string saved = world.CaptureOfflineStateJson(); long restartMono = 1000000;
var restartedClock = new GameClock(monotonicMs: () => restartMono); var restarted = new World(restartedClock);
restarted.RestoreOfflineStateJson(saved); restarted.BindRestoredOfflineOwner("stableowner", 456);
var floor = restarted.ItemsOn(4711).Single();
Check("stable_floor_owner_rebound_without_numeric_id_reuse", floor.LooterId == 456 && floor.BelongsTo(456) && floor.LockedAgainst(123));
Check("all_item_payload_fields_preserved", floor.Id == item.Id && floor.ItemId == item.ItemId && floor.Amount == 17 && floor.Dura == 712
    && floor.Graphic == 214 && floor.CustomName == item.CustomName && floor.Owner == item.Owner && floor.Repair == 2 && floor.Protected == 3);
var state = JsonSerializer.Deserialize<World.OfflineState>(restarted.CaptureOfflineStateJson())!;
var creature = state.Creatures!.Maps.Single(m => m.Map == 4711).Mobs.Single();
var restoredMob = creature.Data.Deserialize<Mob>(new JsonSerializerOptions { IncludeFields = true })!;
Check("creature_damage_owner_poison_and_handed_item_preserved", restoredMob.Hp == 63 && creature.OwnerId == 456
    && restoredMob.PoisonOwnerId == 456 && restoredMob.Handed!.Single().Amount == 5);
long remaining = state.Floor!.Maps.Single().Items.Single().LockRemainingMilliseconds;
restartMono += 900000000; Check("paused_reboot_time_does_not_consume_item_reservation", floor.LockedAgainst(123));
restartedClock.Resume(); restartMono += remaining - 1; Check("reservation_remains_until_last_active_millisecond", floor.LockedAgainst(123));
restartMono++; Check("reservation_expires_after_active_time", !floor.LockedAgainst(123));

// A real r25 writer produced this saved fixture; it fails the original strict reader at room4164.
using var connection = new SqliteConnection("Data Source=" + args[3] + ";Mode=ReadOnly"); connection.Open();
using var command = connection.CreateCommand(); command.CommandText = "SELECT extra_json FROM offline_snapshots WHERE username='growthprobe'";
string previous = (string)command.ExecuteScalar()!; var oldNode = JsonNode.Parse(previous)!.AsObject();
var recovered = new World(new GameClock()); recovered.RestoreOfflineStateJson(previous);
var newNode = JsonNode.Parse(recovered.CaptureOfflineStateJson())!.AsObject();
int oldCount = oldNode["Creatures"]!["Maps"]!.AsArray().Sum(m => m!["Mobs"]!.AsArray().Count);
int newCount = newNode["Creatures"]!["Maps"]!.AsArray().Sum(m => m!["Mobs"]!.AsArray().Count);
var room = newNode["Creatures"]!["Maps"]!.AsArray().Single(m => (int)m!["Map"]! == 4164)!;
var originalRoom = oldNode["Creatures"]!["Maps"]!.AsArray().Single(m => (int)m!["Map"]! == 4164)!;
var pointFixes = new Dictionary<uint, (int x, int y)>();
foreach (var entry in originalRoom["Mobs"]!.AsArray())
{
    var data = entry!["Data"]!;
    if ((int)data["X"]! != 24 || (int)data["Y"]! != 32 || (int)data["HomeX"]! != 24 || (int)data["HomeY"]! != 32) continue;
    var current = room["Mobs"]!.AsArray().Single(m => (uint)m!["Data"]!["Id"]! == (uint)data["Id"]!)!["Data"]!;
    int x = (int)current["X"]!, y = (int)current["Y"]!; pointFixes[(uint)data["Id"]!] = (x, y);
    Check("known_bad_room_relocated_inside_original_terrain", x >= 0 && y >= 0 && x < 20 && y < 30 && !MapData.For((ushort)4164)!.Solid(x, y), new { x, y });
    foreach (string key in new[] { "X", "Y", "HomeX", "HomeY" }) data[key] = current[key]!.DeepClone();
}
foreach (var map in oldNode["Population"]!["Maps"]!.AsArray()) foreach (var point in map!["Points"]!.AsArray())
    if (pointFixes.TryGetValue((uint)point!["LiveId"]!, out var p))
    { point["X"] = p.x; point["Y"] = p.y; point["LiveX"] = p.x; point["LiveY"] = p.y; }
newNode.Remove("EmbeddedMapState"); oldNode.Remove("EmbeddedMapState");
Check("known_bad_room_recovery_changes_only_proven_coordinates", oldCount == newCount && pointFixes.Count > 0 && JsonNode.DeepEquals(oldNode, newNode), new { oldCount, newCount });
var unknown = JsonNode.Parse(previous)!;
var bad = unknown["Creatures"]!["Maps"]!.AsArray().Single(m => (int)m!["Map"]! == 4164)!["Mobs"]!.AsArray().First(m => (int)m!["Data"]!["X"]! == 24)!;
bad["Data"]!["X"] = 65534;
bool refused = false;
try { new World(new GameClock()).RestoreOfflineStateJson(unknown.ToJsonString()); } catch (InvalidDataException) { refused = true; }
Check("unknown_invalid_coordinates_still_refused", refused);
var spawnWorld = new World(new GameClock());
var spawnGate = typeof(World).GetField("_lock", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(spawnWorld)!;
var freeSpawn = typeof(World).GetMethod("FreeSpawnTile", BindingFlags.NonPublic | BindingFlags.Instance)!;
lock (spawnGate) foreach (var origin in new[] { ((ushort)3472, (ushort)11, (ushort)8), ((ushort)4164, (ushort)24, (ushort)32), ((ushort)4472, (ushort)10, (ushort)8) })
{
    var tile = ((ushort, ushort))freeSpawn.Invoke(spawnWorld, new object[] { origin.Item1, origin.Item2, origin.Item3, true })!;
    var dims = Content.Maps[origin.Item1];
    Check("all_declared_invalid_spawn_room_origins_" + origin.Item1, tile.Item1 < dims.Xs && tile.Item2 < dims.Ys
        && !MapData.For(origin.Item1)!.Solid(tile.Item1, tile.Item2), new { map = origin.Item1, x = tile.Item1, y = tile.Item2 });
}
File.WriteAllText(args[2], JsonSerializer.Serialize(new { status = failed ? "FAIL" : "PASS", checks, physical_android = "NOT_RUN", scope = "Stable account floor/creature continuity plus exact r25 invalid-room fixture. No user save writes." }, new JsonSerializerOptions { WriteIndented = true }));
return failed ? 1 : 0;
