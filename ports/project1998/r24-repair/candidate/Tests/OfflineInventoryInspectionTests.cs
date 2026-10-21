using System.Reflection;
using Microsoft.Data.Sqlite;
using Protocol.Tk495;
using Server;
using Shared;
using Tests.Support;
using Xunit;

namespace Tests;

[Collection("world")]
public sealed class OfflineInventoryInspectionTests : IDisposable
{
    private readonly string _root=Path.Combine(Path.GetTempPath(),"p1998-r27-inspection-"+Guid.NewGuid().ToString("N"));
    private readonly CharacterStore _store;
    private readonly Character _character;
    private readonly Session _session;
    private string DatabasePath=>Path.Combine(_root,"test.db");
    public OfflineInventoryInspectionTests(SessionFixture fixture)
    {
        Directory.CreateDirectory(_root);
        _store=CharacterStore.ForDatabase(Path.Combine(_root,"legacy"),DatabasePath);
        _character=new Character { SchemaVersion=Character.CurrentSchemaVersion,Name="Inspection27",ClassName="Mage",Level=8,
            Inventory=new(){new InvItem(0,102,1,357){CustomName="Worn test saber",Protected=2},new InvItem(1,10001,3)},
            Equipment=new(){new InvItem(1,46001,1,4567)},Coins=321 };
        _session=new Session(new RecordingOutbound("r27-inspection"),2005,_store,fixture.World,_character);
        _session.EnableOfflineLifecycle();_session.EnableOfflinePersistence();Assert.True(_session.OfflineFlush("initial").Committed);
    }
    [Fact]
    public void CommittedInspectionCarriesActualInstanceAndOriginalDefinitionWithoutSavingNewFields()
    {
        string before=_session.CaptureOfflineCharacterJson();
        var snapshot=_session.CommittedInventoryInspection;
        var weapon=Assert.Single(snapshot.Inventory.Where(i=>i.Definition.Id==102));
        Assert.Same(Content.ItemById(102),weapon.Definition);Assert.Equal(357u,weapon.Dura);
        Assert.Equal("Worn test saber",weapon.CustomName);Assert.Equal(2,weapon.Protected);Assert.Equal(1,weapon.WireSlot);
        var food=Assert.Single(snapshot.Inventory.Where(i=>i.Definition.Id==10001));
        Assert.Equal("heal",food.UseVerb);Assert.Equal("5",food.UseAmount);Assert.Equal(3,food.Amount);
        Assert.Equal(4567u,Assert.Single(snapshot.Equipment).Dura);
        Assert.Equal(before,_store.ReadOfflineSnapshot(_character.Name)!.CharacterJson);
    }
    [Fact]
    public void UnchangedInventoryReusesImmutableInspectionAcrossFullCommits()
    {
        var before=_session.CommittedInventoryInspection;long revision=_session.LastOfflineSaveReceipt.Revision;
        var result=_session.ExecuteOfflineAction(()=>{_character.Coins++;_session.MarkDirty();},_=>{});
        Assert.True(result.Committed);Assert.True(result.Receipt.Revision>revision);
        Assert.Same(before,_session.CommittedInventoryInspection);
    }
    [Fact]
    public void UiInspectionDoesNotWaitForTheSessionMonitor()
    {
        var monitor=typeof(Session).GetField("_state",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(_session)!;
        using var done=new ManualResetEventSlim();OfflineInventoryInspection? observed=null;
        var reader=new Thread(()=>{observed=_session.CommittedInventoryInspection;done.Set();});
        lock(monitor)
        {
            reader.Start();
            Assert.True(done.Wait(TimeSpan.FromSeconds(1)),"Reading a committed item must not acquire the held game monitor.");
        }
        reader.Join();Assert.Same(_session.CommittedInventoryInspection,observed);
    }
    [Theory]
    [InlineData("amount")][InlineData("durability")][InlineData("owner")][InlineData("protection")]
    [InlineData("custom-name")][InlineData("definition")][InlineData("slot")]
    public void ChangedItemIsRefusedBeforeTheOriginalHandlerOrAnyCommit(string change)
    {
        var previous=_session.CommittedInventoryInspection.Find(2,false)!;
        var changed=_session.ExecuteOfflineAction(()=>
        {
            var item=_character.Inventory[1];
            switch(change)
            {
                case "amount":item.Amount++;break;case "durability":item.Dura=1;break;case "owner":item.Owner="SomeoneElse";break;
                case "protection":item.Protected=1;break;case "custom-name":item.CustomName="Renamed";break;
                case "definition":item.ItemId=10002;break;case "slot":item.Slot=5;break;
            }
            _session.MarkDirty();
        },_=>{});
        Assert.True(changed.Committed);
        long revision=_session.LastOfflineSaveReceipt.Revision;string before=_session.CaptureOfflineCharacterJson();bool called=false;
        var refused=_session.ExecuteOfflineAction(()=>called=true,_=>{},expectedBagItem:previous);
        Assert.True(refused.Cancelled);Assert.False(refused.Committed);Assert.False(called);
        Assert.Equal(before,_session.CaptureOfflineCharacterJson());Assert.Equal(revision,_store.ReadOfflineSnapshot(_character.Name)!.Revision);
    }
    [Fact]
    public void FailedRealEatCommitKeepsPreviousPublishedInspectionAndRestoresFood()
    {
        var before=_session.CommittedInventoryInspection;var food=before.Find(2,false)!;
        using(var db=Db.Open(DatabasePath))using(var command=db.CreateCommand())
        { command.CommandText="CREATE TRIGGER fail_r27 BEFORE UPDATE ON offline_snapshots BEGIN SELECT RAISE(ABORT,'r27 injected commit failure'); END;";command.ExecuteNonQuery(); }
        bool? published=null;
        var action=_session.ExecuteOfflineAction(()=>_session.ReceiveEmbeddedFrame(TkPacket.Build(ClientOp.Eat,0,
            TkCrypt.Crypt(new byte[]{2},0,TkCrypt.LoginKey))),ok=>published=ok,expectedBagItem:food);
        Assert.False(action.Committed);Assert.True(action.CharacterRestored);Assert.False(published);
        Assert.Same(before,_session.CommittedInventoryInspection);
        Assert.Equal(3,CharacterStore.Deserialize(_session.CaptureOfflineCharacterJson()).Inventory.Single(i=>i.ItemId==10001).Amount);
        using(var db=Db.Open(DatabasePath))using(var command=db.CreateCommand())
        {command.CommandText="DROP TRIGGER fail_r27";command.ExecuteNonQuery();}
    }
    public void Dispose(){SqliteConnection.ClearAllPools();Directory.Delete(_root,recursive:true);}
}
