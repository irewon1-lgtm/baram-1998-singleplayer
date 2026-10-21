using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using P1998.Embedded;
using Protocol.Tk495;
using Server;
using Shared;

static class TransactionProbe
{
    sealed class Queued : SynchronizationContext
    {
        readonly ConcurrentQueue<(SendOrPostCallback,object?)> q = new();
        public int Pending => q.Count;
        public override void Post(SendOrPostCallback callback, object? state) => q.Enqueue((callback,state));
        public void Capture(Action body) { var old=Current; try { SetSynchronizationContext(this); body(); } finally { SetSynchronizationContext(old); } }
        public void Run() { int bound=200; while(q.TryDequeue(out var x)) { if(--bound==0)throw new Exception("Continuation loop"); Capture(()=>x.Item1(x.Item2)); } Drain(); }
    }
    static readonly List<object> Checks = new();
    static bool Failed; static int Number; static string Root="";
    static Session S=null!; static World W=null!; static CharacterStore Store=null!; static BoundedOutbound O=null!;
    static byte[]? Prompt; static readonly List<(byte Op,byte[] Body)> Frames=new();
    static Character Live=>CharacterStore.Deserialize(S.CaptureOfflineCharacterJson());
    static void Check(string name,bool pass,object? observed=null) { Checks.Add(new {name,status=pass?"PASS":"FAIL",observed}); Failed|=!pass; }
    static void Drain() { foreach(var f in O.Drain()) if(TkPacket.TryParse(f,out var p,out _)) { var b=TkCrypt.Crypt(p.Body,p.Increment,TkCrypt.LoginKey); Frames.Add((p.Opcode,b)); if(p.Opcode==ServerOp.NpcDialog)Prompt=b; } }
    static void Act(byte op,params byte[] b)
    {
        O.BeginStage();
        var r=S.ExecuteOfflineAction(()=>S.ReceiveEmbeddedFrame(TkPacket.Build(op,0,TkCrypt.Crypt(b,0,TkCrypt.LoginKey))),O.CompleteStage);
        if(!r.Committed)throw new Exception("Input failed: "+r.Error);
        Drain();
    }
    static void Init(int npc,Action<Character> setup)
    {
        if(S is not null){S.StopOffline();S.EndEmbeddedSessionAsync().GetAwaiter().GetResult();}
        var folder=Path.Combine(Root,"case"+ ++Number); Directory.CreateDirectory(folder);
        Store=CharacterStore.ForDatabase(Path.Combine(folder,"legacy"),Path.Combine(folder,"probe.db"));
        var d=Content.NpcById(npc)!;var m=Content.Maps[d.Map];var clock=new GameClock();clock.Resume();W=new World(clock);
        var c=new Character{SchemaVersion=Character.CurrentSchemaVersion,Id=W.AllocatePlayerId(),Name="tx"+Number,Map=d.Map,MapXs=m.Xs,MapYs=m.Ys,X=d.X,Y=(ushort)Math.Min(d.Y+1,m.Ys-1),Level=99,Mark=5,Might=240,Hp=50000,MaxHp=50000,Mp=10000,MaxMp=10000,Coins=1000000};
        setup(c);O=new(4096);S=new Session(O,2005,Store,W,c);S.EnableOfflineLifecycle();S.EnableOfflinePersistence();W.EnterMap(S,c.Map);
        if(!S.OfflineFlush("Synthetic explicit prerequisites").Committed)throw new Exception("Initial commit");
        Drain();Frames.Clear();Prompt=null;
    }
    static string[] Options()
    {
        var b=Prompt??throw new Exception("No prompt");if(b[0]!=2)return Array.Empty<string>();
        int at=23+BinaryPrimitives.ReadUInt16BigEndian(b.AsSpan(21)),n=b[at++];var rows=new List<string>();
        for(int i=0;i<n;i++){int len=b[at++];rows.Add(Encoding.ASCII.GetString(b,at,len));at+=len;}return rows.ToArray();
    }
    static void Pick(string label) { int i=Array.IndexOf(Options(),label)+1;if(i==0)throw new Exception("No choice "+label+": "+string.Join("|",Options()));var b=new byte[12];b[0]=2;b[8]=2;b[10]=(byte)i;Act(ClientOp.NpcDialog,b); }
    static void Input(string text){var t=Encoding.ASCII.GetBytes(text);var b=new byte[11+t.Length];b[0]=4;b[8]=2;b[10]=(byte)t.Length;t.CopyTo(b,11);Act(ClientOp.NpcDialog,b);}
    static void Open(int id){var d=Content.NpcById(id)!;var n=W.NpcsNear(d.Map,d.X,d.Y,1000).Single(x=>x.NpcDefId==id);var b=new byte[5];BinaryPrimitives.WriteUInt32BigEndian(b.AsSpan(1),n.Id);Act(ClientOp.ClickInfo,b);}
    static void FailWrites(bool fail)
    {
        using var cn=new SqliteConnection("Data Source="+Store.Directory);cn.Open();using var cmd=cn.CreateCommand();
        cmd.CommandText=fail?"CREATE TRIGGER r25_write_failure BEFORE UPDATE ON characters BEGIN SELECT RAISE(ABORT,'R25_INJECTED_WRITE_FAILURE'); END;":"DROP TRIGGER r25_write_failure";cmd.ExecuteNonQuery();
    }
    static void Repair(string interruption)
    {
        int smith=Content.Npcs.First(x=>x.Enabled&&x.Repair&&!NpcScript.Has(x.Key)).Id;
        var def=Content.Items.First(x=>x.IsEquip&&x.Repairable&&!x.Indestructible&&x.Durability>2&&x.BuyPrice>0);
        Init(smith,c=>c.Inventory.Add(new InvItem(0,def.Id,1){Dura=def.Durability/2}));
        var q=new Queued();q.Capture(()=>Open(smith));Pick("Fix Item");q.Run();Pick(Options().First(x=>x.Contains("[bag 1]")));q.Run();Pick("Repair");
        string before=S.CaptureOfflineCharacterJson();string db=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson;
        if(interruption=="pause")S.PauseOffline();else if(interruption=="stop")S.StopOffline();
        else if(interruption=="graph_replaced")S.ExecuteOfflineAction(()=>throw new Exception("Replace current graph by real rollback"),_=>{});
        else if(interruption=="write_failure")FailWrites(true);
        SqliteConnection? busy = null; SqliteTransaction? writer = null;
        if(interruption=="busy") { busy=new SqliteConnection("Data Source="+Store.Directory);busy.Open();writer=busy.BeginTransaction(deferred:false); }
        int pending=q.Pending;Frames.Clear();q.Run();
        writer?.Dispose();busy?.Dispose();
        bool changed=S.CaptureOfflineCharacterJson()!=before;bool saved=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson!=db;
        Check("repair_"+interruption,pending>0&&(interruption=="success"?Live.Inventory[0].Dura==def.Durability&&saved:!changed&&!saved),new{pending,changed,saved,Live.Coins,dura=Live.Inventory[0].Dura});
        if(interruption=="write_failure")FailWrites(false);
    }
    static void Deferred(string kind,string interruption)
    {
        int cosmetic=Content.Items.First(x=>x.Type==28).Id;
        Init(360,c=>{if(kind=="cosmetic")c.Inventory.Add(new InvItem(0,cosmetic,1));if(kind=="container"){c.Inventory.Add(new InvItem(0,17024,1){Dura=0});c.Inventory.Add(new InvItem(1,13009,5));}});
        var q=new Queued();
        if(kind=="purchase") {q.Capture(()=>Open(360));Pick("Recovered special items");q.Run();Pick("Mount items");q.Run();Pick(Options().First(x=>x.Contains("[item 15001]:")));q.Run();Pick("Buy");}
        else if(kind=="cosmetic") {q.Capture(()=>Act(ClientOp.UseItem,1));Pick("Apply");}
        else {q.Capture(()=>Act(ClientOp.UseItem,1));Pick("Add materials");q.Run();Input("2");}
        string before=S.CaptureOfflineCharacterJson();string db=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson;int pending=q.Pending;
        if(interruption=="write_failure")FailWrites(true);else if(interruption=="pause")S.PauseOffline();else if(interruption=="stop")S.StopOffline();
        SqliteConnection? busy = null; SqliteTransaction? writer = null;
        if(interruption=="busy") { busy=new SqliteConnection("Data Source="+Store.Directory);busy.Open();writer=busy.BeginTransaction(deferred:false); }
        Frames.Clear();q.Run();writer?.Dispose();busy?.Dispose();
        bool changed=S.CaptureOfflineCharacterJson()!=before,saved=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson!=db;
        int outputs=Frames.Count;
        Check(kind+"_deferred_"+interruption,pending>0&&(interruption=="success"?changed&&saved:!changed&&!saved&&outputs==0),new{pending,changed,saved,outputs,receipt=S.LastOfflineSaveReceipt});
        if(interruption=="write_failure")FailWrites(false);
    }
    static void OrdinaryShop(bool sale,string interruption)
    {
        int apple=Content.ItemByKey("apple")!.Id;
        Init(52,c=>{if(sale)c.Inventory.Add(new InvItem(0,apple,1));});
        var q=new Queued();q.Capture(()=>Open(52));Pick(sale?"Sell":"Buy");q.Run();
        if(sale){var b=new byte[8];b[0]=4;b[7]=1;Act(ClientOp.ShopReply,b);q.Run();Pick("Yes");}
        else {var text=Encoding.ASCII.GetBytes("Apple");var b=new byte[8+text.Length];b[0]=2;b[7]=(byte)text.Length;text.CopyTo(b,8);Act(ClientOp.ShopReply,b);}
        string before=S.CaptureOfflineCharacterJson(),db=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson;int pending=q.Pending;
        if(interruption=="pause")S.PauseOffline();else if(interruption=="stop")S.StopOffline();else if(interruption=="write_failure")FailWrites(true);
        else if(interruption=="graph_replaced")S.ExecuteOfflineAction(()=>throw new Exception("Replace current graph"),_=>{});
        Frames.Clear();q.Run();string now=S.CaptureOfflineCharacterJson(),stored=Store.ReadOfflineSnapshot(Live.Name)!.CharacterJson;
        bool changed=now!=before,saved=stored!=db;
        bool pass=pending>0&&(interruption=="success"||!sale&&interruption=="graph_replaced"?changed&&stored==now:!changed&&!saved);
        Check("ordinary_"+(sale?"sale":"purchase")+"_"+interruption,pass,new{pending,changed,saved,live_and_stored_agree=now==stored,outputs=Frames.Count});
        if(interruption=="write_failure")FailWrites(false);
    }
    static int Main(string[] a)
    {
        Root=a[1];Directory.CreateDirectory(Root);Environment.SetEnvironmentVariable("P1998_GAME_DATA",a[0]);Environment.SetEnvironmentVariable("P1998_STATE",Root);
        Content.Load();NpcScript.Load(Path.Combine(a[0],"npc_dialog.lua"));
        try {if(a.Length>3&&a[3]=="ordinary-only") {foreach(bool sale in new[]{false,true})foreach(var mode in new[]{"success","pause","stop","write_failure","graph_replaced"})OrdinaryShop(sale,mode);}else {foreach(var mode in new[]{"success","pause","stop","graph_replaced","write_failure","busy"})Repair(mode);foreach(var kind in new[]{"purchase","cosmetic","container"})foreach(var mode in new[]{"success","pause","stop","write_failure","busy"})Deferred(kind,mode);}}
        catch(Exception e){Check("execution",false,e.ToString());}
        finally {if(S is not null){S.StopOffline();S.EndEmbeddedSessionAsync().GetAwaiter().GetResult();}}
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=Failed?"FAIL":"PASS",category=a.Length>3?"10_UNIQUE_ORDINARY_SHOP_SCENARIOS":"21_UNIQUE_QUEUED_CHARACTER_TRANSACTION_SCENARIOS",checks=Checks,physical_android="NOT_RUN",world_rollback="NOT_CLAIMED"},new JsonSerializerOptions{WriteIndented=true}));return Failed?1:0;
    }
}
