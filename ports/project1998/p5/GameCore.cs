using System.Text.Json;
using Godot;
using Server;
using Shared;
using P1998.P4;

public partial class GameCore : RefCounted
{
    private sealed class Sink : IOutbound
    {
        public string Remote => "in-process-p4";
        public int Capacity => int.MaxValue;
        public int QueueDepth => 0;
        public bool Send(byte[] bytes) => true;
        public void Close() { }
    }
    private string _root = "";
    private Checkpoint _checkpoint = null!;
    private Character _character = null!;
    private World _world = null!;
    private Session _session = null!;
    private bool _playing, _loaded;
    private long _revision;
    private int _moves, _blocked, _warps;
    private string _error = "", _saveStatus = "";
    private string _moveFailure = "";

    public string Initialize(string root)
    {
        try
        {
            _root = root; _checkpoint = new Checkpoint(root);
            var saved = _checkpoint.Read();
            bool migrated = false;
            if (saved is null) { saved = Checkpoint.ReadLegacy(root); migrated = saved is not null; }
            if (saved is not null)
            {
                _checkpoint.InheritRevision(saved.revision);
                Start(saved.character, saved.world);
            }
            _loaded = saved is not null;
            if (saved is not null) _revision = saved.revision;
            if (migrated) { Save(); _saveStatus = "P4 이어하기 불러옴 · " + _saveStatus; }
            return ReadState();
        }
        catch (Exception e) { _error = e.GetBaseException().Message; return ReadState(); }
    }

    public string Create(string name)
    {
        if (_playing || _checkpoint.Read() is not null) return ReadState();
        _error = NameRules.ShapeProblem(name) ?? "";
        if (_error.Length > 0) return ReadState();
        try
        {
            var c = CharacterFactory.FromCreate(name, new byte[] { 0, 0, 1, 0, 0 });
            CharacterFactory.PlaceNewCharacter(c);
            Start(c, null); Save();
        }
        catch (Exception e) { _error = e.GetBaseException().Message; }
        return ReadState();
    }

    private void Start(Character character, P4WorldState? world)
    {
        if (!Content.TryMap(character.Map, out var map) || character.SchemaVersion != Character.CurrentSchemaVersion)
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: unsupported character/map");
        Checkpoint.PrepareRuntimeCache(_root);
        _character = character;
        var store = new CharacterStore(Path.Combine(_root, "cache-p5/chars"));
        if (!store.Save(character)) throw new IOException("Original runtime CharacterStore refused the character");
        _world = new World();
        if (world is not null) _world.P4Restore(world);
        _session = new Session(new Sink(), 2006, store, _world, character);
        _session.P4Bind();
        _playing = true;
    }

    public string Move(int direction)
    {
        if (!_playing || _session.P4Dialog is not null) return ReadState();
        var old = (_character.Map, _character.X, _character.Y);
        _moveFailure = "";
        var delta = direction switch { 0 => (0, -1), 1 => (1, 0), 2 => (0, 1), 3 => (-1, 0), _ => (0, 0) };
        int nx = _character.X + delta.Item1, ny = _character.Y + delta.Item2;
        if (nx >= 0 && ny >= 0 && Content.TryWarp(_character.Map, (ushort)nx, (ushort)ny, out var edge) && !Content.TryMap(edge.m, out _))
            _session.P4Message = "이 출구의 다음 지역은 아직 열리지 않았습니다.";
        _session.P4Walk(direction);
        if (old == (_character.Map, _character.X, _character.Y))
        {
            _blocked++;
            bool door = nx >= 0 && ny >= 0 && Content.TryWarp(_character.Map, (ushort)nx, (ushort)ny, out _);
            bool hall = Content.PathHalls.ContainsKey(_character.Map) &&
                ((nx is 8 or 9 && ny == 1) || (nx is 1 or 2 && ny == 23));
            _moveFailure = door || hall ? "gate" : _world.MobAt(_character.Map, nx, ny) is not null ? "occupied" : "blocked";
        }
        else { _moves++; if (old.Map != _character.Map) { _warps++; Save(); } }
        return ReadState();
    }
    public void Turn(int direction) { if (_playing) _session.P4Turn(direction); }
    public string Attack() { if (_playing && _session.P4Dialog is null) _session.P4Attack(); return ReadState(); }
    public string Pickup() { if (_playing) { _session.P4Pickup(); Save(); } return ReadState(); }
    public string UseItem(int slot, bool eat) { if (_playing) { _session.P4Use(slot, eat); Save(); } return ReadState(); }
    public string Unequip(int slot) { if (_playing) { _session.P4Unequip(slot); Save(); } return ReadState(); }
    public string CastSpell(string key, long target, string answer)
    {
        if (_playing && _session.P4Dialog is null)
        { _session.P4Cast(key, checked((uint)target), answer); Save(); }
        return ReadState();
    }
    public string Cast() { if (_playing) { _session.P4Cast("soothe"); Save(); } return ReadState(); }
    public string Talk(long id)
    {
        if (_playing)
        {
            Save(); // Durable boundary before an original multi-page script.
            _session.P4Talk(checked((uint)id));
            if (_session.P4Dialog is not null) _saveStatus = "대화 완료 후 저장";
        }
        return ReadState();
    }
    public string Reply(int kind, int option, string input) { if (_playing) { _session.P4Reply(kind, option, input); Save(); } return ReadState(); }
    public string ShopReply(int tag, string name, int slot, string quantity) { if (_playing) { _session.P4ShopReply(tag, name, slot, quantity); Save(); } return ReadState(); }
    public string CloseDialog() { if (_playing) { _session.P4Close(); Save(); } return ReadState(); }
    public string Say(string text) { if (_playing) { _session.P4Say(text); Save(); } return ReadState(); }
    public string Step() { if (_playing) _world.P4Step(); return ReadState(); }

