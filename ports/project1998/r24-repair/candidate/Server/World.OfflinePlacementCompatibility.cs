using System.Text.Json;
using System.Text.Json.Nodes;
using Shared;

namespace Server;

public sealed partial class World
{
    // Admit only the exact retained on_spawn-room signature that could produce an invalid r25 save.
    // Unknown invalid coordinates still fail the original validator. Identity, HP, loot, timers,
    // ownership, quest and character data are untouched; no creature is dropped or replenished.
    private OfflineState NormalizeKnownInvalidRoomPositions(OfflineState state)
    {
        if (state.Creatures is not { Maps: { } maps }
            || maps.Any(map => map is null || map.Mobs is null)) return state;
        var moved = new Dictionary<uint, (ushort x, ushort y)>();
        var updated = maps.Select(map => map with
        {
            Mobs = map.Mobs.Select(saved =>
            {
                if (saved is null) return saved!;
                var data = saved.Data;
                if (data.ValueKind != JsonValueKind.Object || !Number(data, nameof(Mob.DefId), out int defId)
                    || !Number(data, nameof(Mob.Id), out int id) || !Number(data, nameof(Mob.X), out int x)
                    || !Number(data, nameof(Mob.Y), out int y) || !Number(data, nameof(Mob.HomeX), out int hx)
                    || !Number(data, nameof(Mob.HomeY), out int hy)
                    || !data.TryGetProperty(nameof(Mob.WorldSpawned), out var spawned) || spawned.ValueKind != JsonValueKind.True
                    || !Content.TryMap(map.Map, out var info) || (x < info.Xs && y < info.Ys)
                    || Content.MobById(defId) is not { } def || !Content.MobSpawnRules.TryGetValue(def.Key, out var rule)
                    || !rule.Rooms.Any(r => r.Map == map.Map && r.X == x && r.Y == y && r.X == hx && r.Y == hy)) return saved;
                var (nx, ny) = FreeSpawnTile(map.Map, (ushort)x, (ushort)y);
                var node = JsonNode.Parse(data.GetRawText())!.AsObject();
                node[nameof(Mob.X)] = nx; node[nameof(Mob.Y)] = ny;
                node[nameof(Mob.HomeX)] = nx; node[nameof(Mob.HomeY)] = ny;
                moved[(uint)id] = (nx, ny);
                return saved with { Data = JsonSerializer.SerializeToElement(node) };
            }).ToArray()
        }).ToArray();
        if (moved.Count == 0) return state;
        var population = state.Population with
        {
            Maps = state.Population.Maps.Select(map => map with
            {
                Points = map.Points.Select(point => moved.TryGetValue(point.LiveId, out var p)
                    ? point with { X = p.x, Y = p.y, LiveX = p.x, LiveY = p.y } : point).ToArray()
            }).ToArray()
        };
        return state with { Population = population, Creatures = state.Creatures with { Maps = updated } };
    }
}
