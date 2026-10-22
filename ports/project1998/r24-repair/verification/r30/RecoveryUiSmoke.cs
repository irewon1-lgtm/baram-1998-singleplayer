using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using IO=System.IO;

public partial class Main
{
 private static string R30Other(string s){using var d=JsonDocument.Parse(s);return string.Join("\n",d.RootElement.EnumerateObject().Where(p=>p.Name is not("Map" or "MapXs" or "MapYs" or "X" or "Y")).Select(p=>p.Name+":"+p.Value.GetRawText()));}
 private async void BeginR30RecoverySmoke()
 {
  string status="FAIL",error="";
  try
  {
   using var contract=JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root,"ko-contract.json")));await R15Continue(contract.RootElement.GetProperty("id").GetString()!);await R15Return();
   var registry=new LocalProfileStore(_root);var state=IO.Path.Combine(_root,"state");
   foreach(var id in new[]{"gibprobe","gionetest"}){var probe=await PlaySession.OpenAsync(new(state,_content,id,"Synthetic30!",id,true,false));await probe.StopAsync();}
   var profile=new LocalCharacterProfile("totogo","Synthetic30!","totogo");registry.Stage(profile);var initial=await PlaySession.OpenAsync(new(state,_content,profile.Id,profile.Password,profile.Name,true,false));registry.CommitSuccessful(profile);await initial.StopAsync();
   var store=new CharacterStore(IO.Path.Combine(state,"chars"));var old=store.ReadOfflineSnapshot("totogo")!;var c=CharacterStore.Deserialize(old.CharacterJson);var map=Server.Content.Maps[1014];c.Map=1014;c.MapXs=map.Xs;c.MapYs=map.Ys;c.X=0;c.Y=17;c.Level=17;c.Ac=(sbyte)(100-c.Level);c.Exp=47186;c.Coins=61;c.Quests["r30_guard"]=42;c.QuestStrings["r30_guard"]="원문 보존";c.Inventory.Clear();c.Inventory.Add(new(4,10057,1,43){Owner="totogo",CustomName="preserve",Repair=3,Protected=2});
   R27Check("r30_synthetic_stuck_save_seeded_through_original_full_commit",store.SaveOfflineSnapshot("totogo",CharacterStore.Serialize(c),old.ExtraJson,old.RuntimeJson,old.CaptureSequence+1,old.Revision).Committed);
   var before=store.ReadOfflineSnapshot("totogo")!;var legacy=new[]{"gibprobe","gionetest"}.ToDictionary(id=>id,id=>store.ReadOfflineSnapshot(id));
   RefreshProfiles();await R15Continue("totogo");var p=_play!;await InputDelay(200);var scene=p.Capture();
   R27Check("r30_real_character_select_button_enters_buya_330_29_143",scene.EntryComplete&&scene.Map==330&&scene.X==29&&scene.Y==143&&scene.Stats.Level==17&&_fatal.Length==0);
   R27Check("r30_actual_main_login_preserves_every_nonposition_character_field",R30Other(before.CharacterJson)==R30Other(store.ReadOfflineSnapshot("totogo")!.CharacterJson));
   R27Check("r30_real_login_keeps_database_only_legacy_rows_and_missing_credentials",legacy.All(x=>store.ReadOfflineSnapshot(x.Key)==x.Value)&&registry.Load().Characters.Count(x=>x.Issue=="CREDENTIAL_UNAVAILABLE")==2,new{catalog=registry.Load(),legacy_tuples=legacy.ToDictionary(x=>x.Key,x=>store.ReadOfflineSnapshot(x.Key)==x.Value),profile_files=IO.Directory.GetFiles(IO.Path.Combine(_root,"profiles")).Select(IO.Path.GetFileName).ToArray()});
   R27Check("r30_backup_exists_before_normal_world_entry",p.Host.PositionRecovery is{}receipt&&IO.File.Exists(receipt.BackupPath)&&receipt.NonPositionBeforeSha256==receipt.NonPositionAfterSha256);
   await CaptureScreen("r30-totogo-buya");
   var point=_view.GetGlobalTransformWithCanvas()*R21WorldTileCenter(28,143);R15Touch(point,true);await InputDelay(60);R15Touch(point,false);await WaitUi(()=>p.Capture().Map==330&&p.Capture().X==28&&p.Capture().Y==143,"Actual floor tap did not move recovered character",8);
   R27Check("r30_actual_floor_tap_moves_after_recovery",p.Capture().X==28&&p.Capture().Y==143&&!p.Faulted);
   await R15Return();await R15Continue("totogo");p=_play!;var reopened=p.Capture();
   R27Check("r30_actual_return_and_second_login_keep_progress_without_repeat_migration",reopened.Map==330&&reopened.X==28&&reopened.Y==143&&reopened.Stats.Level==17&&reopened.Stats.Experience==47186&&reopened.Stats.Coins==61&&p.Host.PositionRecovery is null);
   R27Check("r30_original_save_and_entry_remain_healthy",p.Host.LastSave.Committed&&!p.Faulted&&_fatal.Length==0);
   status="PASS_ACTUAL_GODOT_MIXED_CATALOG_SELECT_RECOVER_TAP_RETURN_REOPEN";
  }
  catch(Exception e){error=e.ToString();try{await CaptureScreen("r30-failure");}catch(Exception){}}
  AtomicWrite(IO.Path.Combine(_root,"ko-checks.json"),JsonSerializer.Serialize(new{status,checks=_r27Checks,error,physical_android="NOT_RUN",actual_user_database="NOT_AVAILABLE; ISOLATED_MIXED_CATALOG_FIXTURE"},new JsonSerializerOptions{WriteIndented=true}));WriteReport(IO.Path.Combine(_root,"r30-input-result.json"));await End(true);
 }
}
