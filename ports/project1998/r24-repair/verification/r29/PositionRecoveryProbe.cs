using System.Reflection;
using System.Text.Json;
using System.Security.Cryptography;
using Microsoft.Data.Sqlite;
using P1998.Embedded;
using Shared;

static class PositionRecoveryProbe
{
    static readonly List<object> Checks=new();static bool Failed;
    static void Check(string n,bool ok,object? observed=null){Checks.Add(new{name=n,status=ok?"PASS":"FAIL",observed});Failed|=!ok;}
    static string NonPosition(string json)
    {
        using var d=JsonDocument.Parse(json);return string.Join("\n",d.RootElement.EnumerateObject().Where(p=>p.Name is not("Map" or "MapXs" or "MapYs" or "X" or "Y")).Select(p=>p.Name+":"+p.Value.GetRawText()));
    }
    static async Task<int> Main(string[] a)
    {
        var root=a[1];var state=Path.Combine(root,"state");var profiles=new LocalProfileStore(root);
        var options=new HostOptions(state,a[0],"totogo","Synthetic29!","totogo",true,false);
        foreach(var id in new[]{"keeper","totogo"})
        {
            var profile=new LocalCharacterProfile(id,"Synthetic29!",id);profiles.Stage(profile);
            var first=await PlaySession.OpenAsync(options with{InternalId=id,DisplayName=id});profiles.CommitSuccessful(profile);await first.StopAsync();
        }
        var store=new CharacterStore(Path.Combine(state,"chars"));
        void Seed(int y,int level=17)
        {
            var old=store.ReadOfflineSnapshot("totogo")!;var c=CharacterStore.Deserialize(old.CharacterJson);var m=Server.Content.Maps[1014];
            c.Map=1014;c.MapXs=m.Xs;c.MapYs=m.Ys;c.X=0;c.Y=(ushort)y;c.Level=(byte)level;c.Exp=47186;c.Coins=61;
            c.MaxHp=781;c.Hp=781;c.MaxMp=694;c.Mp=694;c.Quests["r29_guard"]=42;c.QuestStrings["r29_guard"]="unchanged";
            c.Inventory.Clear();c.Inventory.Add(new(4,10057,1,43){Owner="totogo",CustomName="preserve",Repair=3,Protected=2});
            c.Equipment.Clear();c.Equipment.Add(new(1,102,1,357));c.Spells=Server.Content.Spells.Where(s=>!Server.Content.IsOutOfEraSplitTrap(s)).Take(12).Select(s=>s.Id).ToList();
            var result=store.SaveOfflineSnapshot("totogo",CharacterStore.Serialize(c),old.ExtraJson,old.RuntimeJson,old.CaptureSequence+1,old.Revision);if(!result.Committed)throw new Exception(result.Error);
        }
        Seed(15);var play=await PlaySession.OpenAsync(options with{CreateIfMissing=false});
        await play.TurnAsync(2);await play.StepAsync(2);await play.StepAsync(2);
        var south=play.Capture();await play.TurnAsync(0);await play.StepAsync(0);
        Check("visible_south_fence_prevents_entry_into_closed_strip",south.X==0&&south.Y==15,new{south.X,south.Y,return_y=play.Capture().Y});await play.StopAsync();
        var repairType=typeof(EmbeddedHost).Assembly.GetType("P1998.Embedded.OfflinePositionRecovery");
        Check("position_only_recovery_entry_exists",repairType is not null);
        if(repairType is not null)
        {
            Seed(17);var before=store.ReadOfflineSnapshot("totogo")!;var keeper=store.ReadOfflineSnapshot("keeper")!;
            // An unrecognised future field must survive the repair byte-for-byte too.
            string raw=before.CharacterJson.TrimEnd();raw=raw[..^1]+",\"R29FutureField\": {\"raw\": [1, 2, \"기타 데이터\"]}}";
            var injected=store.SaveOfflineSnapshot("totogo",raw,before.ExtraJson,before.RuntimeJson,before.CaptureSequence+1,before.Revision);if(!injected.Committed)throw new Exception(injected.Error);before=store.ReadOfflineSnapshot("totogo")!;
            var leaseType=typeof(EmbeddedHost).Assembly.GetType("P1998.Embedded.OfflineStateLease")!;
            var acquire=leaseType.GetMethod("Acquire",BindingFlags.Static|BindingFlags.NonPublic)!;
            var recover=repairType.GetMethod("TryRecover",BindingFlags.Static|BindingFlags.NonPublic)!;
            object? Invoke(string id)
            {
                using var lease=(IDisposable)acquire.Invoke(null,new object[]{state})!;
                try{return recover.Invoke(null,new[]{store,(object)state,id,lease});}
                catch(TargetInvocationException e)when(e.InnerException is not null){throw e.InnerException;}
            }
            try{Invoke("totogo");Check("unsupported_future_fields_are_preserved_and_refused",false);}catch(JsonException){Check("unsupported_future_fields_are_preserved_and_refused",store.ReadOfflineSnapshot("totogo")==before);}
            // Return this isolated synthetic fixture to its originally readable schema.
            var compatible=JsonDocument.Parse(before.CharacterJson).RootElement.EnumerateObject().Where(p=>p.Name!="R29FutureField").ToDictionary(p=>p.Name,p=>p.Value.Clone());
            var compatibleSave=store.SaveOfflineSnapshot("totogo",JsonSerializer.Serialize(compatible),before.ExtraJson,before.RuntimeJson,before.CaptureSequence+1,before.Revision);if(!compatibleSave.Committed)throw new Exception(compatibleSave.Error);before=store.ReadOfflineSnapshot("totogo")!;
            var receipt=JsonSerializer.SerializeToElement(Invoke("totogo"));var after=store.ReadOfflineSnapshot("totogo")!;
            using var actual=JsonDocument.Parse(after.CharacterJson);
            Check("recovery_moves_exactly_to_buya_330_29_143",actual.RootElement.GetProperty("Map").GetInt32()==330&&actual.RootElement.GetProperty("X").GetInt32()==29&&actual.RootElement.GetProperty("Y").GetInt32()==143);
            Check("all_other_character_fields_and_raw_values_are_exact",NonPosition(before.CharacterJson)==NonPosition(after.CharacterJson));
            Check("world_runtime_and_other_character_are_unchanged",before.ExtraJson==after.ExtraJson&&before.RuntimeJson==after.RuntimeJson&&store.ReadOfflineSnapshot("keeper")==keeper);
            Check("original_full_commit_revision_advances_once",after.Revision==before.Revision+1&&after.CaptureSequence==before.CaptureSequence+1);
            var archive=receipt.GetProperty("BackupPath").GetString()!;Check("complete_backup_exists_before_position_commit",File.Exists(archive)&&new FileInfo(archive).Length>0);
            var restored=Path.Combine(root,"restored-before-position");OfflineBackupStore.RestoreNew(archive,restored);
            using(var cn=new SqliteConnection("Data Source="+Path.Combine(restored,"state/project1998.db")))
            {cn.Open();using var q=cn.CreateCommand();q.CommandText="SELECT json FROM characters WHERE username='totogo'";Check("backup_restores_original_level17_stuck_save_exactly",(string?)q.ExecuteScalar()==before.CharacterJson);}
            Check("repeated_recovery_does_not_reapply_or_write",Invoke("totogo") is null&&store.ReadOfflineSnapshot("totogo")==after);
            Check("unrelated_character_never_migrates",Invoke("keeper") is null&&store.ReadOfflineSnapshot("keeper")==keeper);
            // Normal app entry must accept the new tuple and its original watermark contract.
            play=await PlaySession.OpenAsync(options with{CreateIfMissing=false});var arrived=play.Capture();
            Check("normal_authenticated_entry_uses_recovered_coordinate",arrived.Map==330&&arrived.X==29&&arrived.Y==143&&arrived.Stats.Level==17);
            await play.TurnAsync(3);await play.StepAsync(3);Check("recovered_character_can_move_normally",play.Capture().Map==330&&play.Capture().X==28&&play.Capture().Y==143);await play.StopAsync();
            Seed(17,16);var wrong=store.ReadOfflineSnapshot("totogo");Check("wrong_level_does_not_match_guard",Invoke("totogo") is null&&store.ReadOfflineSnapshot("totogo")==wrong);
            Seed(17);before=store.ReadOfflineSnapshot("totogo")!;
            play=await PlaySession.OpenAsync(options with{CreateIfMissing=false});
            var automatic=play.Capture();var witness=play.Host.PositionRecovery;
            Check("normal_app_start_applies_recovery_without_manual_invocation",witness is not null&&witness.Status=="APPLIED_AND_VERIFIED_ON_THIS_SAVE"&&File.Exists(witness.BackupPath)&&automatic.Map==330&&automatic.X==29&&automatic.Y==143&&automatic.Stats.Level==17);
            var automaticSaved=store.ReadOfflineSnapshot("totogo")!;
            Check("automatic_start_preserves_exp_coins_items_and_quests",CharacterStore.Deserialize(automaticSaved.CharacterJson).Exp==47186&&NonPosition(before.CharacterJson)==NonPosition(automaticSaved.CharacterJson));
            await play.StopAsync();
            Seed(17);before=store.ReadOfflineSnapshot("totogo")!;
            using(var cn=new SqliteConnection("Data Source="+Path.Combine(state,"project1998.db")))
            {cn.Open();using var q=cn.CreateCommand();q.CommandText="CREATE TRIGGER r29_position_failure BEFORE UPDATE ON characters BEGIN SELECT RAISE(ABORT,'R29_POSITION_WRITE_FAILURE'); END;";q.ExecuteNonQuery();}
            try{Invoke("totogo");Check("failed_position_commit_preserves_original_save",false);}catch(IOException){Check("failed_position_commit_preserves_original_save",store.ReadOfflineSnapshot("totogo")==before);}
        }
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=Failed?"FAIL":"PASS_POSITION_ONLY_BACKUP_RECOVERY_AND_FENCE_PREVENTION",checks=Checks,physical_android="NOT_RUN",actual_user_database="NOT_AVAILABLE; SYNTHETIC_RICH_SAVE_ONLY"},new JsonSerializerOptions{WriteIndented=true}));return Failed?1:0;
    }
}
