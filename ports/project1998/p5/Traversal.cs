using System.Text.Json;
using Server;
using Shared;

// Explicit fixtures: one legal adjacent starting tile per exit, no GM bypass.
// They prove native-handler connectivity, not a normal character's world tour.
Environment.SetEnvironmentVariable("P1998_GAME_DATA", Path.GetFullPath(args[0]));
Environment.SetEnvironmentVariable("P1998_STATE", Path.GetFullPath(args[1]));
Environment.SetEnvironmentVariable("P1998_LOGS", Path.Combine(Path.GetFullPath(args[1]), "logs"));
Content.Load();
var options = new JsonSerializerOptions { IncludeFields = true, WriteIndented = true };
var checks = new List<object>(); var failures = new List<object>(); var visited = new HashSet<ushort>();
var originalCharacter = JsonSerializer.Deserialize<Character>(File.ReadAllText(args[2]), options)!;
var store = new CharacterStore(Path.Combine(args[1], "chars"));
void Record(string label, bool ok, object detail) {
    checks.Add(new { label, status = ok ? "PASS" : "FAIL", detail });
    if (!ok) failures.Add(new { label, detail });
}
(Character c, World world, Session s) Fixture(ushort map, ushort x, ushort y, string cls = "Peasant", int stage = 10) {
    var c = JsonSerializer.Deserialize<Character>(JsonSerializer.Serialize(originalCharacter, options), options)!;
    c.Name = "ExitFixture"; c.ClassName = cls; c.Level = 20; c.Hp = c.MaxHp = 300; c.Mp = c.MaxMp = 150;
    c.Quests["newbie_area_quest"] = stage; c.Map = map; c.X = x; c.Y = y;
    c.MapXs = Content.Maps[map].Xs; c.MapYs = Content.Maps[map].Ys;
    var world = new World(); var s = new Session(new Sink(), 2006, store, world, c); s.P4Bind();
    return (c, world, s);
}
foreach (var (from, to) in Content.Warps.OrderBy(x => x.Key.m).ThenBy(x => x.Key.x).ThenBy(x => x.Key.y)) {
    if (!Content.TryMap(from.m, out var map) || from.x >= map.Xs || from.y >= map.Ys) {
        checks.Add(new { label = "unreachable source row", status = "SOURCE_DEFECT_UNCHANGED", from, to }); continue;
    }
    var candidates = new[] { ((int)from.x, (int)from.y + 1, 0), ((int)from.x - 1, (int)from.y, 1), ((int)from.x, (int)from.y - 1, 2), ((int)from.x + 1, (int)from.y, 3) };
    var terrain = MapData.For(from.m, map.Xs, map.Ys)!;
    var at = candidates.First(p => p.Item1 >= 0 && p.Item1 < map.Xs && p.Item2 >= 0 && p.Item2 < map.Ys && !terrain.BlockedMove(p.Item1, p.Item2, p.Item3));
    var f = Fixture(from.m, (ushort)at.Item1, (ushort)at.Item2);
    f.s.P4Walk(at.Item3);
    bool ok = f.c.Map == to.m && f.c.X == to.x && f.c.Y == to.y;
    Record($"native warp {from.m}:{from.x},{from.y}", ok, new { expected = to, actual = new { f.c.Map, f.c.X, f.c.Y } });
    visited.Add(from.m); if (ok) visited.Add(to.m);
    var saved = f.s.P4CaptureAll();
    var restored = new World(); restored.P4Restore(saved.world);
    bool same = JsonSerializer.Serialize(saved.character, options) == JsonSerializer.Serialize(f.s.P4Capture(), options);
    bool mobIds = restored.P4Actors(f.c.Map).Where(m => !m.IsNpc).Select(m => m.Id).Order().SequenceEqual(f.world.P4Actors(f.c.Map).Where(m => !m.IsNpc).Select(m => m.Id).Order());
    Record($"world snapshot restore {from.m}:{from.x},{from.y}", same && mobIds, new { map = f.c.Map });
}
foreach (var (mid, hall) in Content.PathHalls) {
    foreach (var item in new[] { (x: (ushort)8, y: (ushort)1, dest: hall.Sanctum[0], cls: "Peasant"), (x: (ushort)1, y: (ushort)23, dest: hall.GuildMap, cls: Content.PathName(hall.BaseClass)) }) {
        if (!Content.Maps.ContainsKey(item.dest)) continue;
        ushort startY = (ushort)(item.y == 1 ? 2 : 22); int dir = item.y == 1 ? 0 : 2;
        var f = Fixture(mid, item.x, startY, item.cls); f.s.P4Walk(dir);
        Record($"scripted hall {mid} → {item.dest}", f.c.Map == item.dest, new { f.c.Map, f.c.X, f.c.Y });
        if (f.c.Map == item.dest) visited.Add(item.dest);
    }
    var denied = Fixture(mid, 1, 22, "Peasant"); denied.s.P4Walk(2);
    Record($"native class gate {mid}", denied.c.Map == mid && denied.c.Y == 22, new { denied.s.P4Message });
}
var gate = Fixture(4712, 13, 18, "Peasant", 0); gate.s.P4Walk(2);
Record("original newbie quest gate retained", gate.c.Map == 4712, new { gate.s.P4Message });
var result = new { status = failures.Count == 0 ? "PASS_HOST_FIXTURES" : "FAIL", scope = "Adjacent-spawn exit fixtures, unmodified native handlers, no GM. Not a normal character tour or Android execution.", checks, failures, maps_visited = visited.Order().ToArray(), map_count = visited.Count };
File.WriteAllText(args[3], JsonSerializer.Serialize(result, options)); Console.WriteLine($"TRAVERSAL checks={checks.Count} failures={failures.Count} maps={visited.Count}");
if (failures.Count > 0) Environment.ExitCode = 1;
sealed class Sink : IOutbound {
 public string Remote => "p5-exit-fixture"; public int Capacity => int.MaxValue; public int QueueDepth => 0;
 public bool Send(byte[] bytes) => true; public void Close() { }
}
