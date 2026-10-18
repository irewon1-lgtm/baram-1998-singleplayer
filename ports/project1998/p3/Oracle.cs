using System.Text.Json;
using P1998.P3;
using Server;
using Shared;

if (args.Length != 4) throw new ArgumentException("content fixture isolated-state output");
Directory.CreateDirectory(args[2]);
Environment.SetEnvironmentVariable("P1998_GAME_DATA", Path.GetFullPath(args[0]));
Environment.SetEnvironmentVariable("P1998_STATE", Path.GetFullPath(args[2]));
Environment.SetEnvironmentVariable("P1998_LOGS", Path.Combine(Path.GetFullPath(args[2]), "logs"));
Content.Load();
using var fixture = JsonDocument.Parse(File.ReadAllText(args[1]));
var store = new CharacterStore(Path.Combine(args[2], "chars"));
var scenario = new Scenario(store, fixture.RootElement);
scenario.Run(fixture.RootElement);
File.WriteAllText(args[3], JsonSerializer.Serialize(scenario.Result(fixture.RootElement), Scenario.Json));
Console.WriteLine($"P3_ORACLE_PASS trace={scenario.Trace.Count} worldStarted={scenario.World.IsStarted}");
