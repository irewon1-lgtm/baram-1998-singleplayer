using System.Text.Json;
using Godot;
using Server;
using Shared;
using P1998.P3;
using Environment = System.Environment;

// UI boundary only. Authoritative movement, inventory and Lua remain in Server.
public partial class InteractiveCore : RefCounted
{
    private const string PlayerKey = "p3player";
    private ProbeStore _store = null!;
    private Character _character = null!;
    private Session _session = null!;
    private World _world = null!;
    private Mob _rabbit = null!;
    private string _root = "";
    private bool _ready;
    private bool _loaded;
    private int _moves;
    private int _blocked;
    private int _uses;
    private string _message = "빈 곳을 눌러 이동 · 방향 버튼을 눌러 이동";

    public string Initialize(string root)
    {
        try
        {
            if (!Path.IsPathFullyQualified(root)) throw new InvalidDataException("Absolute app root required");
            _root = root;
            ProbeStore.Guard(Path.Combine(root, "v1"), ProbeStore.Hash(Godot.FileAccess.GetFileAsBytes("res://capsule.json")));
            _store = new ProbeStore(Path.Combine(root, "v1"), "p3-player-v1.backup.db");
            var prior = _store.Store.Load(PlayerKey);
            if (prior.Status is not (CharacterLoadStatus.Ok or CharacterLoadStatus.NotFound))
                throw new InvalidDataException("EXISTING_SAVE_PROTECTED: player " + prior.Status);
            _loaded = prior.Status == CharacterLoadStatus.Ok;
            using var fixture = JsonDocument.Parse(Godot.FileAccess.GetFileAsString("res://fixtures.json"));
            _character = prior.Character ?? CharacterFactory.FromCreate(PlayerKey,
                fixture.RootElement.GetProperty("appearance").EnumerateArray().Select(x => x.GetByte()).ToArray());
            if (!_loaded)
            {
                var (map, x, y, xs, ys) = CharacterFactory.StartFor(_character.Nation);
                _character.Map = map; _character.X = x; _character.Y = y; _character.MapXs = xs; _character.MapYs = ys;
                // Same explicit P3 starting fixture as the independent oracle.
                _character.Hp = fixture.RootElement.GetProperty("hp").GetUInt32();
                _character.Mp = fixture.RootElement.GetProperty("mp").GetUInt32();
            }
            var terrain = MapData.For(4711, 16, 16) ?? throw new InvalidDataException("P3 map missing");
            if (_character.Map != 4711 || _character.MapXs != 16 || _character.MapYs != 16 ||
                terrain.Solid(_character.X, _character.Y) || (_character.X == 6 && _character.Y == 6))
                throw new InvalidDataException("EXISTING_SAVE_PROTECTED: player outside supported P3 scene");
            _world = new World();
            _session = new Session(new LocalSink(), 2006, _store.Store, _world, _character);
            _world.EnterMap(_session, _character.Map);
            var def = Content.MobById(1) ?? throw new InvalidDataException("Rabbit definition missing");
            _rabbit = new Mob(9002, def.Look, 6, 6, def.Name, def.Hp)
                { Key = def.Key, Color = def.Color, HomeX = 6, HomeY = 6 };
            _world.AddMob(_character.Map, _rabbit);
            if (!_loaded)
            {
                _session.P3Give(Content.ItemByKey("apple")!.Id, 3);
                _session.P3Give(Content.ItemByKey("wine")!.Id, 1);
            }
            _ready = true;
            if (!_loaded) Save();
            else _message = "저장한 위치에서 이어하기";
            Record();
            return ReadState();
        }
        catch (Exception e)
        {
            _ready = false;
            return JsonSerializer.Serialize(new { ok = false, error = e.GetBaseException().Message });
        }
    }

    public bool CanStep(int x, int y, int nx, int ny)
    {
        if (!_ready) return false;
        int dir = nx == x && ny == y - 1 ? 0 : nx == x + 1 && ny == y ? 1 :
                  nx == x && ny == y + 1 ? 2 : nx == x - 1 && ny == y ? 3 : -1;
        if (dir < 0 || (_rabbit.Alive && nx == _rabbit.X && ny == _rabbit.Y)) return false;
        return !MapData.For(_character.Map, _character.MapXs, _character.MapYs)!.BlockedMove(nx, ny, dir);
    }

    public bool ValidCell(int x, int y) => _ready &&
        !MapData.For(_character.Map, _character.MapXs, _character.MapYs)!.Solid(x, y);

    public string Move(int direction)
    {
        if (!_ready) return ReadState();
        bool moved = _session.P3Move(direction);
        if (moved) { _moves++; _message = "빈 곳을 누르거나 방향 버튼으로 이동"; }
        else { _blocked++; _message = "그쪽으로 이동할 수 없습니다"; }
        return ReadState();
    }

    public string UseItem(string key)
    {
        if (!_ready) return ReadState();
        if (key is not ("apple" or "wine")) throw new ArgumentException("Unsupported P3 item");
        var def = Content.ItemByKey(key)!;
        var item = _character.Inventory.FirstOrDefault(x => x.ItemId == def.Id);
        if (item is null) { _message = "남은 아이템이 없습니다"; return ReadState(); }
        uint hp = _character.Hp, mp = _character.Mp;
        int amount = item.Amount; ushort durability = item.Dura;
        _session.P3Use(item.Slot, key == "apple");
        bool changed = hp != _character.Hp || mp != _character.Mp || amount != item.Amount || durability != item.Dura ||
                       !_character.Inventory.Contains(item);
        if (changed) _uses++;
        _message = changed ? (key == "apple" ? "사과를 먹었습니다" : "음료를 마셨습니다") : "지금은 사용할 수 없습니다";
        Save();
        return ReadState();
    }

    public string Save()
    {
        if (!_ready) return ReadState();
        try
        {
            if (!_store.Save(_character)) throw new IOException("Character save failed");
            _message = "위치와 아이템 저장 완료";
            Record();
        }
        catch (Exception e) { _message = "저장 확인 필요: " + e.GetBaseException().Message; }
        return ReadState();
    }

    private void Record() => ProbeStore.AtomicText(Path.Combine(_root, "play-state.json"), ReadState());

    public string ReadState() => !_ready ? JsonSerializer.Serialize(new { ok = false, error = "Core not initialized" }) :
        JsonSerializer.Serialize(new { ok = true, loaded = _loaded, x = _character.X, y = _character.Y,
            map = _character.Map, facing = _character.Dir, hp = _character.Hp, max_hp = _character.MaxHp,
            mp = _character.Mp, max_mp = _character.MaxMp, moves = _moves, blocked = _blocked, uses = _uses,
            message = _message, world_started = _world.IsStarted, platform = OS.GetName(),
            inventory = _character.Inventory.Select(x => new { key = Content.ItemById(x.ItemId)!.Key,
                id = x.ItemId, amount = x.Amount, charges = x.Dura }).ToArray(),
            rabbit = new { x = _rabbit.X, y = _rabbit.Y, hp = _rabbit.Hp, alive = _rabbit.Alive },
            character_key = PlayerKey, build = "0.0.3-p3-map" });
}
