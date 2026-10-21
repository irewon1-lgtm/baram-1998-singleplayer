using System.Text.Json;
using Server;

namespace P1998.Embedded;

/// <summary>Host-owned optional extension to the existing atomically committed offline extra JSON.
/// It stores only runtime changes against each original map's authored baseline. Original content,
/// collision, door handling and TCP saves are untouched. No write-through map-table side commit is used.</summary>
internal static class OfflineMapState
{
    internal const string Property = "EmbeddedMapState";
    private const int Policy = 1, MaximumMaps = 4096, MaximumCells = 262144;
    internal sealed record State(int Policy, Map[] Maps);
    internal sealed record Map(ushort Id, ushort Width, ushort Height, Cell[] Cells);
    internal sealed record Cell(ushort X, ushort Y, ushort Tile, ushort Pass, ushort Object);

    internal static string Capture(World world, IEnumerable<ushort> visited)
    {
        ushort[] ids = visited.Distinct().Order().ToArray();
        if (ids.Length > MaximumMaps) throw new InvalidDataException("Offline visited-map bound exceeded.");
        var maps = new List<Map>(); int total = 0;
        foreach (ushort id in ids)
        {
            if (!Content.Maps.TryGetValue(id, out var info)) throw new InvalidDataException("Unknown visited offline map.");
            // A historical empty row is visit metadata, not a reason to read/decode the full terrain.
            // Nonempty committed overlays are installed by Restore; all later mutations use MapData.For.
            var original = MapData.AlreadyLoaded(id);
            var cells = original?.RuntimeCells().Select(c => new Cell(c.X, c.Y, c.Cell.Tile, c.Cell.Pass, c.Cell.Obj)).ToArray()
                ?? Array.Empty<Cell>();
            total += cells.Length;
            if (total > MaximumCells) throw new InvalidDataException("Offline runtime-map cell bound exceeded.");
            maps.Add(new(id, info.Xs, info.Ys, cells));
        }
        // Capture the original world with its original policy and append one optional namespaced field.
        // Session captures this string with Character/runtime and commits all of it in one SQLite transaction.
        return world.CaptureOfflineStateJson(writer =>
        {
            writer.WritePropertyName(Property);
            JsonSerializer.Serialize(writer, new State(Policy, maps.ToArray()));
        });
    }

    internal static ushort[] Restore(string json)
    {
        using var document = JsonDocument.Parse(json);
        if (!document.RootElement.TryGetProperty(Property, out var property)) return Array.Empty<ushort>();
        State state;
        try { state = property.Deserialize<State>() ?? throw new InvalidDataException("Missing offline map extension."); }
        catch (JsonException error) { throw new InvalidDataException("Malformed offline map extension.", error); }
        if (state.Policy != Policy || state.Maps is null || state.Maps.Length > MaximumMaps
            || state.Maps.Select(m => m.Id).Distinct().Count() != state.Maps.Length)
            throw new InvalidDataException("Unsupported or invalid offline map extension.");
        int total = 0;
        // Validate every row before applying any of them. A malformed/future save is never replaced
        // with a new empty world, and no map/character/database write occurs on this validation path.
        foreach (var map in state.Maps)
        {
            if (!Content.Maps.TryGetValue(map.Id, out var info) || map.Width != info.Xs || map.Height != info.Ys || map.Cells is null)
                throw new InvalidDataException("Offline map content or dimensions differ.");
            total += map.Cells.Length;
            if (total > MaximumCells || map.Cells.Select(c => (c.X, c.Y)).Distinct().Count() != map.Cells.Length
                || map.Cells.Any(c => c.X >= map.Width || c.Y >= map.Height || c.Tile > 0x3fff || c.Pass > 3 || c.Object > 0x3fff))
                throw new InvalidDataException("Invalid offline runtime-map cell.");
        }
        foreach (var map in state.Maps)
        {
            if (map.Cells.Length == 0) continue;
            var original = MapData.For(map.Id, map.Width, map.Height)
                ?? throw new InvalidDataException("Missing committed offline map data.");
            foreach (var cell in map.Cells) original.SetCell(cell.X, cell.Y, cell.Tile, cell.Pass, cell.Object);
        }
        return state.Maps.Select(m => m.Id).ToArray();
    }
}
