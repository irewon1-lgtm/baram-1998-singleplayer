using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Data.Sqlite;
using Server;
using Shared;

Environment.SetEnvironmentVariable("P1998_GAME_DATA", args[0]); Environment.SetEnvironmentVariable("P1998_STATE", args[1]);
Directory.CreateDirectory(args[1]); Content.Load(); var checks = new List<object>(); bool failed = false;
void Check(string name, bool pass, object? evidence = null) { checks.Add(new { name, status = pass ? "PASS" : "FAIL", evidence }); failed |= !pass; }
long mono = 0; var clock = new GameClock(monotonicMs: () => mono); var world = new World(clock);
world.BindRestoredOfflineOwner("stableowner", 123);
var item = new GroundItem { Id = world.AllocateItemId(), ItemId = Content.ItemByKey("acorn")!.Id, X = 5, Y = 6,
    Amount = 17, Dura = 712, Graphic = 214, CustomName = "continuity fixture", Owner = "stableowner",
    LooterId = 123, LockedUntil = Environment.TickCount64 + 300000, Repair = 2, Protected = 3 };
world.DropItem(4711, item);
var mob = new Mob(world.AllocateMobId(), 1, 8, 9, "continuity", 100) { Hp = 63, HomeX = 8, HomeY = 9,
    OwnerId = 123, TargetId = 123, PoisonOwnerId = 123, PoisonUntil = 1000, Handed = new() { new InvItem(0, item.ItemId, 5) } };
world.AddMob(4711, mob);
string saved = world.CaptureOfflineStateJson(); long restartMono = 1000000;
var restartedClock = new GameClock(monotonicMs: () => restartMono); var restarted = new World(restartedClock);
restarted.RestoreOfflineStateJson(saved); restarted.BindRestoredOfflineOwner("stableowner", 456);
var floor = restarted.ItemsOn(4711).Single();
Check("stable_floor_owner_rebound_without_numeric_id_reuse", floor.LooterId == 456 && floor.BelongsTo(456) && floor.LockedAgainst(123));
Check("all_item_payload_fields_preserved", floor.Id == item.Id && floor.ItemId == item.ItemId && floor.Amount == 17 && floor.Dura == 712
    && floor.Graphic == 214 && floor.CustomName == item.CustomName && floor.Owner == item.Owner && floor.Repair == 2 && floor.Protected == 3);
var state = JsonSerializer.Deserialize<World.OfflineState>(restarted.CaptureOfflineStateJson())!;
var creature = state.Creatures!.Maps.Single(m => m.Map == 4711).Mobs.Single();
var restoredMob = creature.Data.Deserialize<Mob>(new JsonSerializerOptions { IncludeFields = true })!;
Check("creature_damage_owner_poison_and_handed_item_preserved", restoredMob.Hp == 63 && creature.OwnerId == 456
    && restoredMob.PoisonOwnerId == 456 && restoredMob.Handed!.Single().Amount == 5);
long remaining = state.Floor!.Maps.Single().Items.Single().LockRemainingMilliseconds;
restartMono += 900000000; Check("paused_reboot_time_does_not_consume_item_reservation", floor.LockedAgainst(123));
restartedClock.Resume(); restartMono += remaining - 1; Check("reservation_remains_until_last_active_millisecond", floor.LockedAgainst(123));
restartMono++; Check("reservation_expires_after_active_time", !floor.LockedAgainst(123));

File.WriteAllText(args[2], JsonSerializer.Serialize(new { status = failed ? "FAIL" : "PASS", checks, physical_android = "NOT_RUN", scope = "Stable-account floor ownership, all item payloads, monster damage/ownership/poison/handed items and paused/active reservation time. Historical bad-room database branch NOT_RUN; it requires its separate original fixture." }, new JsonSerializerOptions { WriteIndented = true }));
return failed ? 1 : 0;
