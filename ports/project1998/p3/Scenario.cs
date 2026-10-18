using System.Reflection;
using System.Text.Json;
using Server;
using Shared;

namespace P1998.P3;

public sealed class LocalSink : IOutbound
{
    public string Remote => "in-process-p3";
    public int Capacity => int.MaxValue;
    public int QueueDepth => 0;
    public int Frames { get; private set; }
    public bool Send(byte[] frame) { Frames++; return true; }
    public void Close() { }
}

public sealed class Scenario
{
    public static readonly JsonSerializerOptions Json = new() { IncludeFields = true, WriteIndented = true };
    public Character Character { get; }
    public Mob Rabbit { get; }
    public World World { get; }
    public Session Session { get; }
    public LocalSink Sink { get; } = new();
    public List<object> Trace { get; } = new();

    public Scenario(CharacterStore store, JsonElement fixture)
    {
        Character = CharacterFactory.FromCreate("p3probe", fixture.GetProperty("appearance").EnumerateArray().Select(x => x.GetByte()).ToArray());
        var (map, x, y, xs, ys) = CharacterFactory.StartFor(Character.Nation);
        Character.Map = map; Character.X = x; Character.Y = y; Character.MapXs = xs; Character.MapYs = ys;
        // Controlled pre-existing character fixture, NOT a claim about the random
        // starting HP/MP rolls in PlaceNewCharacter. Those use Random.Shared.
        Character.Hp = fixture.GetProperty("hp").GetUInt32();
        Character.Mp = fixture.GetProperty("mp").GetUInt32();
        World = new World(); // Constructor only: no listener, tick or autosave thread.
        Session = new Session(Sink, 2005, store, World, Character);
        World.EnterMap(Session, map);
        var def = Content.MobById(1) ?? throw new InvalidOperationException("Original rabbit row missing");
        Rabbit = new Mob(9001, def.Look, 6, 6, def.Name, def.Hp) { Key = def.Key, Color = def.Color, HomeX = 6, HomeY = 6 };
        World.AddMob(map, Rabbit);
        Trace.Add(new { step = "create", state = Snapshot() });
    }

    public void Run(JsonElement fixture)
    {
        foreach (var a in fixture.GetProperty("actions").EnumerateArray())
        {
            string op = a.GetProperty("op").GetString()!;
            object? result = null;
            switch (op)
            {
                case "move": result = Move(a.GetProperty("dir").GetInt32()); break;
                case "give": result = Give(a.GetProperty("id").GetInt32(), a.GetProperty("amount").GetInt32()); break;
                case "use": Use(a.GetProperty("slot").GetByte(), a.GetProperty("eat").GetBoolean()); break;
                case "capacity": Character.MaxInv = a.GetProperty("value").GetByte(); break;
                case "mounted": Character.Mounted = a.GetProperty("value").GetBoolean(); break;
                case "status": Rabbit.SetStatus(a.GetProperty("category").GetString()!, a.GetProperty("until").GetInt64(), a.GetProperty("key").GetString()!); break;
                case "status_query":
                    string category = a.GetProperty("category").GetString()!;
                    long now = a.GetProperty("now").GetInt64();
                    result = new { active = Rabbit.HasStatus(category, now), key = Rabbit.StatusKey(category, now) }; break;
                case "clear_status": Rabbit.ClearStatus(a.GetProperty("category").GetString()!); break;
                case "threat": Rabbit.AddThreat(a.GetProperty("player").GetUInt32(), a.GetProperty("amount").GetInt64()); break;
                case "clear_threat": Rabbit.ClearThreat(a.GetProperty("player").GetUInt32()); break;
                case "threat_query": result = Rabbit.ThreatOf(a.GetProperty("player").GetUInt32()); break;
                default: throw new ArgumentException("Unknown P3 action: " + op);
            }
            Trace.Add(new { step = a.GetProperty("label").GetString(), result, state = Snapshot() });
        }
    }

    private object Snapshot() => new
    {
        character = new { Character.SchemaVersion, Character.Name, Character.Map, Character.X, Character.Y,
            Character.Dir, Character.Sex, Character.Face, Character.Nation, Character.Totem, Character.Hair,
            Character.Level, Character.Hp, Character.MaxHp, Character.Mp, Character.MaxMp, Character.MaxInv,
            Character.Mounted, inventory = Character.Inventory.OrderBy(x => x.Slot).Select(x => new { x.Slot, x.ItemId, x.Amount, x.Dura, x.Owner, x.CustomName }).ToArray() },
        rabbit = new { Rabbit.Id, Rabbit.Key, Rabbit.X, Rabbit.Y, Rabbit.Hp, Rabbit.MaxHp, Rabbit.Alive }
    };

    private int Give(int id, int amount)
    {
#if ORIGINAL_ORACLE
        return OriginalState(() => (int)typeof(Session).GetMethod("GivePlaced", BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(Session, new object[] { Content.ItemById(id)!, amount, (ushort)0, "", false, "" })!);
#else
        return Session.P3Give(id, amount);
#endif
    }

    private void Use(byte slot, bool eat)
    {
#if ORIGINAL_ORACLE
        OriginalState(() => { typeof(Session).GetMethod("HandleUseItem", BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(Session, new object[] { new[] { checked((byte)(slot + 1)) }, eat }); return true; });
#else
        Session.P3Use(slot, eat);
#endif
    }

    private bool Move(int dir)
    {
#if ORIGINAL_ORACLE
        return OriginalState(() =>
        {
        if (dir is < 0 or > 3) return false;
        int[] dx = { 0, 1, 0, -1 }, dy = { -1, 0, 1, 0 };
        int x = Character.X + dx[dir], y = Character.Y + dy[dir];
        var map = MapData.For(Character.Map, Character.MapXs, Character.MapYs)!;
        Character.Dir = (byte)dir;
        bool blocked = x < 0 || y < 0 || x >= map.Xs || y >= map.Ys || map.BlockedMove(x, y, dir);
        return World.TryMovePlayer(Session, Character.Map, x, y, false, true, blocked, out _);
        });
#else
        return Session.P3Move(dir);
#endif
    }

#if ORIGINAL_ORACLE
    private T OriginalState<T>(Func<T> action) => (T)typeof(Session)
        .GetMethods(BindingFlags.Instance | BindingFlags.NonPublic)
        .Single(m => m.Name == "WithState" && m.IsGenericMethodDefinition)
        .MakeGenericMethod(typeof(T)).Invoke(Session, new object[] { action })!;
#endif

    public object Result(JsonElement fixture) => new { schema = "project1998.p3.parity.v1", seed = fixture.GetProperty("seed").GetInt32(),
        random_draws = 0, world_started = World.IsStarted, trace = Trace };
}
