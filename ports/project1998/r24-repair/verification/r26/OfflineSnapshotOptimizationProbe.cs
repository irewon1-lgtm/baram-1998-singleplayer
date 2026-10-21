using System.Collections;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using P1998.Embedded;
using Server;
using Shared;

Environment.SetEnvironmentVariable("P1998_GAME_DATA", args[0]);
Environment.SetEnvironmentVariable("P1998_STATE", args[1]); Directory.CreateDirectory(args[1]); Content.Load();
var checks = new List<object>(); bool failed = false;
void Check(string name, bool pass, object? detail = null) { checks.Add(new { name, status = pass ? "PASS" : "FAIL", detail }); failed |= !pass; }
var mapType = typeof(EmbeddedHost).Assembly.GetType("P1998.Embedded.OfflineMapState")!;
var capture = mapType.GetMethod("Capture", BindingFlags.NonPublic | BindingFlags.Static)!;
var restore = mapType.GetMethod("Restore", BindingFlags.NonPublic | BindingFlags.Static)!;
string Capture(World world, ushort[] ids) => (string)capture.Invoke(null, new object[] { world, ids })!;
int Cached() => ((IDictionary)typeof(MapData).GetField("Cache", BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!).Count;
var world = new World(new GameClock()); MapData.Invalidate();
ushort[] history = Content.Maps.Keys.Order().Take(128).ToArray();
string originalWorld = world.CaptureOfflineStateJson(); string combined = Capture(world, history);
Check("capture_unchanged_history_does_not_materialize_terrain", Cached() == 0, new { loaded_maps = Cached(), history = history.Length });
var expected = JsonNode.Parse(originalWorld)!; var actual = JsonNode.Parse(combined)!.AsObject(); actual.Remove("EmbeddedMapState");
Check("one_pass_extension_preserves_original_world_fields", JsonNode.DeepEquals(expected, actual));
MapData.Invalidate(); restore.Invoke(null, new object[] { combined });
Check("restore_empty_history_does_not_materialize_terrain", Cached() == 0, new { loaded_maps = Cached() });
var terrain = MapData.For((ushort)330)!; var old = terrain.At(110, 140); terrain.SetCell(110, 140, null, old.Pass == 0 ? (ushort)3 : (ushort)0, null);
string changed = Capture(world, history.Append((ushort)330).ToArray()); MapData.Invalidate(); restore.Invoke(null, new object[] { changed });
Check("changed_runtime_cell_restored_without_loading_empty_maps", Cached() == 1 && MapData.For((ushort)330)!.Pass(110, 140) != old.Pass, new { loaded_maps = Cached() });
var invalid = JsonNode.Parse(changed)!.AsObject(); var rows = invalid["EmbeddedMapState"]!["Maps"]!.AsArray();
rows[^1]!["Cells"]!.AsArray().Add(new JsonObject { ["X"] = 65535, ["Y"] = 0, ["Tile"] = 0, ["Pass"] = 0, ["Object"] = 0 });
MapData.Invalidate(); bool rejected = false;
try { restore.Invoke(null, new object[] { invalid.ToJsonString() }); } catch (TargetInvocationException e) when (e.InnerException is InvalidDataException) { rejected = true; }
Check("invalid_map_extension_validated_before_any_application", rejected && Cached() == 0);

// Every scalar serializer member is changed independently. Mutable graphs are deliberately uncached.
var mob = new Mob(100000, 1, 5, 5, "cacheprobe", 100) { Key = "", WorldSpawned = false };
world.AddMob(330, mob);
var mobJson = new JsonSerializerOptions { IncludeFields = true };
JsonElement SavedData() => JsonSerializer.Deserialize<World.OfflineState>(world.CaptureOfflineStateJson())!.Creatures!.Maps.Single(m => m.Map == 330).Mobs.Single(m => m.Data.GetProperty("Id").GetUInt32() == mob.Id).Data;
bool Matches() => JsonNode.DeepEquals(JsonNode.Parse(SavedData().GetRawText()), JsonNode.Parse(JsonSerializer.Serialize(mob, mobJson)));
Check("initial_creature_capture_matches_full_original_serializer", Matches());
world.CaptureOfflineStateJson();
var metrics = typeof(World).GetProperty("LastOfflineCapture")?.GetValue(world);
bool reused = metrics is not null && (int)metrics.GetType().GetProperty("ReusedMonsters")!.GetValue(metrics)! > 0;
Check("unchanged_simple_creature_reuses_exact_serialization", reused, metrics);
int members = 0;
foreach (var field in typeof(Mob).GetFields(BindingFlags.Instance | BindingFlags.Public).Where(f => f.FieldType.IsPrimitive || f.FieldType == typeof(string)))
{
    if (field.Name is "Id" or "IsNpc") continue;
    object? value = field.GetValue(mob); Type type = field.FieldType;
    field.SetValue(mob, type == typeof(string) ? "changed" : type == typeof(bool) ? !(bool)value! : Convert.ChangeType(Convert.ToDouble(value) + 1, type));
    Check("scalar_field_" + field.Name, Matches()); field.SetValue(mob, value); members++;
}
foreach (var property in typeof(Mob).GetProperties(BindingFlags.Instance | BindingFlags.Public).Where(p => p.SetMethod is not null))
{
    object? value = property.GetValue(mob); Type type = property.PropertyType;
    property.SetValue(mob, type == typeof(bool) ? !(bool)value! : Convert.ChangeType(Convert.ToDouble(value) + 1, type));
    Check("scalar_property_" + property.Name, Matches()); property.SetValue(mob, value); members++;
}
mob.Threat = new() { [123] = 4 }; Check("mutable_threat_first", Matches()); mob.Threat[123] = 9; Check("mutable_threat_changed_in_place", Matches());
mob.Statuses = new() { ["hold"] = new(1000, "paralyze") }; Check("mutable_status_first", Matches()); mob.Statuses["hold"] = new(2000, "sleep"); Check("mutable_status_changed_in_place", Matches());
mob.Handed = new() { new InvItem { ItemId = 21001, Amount = 2 } }; Check("mutable_item_first", Matches()); mob.Handed[0].Amount = 9; Check("mutable_item_changed_in_place", Matches());
mob.Buffs = new() { new Mob.TimedBuff { Stat = "Hit", Amount = 2 } }; Check("mutable_buff_first", Matches()); mob.Buffs[0].Amount = 7; Check("mutable_buff_changed_in_place", Matches());
File.WriteAllText(args[2], JsonSerializer.Serialize(new { status = failed ? "FAIL" : "PASS", scalar_members_mutated = members, checks, physical_android = "NOT_RUN" }, new JsonSerializerOptions { WriteIndented = true }));
return failed ? 1 : 0;
