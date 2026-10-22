using P1998.Embedded;
using Protocol.Tk495;
using Server;
using Shared;
using System.Buffers.Binary;
using System.Text.Json;

Environment.SetEnvironmentVariable("P1998_GAME_DATA",args[0]);Environment.SetEnvironmentVariable("P1998_STATE",args[1]);Directory.CreateDirectory(args[1]);Content.Load();
long now=0;var clock=new GameClock(monotonicMs:()=>now);clock.Resume();var world=new World(clock);
var store=CharacterStore.ForDatabase(Path.Combine(args[1],"legacy"),Path.Combine(args[1],"sweep.db"));
string root=Path.GetDirectoryName(args[2])!;using var writer=new StreamWriter(Path.Combine(root,"warp-execution.jsonl"));
int index=0;var totals=new Dictionary<string,int>();var visited=new HashSet<ushort>();
(int x,int y) Delta(int d)=>(d==1?1:d==3?-1:0,d==2?1:d==0?-1:0);
int[]? PathTo(ushort mid,(int x,int y) start,(int x,int y) goal,HashSet<(int,int)> blocked){
 var map=MapData.For(mid)!;var q=new Queue<(int x,int y)>();q.Enqueue(start);var previous=new Dictionary<(int,int),((int x,int y) p,int d)>();var seen=new HashSet<(int,int)>{start};
 while(q.TryDequeue(out var p)){
  if(p==goal){var ds=new List<int>();while(previous.TryGetValue(p,out var old)){ds.Add(old.d);p=old.p;}ds.Reverse();return ds.ToArray();}
  for(int d=0;d<4;d++){var delta=Delta(d);var next=(x:p.x+delta.x,y:p.y+delta.y);if(next.x<0||next.y<0||next.x>=map.Xs||next.y>=map.Ys||seen.Contains(next)||blocked.Contains(next))continue;
   bool warp=Content.TryWarp(mid,(ushort)next.x,(ushort)next.y,out _);if(warp&&next!=goal)continue;if(!warp&&map.BlockedMove(next.x,next.y,d))continue;
   previous[next]=(p,d);seen.Add(next);q.Enqueue(next);
  }
 }return null;
}
(int x,int y)? OrdinaryStart(ushort mid,(int x,int y) goal){
 var map=MapData.For(mid)!;for(int radius=5;radius<=12;radius++)for(int d=0;d<4;d++){
  var delta=Delta(d);var p=(x:goal.x+delta.x*radius,y:goal.y+delta.y*radius);
  if(p.x<0||p.y<0||p.x>=map.Xs||p.y>=map.Ys||map.Pass(p.x,p.y)!=0||Content.TryWarp(mid,(ushort)p.x,(ushort)p.y,out _))continue;
  var route=PathTo(mid,p,goal,new());if(route is {Length:>=5 and <=50})return p;
 }return null;
}
var filter = args.Length>3 ? File.ReadLines(args[3]).Select(l=>JsonDocument.Parse(l)).Where(d=>d.RootElement.GetProperty("status").GetString()=="PASS_SCOPED_HOST_ROAD_ENTRY_INTERIOR_RETURN").Select(d=>(d.RootElement.GetProperty("source_map").GetUInt16(),d.RootElement.GetProperty("x").GetUInt16(),d.RootElement.GetProperty("y").GetUInt16())).ToHashSet() : null;
foreach(var row in Content.Warps.Where(w=>w.Key.m==1014||w.Value.m==1014).OrderBy(w=>w.Key.m).ThenBy(w=>w.Key.y).ThenBy(w=>w.Key.x)){
 var key=row.Key;if(filter is not null&&!filter.Contains((key.m,key.x,key.y)))continue;var destination=row.Value;string status="NOT_RUN",detail="";int walks=0;bool entered=false,interior=false,returned=false,outsideMoved=false;Session? session=null;
 try{
  if(!Content.Maps.TryGetValue(key.m,out var mi)||key.x>=mi.Xs||key.y>=mi.Ys){status="EXCLUDED_INVALID_SOURCE_COORDINATE";detail="Original runtime table row retained; cannot walk to a tile outside the registered terrain.";}
  else if(OrdinaryStart(key.m,(key.x,key.y))is not{} start){status="REVIEW_NO_FIVE_STEP_ORDINARY_APPROACH";}
  else{
   Content.MapMeta.TryGetValue(destination.m,out var gate);int level=gate is null?30:Math.Max(1,gate.ReqLvl);if(gate?.LvlMax>0)level=Math.Min(level,gate.LvlMax);
   string name="sweep"+index;var c=new Character{SchemaVersion=Character.CurrentSchemaVersion,Id=world.AllocatePlayerId(),Name=name,Map=key.m,MapXs=mi.Xs,MapYs=mi.Ys,X=(ushort)start.x,Y=(ushort)start.y,Level=(byte)Math.Clamp(level,1,99),Mark=(byte)Math.Clamp(gate?.ReqMark??0,0,5),ClassName=gate?.ReqPath>0?Content.PathName(gate.ReqPath):"Warrior",Hp=1000,MaxHp=(uint)Math.Max(1000,gate?.ReqVita??0),Mp=1000,MaxMp=(uint)Math.Max(1000,gate?.ReqMana??0),Coins=123456};
   var output=new BoundedOutbound(32768);session=new Session(output,2005,store,world,c);session.EnableOfflineLifecycle();session.EnableOfflinePersistence();world.EnterMap(session,key.m);output.Drain();visited.Add(key.m);
   Character Current()=>CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());
   bool MoveTo(ushort map,(int x,int y) goal){var blocked=new HashSet<(int,int)>();for(int retry=0;retry<16;retry++){
     var before=Current();if(before.Map!=map)return false;var path=PathTo(map,(before.X,before.Y),goal,blocked);if(path is null)return false;bool blockedOnce=false;
     foreach(int d in path){before=Current();var b=new byte[6];b[0]=(byte)d;BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(2),before.X);BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(4),before.Y);output.BeginStage();var receipt=session.ExecuteOfflineAction(()=>session.ReceiveEmbeddedFrame(TkPacket.Build(ClientOp.Walk,0,TkCrypt.Crypt(b,0,TkCrypt.LoginKey))),output.CompleteStage);output.Drain();walks++;now+=335;
      if(!receipt.Committed)throw new IOException("Actual movement did not commit: "+receipt.Error);var after=Current();
      if(after.Map!=before.Map)return true;
      if(after.X==before.X&&after.Y==before.Y){var delta=Delta(d);blocked.Add((before.X+delta.x,before.Y+delta.y));blockedOnce=true;break;}
     }if(!blockedOnce)return true;
    }return false;}
   bool approached=MoveTo(key.m,(key.x,key.y));var after=Current();entered=approached&&after.Map==destination.m&&(destination.m!=key.m||after.X==destination.x&&after.Y==destination.y);
   if(!entered){status="REVIEW_ORIGINAL_ENTRY_REFUSED_OR_DYNAMIC_BLOCKED";detail="Original handlers enforced; no gate waived, no monsters removed, no teleport used.";}
   else{
    visited.Add(after.Map);var dm=MapData.For(after.Map)!;
    // Walk to an interior ordinary tile at least three steps from arrival, without crossing another portal.
    for(int d=0;d<4&&!interior;d++){var delta=Delta(d);var goal=(x:after.X+3*delta.x,y:after.Y+3*delta.y);if(goal.x<0||goal.y<0||goal.x>=dm.Xs||goal.y>=dm.Ys||Content.TryWarp(after.Map,(ushort)goal.x,(ushort)goal.y,out _))continue;
     var route=PathTo(after.Map,(after.X,after.Y),goal,new());if(route is {Length:>=3 and <=25})interior=MoveTo(after.Map,goal);}
    if(interior){var current=Current();var exits=Content.Warps.Where(w=>w.Key.m==current.Map&&w.Value.m==key.m).Select(w=>(w,path:PathTo(current.Map,(current.X,current.Y),(w.Key.x,w.Key.y),new()))).Where(x=>x.path is not null).OrderBy(x=>x.path!.Length).ToArray();
     foreach(var exit in exits.Take(3)){if(MoveTo(current.Map,(exit.w.Key.x,exit.w.Key.y))&&Current().Map==key.m){returned=true;break;}}
    }
    if(returned){var outside=Current();for(int d=0;d<4&&!outsideMoved;d++){var delta=Delta(d);var goal=(x:outside.X+delta.x,y:outside.Y+delta.y);var om=MapData.For(outside.Map)!;if(goal.x<0||goal.y<0||goal.x>=om.Xs||goal.y>=om.Ys||Content.TryWarp(outside.Map,(ushort)goal.x,(ushort)goal.y,out _))continue;var path=PathTo(outside.Map,(outside.X,outside.Y),goal,new());if(path is {Length:1})outsideMoved=MoveTo(outside.Map,goal)&&Current().Map==outside.Map&&(Current().X!=outside.X||Current().Y!=outside.Y);}}
    status=entered&&interior&&returned&&outsideMoved?"PASS_SCOPED_HOST_COMPLETE_ROUNDTRIP_WITH_OUTSIDE_MOVE":"REVIEW_ENTERED_INTERIOR_OR_RETURN_NOT_COMPLETED";
   }
  }
 }catch(Exception e){status="FAIL_EXECUTION";detail=e.GetType().Name+": "+e.Message;}
 finally{if(session is not null){session.StopOffline();session.EndEmbeddedSessionAsync().GetAwaiter().GetResult();}}
 totals[status]=totals.GetValueOrDefault(status)+1;writer.WriteLine(JsonSerializer.Serialize(new{source_map=key.m,x=key.x,y=key.y,destination_map=destination.m,dx=destination.x,dy=destination.y,status,detail,walks,entered,interior,returned,outsideMoved,conditions="Original condition handling; synthetic destination-level/class prerequisites. No quest stages waived. Condition-negative matrix NOT_RUN.",physical_android="NOT_RUN"}));writer.Flush();index++;
 if(index%100==0){File.WriteAllText(Path.Combine(root,"SWEEP-PROGRESS.json"),JsonSerializer.Serialize(new{processed=index,total=Content.Warps.Count,totals}));Console.WriteLine("SWEEP "+index+"/"+Content.Warps.Count);}
}
File.WriteAllText(args[2],JsonSerializer.Serialize(new{status="MAP1014_TEN_ENTRIES_EXECUTED_REVIEW_PER_ROW",processed=index,total=Content.Warps.Count,visited_maps=visited.Count,totals,scope="Original Session walking and actual SQLite on isolated prerequisite characters. Five-step ordinary approach and three-step interior traversal; synthetic accelerated clock; no GameView/visual or physical touch PASS implied.",physical_android="NOT_RUN"},new JsonSerializerOptions{WriteIndented=true}));return 0;
