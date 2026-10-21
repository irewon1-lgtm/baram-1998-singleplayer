using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Data.Sqlite;
using Server;
using Shared;

Environment.SetEnvironmentVariable("P1998_GAME_DATA", args[0]); Environment.SetEnvironmentVariable("P1998_STATE", args[1]);
Directory.CreateDirectory(args[1]); Content.Load();
using var connection = new SqliteConnection("Data Source=" + args[3] + ";Mode=ReadOnly"); connection.Open();
using var command = connection.CreateCommand(); command.CommandText = "SELECT extra_json FROM offline_snapshots WHERE username='growthprobe'";
string json = (string)command.ExecuteScalar()!;
var world = new World(new GameClock()); world.RestoreOfflineStateJson(json);
var expected = JsonNode.Parse(json)!.AsObject(); expected.Remove("EmbeddedMapState");
var actual = JsonNode.Parse(world.CaptureOfflineStateJson());
bool equal = JsonNode.DeepEquals(expected, actual);
var state = JsonSerializer.Deserialize<World.OfflineState>(json)!;
File.WriteAllText(args[2], JsonSerializer.Serialize(new { status = equal ? "PASS" : "FAIL",
    existing_r25_reader_accepts_r26_world_snapshot_without_field_changes = equal,
    materialized_maps = state.Population.Maps.Length, monsters = state.Creatures!.Maps.Sum(m => m.Mobs.Length),
    physical_android = "NOT_RUN", scope = "Executed with frozen original r25 Server/Host DLLs against new r26 committed snapshot. No user data." }, new JsonSerializerOptions { WriteIndented = true }));
return equal ? 0 : 1;
