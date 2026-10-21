using System.Buffers.Binary;
using System.Collections;
using System.Text;

namespace P1998.Embedded;

public sealed record ModelCell(int X, int Y, ushort Ground, ushort Object);
/// <summary>An owned, immutable terrain image. Scene polls can share this reference while
/// actors and the camera move; a map reset or tile patch publishes a new image. Neither the
/// backing array nor a mutable collection is exposed to scene consumers.</summary>
public sealed class ModelTerrainSnapshot : IReadOnlyList<ModelCell>
{
    private readonly ModelCell[] _cells;
    internal ModelTerrainSnapshot(IEnumerable<ModelCell> cells) => _cells = cells.ToArray();
    public int Length => _cells.Length;
    public int Count => _cells.Length;
    public ModelCell this[int index] => _cells[index];
    public IEnumerator<ModelCell> GetEnumerator() => ((IEnumerable<ModelCell>)_cells).GetEnumerator();
    IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
}
public sealed record PlayerStatsSnapshot(int Nation, int Totem, int Level, uint MaxHp, uint MaxMp,
    int Might, int Will, int Grace, uint Hp, uint Mp, uint Experience, uint Coins, bool FastMove);
public sealed record PlayerLookSnapshot(uint Id, int X, int Y, int Direction, byte[] Appearance, string Name);
public sealed record FloorItemSnapshot(uint Id, int X, int Y, ushort WireLook, int Icon);
public sealed record SceneItemSnapshot(byte WireSlot, string Name, string BaseName, uint Amount, ushort WireIcon, int Icon);
public sealed record SceneSpellSnapshot(byte WireSlot, string Name, byte Type);
public sealed record SceneDialogSnapshot(long Sequence, int Kind, uint EntityId, string Text, string[] Options,
    bool Previous, bool Next, int HeadKind, int PortraitLook, int PortraitColor, byte[]? Appearance);
public sealed record SceneShopRow(ushort WireIcon, uint Number, string Name, string Blurb, byte WireSlot);
public sealed record SceneShopSnapshot(long Sequence, int Kind, byte Tag, uint EntityId, string Text,
    SceneShopRow[] Rows, string ItemName, int Maximum);
public sealed record SceneWorldMapDestination(string Name, uint Map, ushort X, ushort Y, int DotX, int DotY);
public sealed record SceneWorldMapSnapshot(long Sequence, string Background, SceneWorldMapDestination[] Destinations);
public sealed record SceneLegendSnapshot(int Icon, int Color, string Text);
public sealed record SceneProfileSnapshot(int Ac, int Dam, int Hit, uint Tnl, string Title,
    string ClanName, string ClanTitle, string ClassName, string GroupText, string BuffText,
    bool Grouped, bool Exchange, SceneLegendSnapshot[] Legends);
public sealed record SceneEvent(long Sequence, string Kind, byte Opcode, uint EntityId, int Value,
    int Auxiliary, string Text, byte[] Body, int? PresentationSourceX = null, int? PresentationSourceY = null, bool SystemGenerated = false);
public sealed record ClientSceneSnapshot(int Map, int Width, int Height, string MapTitle, int X, int Y,
    int Direction, uint SelfId, PlayerLookSnapshot? SelfLook, PlayerStatsSnapshot Stats, ModelTerrainSnapshot Cells,
    Creature[] Creatures, PlayerLookSnapshot[] Players, FloorItemSnapshot[] FloorItems,
    SceneItemSnapshot[] Inventory, SceneItemSnapshot[] Equipment, SceneSpellSnapshot[] Spells,
    SceneDialogSnapshot? Dialog, SceneShopSnapshot? Shop, SceneEvent[] Events, long LastEventSequence,
    bool EntryComplete, SceneWorldMapSnapshot? WorldMap = null, SceneProfileSnapshot? Profile = null,
    Shared.RecoveredAppearance Cosmetics = default);

