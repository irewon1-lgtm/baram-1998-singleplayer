using System.Text;
using System.Text.Json;
using Shared;

namespace Server;

public sealed class P4Window
{
    public string kind = "text";
    public uint npc;
    public string text = "";
    public string[] options = Array.Empty<string>();
    public string[] names = Array.Empty<string>();
    public int[] prices = Array.Empty<int>();
    public int[] slots = Array.Empty<int>();
    public int max = 1;
    public long revision;
}

// A transport/host boundary, compiled beside the pinned source. The actual
// movement, quests, buy/sell, damage, experience, use and casts stay unchanged.
public sealed partial class Session
{
    public P4Window? P4Dialog;
    public string P4Message = "";
    public long P4DialogRevision;
    public long P4ActionRevision;
    public string P4Action = "idle";
    public byte P4Facing => _facing;

    public void P4Bind() => WithState(() =>
    {
        _user = _char.Name;
        _claimedKey = CharacterStore.Key(_user);
        _world.Online.Register(_claimedKey, this, out _);
        _facing = _char.Dir;
        RestoreTimedEffects();
        _char.Ac = (sbyte)Math.Clamp(100 - _char.Level, -128, 127);
        EnterMap(_char.Map, _char.MapXs, _char.MapYs, _char.X, _char.Y,
                 Content.TryMap(_char.Map, out var map) ? map.Name : "");
    });

    public void P4Show(P4Window window)
    {
        window.revision = ++P4DialogRevision;
        P4Dialog = window;
    }

    public void P4Walk(int direction) => WithState(() =>
    {
        if (direction is >= 0 and <= 3) HandleWalk(new[] { (byte)direction });
    });
    public void P4Turn(int direction) => WithState(() =>
    {
        if (direction is >= 0 and <= 3) HandleTurn(new[] { (byte)direction });
    });
    public void P4Attack() => WithState(() =>
    {
        long before = _nextActionTick;
        BumpActionTime(); HandleAttack(Array.Empty<byte>());
        if (_nextActionTick != before) { P4Action = "attack"; P4ActionRevision++; }
    });
    public void P4Use(int slot, bool eat) => WithState(() =>
    {
        if (slot is >= 0 and < 254) HandleUseItem(new[] { (byte)(slot + 1) }, eat);
    });
    public void P4Unequip(int slot) => WithState(() => { if (ActionBudgetLeft()) HandleUnequip(new[] { checked((byte)slot) }); });
    public void P4Pickup() => WithState(() =>
    {
        if (ActionAllowed(ClientOp.Pickup)) HandlePickup(new byte[] { 1 });
    });
    public void P4Cast(string key) => WithState(() =>
    {
        var spell = Content.SpellByKey(key);
        int slot = spell is null ? -1 : _char.Spells.IndexOf(spell.Id);
        if (slot < 0) { P4Message = "먼저 교습 NPC에게 기술을 배워야 합니다."; return; }
        uint hp = _char.Hp, mp = _char.Mp;
        if (ActionAllowed(ClientOp.Cast)) HandleCast(new[] { (byte)(slot + 1) });
        if (hp != _char.Hp || mp != _char.Mp) { P4Action = "cast"; P4ActionRevision++; }
    });
    public void P4Talk(uint id) => WithState(() =>
    {
        P4Close();
        HandleClickInfo(new[] { (byte)1, (byte)(id >> 24), (byte)(id >> 16), (byte)(id >> 8), (byte)id, (byte)0 });
    });
    public void P4Reply(int kind, int option = 0, string input = "") => WithState(() =>
    {
        P4Dialog = null;
        var text = Encoding.ASCII.GetBytes(input);
        var body = new byte[11 + text.Length]; body[0] = checked((byte)kind); body[8] = (byte)(kind == 4 ? 2 : 1);
        body[10] = checked((byte)(kind == 4 ? text.Length : option)); text.CopyTo(body, 11);
        HandleNpcDialog(body);
    });
    public void P4ShopReply(int tag, string name = "", int slot = 0, string amount = "1") => WithState(() =>
    {
        P4Dialog = null;
        var a = Encoding.ASCII.GetBytes(name); var b = Encoding.ASCII.GetBytes(amount);
        var body = new byte[9 + a.Length + b.Length]; body[0] = checked((byte)tag);
        body[7] = checked((byte)(tag == 4 ? slot : a.Length));
        if (tag != 4) { a.CopyTo(body, 8); body[8 + a.Length] = checked((byte)b.Length); b.CopyTo(body, 9 + a.Length); }
        HandleShopReply(body);
    });
    public void P4Close() => WithState(() =>
    {
        // The original text sequence commits grants/stages between pages and
        // treats a close as an acknowledgement. Drain those text pages through
        // its real handler; menu/input/shop receive their native cancel reply.
        // Cancelling the Task instead would abandon a grant before its stage.
        for (int i = 0; i < 64 && (_dlgReply is not null || _shopReply is not null); i++)
        {
            var window = P4Dialog; P4Dialog = null;
            if (_shopReply is not null) { HandleShopReply(Array.Empty<byte>()); continue; }
            var body = new byte[11];
            body[0] = (byte)(window?.kind == "menu" ? 2 : window?.kind == "input" ? 4 : 1);
            HandleNpcDialog(body);
        }
        P4Dialog = null;
    });
    public void P4Say(string text) => WithState(() =>
    {
        var message = Encoding.ASCII.GetBytes(text.Length > 200 ? text[..200] : text);
        HandleChat(new byte[] { 0, (byte)message.Length }.Concat(message).ToArray());
    });
    public Character P4Capture() => WithState(() =>
    {
        CaptureTimedEffects(); _char.Dir = _facing;
        return JsonSerializer.Deserialize<Character>(JsonSerializer.Serialize(_char, P4Json.Options), P4Json.Options)!;
    });
    public (Character character, P4WorldState world) P4CaptureAll() =>
        WithState(() => (P4Capture(), _world.P4Capture()));
    public int P4Stage => WithState(() => Quest(QuestState.Registry).Get("newbie_area_quest"));
}

