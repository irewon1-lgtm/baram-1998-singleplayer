using System.Reflection;
using System.Text;
using System.Text.Json;
using Server;
using Shared;

// Compiled twice: once against the unmodified pinned original server, once
// against the app's private adapter. Fixtures are isolated from the journey.
if (args.Length != 3) throw new ArgumentException("content state output");
Environment.SetEnvironmentVariable("P1998_GAME_DATA", Path.GetFullPath(args[0]));
Environment.SetEnvironmentVariable("P1998_STATE", Path.GetFullPath(args[1]));
Environment.SetEnvironmentVariable("P1998_LOGS", Path.Combine(Path.GetFullPath(args[1]), "logs"));
Directory.CreateDirectory(args[1]); Content.Load();
var options = new JsonSerializerOptions { IncludeFields = true, WriteIndented = true };
var trace = new List<object>();
var c = CharacterFactory.FromCreate("ParityHero", new byte[] { 0, 0, 1, 0, 0 });
c.Map = 4711; c.MapXs = c.MapYs = 16; c.X = 8; c.Y = 14; c.Hp = 40; c.MaxHp = 55; c.Mp = 10; c.MaxMp = 36;
var world = new World(); var session = new Session(new Sink(), 2006, new CharacterStore(Path.Combine(args[1], "chars")), world, c);
world.EnterMap(session, c.Map);
object? Invoke(string name, params object[] values) => typeof(Session).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Instance)!.Invoke(session, values);
T State<T>(Func<T> fn) => (T)typeof(Session).GetMethods(BindingFlags.NonPublic | BindingFlags.Instance)
    .Single(m => m.Name == "WithState" && m.IsGenericMethodDefinition).MakeGenericMethod(typeof(T)).Invoke(session, new object[] { fn })!;
void Save(string label, object? result = null) => trace.Add(new { label, result, c.Map, c.X, c.Y, c.Level, c.Hp, c.Mp, c.Coins,
    c.Armor, c.Weapon, c.Spells, c.Quests, inventory = c.Inventory.Select(i => new { i.ItemId, i.Slot, i.Amount, i.Dura }).ToArray(),
    equipment = c.Equipment.Select(i => new { i.ItemId, i.Slot, i.Amount, i.Dura }).ToArray() });
void Walk(int d) {
#if ADAPTER
    session.P4Walk(d);
#else
    State(() => { Invoke("HandleWalk", new byte[] { (byte)d }); return true; });
#endif
}
void Use(int slot, bool eat) {
#if ADAPTER
    session.P4Use(slot, eat);
#else
    State(() => { Invoke("HandleUseItem", new byte[] { (byte)(slot + 1) }, eat); return true; });
#endif
}
Save("names", new[] { "ab", "ParityHero", "a1b", "테스트" }.Select(n => NameRules.ShapeProblem(n)).ToArray());
Save("start"); Walk(2); Save("real exit to field"); Walk(0); Save("source return to Welcome");
foreach (var key in new[] { "apple", "wine", "wooden_saber", "spring_garb" })
{
    int amount = key == "apple" ? 2 : 1;
    int placed = State(() => (int)Invoke("GivePlaced", Content.ItemByKey(key)!, amount, (ushort)0, "", false, "")!);
    Save("fixture grant " + key, placed);
}
Use(c.Inventory.Single(i => Content.ItemById(i.ItemId)!.Key == "apple").Slot, true); Save("original apple Lua");
Use(c.Inventory.Single(i => Content.ItemById(i.ItemId)!.Key == "wine").Slot, false); Save("original wine Lua");
Use(c.Inventory.Single(i => Content.ItemById(i.ItemId)!.Key == "wooden_saber").Slot, false); Save("equip wooden saber");
Use(c.Inventory.Single(i => Content.ItemById(i.ItemId)!.Key == "spring_garb").Slot, false); Save("equip spring garb");
byte worn = c.Equipment.Single(i => Content.ItemById(i.ItemId)!.Key == "wooden_saber").Slot;
#if ADAPTER
session.P4Unequip(worn);
#else
State(() => { if ((bool)typeof(Session).GetMethod("ActionBudgetLeft", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(session, null)!) Invoke("HandleUnequip", new[] { worn }); return true; });
#endif
Save("unequip wooden saber");
State(() => { Invoke("LearnSpellFromNpc", Content.SpellByKey("soothe")!); return true; }); Save("fixture learn Soothe");
c.Hp = 30; c.Mp = 36;
Thread.Sleep(1100); // The original per-second action budget remains active.
#if ADAPTER
session.P4Cast("soothe");
#else
State(() => { if ((bool)Invoke("ActionAllowed", ClientOp.Cast)!) Invoke("HandleCast", new byte[] { 1 }); return true; });
#endif
Save("original Soothe cast");
File.WriteAllText(args[2], JsonSerializer.Serialize(new { schema = "p4.deterministic.parity.v1", random_draws_in_compared_actions = 0,
    scope = "Names, source exit/return, item Lua, equip/unequip, known Soothe. Spawn RNG excluded; combat/level rolls tested in natural journey.", trace }, options));
Console.WriteLine("P4_PARITY_TRACE " + trace.Count);

sealed class Sink : IOutbound
{
    public string Remote => "parity-fixture";
    public int Capacity => int.MaxValue;
    public int QueueDepth => 0;
    public bool Send(byte[] bytes) => true;
    public void Close() { }
}