/// <summary>Presentation state comes only from original 4.95 output. Content IDs, collision,
/// inventory ownership, spell eligibility and quest state are never fabricated by this adapter.
/// Offsets are pinned to Session.Entity, Session.Items, Session.Dialog, Session.Shop and Session.Media.
/// The bounded event journal lets a renderer poll without executing callbacks under the model lock.</summary>
public sealed partial class ClientModel
{
    private long _mapEpoch;
    public long MapEpoch => Interlocked.Read(ref _mapEpoch);
    private string _mapTitle = "";
    private int _direction;
    private readonly Dictionary<uint, PlayerLookSnapshot> _players = new();
    private readonly Dictionary<uint, FloorItemSnapshot> _floorItems = new();
    private readonly Dictionary<byte, ushort> _bagIcons = new(), _equipmentIcons = new();
    private readonly Dictionary<byte, byte> _spellTypes = new();
    private PlayerStatsSnapshot _stats = new(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, false);
    private SceneDialogSnapshot? _dialog;
    private SceneShopSnapshot? _shop;
    private SceneWorldMapSnapshot? _worldMap;
    private SceneProfileSnapshot? _profile;
    private readonly Queue<SceneEvent> _events = new();
    private long _eventSequence;
    public const int EventCapacity = 256;
    private bool _interactivePresentation;
    // Accessed only under _gate. _cells remains the complete wire-derived collision/map cache;
    // this presentation image is rebuilt lazily only when that cache actually changes.
    private ModelTerrainSnapshot? _terrainSnapshot;
    public void EnableInteractivePresentation() { lock (_gate) _interactivePresentation = true; }

    public ClientSceneSnapshot CaptureScene()
    {
        lock (_gate)
        {
            if (_heldLocalWalk is { } held) return CopyOwnedScene(held.Scene);
            PlayerLookSnapshot CopyLook(PlayerLookSnapshot p) => p with { Appearance = p.Appearance.ToArray() };
            PlayerLookSnapshot? self = _players.TryGetValue(SelfId, out var look)
                ? CopyLook(look) with { X = X, Y = Y, Direction = _direction } : null;
            SceneItemSnapshot Item(KeyValuePair<byte, BagRow> pair, Dictionary<byte, ushort> icons)
            {
                ushort icon = icons.GetValueOrDefault(pair.Key);
                return new(pair.Key, pair.Value.Name, pair.Value.BaseName, pair.Value.Amount, icon, (icon + 0x4000) & 0xffff);
            }
            return new(Map, Width, Height, _mapTitle, X, Y, _direction, SelfId, self, _stats,
                _terrainSnapshot ??= new(_cells.OrderBy(p => p.Key.Y).ThenBy(p => p.Key.X)
                    .Select(p => new ModelCell(p.Key.X, p.Key.Y, p.Value.Ground, p.Value.Object))),
                _creatures.Values.OrderBy(p => p.Id).ToArray(), _players.Values.OrderBy(p => p.Id).Select(CopyLook).ToArray(),
                _floorItems.Values.OrderBy(p => p.Id).ToArray(),
                _inventory.OrderBy(p => p.Key).Select(p => Item(p, _bagIcons)).ToArray(),
                _equipment.OrderBy(p => p.Key).Select(p => Item(p, _equipmentIcons)).ToArray(),
                _spells.OrderBy(p => p.Key).Select(p => new SceneSpellSnapshot(p.Key, p.Value, _spellTypes.GetValueOrDefault(p.Key))).ToArray(),
                _dialog is null ? null : _dialog with { Options = _dialog.Options.ToArray(), Appearance = _dialog.Appearance?.ToArray() },
                _shop is null ? null : _shop with { Rows = _shop.Rows.ToArray() },
                _events.Select(e => e with { Body = e.Body.ToArray() }).ToArray(), _eventSequence, EntryComplete,
                _worldMap is null ? null : _worldMap with { Destinations = _worldMap.Destinations.ToArray() },
                _profile is null ? null : _profile with { Legends = _profile.Legends.ToArray() });
        }
    }

