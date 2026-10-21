using System.Text.Json;
using Shared;

static class CrashProbe
{
    static int Main(string[] a)
    {
        string root=a[1],mode=a[3];Directory.CreateDirectory(root);
        var store=CharacterStore.ForDatabase(Path.Combine(root,"legacy"),Path.Combine(root,"crash.db"));store.InitializeOfflinePersistence();
        if(mode=="seed")
        {
            var c=new Character{Name="crashfixture",Coins=1000};
            if(!store.SaveOfflineSnapshot(c.Name,CharacterStore.Serialize(c),"{}","{}",1,0).Committed)return 1;
            return 0;
        }
        var old=store.ReadOfflineSnapshot("crashfixture")!;
        if(mode=="before"||mode=="after")
        {
            var c=CharacterStore.Deserialize(old.CharacterJson);c.Coins-=100;c.Inventory.Add(new InvItem(0,15001,1));
            var result=store.SaveOfflineSnapshot(c.Name,CharacterStore.Serialize(c),"{}","{}",2,1,
                mode=="before"?(cn,tx)=>
                {
                    // A real uncommitted write, then the parent sends SIGKILL. Never a mocked receipt.
                    using var cmd=cn.CreateCommand();cmd.Transaction=tx;cmd.CommandText="UPDATE characters SET updated_utc=123 WHERE username='crashfixture'";cmd.ExecuteNonQuery();
                    File.WriteAllText(a[4],"uncommitted");Thread.Sleep(Timeout.Infinite);return true;
                }:null);
            if(!result.Committed)return 2;
            File.WriteAllText(a[4],"committed");Thread.Sleep(Timeout.Infinite);return 0;
        }
        var actual=CharacterStore.Deserialize(old.CharacterJson);bool committed=mode=="verify_after";
        bool pass=committed?actual.Coins==900&&actual.Inventory.Count==1&&old.Revision==2:actual.Coins==1000&&actual.Inventory.Count==0&&old.Revision==1;
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=pass?"PASS":"FAIL",mode,actual.Coins,inventory=actual.Inventory.Count,old.Revision,scope="actual SQLite atomic snapshot killed immediately before or after commit; no world rollback claim"}));return pass?0:1;
    }
}
