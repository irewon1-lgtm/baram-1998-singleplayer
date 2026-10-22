using System.Text.Json;
using P1998.Embedded;
using Shared;
using Microsoft.Data.Sqlite;
using System.IO.Compression;

static class LegacyCatalogRecoveryProbe
{
 static string Other(string s){using var d=JsonDocument.Parse(s);return string.Join("\n",d.RootElement.EnumerateObject().Where(p=>p.Name is not("Map" or "MapXs" or "MapYs" or "X" or "Y")).Select(p=>p.Name+":"+p.Value.GetRawText()));}
 static string Tables(string root)
 {
  using var cn=new SqliteConnection("Data Source="+Path.Combine(root,"state/project1998.db")+";Mode=ReadOnly");cn.Open();using var q=cn.CreateCommand();q.CommandText="SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name";var names=new List<string>();using(var rows=q.ExecuteReader())while(rows.Read())names.Add(rows.GetString(0));var result=new Dictionary<string,string[]>();
  foreach(var name in names){using var cmd=cn.CreateCommand();cmd.CommandText="SELECT * FROM \""+name.Replace("\"","\"\"")+"\"";using var rows=cmd.ExecuteReader();var values=new List<string>();while(rows.Read()){var cells=new object[rows.FieldCount];rows.GetValues(cells);values.Add(JsonSerializer.Serialize(cells));}result[name]=values.Order().ToArray();}return JsonSerializer.Serialize(result);
 }
 static async Task<int> Main(string[] a)
 {
  var root=a[1];var state=Path.Combine(root,"state");var registry=new LocalProfileStore(root);var checks=new List<object>();bool fail=false;
  void Check(string n,bool ok,object? observed=null){checks.Add(new{name=n,status=ok?"PASS":"FAIL",observed});fail|=!ok;}
  var options=new HostOptions(state,a[0],"totogo","Synthetic30!","totogo",true,false);
  // The original diagnostic's two probes predate device-profile archiving. Create
  // their real DB accounts directly; never stage a device credential for them.
  foreach(var id in new[]{"gibprobe","gionetest"}){var p=await PlaySession.OpenAsync(options with{InternalId=id,DisplayName=id});await p.StopAsync();}
  var totogo=new LocalCharacterProfile("totogo","Synthetic30!","totogo");registry.Stage(totogo);var initial=await PlaySession.OpenAsync(options);registry.CommitSuccessful(totogo);await initial.StopAsync();
  var store=new CharacterStore(Path.Combine(state,"chars"));var prior=store.ReadOfflineSnapshot("totogo")!;var c=CharacterStore.Deserialize(prior.CharacterJson);var map=Server.Content.Maps[1014];
  c.Map=1014;c.MapXs=map.Xs;c.MapYs=map.Ys;c.X=0;c.Y=17;c.Level=17;c.Ac=(sbyte)(100-c.Level);c.Exp=47186;c.Coins=61;c.Quests["preserved"]=42;c.QuestStrings["preserved"]="원문";
  c.Inventory.Clear();c.Inventory.Add(new(4,10057,1,43){Owner="totogo",CustomName="keep",Repair=3,Protected=2});
  var seeded=store.SaveOfflineSnapshot("totogo",CharacterStore.Serialize(c),prior.ExtraJson,prior.RuntimeJson,prior.CaptureSequence+1,prior.Revision);if(!seeded.Committed)throw new IOException(seeded.Error);
  var before=store.ReadOfflineSnapshot("totogo")!;var originalTables=Tables(root);var oldProbes=new[]{"gibprobe","gionetest"}.ToDictionary(id=>id,id=>store.ReadOfflineSnapshot(id));
  var catalog=registry.Load();Check("fixture_matches_actual_diagnostic_two_database_only_accounts",catalog.Characters.Count(x=>x.Issue=="CREDENTIAL_UNAVAILABLE")==2&&catalog.Characters.Single(x=>x.Id=="totogo").CanOpen,catalog);
  string? error=null;PositionRecoveryReceipt? receipt=null;PlaySession? play=null;
  try{play=await PlaySession.OpenAsync(options with{CreateIfMissing=false});receipt=play.Host.PositionRecovery;var s=play.Capture();Check("normal_start_recovers_totogo_with_legacy_accounts_present",s.EntryComplete&&s.Map==330&&s.X==29&&s.Y==143&&receipt is not null,new{s.Map,s.X,s.Y});}
  catch(Exception e){error=e.ToString();Check("normal_start_recovers_totogo_with_legacy_accounts_present",false,error);}
  var after=store.ReadOfflineSnapshot("totogo")!;Check("other_character_fields_preserved",Other(before.CharacterJson)==Other(after.CharacterJson));Check("legacy_database_only_character_tuples_preserved",oldProbes.All(p=>store.ReadOfflineSnapshot(p.Key)==p.Value));
  if(play is not null){await play.TurnAsync(3);await play.StepAsync(3);Check("actual_original_move_after_automatic_recovery",play.Capture().Map==330&&play.Capture().X==28&&play.Capture().Y==143);await play.StopAsync();}
  if(receipt is not null){var restored=Path.Combine(root,"restored-original");OfflineBackupStore.RestoreNew(receipt.BackupPath,restored);OfflineStoredSnapshot? Restored(string id){using var cn=new SqliteConnection("Data Source="+Path.Combine(restored,"state/project1998.db")+";Mode=ReadOnly");cn.Open();using var q=cn.CreateCommand();q.CommandText="SELECT c.json,o.extra_json,o.runtime_json,o.revision,o.capture_sequence FROM characters c JOIN offline_snapshots o ON c.username=o.username WHERE c.username=$u";q.Parameters.AddWithValue("$u",id);using var row=q.ExecuteReader();return row.Read()?new(row.GetString(0),row.GetString(1),row.GetString(2),row.GetInt64(3),row.GetInt64(4)):null;}Check("whole_backup_restores_original_stuck_totogo_exactly",Restored("totogo")==before);Check("every_original_sqlite_table_is_preserved_by_backup",Tables(restored)==originalTables);Check("whole_backup_restores_unopenable_legacy_accounts_without_inventing_credentials",oldProbes.All(p=>Restored(p.Key)==p.Value)&&new LocalProfileStore(restored).Load().Characters.Count(p=>p.Issue=="CREDENTIAL_UNAVAILABLE")==2);OfflineBackupStore.ValidateRoot(restored);Check("original_backup_restore_admission_accepts_preserved_legacy_catalog",true);}
  if(receipt is not null)
  {
   bool denied=false;try{registry.Get("gibprobe");}catch(InvalidOperationException){denied=true;}Check("legacy_accounts_do_not_gain_invented_credentials_or_login",denied);
   int serial=0;void MustRefuse(string name){var archive=Path.Combine(root,"refused-"+(++serial)+".zip");bool rejected=false;try{OfflineBackupStore.Create(root,archive);}catch(InvalidDataException){rejected=true;}Check(name,rejected&&!File.Exists(archive));}
   var selected=Path.Combine(root,"local-character-selection-v1.json");var selection=File.ReadAllText(selected);File.WriteAllText(selected,"{\"Version\":1,\"SelectedId\":\"gibprobe\"}");MustRefuse("selected_account_without_credentials_still_refuses_backup");File.WriteAllText(selected,selection);
   var malformed=Path.Combine(root,"profiles/malformed.json");File.WriteAllText(malformed,"{bad");MustRefuse("malformed_archived_credential_still_refuses_backup");File.Delete(malformed);
   var watermark=Path.Combine(state,"offline-save-watermarks/gibprobe.json");var witness=File.ReadAllText(watermark);File.WriteAllText(watermark,"{bad");MustRefuse("legacy_account_save_witness_corruption_still_refuses_backup");File.WriteAllText(watermark,witness);
   var badArchive=Path.Combine(root,"corrupted-backup.zip");File.Copy(receipt.BackupPath,badArchive);using(var zip=ZipFile.Open(badArchive,ZipArchiveMode.Update)){var entry=zip.GetEntry("g2-local-profile.json")!;entry.Delete();using var writer=new StreamWriter(zip.CreateEntry("g2-local-profile.json").Open());writer.Write("{}");}
   var refusedRoot=Path.Combine(root,"must-not-publish");bool badHash=false;try{OfflineBackupStore.RestoreNew(badArchive,refusedRoot);}catch(InvalidDataException){badHash=true;}Check("changed_archive_payload_is_rejected_before_restore",badHash&&!Directory.Exists(refusedRoot));
   var existingBefore=Tables(root);bool overwrite=false;try{OfflineBackupStore.RestoreNew(receipt.BackupPath,root);}catch(IOException){overwrite=true;}Check("restore_never_overwrites_existing_player_root",overwrite&&Tables(root)==existingBefore);
  }
  File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=fail?"FAIL_REPRODUCED_R29_CATALOG_BACKUP_STARTUP_BLOCK":"PASS_MIXED_LEGACY_CATALOG_RECOVERY",checks,error,physical_android="NOT_RUN",actual_user_database="NOT_AVAILABLE; CATALOG_SHAPE_FROM_ACTUAL_SUPPLIED_DIAGNOSTIC"},new JsonSerializerOptions{WriteIndented=true}));return fail?1:0;
 }
}