public static class P4Json
{
    public static readonly JsonSerializerOptions Options = new() { IncludeFields = true };
}

public sealed class P4PointState
{
    public ushort map, x, y;
    public int index, def;
    public uint live;
    public long respawn;
    public bool placed;
}
public sealed class P4GroupState { public ushort map; public int index; public long next; }
public sealed class P4MobState { public ushort map; public JsonElement data; }
public sealed class P4LootState { public ushort map; public GroundItem item = new(); }
public sealed class P4WorldState
{
    public int schema_version = 1;
    public long tick, mono;
    public uint next_mob, next_item;
    public ushort[] materialized = Array.Empty<ushort>();
    public List<P4PointState> points = new();
    public List<P4GroupState> groups = new();
    public List<P4MobState> mobs = new();
    public List<P4LootState> loot = new();
}

public sealed partial class World
{
    public void P4Step() => Tick();
    public Mob[] P4Actors(ushort mid) { lock (_lock) return Map(mid).Mobs.Where(m => m.Alive).ToArray(); }
    public P4WorldState P4Capture()
    {
        lock (_lock)
        {
            var state = new P4WorldState { tick = _tick, mono = Environment.TickCount64,
                next_mob = _nextMobId, next_item = _nextItemId };
            foreach (var (mid, map) in _maps)
            {
                foreach (var mob in map.Mobs.Where(m => !m.IsNpc && m.Alive))
                    state.mobs.Add(new P4MobState { map = mid, data = JsonSerializer.SerializeToElement(mob, P4Json.Options) });
                foreach (var item in map.Items)
                    state.loot.Add(new P4LootState { map = mid,
                        item = JsonSerializer.Deserialize<GroundItem>(JsonSerializer.Serialize(item, P4Json.Options), P4Json.Options)! });
            }
            _spawnDirector.P4Capture(state);
            return state;
        }
    }
    public void P4Restore(P4WorldState state)
    {
        if (state.schema_version != 1) throw new InvalidDataException("EXISTING_SAVE_PROTECTED: future world");
        lock (_lock)
        {
            foreach (var map in _maps.Values) { map.Mobs.RemoveAll(m => !m.IsNpc); map.Items.Clear(); map.ViewGen++; }
            var live = new Dictionary<uint, Mob>();
            foreach (var row in state.mobs)
            {
                if (!Content.TryMap(row.map, out _)) throw new InvalidDataException("Saved map is not in this slice");
                var mob = JsonSerializer.Deserialize<Mob>(row.data, P4Json.Options)!;
                foreach (var property in typeof(Mob).GetProperties())
                    if (property.GetSetMethod(true) is not null && row.data.TryGetProperty(property.Name, out var value))
                        property.SetValue(mob, JsonSerializer.Deserialize(value, property.PropertyType, P4Json.Options));
                long now = Environment.TickCount64;
                foreach (var field in typeof(Mob).GetFields())
                    if (field.FieldType == typeof(long) && (field.Name.EndsWith("Until") || field.Name.EndsWith("At") || field.Name.EndsWith("NextTick") || field.Name == "FxRepeatNext"))
                    {
                        long deadline = (long)field.GetValue(mob)!;
                        field.SetValue(mob, deadline > state.mono ? now + deadline - state.mono : 0L);
                    }
                if (mob.FrozenUntil > 0) mob.FrozenUntil = now + Math.Max(0, mob.FrozenUntil - state.mono);
                if (mob.IsNpc || Content.MobById(mob.DefId) is null) throw new InvalidDataException("Saved mob definition mismatch");
                Map(row.map).Mobs.Add(mob); live.Add(mob.Id, mob);
            }
            foreach (var row in state.loot)
            {
                if (!Content.TryMap(row.map, out _) || Content.ItemById(row.item.ItemId) is null)
                    throw new InvalidDataException("Saved floor item mismatch");
                row.item.LockedUntil = row.item.LockedUntil > state.mono ? Environment.TickCount64 + row.item.LockedUntil - state.mono : 0;
                Map(row.map).Items.Add(row.item);
            }
            _tick = state.tick; _nextMobId = state.next_mob; _nextItemId = state.next_item;
            _spawnDirector.P4Restore(state, live);
        }
    }
    internal sealed partial class SpawnDirector
    {
        internal void P4Capture(P4WorldState state)
        {
            state.materialized = _materialized.ToArray();
            foreach (var (mid, points) in _spawns)
                for (int i = 0; i < points.Count; i++)
                {
                    var p = points[i]; state.points.Add(new P4PointState { map = mid, index = i, def = p.Def.Id,
                        x = p.X, y = p.Y, placed = p.Placed, live = p.Live?.Id ?? 0, respawn = p.RespawnTick });
                }
            foreach (var (mid, groups) in _groups)
                for (int i = 0; i < groups.Count; i++) state.groups.Add(new P4GroupState { map = mid, index = i, next = groups[i].NextBatchUnix });
        }
        internal void P4Restore(P4WorldState state, Dictionary<uint, Mob> live)
        {
            _materialized.Clear(); foreach (var mid in state.materialized) _materialized.Add(mid);
            _mobSpawn.Clear();
            foreach (var saved in state.points)
            {
                var point = _spawns[saved.map][saved.index];
                if (point.Def.Id != saved.def) throw new InvalidDataException("Spawn roster mismatch");
                point.X = saved.x; point.Y = saved.y; point.Placed = saved.placed; point.RespawnTick = saved.respawn;
                point.Live = saved.live == 0 ? null : live[saved.live];
                if (point.Live is not null) _mobSpawn.Add(point.Live.Id, point);
            }
            foreach (var saved in state.groups) _groups[saved.map][saved.index].NextBatchUnix = saved.next;
        }
    }
}
