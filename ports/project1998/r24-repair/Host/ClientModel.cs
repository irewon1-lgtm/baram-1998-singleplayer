using System.Collections.Concurrent;
using System.Buffers.Binary;
using System.Text;

namespace P1998.Embedded;

public sealed record Creature(uint Id, int X, int Y, int Look, int Color, int Direction);
public sealed record BagRow(string Name, string BaseName, uint Amount);
public sealed record DialogRow(int Kind, string Text, string[] Options);
public sealed record ModelItemSnapshot(byte WireSlot, string Name, string BaseName, uint Amount);
public sealed record ModelSpellSnapshot(byte WireSlot, string Name);
public sealed record ClientModelSnapshot(int Map, int Width, int Height, int X, int Y, uint SelfId,
    uint Hp, uint Mp, int? MusicTrack, int TerrainCells, int CreatureCount, int[] SeenOpcodes,
    ModelItemSnapshot[] Inventory, ModelItemSnapshot[] Equipment, ModelSpellSnapshot[] Spells,
    bool EntryComplete);

/// <summary>Wire-derived diagnostic model only. The UI never writes Character/World or grants rules.</summary>
public sealed partial class ClientModel
{
    private readonly object _gate = new(); // model bytes only, no host/session/DB callbacks
    private HashSet<byte> Seen { get; } = new();
    public int Map { get; private set; }
    public int Width { get; private set; }
    public int Height { get; private set; }
    public int X { get; private set; }
    public int Y { get; private set; }
    public uint SelfId { get; private set; }
    public uint Hp { get; private set; }
    public uint Mp { get; private set; }
    public int? MusicTrack { get; private set; }
    private readonly Dictionary<(int X, int Y), (ushort Ground, ushort Object)> _cells = new();
    public IReadOnlyDictionary<(int X, int Y), (ushort Ground, ushort Object)> Cells { get { lock (_gate) return new Dictionary<(int X, int Y), (ushort Ground, ushort Object)>(_cells); } }
    private readonly Dictionary<uint, Creature> _creatures = new();
    public IReadOnlyDictionary<uint, Creature> Creatures { get { lock (_gate) return new Dictionary<uint, Creature>(_creatures); } }
    private readonly Dictionary<byte, BagRow> _inventory = new();
    public IReadOnlyDictionary<byte, BagRow> Inventory { get { lock (_gate) return new Dictionary<byte, BagRow>(_inventory); } }
    private readonly Dictionary<byte, BagRow> _equipment = new();
    public IReadOnlyDictionary<byte, BagRow> Equipment { get { lock (_gate) return new Dictionary<byte, BagRow>(_equipment); } }
    private readonly Dictionary<byte, string> _spells = new();
    public IReadOnlyDictionary<byte, string> Spells { get { lock (_gate) return new Dictionary<byte, string>(_spells); } }
    public ConcurrentQueue<DialogRow> Dialogs { get; } = new();
    public bool EntryComplete { get { lock (_gate) return SelfId != 0 && Seen.Contains(0x15) && Seen.Contains(2) && Seen.Contains(4) &&
        Seen.Contains(0x33) && Seen.Contains(8) && Seen.Contains(6) && _cells.Count > 0; } }
    /// <summary>One consistent read under the packet-application gate. Slots/names are wire facts;
    /// the 4.95 bag/equipment/spell packets do not carry content-definition IDs.</summary>
    public ClientModelSnapshot Capture()
    {
        lock (_gate)
            return new(Map, Width, Height, X, Y, SelfId, Hp, Mp, MusicTrack, _cells.Count, _creatures.Count,
                Seen.Select(op => (int)op).OrderBy(op => op).ToArray(),
                _inventory.OrderBy(p => p.Key).Select(p => new ModelItemSnapshot(p.Key, p.Value.Name, p.Value.BaseName, p.Value.Amount)).ToArray(),
                _equipment.OrderBy(p => p.Key).Select(p => new ModelItemSnapshot(p.Key, p.Value.Name, p.Value.BaseName, p.Value.Amount)).ToArray(),
                _spells.OrderBy(p => p.Key).Select(p => new ModelSpellSnapshot(p.Key, p.Value)).ToArray(),
                SelfId != 0 && Seen.Contains(0x15) && Seen.Contains(2) && Seen.Contains(4) && Seen.Contains(0x33) &&
                    Seen.Contains(8) && Seen.Contains(6) && _cells.Count > 0);
    }
    private static ushort U16(ReadOnlySpan<byte> b) => BinaryPrimitives.ReadUInt16BigEndian(b);
    private static uint U32(ReadOnlySpan<byte> b) => BinaryPrimitives.ReadUInt32BigEndian(b);
    public void PredictWalk(int direction)
    { lock (_gate) { _direction = direction; X += direction == 1 ? 1 : direction == 3 ? -1 : 0; Y += direction == 2 ? 1 : direction == 0 ? -1 : 0; } }
    public void CancelPrediction(int x, int y) { lock (_gate) { X = x; Y = y; } }
    public void Apply(byte op, byte[] body, bool systemGenerated = false)
    { lock (_gate) ApplyCore(op, body, systemGenerated); }
    private void ApplyCore(byte op, byte[] body, bool systemGenerated)
    {
        ReadOnlySpan<byte> b = body; Seen.Add(op);
        switch (op)
        {
            case 0x15:
                Interlocked.Increment(ref _mapEpoch);
                Map = U16(b); Width = U16(b[2..]); Height = U16(b[4..]);
                _cells.Clear(); _terrainSnapshot = null; _creatures.Clear(); break;
            case 4: X = U16(b); Y = U16(b[2..]); break;
            case 5: SelfId = U32(b); break;
            case 8: Hp = U32(b[24..]); Mp = U32(b[28..]); break;
            case 6:
                int x = U16(b), y = U16(b[2..]), w = b[4], h = b[5];
                if (b.Length != 6 + w * h * 4) throw new InvalidDataException("Map body length differs from dimensions.");
                bool terrainChanged = false;
                for (int i = 0; i < w * h; i++)
                {
                    var position = (x + i % w, y + i / w);
                    var cell = (U16(b[(6 + 4 * i)..]), U16(b[(8 + 4 * i)..]));
                    if (!_cells.TryGetValue(position, out var prior) || prior != cell)
                    {
                        _cells[position] = cell;
                        terrainChanged = true;
                    }
                }
                if (terrainChanged) _terrainSnapshot = null;
                break;
            case 7:
                int count = U16(b);
                if (b.Length != 2 + count * 12) throw new InvalidDataException("Creature count/body length differs.");
                for (int i = 0; i < count; i++)
                {
                    var item = b[(2 + i * 12)..]; int look = U16(item[8..]);
                    if ((look & 0xc000) == 0x8000)
                        _creatures[U32(item[4..])] = new(U32(item[4..]), U16(item), U16(item[2..]), look & 0x7fff, item[10], item[11]);
                }
                break;
            case 0x0c:
                uint id = U32(b);
                if (_creatures.TryGetValue(id, out var old))
                {
                    int dir = b[8] & 3;
                    _creatures[id] = old with { X = U16(b[4..]) + (dir == 1 ? 1 : dir == 3 ? -1 : 0), Y = U16(b[6..]) + (dir == 2 ? 1 : dir == 0 ? -1 : 0), Direction = dir };
                }
                break;
            case 0x0e: for (int i = 0; i < b[0]; i++) _creatures.Remove(U32(b[(1 + 4 * i)..])); break;
            case 0x0f:
            case 0x37:
                int at = 3; string name = Text(b, ref at); string baseName = Text(b, ref at);
                var row = new BagRow(name, baseName, op == 0x0f ? U32(b[at..]) : 1);
                (op == 0x0f ? _inventory : _equipment)[b[0]] = row; break;
            case 0x10: _inventory.Remove(b[0]); break;
            case 0x38: _equipment.Remove(b[0]); break;
            case 0x17: at = 2; _spells[b[0]] = Text(b, ref at); break;
            case 0x18: _spells.Remove(b[0]); break;
            case 0x19: if (b[0] is 1 or 2) MusicTrack = U16(b[2..]); break;
            case 0x30:
                at = 21 + (b[7] == 0 ? 4 : 0); int length = U16(b[at..]); at += 2;
                string text = Encoding.ASCII.GetString(b.Slice(at, length)); at += length;
                var options = new List<string>();
                if (b[0] == 2) { int n = b[at++]; for (int i = 0; i < n; i++) options.Add(Text(b, ref at)); }
                Dialogs.Enqueue(new(b[0], text, options.ToArray()));
                if (_interactivePresentation) while (Dialogs.Count > 8) Dialogs.TryDequeue(out _);
                break;
        }
        ApplySceneCore(op, body, systemGenerated);
    }
    private static string Text(ReadOnlySpan<byte> b, ref int at)
    { int n = b[at++]; string s = Encoding.ASCII.GetString(b.Slice(at, n)); at += n; return s; }
}