    public void AcknowledgeDialog(long sequence)
    {
        lock (_gate)
        {
            if (_dialog?.Sequence == sequence) _dialog = null;
            if (_shop?.Sequence == sequence) _shop = null;
            if (_worldMap?.Sequence == sequence) _worldMap = null;
        }
    }

    private void Event(string kind, byte opcode, ReadOnlySpan<byte> body, uint entityId = 0, int value = 0, int auxiliary = 0, string text = "",
        int? presentationSourceX = null, int? presentationSourceY = null, bool systemGenerated = false)
    {
        _events.Enqueue(new(++_eventSequence, kind, opcode, entityId, value, auxiliary, text, body[..Math.Min(body.Length, 256)].ToArray(),
            presentationSourceX, presentationSourceY, systemGenerated));
        while (_events.Count > EventCapacity) _events.Dequeue();
    }

    private void ApplySceneCore(byte op, byte[] body, bool systemGenerated)
    {
        ReadOnlySpan<byte> b = body;
        switch (op)
        {
            case 0x39:
                ApplyProfile(b);
                break;
            case 0x15:
                _players.Clear(); _floorItems.Clear(); _dialog = null; _shop = null; _worldMap = null;
                int at = 8; _mapTitle = Text(b, ref at);
                Event("map", op, b, value: Map, text: _mapTitle);
                break;
            case 0x08:
                _stats = new(b[1], b[2], b[4], U32(b[5..]), U32(b[9..]), b[13], b[14], b[17], U32(b[24..]), U32(b[28..]), U32(b[32..]), U32(b[36..]), b[46] != 0);
                break;
            case 0x33:
                if (b.Length < 19 || b[9] != 0) throw new InvalidDataException("Unsupported 4.95 player-look record.");
                at = 18; string name = Text(b, ref at); uint player = U32(b[5..]);
                _players[player] = new(player, U16(b), U16(b[2..]), b[4] & 3, b.Slice(10, 7).ToArray(), name);
                if (player == SelfId) { X = U16(b); Y = U16(b[2..]); _direction = b[4] & 3; }
                Event("look", op, b, player);
                break;
            case 0x1d:
                player = U32(b);
                if (b.Length != 12 || b[4] != 0) throw new InvalidDataException("Unsupported 4.95 look-update record.");
                if (_players.TryGetValue(player, out var p)) _players[player] = p with { Appearance = b.Slice(5, 7).ToArray() };
                Event("look", op, b, player);
                break;
            case 0x07:
                int n = U16(b);
                for (int i = 0; i < n; i++)
                {
                    var row = b[(2 + i * 12)..]; ushort raw = U16(row[8..]); uint id = U32(row[4..]);
                    if ((raw & 0xc000) != 0x8000)
                        _floorItems[id] = new(id, U16(row), U16(row[2..]), raw, (raw + 0x4000) & 0xffff);
                }
                break;
            case 0x0e:
                for (int i = 0; i < b[0]; i++) { uint id = U32(b[(1 + 4 * i)..]); _players.Remove(id); _floorItems.Remove(id); }
                Event("despawn", op, b);
                break;
            case 0x11:
                uint turned = U32(b); int side = b[4] & 3;
                if (turned == SelfId) _direction = side;
                if (_players.TryGetValue(turned, out p)) _players[turned] = p with { Direction = side };
                if (_creatures.TryGetValue(turned, out var creature)) _creatures[turned] = creature with { Direction = side };
                Event("turn", op, b, turned, side);
                break;
            case 0x26:
                _direction = b[0] & 3;
                X = U16(b[1..]) + (_direction == 1 ? 1 : _direction == 3 ? -1 : 0);
                Y = U16(b[3..]) + (_direction == 2 ? 1 : _direction == 0 ? -1 : 0);
                Event("walk", op, b, SelfId, _direction);
                break;
            case 0x0c:
                uint moved = U32(b); side = b[8] & 3;
                if (_players.TryGetValue(moved, out p)) _players[moved] = p with
                { X = U16(b[4..]) + (side == 1 ? 1 : side == 3 ? -1 : 0), Y = U16(b[6..]) + (side == 2 ? 1 : side == 0 ? -1 : 0), Direction = side };
                Event("walk", op, b, moved, side);
                break;
            case 0x04: Event("position", op, b, SelfId); break;
            case 0x0f: _bagIcons[b[0]] = U16(b[1..]); break;
            case 0x37: _equipmentIcons[b[0]] = U16(b[1..]); break;
            case 0x10: _bagIcons.Remove(b[0]); break;
            case 0x38: _equipmentIcons.Remove(b[0]); break;
            case 0x17: _spellTypes[b[0]] = b[1]; break;
            case 0x18: _spellTypes.Remove(b[0]); break;
            case 0x19:
                Event(b[0] == 0 ? "sound" : "music", op, b, value: U16(b[2..]), auxiliary: b[0]);
                break;
            case 0x1a: Event("action", op, b, U32(b), b[4], U16(b[5..])); break;
            case 0x29: Event("effect", op, b, U32(b), b[4]); break;
            case 0x13: Event("damage", op, b, U32(b), b[5], b[4]); break;
            case 0x0a:
                Event("message", op, b, value: b[0], text: Encoding.ASCII.GetString(b.Slice(3, U16(b[1..]))));
                break;
            case 0x0d:
                Event("speech", op, b, U32(b[1..]), b[0], text: Encoding.ASCII.GetString(b.Slice(6, b[5])), systemGenerated: systemGenerated);
                break;
            case 0x02:
                if (b.Length > 1 && b[0] == 0x0f) Event("message", op, b, text: Encoding.ASCII.GetString(b.Slice(2, b[1])));
                break;
            case 0x30:
                int shift = b[7] == 0 ? 4 : 0; at = 21 + shift;
                int length = U16(b[at..]); at += 2;
                string text = Encoding.ASCII.GetString(b.Slice(at, length)); at += length;
                var options = new List<string>();
                if (b[0] == 2) { n = b[at++]; for (int i = 0; i < n; i++) options.Add(Text(b, ref at)); }
                Event("dialog", op, b, U32(b[2..]), b[0] == 0 ? 1 : b[0], text: text);
                _dialog = new(_eventSequence, b[0] == 0 ? 1 : b[0], U32(b[2..]), text, options.ToArray(),
                    b[19 + shift] != 0, b[20 + shift] != 0, b[6], b[7] == 0 ? 0 : U16(b[8..]),
                    b[7] == 0 ? 0 : b[10], b[7] == 0 ? b.Slice(8, 7).ToArray() : null);
                _shop = null;
                _worldMap = null;
                break;
            case 0x2f:
                ApplyShop(b);
                break;
            case 0x2e:
                ApplyWorldMap(b);
                break;
        }
    }