    public bool CanStep(int x, int y, int nx, int ny)
    {
        if (!_playing) return false;
        int dir = nx == x && ny == y - 1 ? 0 : nx == x + 1 && ny == y ? 1 : nx == x && ny == y + 1 ? 2 : nx == x - 1 && ny == y ? 3 : -1;
        if (dir < 0) return false;
        if (Content.PathHalls.TryGetValue(_character.Map, out var hall) &&
            ((nx is 8 or 9 && ny == 1) || (nx is 1 or 2 && ny == 23 && hall.GuildMap != 0)))
            return true; // native HandleWalk still owns class/alignment gates
        // Warp precedence is original HandleWalk's policy. The actual step
        // still runs its map/quest gates; planning does not bypass them.
        if (nx >= 0 && ny >= 0 && Content.TryWarp(_character.Map, (ushort)nx, (ushort)ny, out var warp) && Content.TryMap(warp.m, out _)) return true;
        var map = MapData.For(_character.Map, _character.MapXs, _character.MapYs)!;
        return !map.BlockedMove(nx, ny, dir) && _world.MobAt(_character.Map, nx, ny) is null;
    }
    public bool ValidCell(int x, int y) => _playing && x >= 0 && y >= 0 && x < _character.MapXs && y < _character.MapYs;

    public string Save()
    {
        // Original Lua can grant an item between two awaited pages and set its
        // quest stage on a later page. Persist the completed conversation as a
        // unit so a cold restart cannot replay a half-committed reward. Shop
        // visits use the same boundary; a pending visit resumes from pre-talk.
        if (_playing && _session.P4Dialog is not null)
        {
            _saveStatus = "대화 완료 후 저장";
            return ReadState();
        }
        if (_playing)
        {
            try
            {
                var data = _session.P4CaptureAll();
                _revision = _checkpoint.Save(data.character, data.world);
                _saveStatus = "저장 완료";
                Checkpoint.AtomicText(Path.Combine(_root, "play-state.json"), ReadState());
            }
            catch (Exception e) { _saveStatus = "저장 실패: " + e.GetBaseException().Message; }
        }
        return ReadState();
    }

    private object Item(InvItem i)
    {
        var d = Content.ItemById(i.ItemId)!;
        return new { slot = i.Slot, id = i.ItemId, key = d.Key, name = d.Name,
            type = d.Type, look = d.Look, dye = d.LookColor, amount = i.Amount, durability = i.Dura, max_durability = d.Durability, buy = d.BuyPrice, sell = d.SellPrice };
    }

    public string ReadState()
    {
        if (!_playing) return JsonSerializer.Serialize(new { ok = _error.Length == 0, playing = false, error = _error, loaded = false });
        var map = MapData.For(_character.Map, _character.MapXs, _character.MapYs)!;
        return JsonSerializer.Serialize(new { ok = true, playing = true, error = _error, loaded = _loaded,
            character = _character, x = _character.X, y = _character.Y, map = _character.Map, facing = _session.P4Facing,
            hp = _character.Hp, max_hp = _character.MaxHp, mp = _character.Mp, max_mp = _character.MaxMp,
            name = _character.Name, level = _character.Level, exp = _character.Exp, coins = _character.Coins,
            stage = _session.P4Stage, kills = _character.Kills, inventory = _character.Inventory.Select(Item).ToArray(),
            equipment = _character.Equipment.Select(Item).ToArray(), appearance = _session.P5Appearance(),
            class_name = _character.ClassName, spellbook = _character.Spells.Select(id => Content.SpellById(id)!).Select(s => new { key = s.Key, name = s.Name, type = s.Type, question = s.Question, mana = Content.SpellFx.TryGetValue(s.Key, out var fx) ? (int?)fx.Mana : null }).ToArray(), spells = _character.Spells.Select(id => Content.SpellById(id)?.Key).ToArray(),
            actors = _world.P4Actors(_character.Map).Select(m => new { id = m.Id, key = m.IsNpc ? Content.NpcById(m.NpcDefId)!.Key : m.Key,
                name = m.Name, npc_def = m.NpcDefId, npc = m.IsNpc, x = m.X, y = m.Y, hp = m.Hp, max_hp = m.MaxHp, facing = m.Dir }).ToArray(),
            loot = _world.ItemsOn(_character.Map).Select(i => new { id = i.Id,
                key = i.ItemId == -1 ? "gold" : Content.ItemById(i.ItemId)?.Key ?? "unknown:" + i.ItemId,
                name = i.ItemId == -1 ? "금전" : Content.ItemById(i.ItemId)?.Name ?? "아이템 " + i.ItemId,
                item_id = i.ItemId, graphic = i.Graphic, x = i.X, y = i.Y, amount = i.Amount }).ToArray(),
            cells = map.RuntimeCells().Select(c => new { x = c.X, y = c.Y, tile = c.Cell.Tile, pass = c.Cell.Pass, obj = c.Cell.Obj }).ToArray(),
            dialog = _session.P4Dialog, message = _session.P4Message, save_status = _saveStatus,
            action = _session.P4Action, action_revision = _session.P4ActionRevision,
            revision = _revision, moves = _moves, blocked = _blocked, warps = _warps, move_failure = _moveFailure,
            world_thread_started = _world.IsStarted, platform = OS.GetName(), build = "0.0.5-p5" }, P4Json.Options);
    }
}
