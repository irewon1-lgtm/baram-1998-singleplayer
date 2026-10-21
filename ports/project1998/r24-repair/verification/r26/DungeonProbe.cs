using P1998.Embedded;
using Protocol.Tk495;
using Server;
using Shared;
using System.Buffers.Binary;
using System.Text.Json;

Environment.SetEnvironmentVariable("P1998_GAME_DATA",args[0]);Environment.SetEnvironmentVariable("P1998_STATE",args[1]);Directory.CreateDirectory(args[1]);Content.Load();
var checks=new List<object>();bool failed=false;
void Check(string name,bool pass,object? evidence=null){checks.Add(new{name,status=pass?"PASS":"FAIL",evidence});failed|=!pass;}
int[]? Route(ushort mid,int sx,int sy,int tx,int ty,HashSet<(int,int)> occupied){
 var m=MapData.For(mid)!;var q=new Queue<(int x,int y)>();q.Enqueue((sx,sy));var previous=new Dictionary<(int,int),(int,int,int)>();var seen=new HashSet<(int,int)>{(sx,sy)};
 while(q.TryDequeue(out var p)){
  if(p==(tx,ty)){var list=new List<int>();while(previous.TryGetValue(p,out var v)){list.Add(v.Item3);p=(v.Item1,v.Item2);}list.Reverse();return list.ToArray();}
  for(int d=0;d<4;d++){int x=p.x+(d==1?1:d==3?-1:0),y=p.y+(d==2?1:d==0?-1:0);if(x<0||y<0||x>=m.Xs||y>=m.Ys||seen.Contains((x,y)))continue;
   bool warp=Content.TryWarp(mid,(ushort)x,(ushort)y,out _);if(warp&&(x,y)!=(tx,ty))continue;
   if(!warp&&(m.BlockedMove(x,y,d)||occupied.Contains((x,y))))continue;
   seen.Add((x,y));previous[(x,y)]=(p.x,p.y,d);q.Enqueue((x,y));}
 }return null;
}
foreach(ushort city in new ushort[]{0,330}){
 ushort[] chain=city==0?new ushort[]{50,51,52,53,54,55}:new ushort[]{370,371,372,373,374,375};
 var entry=Content.Warps.First(w=>w.Key.m==city&&w.Value.m==chain[0]);var terrain=MapData.For(city)!;
 var options=new List<(int x,int y,int length)>();
 for(int y=Math.Max(0,entry.Key.y-8);y<=Math.Min(terrain.Ys-1,entry.Key.y+8);y++)for(int x=Math.Max(0,entry.Key.x-8);x<=Math.Min(terrain.Xs-1,entry.Key.x+8);x++){
  if(terrain.Pass(x,y)!=0||terrain.Obj(x,y)!=0||Content.TryWarp(city,(ushort)x,(ushort)y,out _))continue;
  var path=Route(city,x,y,entry.Key.x,entry.Key.y,new());if(path is {Length:>=5 and <=15})options.Add((x,y,path.Length));}
 if(options.Count==0){Check("ordinary_road_start_"+city,false);continue;}
 var start=options.OrderBy(x=>Math.Abs(x.length-8)).First();var map=Content.Maps[city];
 var clock=new GameClock();clock.Resume();var world=new World(clock);var outbound=new BoundedOutbound(16384);
 var store=CharacterStore.ForDatabase(Path.Combine(args[1],"legacy"+city),Path.Combine(args[1],"route"+city+".db"));
 var c=new Character{SchemaVersion=Character.CurrentSchemaVersion,Id=world.AllocatePlayerId(),Name="route"+city,Map=city,MapXs=map.Xs,MapYs=map.Ys,X=(ushort)start.x,Y=(ushort)start.y,Level=30,ClassName="Warrior",Hp=1000,MaxHp=1000,Mp=1000,MaxMp=1000,Coins=123456};
 var session=new Session(outbound,2005,store,world,c);session.EnableOfflineLifecycle();session.EnableOfflinePersistence();world.EnterMap(session,city);outbound.Drain();
 int moves=0;var travelled=new List<object>();
 bool WalkTo(ushort target){
  var current=CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());
  var exits=Content.Warps.Where(w=>w.Key.m==current.Map&&w.Value.m==target).ToArray();
  var occupied=new HashSet<(int,int)>();
  for(int retry=0;retry<12;retry++){
   current=CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());
   var paths=exits.Select(w=>(w,route:Route(current.Map,current.X,current.Y,w.Key.x,w.Key.y,occupied))).Where(x=>x.route is not null).OrderBy(x=>x.route!.Length).ToArray();
   if(paths.Length==0)return false;var chosen=paths[0];bool blocked=false;
   foreach(int d in chosen.route!){
    var old=CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());var b=new byte[6];b[0]=(byte)d;BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(2),old.X);BinaryPrimitives.WriteUInt16BigEndian(b.AsSpan(4),old.Y);
    outbound.BeginStage();var receipt=session.ExecuteOfflineAction(()=>session.ReceiveEmbeddedFrame(TkPacket.Build(ClientOp.Walk,0,TkCrypt.Crypt(b,0,TkCrypt.LoginKey))),outbound.CompleteStage);outbound.Drain();
    var after=CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());moves++;
    if(!receipt.Committed)return false;
    if(old.Map!=after.Map){travelled.Add(new{from=old.Map,to=after.Map,from_x=old.X,from_y=old.Y,after.X,after.Y,warp_x=chosen.w.Key.x,warp_y=chosen.w.Key.y});return after.Map==target;}
    if(old.X==after.X&&old.Y==after.Y){Thread.Sleep(650);world.TickOffline();outbound.Drain();occupied.Clear();blocked=true;break;}
   }if(!blocked)return false;
  }return false;
 }
 bool pass=true;foreach(ushort next in chain){if(!WalkTo(next)){pass=false;break;}}
 if(pass)foreach(ushort next in chain.Reverse().Skip(1).Append(city)){if(!WalkTo(next)){pass=false;break;}}
 var final=CharacterStore.Deserialize(session.CaptureOfflineCharacterJson());
 Check("city_dungeon_six_floors_roundtrip_"+city,pass&&final.Map==city,new{start,moves,travelled,final.Map,final.X,final.Y});
 Check("route_save_money_and_progress_preserved_"+city,final.Coins==123456&&final.Level==30&&session.LastOfflineSaveReceipt.Committed,new{final.Coins,final.Level,session.LastOfflineSaveReceipt});
 session.StopOffline();session.EndEmbeddedSessionAsync().GetAwaiter().GetResult();
}
File.WriteAllText(args[2],JsonSerializer.Serialize(new{status=failed?"FAIL":"PASS",checks,physical_android="NOT_RUN",scope="Original Session walk+SQLite from ordinary road, both rat/bat chains to deepest room and back. Synthetic prerequisite character, not user's current dungeon identification."},new JsonSerializerOptions{WriteIndented=true}));return failed?1:0;