    private void ApplyProfile(ReadOnlySpan<byte> body)
    {
        // Native4.95 self-profile grammar, independently documented by the
        // original Session.Dialog SendSelfProfile/parser0x4732a0. No 7.x equip block.
        int at = 3;
        string clan = Text(body, ref at), clanTitle = Text(body, ref at), title = Text(body, ref at), party = Text(body, ref at);
        bool grouped = body[at++] != 0;
        uint tnl = U32(body[at..]); at += 4;
        string className = Text(body, ref at);
        at += 6; // three native portrait icon ids; actual live gear packets supply icons
        string buffs = Text(body, ref at).Replace('\t', '\n');
        bool exchange = body[at++] != 0;
        int count = body[at++];
        var legends = new SceneLegendSnapshot[count];
        for (int i = 0; i < count; i++)
        { int icon = body[at++], color = body[at++]; legends[i] = new(icon, color, Text(body, ref at)); }
        if (at != body.Length) throw new InvalidDataException("4.95 profile has trailing or missing fields.");
        _profile = new(unchecked((sbyte)body[0]), body[1], body[2], tnl, title, clan, clanTitle, className, party, buffs, grouped, exchange, legends);
    }

    private void ApplyWorldMap(ReadOnlySpan<byte> b)
    {
        // Session.WorldMapBody(V495): byte-counted background, count, unused byte,
        // then dot X/Y, byte-counted name, map u32BE and tile X/Y u16BE. Validate
        // the entire packet before publishing anything; an invalid modal cannot
        // overwrite a still-answerable one. The first row is the original ESC reply.
        int at = 0;
        static string ReadWorldText(ReadOnlySpan<byte> bytes, ref int position)
        {
            if (position >= bytes.Length) throw new InvalidDataException("Truncated original world-map text.");
            int length = bytes[position++];
            if (length > bytes.Length - position) throw new InvalidDataException("Truncated original world-map text.");
            string value = Encoding.ASCII.GetString(bytes.Slice(position, length)); position += length; return value;
        }
        string background = ReadWorldText(b, ref at);
        if (b.Length - at < 2) throw new InvalidDataException("Truncated original world-map header.");
        int count = b[at++]; at++;
        if (count == 0) throw new InvalidDataException("Original world map has no return destination.");
        var destinations = new SceneWorldMapDestination[count];
        for (int i = 0; i < count; i++)
        {
            if (b.Length - at < 4) throw new InvalidDataException("Truncated original world-map dot.");
            int dotX = U16(b[at..]), dotY = U16(b[(at + 2)..]); at += 4;
            string name = ReadWorldText(b, ref at);
            if (b.Length - at < 8) throw new InvalidDataException("Truncated original world-map destination.");
            destinations[i] = new(name, U32(b[at..]), U16(b[(at + 4)..]), U16(b[(at + 6)..]), dotX, dotY); at += 8;
        }
        if (at != b.Length) throw new InvalidDataException("Trailing bytes in original 4.95 world map.");
        Event("world-map", 0x2e, b, text: background);
        _worldMap = new(_eventSequence, background, destinations); _dialog = null; _shop = null;
    }

