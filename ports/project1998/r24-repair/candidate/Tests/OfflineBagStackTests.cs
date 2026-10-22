using System.Reflection;
using Microsoft.Data.Sqlite;
using Protocol.Tk495;
using Server;
using Shared;
using Tests.Support;
using Xunit;
namespace Tests;
[Collection("world")]
public sealed class OfflineBagStackTests : IDisposable
{
    private readonly string _root=Path.Combine(Path.GetTempPath(),"p1998-r28-stack-"+Guid.NewGuid().ToString("N"));
    private readonly CharacterStore _store;private readonly Session _session;private readonly Character _char;
    private static readonly MethodInfo Give=typeof(Session).GetMethod("GivePlaced",BindingFlags.Instance|BindingFlags.NonPublic)!;
    public OfflineBagStackTests(SessionFixture fixture)
    {
        Directory.CreateDirectory(_root);_store=CharacterStore.ForDatabase(Path.Combine(_root,"legacy"),Path.Combine(_root,"test.db"));
        _char=new Character{SchemaVersion=Character.CurrentSchemaVersion,Name="Stack28",Level=99,Hp=80,MaxHp=100,Might=100,Sex=1};
        _session=new Session(new RecordingOutbound("stack28"),2005,_store,fixture.World,_char);
        _session.EnableOfflineLifecycle();_session.EnableOfflinePersistence();Assert.True(_session.OfflineFlush("initial").Committed);
    }
    private int Put(int id,int amount,InvItem? instance=null)
    {
        int placed=0;var def=Content.ItemById(id)!;
        var r=_session.ExecuteOfflineAction(()=>placed=(int)Give.Invoke(_session,new object?[]{def,amount,instance?.Dura??0u,instance?.CustomName??"",false,instance?.Owner??"",instance})!,_=>{});
        Assert.True(r.Committed,r.Error);return placed;
    }
    [Fact] public void HundredAcornsOccupyNinetyNineAndOneAndMoreStacksAreAllowed()
    {Assert.Equal(100,Put(10009,100));Assert.Equal(new[]{99,1},_char.Inventory.OrderBy(i=>i.Slot).Select(i=>i.Amount));Assert.Equal(200,Put(10009,200));Assert.Equal(new[]{99,99,99,3},_char.Inventory.OrderBy(i=>i.Slot).Select(i=>i.Amount));}
    [Fact] public void FoodAndIdenticalEquipmentAlsoUseNinetyNineLimit()
    {Assert.Equal(100,Put(10002,100));Assert.Equal(new[]{99,1},_char.Inventory.Select(i=>i.Amount));Assert.Equal(2,Put(102,2));Assert.Equal(2,_char.Inventory.Single(i=>i.ItemId==102).Amount);}
    [Theory][InlineData("owner")][InlineData("name")][InlineData("dura")][InlineData("repair")][InlineData("protected")]
    public void EveryDifferentInstanceStateRemainsSeparate(string property)
    {
        var a=new InvItem(0,102,1,357){CustomName="Same",Owner="Stack28",Protected=2,Repair=1};var b=a.Clone();
        switch(property){case"owner":b.Owner="Other";break;case"name":b.CustomName="Different";break;case"dura":b.Dura--;break;case"repair":b.Repair++;break;case"protected":b.Protected++;break;}
        Put(102,2,a);Put(102,1,b);Assert.Equal(2,_char.Inventory.Count);Assert.Equal(3,_char.Inventory.Sum(i=>i.Amount));
    }
    [Fact] public void PlainGrantCannotMergeIntoProtectedOrOwnedOrDamagedStack()
    {Put(102,2,new InvItem(0,102,1,357){Protected=1,Owner="Other"});Put(102,2);Assert.Equal(2,_char.Inventory.Count);}
    [Fact] public void FullPackPartialPlacementDebitsOnlyWhatActuallyFits()
    {Put(10001,98);for(int n=1;n<_char.MaxInv;n++)_char.Inventory.Add(new InvItem((byte)n,102,1,(uint)(100+n)));Assert.Equal(1,Put(10001,5));Assert.Equal(99,_char.Inventory.First().Amount);}
    [Fact] public void FailedCommitRestoresOriginalQuantitiesAndPublishedInspection()
    {
        Put(10001,98);string before=_session.CaptureOfflineCharacterJson();var inspection=_session.CommittedInventoryInspection;
        using(var db=Db.Open(Path.Combine(_root,"test.db")))using(var c=db.CreateCommand()){c.CommandText="CREATE TRIGGER fail28 BEFORE UPDATE ON offline_snapshots BEGIN SELECT RAISE(ABORT,'injected28'); END;";c.ExecuteNonQuery();}
        var r=_session.ExecuteOfflineAction(()=>Give.Invoke(_session,new object?[]{Content.ItemById(10001)!,5,0u,"",false,"",null}),_=>{});
        Assert.False(r.Committed);Assert.Equal(before,_session.CaptureOfflineCharacterJson());Assert.Same(inspection,_session.CommittedInventoryInspection);
    }
    [Fact] public void EquippingOneKeepsNinetyEightAndAllInstanceMetadata()
    {Put(102,99,new InvItem(0,102,1,357){Protected=2,Repair=1});var r=_session.ExecuteOfflineAction(()=>_session.ReceiveEmbeddedFrame(TkPacket.Build(ClientOp.Wield,0,TkCrypt.Crypt(new byte[]{1},0,TkCrypt.LoginKey))),_=>{});Assert.True(r.Committed,r.Error);Assert.Equal(98,_char.Inventory.Single().Amount);var worn=Assert.Single(_char.Equipment);Assert.Equal(1,worn.Amount);Assert.Equal(357u,worn.Dura);Assert.Equal(2,worn.Protected);}
    [Fact] public void ExistingIndividualEquipmentCompactsWithoutChangingItsState()
    {
        _char.Inventory=new(){new InvItem(0,102,1,357){Protected=2},new InvItem(1,102,1,357){Protected=2},new InvItem(2,102,1,356){Protected=2},new InvItem(3,10009,201)};
        var r=_session.ExecuteOfflineAction(_session.CompactOfflineInventory,_=>{});Assert.True(r.Committed,r.Error);
        Assert.Equal(5,_char.Inventory.Count);Assert.Equal(204,_char.Inventory.Sum(i=>i.Amount));
        Assert.Equal(new[]{99,99,3},_char.Inventory.Where(i=>i.ItemId==10009).OrderBy(i=>i.Slot).Select(i=>i.Amount));
        Assert.Contains(_char.Inventory,i=>i.ItemId==102&&i.Dura==357&&i.Protected==2&&i.Amount==2);
        Assert.Equal(CharacterStore.Serialize(_char),_store.ReadOfflineSnapshot(_char.Name)!.CharacterJson);
    }
    [Fact] public void LegacyOverCapStockWithNoRoomIsPreservedAndNeverTruncated()
    {
        _char.Inventory=new(){new InvItem(0,10009,201)};
        for(int n=1;n<_char.MaxInv;n++)_char.Inventory.Add(new InvItem((byte)n,102,1,(uint)(100+n)));
        string before=CharacterStore.Serialize(_char);
        var r=_session.ExecuteOfflineAction(_session.CompactOfflineInventory,_=>{});Assert.True(r.Committed,r.Error);
        Assert.Equal(before,CharacterStore.Serialize(_char));Assert.Equal(201,_char.Inventory[0].Amount);
    }
    [Fact] public void OneChargedUnitIsDetachedWithoutChangingOtherUnitsCharges()
    {
        Put(10049,3);var r=_session.ExecuteOfflineAction(()=>_session.ReceiveEmbeddedFrame(TkPacket.Build(ClientOp.UseItem,0,TkCrypt.Crypt(new byte[]{1},0,TkCrypt.LoginKey))),_=>{});
        Assert.True(r.Committed,r.Error);Assert.Equal(3,_char.Inventory.Sum(i=>i.Amount));
        Assert.Contains(_char.Inventory,i=>i.ItemId==10049&&i.Amount==2&&i.Dura==Content.ItemById(10049)!.Durability);
    }
    [Fact] public void LegacyVaultWithdrawalSplitsAndPreservesEveryTransferredField()
    {
        _char.BankItems.Add(new InvItem(0,102,200,357){CustomName="Exact",Owner="Stack28",Repair=2,Protected=3});
        var method=typeof(Session).GetMethod("WithdrawItemFromBank",BindingFlags.Instance|BindingFlags.NonPublic)!;
        var npc=new Mob(0x1234,0,0,0,"Bank",1);
        var r=_session.ExecuteOfflineAction(()=>method.Invoke(_session,new object[]{npc,"Wooden saber",200}),_=>{});
        Assert.True(r.Committed,r.Error);Assert.Empty(_char.BankItems);Assert.Equal(new[]{99,99,2},_char.Inventory.OrderBy(i=>i.Slot).Select(i=>i.Amount));
        Assert.All(_char.Inventory,i=>{Assert.Equal("Exact",i.CustomName);Assert.Equal("Stack28",i.Owner);Assert.Equal(357u,i.Dura);Assert.Equal(2,i.Repair);Assert.Equal(3,i.Protected);});
    }
    [Fact] public void VaultOnlyDebitsTheAmountThatFitsInAFullBag()
    {
        Put(10009,98);for(int n=1;n<_char.MaxInv;n++)_char.Inventory.Add(new InvItem((byte)n,102,1,(uint)(100+n)));
        _char.BankItems.Add(new InvItem(0,10009,150));
        var method=typeof(Session).GetMethod("WithdrawItemFromBank",BindingFlags.Instance|BindingFlags.NonPublic)!;
        var r=_session.ExecuteOfflineAction(()=>method.Invoke(_session,new object[]{new Mob(0x1234,0,0,0,"Bank",1),"Acorn",150}),_=>{});
        Assert.True(r.Committed,r.Error);Assert.Equal(149,_char.BankItems.Single().Amount);Assert.Equal(99,_char.Inventory.First().Amount);
    }
    [Fact] public void AlreadyPackedBagRetainsExactSavedListOrderAndObjectIdentities()
    {
        _char.Inventory=new(){new InvItem(7,10009,2),new InvItem(0,102,1,357),new InvItem(3,10001,2)};
        string before=CharacterStore.Serialize(_char);var references=_char.Inventory.ToArray();
        var r=_session.ExecuteOfflineAction(_session.CompactOfflineInventory,_=>{});Assert.True(r.Committed,r.Error);
        Assert.Equal(before,CharacterStore.Serialize(_char));Assert.True(references.Zip(_char.Inventory).All(p=>ReferenceEquals(p.First,p.Second)));
    }
    public void Dispose(){_session.AbandonOfflinePersistence("isolated stack test finished");}
}
