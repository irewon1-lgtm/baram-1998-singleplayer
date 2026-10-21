using Server;
using System.Text.Json;
using System.Security.Cryptography;
using System.Buffers.Binary;

Environment.SetEnvironmentVariable("P1998_GAME_DATA",args[0]);Content.Load();
string folder=Path.GetDirectoryName(args[2])!;Directory.CreateDirectory(folder);
var mapRows=new List<object>();var warpRows=new List<object>();
var bySource=Content.Warps.GroupBy(w=>w.Key.m).ToDictionary(g=>g.Key,g=>g.ToArray());
var arrivals=Content.Warps.GroupBy(w=>w.Value.m).ToDictionary(g=>g.Key,g=>g.ToArray());
var terrainHashes=new HashSet<string>();
foreach(var pair in Content.Maps.OrderBy(x=>x.Key)){
 ushort id=pair.Key;var info=pair.Value;var map=MapData.For(id,info.Xs,info.Ys);
 if(map is null){mapRows.Add(new{id,status="BLOCKED_MISSING_TERRAIN",visual="NOT_RUN",roundtrip="NOT_RUN"});continue;}
 int width=info.Xs,height=info.Ys,n=width*height;var bytes=new byte[n*4];
 for(int i=0;i<n;i++){BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(i*4),map.GroundWord(i%width,i/width));BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(i*4+2),map.Obj(i%width,i/width));}
 string hash=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
 var outbound=bySource.GetValueOrDefault(id)??Array.Empty<KeyValuePair<(ushort m,ushort x,ushort y),(ushort m,ushort x,ushort y)>>();
 var portal=new HashSet<int>(outbound.Where(w=>w.Key.x<width&&w.Key.y<height).Select(w=>w.Key.y*width+w.Key.x));
 var distance=Enumerable.Repeat(-1,n).ToArray();var q=new Queue<int>();foreach(int p in portal){distance[p]=0;q.Enqueue(p);}
 // Reverse all four directed movement edges. Portal cells are terminal, never shortcuts.
 while(q.TryDequeue(out int v)){
  int x=v%width,y=v/width;
  for(int d=0;d<4;d++){
   int sx=x-(d==1?1:d==3?-1:0),sy=y-(d==2?1:d==0?-1:0);
   if(sx<0||sy<0||sx>=width||sy>=height)continue;int u=sy*width+sx;
   if(distance[u]>=0||portal.Contains(u)||(!portal.Contains(v)&&map.BlockedMove(x,y,d)))continue;
   if(map.Pass(sx,sy)!=0||Enumerable.Range(0,4).All(k=>ObjectFlags.Blocks(map.Obj(sx,sy),k)))continue;
   distance[u]=distance[v]+1;q.Enqueue(u);
  }
 }
 int arrivalCount=0,isolated=0;
 foreach(var row in arrivals.GetValueOrDefault(id)??Array.Empty<KeyValuePair<(ushort m,ushort x,ushort y),(ushort m,ushort x,ushort y)>>()){
  int x=Math.Clamp((int)row.Value.x,0,width-1),y=Math.Clamp((int)row.Value.y,0,height-1);arrivalCount++;if(distance[y*width+x]<0)isolated++;
 }
 foreach(var row in outbound){
  var k=row.Key;var dest=row.Value;bool inBounds=k.x<width&&k.y<height;
  bool approachable=inBounds&&Enumerable.Range(0,4).Any(d=>{int x=k.x-(d==1?1:d==3?-1:0),y=k.y-(d==2?1:d==0?-1:0);return x>=0&&y>=0&&x<width&&y<height&&distance[y*width+x]>0;});
  Content.MapMeta.TryGetValue(dest.m,out var gate);
  bool destinationBounds=Content.Maps.TryGetValue(dest.m,out var dm)&&dest.x<dm.Xs&&dest.y<dm.Ys;
  bool quest=Content.WarpQuestLocks.ContainsKey((id,dest.m));
  warpRows.Add(new{map=id,x=k.x,y=k.y,destination=dest.m,dx=dest.x,dy=dest.y,source_in_bounds=inBounds,destination_in_bounds=destinationBounds,directional_approach=approachable,
   destination_req_level=gate?.ReqLvl??0,destination_req_path=gate?.ReqPath??0,quest_lock=quest,
   condition_execution="NOT_RUN",saved_dynamic_doors="NOT_RUN_USER_SAVE",occupancy="STATIC_TERRAIN_ONLY_DYNAMIC_RECHECK_REQUIRED",visual="NOT_RUN",roundtrip="NOT_RUN",status=!inBounds||!destinationBounds||!approachable?"REVIEW":"STATIC_ONLY"});
 }
 bool first=terrainHashes.Add(hash);
 if(first){string path=Path.Combine(folder,"terrain",hash+".bin");Directory.CreateDirectory(Path.GetDirectoryName(path)!);File.WriteAllBytes(path,bytes);}
 mapRows.Add(new{id,name=info.Name,width,height,terrain_sha256=hash,shared_analysis=!first,effective_warps=outbound.Length,inbound=arrivalCount,arrivals_without_static_exit=isolated,
  cells=n,cells_reaching_an_exit=distance.Count(d=>d>=0),visual="NOT_RUN",roundtrip="NOT_RUN",saved_dynamic_doors="NOT_RUN_USER_SAVE",status=isolated>0?"REVIEW":"STATIC_ONLY"});
 if(mapRows.Count%200==0){Console.WriteLine("MAPS "+mapRows.Count);MapData.Invalidate();}
}
File.WriteAllText(Path.Combine(folder,"maps.json"),JsonSerializer.Serialize(mapRows));File.WriteAllText(Path.Combine(folder,"warps.json"),JsonSerializer.Serialize(warpRows));
File.WriteAllText(args[2],JsonSerializer.Serialize(new{status="STATIC_ALL_MAPS_NOT_WHOLE_GAME_PASS",maps=mapRows.Count,effective_warps=warpRows.Count,unique_terrain=terrainHashes.Count,visual=0,actual_roundtrip=0,physical_android="NOT_RUN",scope="Original Content.Load, MapData authored overlays and directed collision; baseline default doors. Dynamic save conditions and actual UI separate."},new JsonSerializerOptions{WriteIndented=true}));return 0;