    private void ApplyShop(ReadOnlySpan<byte> b)
    {
        int at = 15 + (b[7] == 0 ? 4 : 0);
        int length = U16(b[at..]); at += 2;
        string text = Encoding.ASCII.GetString(b.Slice(at, length)); at += length;
        var rows = new List<SceneShopRow>(); string item = ""; int max = 0;
        switch (b[0])
        {
            case 4:
                at += 2; int count = U16(b[at..]); at += 2;
                for (int i = 0; i < count; i++)
                {
                    ushort icon = U16(b[at..]); uint number = U32(b[(at + 2)..]); at += 6;
                    string name = Text(b, ref at), blurb = Text(b, ref at);
                    rows.Add(new(icon, number, name, blurb, 0));
                }
                break;
            case 5:
                at += 2; count = b[at++];
                for (int i = 0; i < count; i++)
                {
                    byte slot = b[at++]; _inventory.TryGetValue(slot, out var bag);
                    rows.Add(new(_bagIcons.GetValueOrDefault(slot), 0, bag?.BaseName ?? "", "", slot));
                }
                break;
            case 3: item = Text(b, ref at); max = U16(b[at..]); break;
            default: throw new InvalidDataException("Unsupported original merchant window kind: " + b[0]);
        }
        Event("shop", 0x2f, b, U32(b[2..]), b[0], text: text);
        _shop = new(_eventSequence, b[0], b[1], U32(b[2..]), text, rows.ToArray(), item, max);
        _dialog = null;
        _worldMap = null;
    }
}
