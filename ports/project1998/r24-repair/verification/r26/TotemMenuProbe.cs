using System.Reflection;
using System.Text.Json;
using P1998.Embedded;
using Server;
using Shared;

static class TotemMenuProbe
{
 static async Task<int> Main(string[] a)
 {
  var checks=new List<object>();bool failed=false;
  void Check(string name,bool pass,object? observed=null){checks.Add(new{name,status=pass?"PASS":"FAIL",observed});failed|=!pass;}
  var options=new HostOptions(a[1],a[0],"totemprobe","Synthetic26!","totemprobe",true,false);
  var p=await PlaySession.OpenAsync(options);await p.StopAsync();
  var store=new CharacterStore(Path.Combine(a[1],"chars"));var saved=store.ReadOfflineSnapshot(options.InternalId)!;
  var c=CharacterStore.Deserialize(saved.CharacterJson);var shrine=Content.NpcById(388)!;var map=Content.Maps[shrine.Map];
  c.Map=map.Id;c.MapXs=map.Xs;c.MapYs=map.Ys;c.X=shrine.X;c.Y=(ushort)(shrine.Y+1);c.Level=30;c.Totem=0;
  var acorn=Content.ItemByKey("gold_acorn")!;c.Inventory.Clear();c.Inventory.Add(new InvItem(0,acorn.Id,5));
  if(!store.SaveOfflineSnapshot(c.Name,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision).Committed)throw new IOException("Fixture save failed");
  p=await PlaySession.OpenAsync(options with{CreateIfMissing=false});
  var world=(World)typeof(EmbeddedHost).GetField("_world",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(p.Host)!;
  var npc=world.NpcsNear(shrine.Map,shrine.X,shrine.Y,100).Single(n=>n.NpcDefId==388);
  async Task<SceneDialogSnapshot> Wait(Func<SceneDialogSnapshot,bool> predicate){for(int i=0;i<500;i++){if(p.Capture().Dialog is{}d&&predicate(d))return d;await Task.Delay(10);}throw new TimeoutException(JsonSerializer.Serialize(p.Capture().Dialog));}
  async Task Pick(string text){var d=await Wait(d=>d.Options.Any(o=>o.Contains(text,StringComparison.OrdinalIgnoreCase)));int index=Array.FindIndex(d.Options,o=>o.Contains(text,StringComparison.OrdinalIgnoreCase))+1;var r=await p.ReplyAsync(2,menu:index,expectedDialogSequence:d.Sequence);if(!r.Committed)throw new IOException(r.Error);}
  await p.ClickAsync(npc.Id);var first=await Wait(d=>d.Options.Length>0);
  Check("current_shrine_menu_contains_recovered_entries",first.Options.Any(x=>x.StartsWith("Worship ")),first.Options);
  await Pick("Worship ");await Pick("Yes");await Pick("five Gold acorns");
  await Wait(d=>d.Text.Contains("accepts your devotion",StringComparison.OrdinalIgnoreCase));
  var changed=CharacterStore.Deserialize(p.Host.CharacterJson);
  Check("named_original_worship_route_spends_exact_tribute",changed.Totem==1&&changed.Inventory.All(i=>i.ItemId!=acorn.Id),new{changed.Totem,changed.Quests});
  await p.StopAsync();p=await PlaySession.OpenAsync(options with{CreateIfMissing=false});var reopened=CharacterStore.Deserialize(p.Host.CharacterJson);
  Check("totem_and_worship_quest_survive_normal_reopen",reopened.Totem==1&&changed.Quests.All(q=>reopened.Quests.GetValueOrDefault(q.Key)==q.Value));await p.StopAsync();
  File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=failed?"FAIL":"PASS",checks,physical_android="NOT_RUN",scope="Current named shrine options, original input+FULL SQLite+normal authenticated reopen. Original hardcoded-menu xUnit failure remains reported."},new JsonSerializerOptions{WriteIndented=true}));return failed?1:0;
 }
}
