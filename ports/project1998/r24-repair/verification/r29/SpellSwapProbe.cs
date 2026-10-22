using Server;
using System.Reflection;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using P1998.Embedded;
using Shared;

static class SpellSwapProbe
{
    static readonly List<object> Checks=new();
    static bool Failed;
    static void Check(string name,bool ok,object? observed=null){Checks.Add(new{name,status=ok?"PASS":"FAIL",observed});Failed|=!ok;}
    static async Task<int> Main(string[] a)
    {
        var method=typeof(PlaySession).GetMethod("SwapSpellsAsync");
        Check("touch_client_exposes_original_spell_swap",method is not null);
        if(method is not null)
        {
            var options=new HostOptions(Path.Combine(a[1],"state"),a[0],"sortprobe","Synthetic29!","정렬검사",true,false);
            var p=await PlaySession.OpenAsync(options);await p.StopAsync();
            var store=new CharacterStore(Path.Combine(a[1],"state","chars"));var saved=store.ReadOfflineSnapshot("sortprobe")!;
            var c=CharacterStore.Deserialize(saved.CharacterJson);
            c.Map=332;c.MapXs=Server.Content.Maps[332].Xs;c.MapYs=Server.Content.Maps[332].Ys;c.X=14;c.Y=7;
            c.Spells=Server.Content.Spells.Where(s=>!Server.Content.IsOutOfEraSplitTrap(s)).Take(14).Select(s=>s.Id).ToList();
            c.Inventory.Clear();c.Inventory.Add(new(0,10009,99));c.Mp=100;c.MaxMp=100;c.Hp=100;c.MaxHp=100;
            Check("isolated_seed_commits",store.SaveOfflineSnapshot("sortprobe",CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision).Committed);
            p=await PlaySession.OpenAsync(options with{CreateIfMissing=false});
            var initial=p.Capture();var original=CharacterStore.Deserialize(p.Host.CharacterJson);var expected=original.Spells.ToArray();(expected[0],expected[11])=(expected[11],expected[0]);
            async Task<OfflineActionResult> Swap(byte from,byte to,string? name=null,long? epoch=null)
            {
                var s=p.Capture();
                try{return await (Task<OfflineActionResult>)method.Invoke(p,new object[]{from,to,name??s.Spells.Single(x=>x.WireSlot==from).Name,s.Spells.Single(x=>x.WireSlot==to).Name,epoch??s.MapEpoch})!;}
                catch(TargetInvocationException e)when(e.InnerException is not null){throw e.InnerException;}
            }
            var result=await Swap(1,12);var after=CharacterStore.Deserialize(p.Host.CharacterJson);
            Check("cross_page_swap_uses_original_handler_and_commits",result.Committed&&after.Spells.SequenceEqual(expected));
            Check("swapping_never_casts_or_changes_resources",after.Mp==original.Mp&&after.Coins==original.Coins&&after.Inventory.Select(i=>(i.ItemId,i.Amount,i.Dura)).SequenceEqual(original.Inventory.Select(i=>(i.ItemId,i.Amount,i.Dura))));
            Check("wire_slots_retain_correct_spell_identities",p.Capture().Spells.Single(x=>x.WireSlot==1).Name==initial.Spells.Single(x=>x.WireSlot==12).Name&&p.Capture().Spells.Single(x=>x.WireSlot==12).Name==initial.Spells.Single(x=>x.WireSlot==1).Name);
            string before=p.Host.CharacterJson;
            try{await Swap(1,2,"stale skill");Check("stale_spell_identity_is_rejected",false);}catch(InvalidOperationException){Check("stale_spell_identity_is_rejected",before==p.Host.CharacterJson);}
            try{await Swap(1,2,epoch:p.Capture().MapEpoch-1);Check("old_map_epoch_is_rejected",false);}catch(InvalidOperationException){Check("old_map_epoch_is_rejected",before==p.Host.CharacterJson);}
            await p.StopAsync();p=await PlaySession.OpenAsync(options with{CreateIfMissing=false});
            Check("spell_order_survives_full_save_and_reopen",CharacterStore.Deserialize(p.Host.CharacterJson).Spells.SequenceEqual(expected));
            using(var cn=new SqliteConnection("Data Source="+Path.Combine(a[1],"state/project1998.db")))
            {
                cn.Open();using var q=cn.CreateCommand();q.CommandText="CREATE TRIGGER r29_swap_failure BEFORE UPDATE ON characters BEGIN SELECT RAISE(ABORT,'R29_INJECTED_WRITE_FAILURE'); END;";q.ExecuteNonQuery();
            }
            before=p.Host.CharacterJson;
            var failed=await Swap(1,2);
            Check("failed_full_commit_rolls_back_spell_order",!failed.Committed&&p.Host.CharacterJson==before);
            Check("failed_swap_never_publishes_new_slot_names",p.Capture().Spells.Single(x=>x.WireSlot==1).Name==initial.Spells.Single(x=>x.WireSlot==12).Name);
            await p.StopAsync();
        }
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=Failed?"FAIL":"PASS_ORIGINAL_SPELL_SWAP_FULL_SAVE_AND_ROLLBACK",checks=Checks,physical_android="NOT_RUN",user_save_writes=0},new JsonSerializerOptions{WriteIndented=true}));
        return Failed?1:0;
    }
}
