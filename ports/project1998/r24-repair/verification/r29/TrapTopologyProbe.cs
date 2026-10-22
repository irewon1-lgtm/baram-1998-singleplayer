using Server;
using System.Text.Json;
Environment.SetEnvironmentVariable("P1998_GAME_DATA",args[0]);Content.Load();
var m=Content.Maps[1014];var map=MapData.For(1014,m.Xs,m.Ys)!;
var deltas=new(int x,int y)[]{(0,-1),(1,0),(0,1),(-1,0)};
bool Open(int x,int y,int d)=>x>=0&&y>=0&&x<m.Xs&&y<m.Ys&&!map.BlockedMove(x,y,d);
var seen=new HashSet<(int x,int y)>{(0,17)};var q=new Queue<(int x,int y)>();q.Enqueue((0,17));
while(q.TryDequeue(out var p))for(int d=0;d<4;d++){var n=(x:p.x+deltas[d].x,y:p.y+deltas[d].y);if(Open(n.x,n.y,d)&&seen.Add(n))q.Enqueue(n);}
var incoming=new List<object>();for(int y=0;y<m.Ys;y++)for(int x=0;x<m.Xs;x++)for(int d=0;d<4;d++){var n=(x:x+deltas[d].x,y:y+deltas[d].y);if(!seen.Contains((x,y))&&seen.Contains(n)&&Open(n.x,n.y,d))incoming.Add(new{x,y,d,to=n.ToString(),source=map.At(x,y),sourceSolid=map.Solid(x,y)});}
var cells=Enumerable.Range(13,5).SelectMany(y=>Enumerable.Range(0,6).Select(x=>new{x,y,cell=map.At(x,y),directions=Enumerable.Range(0,4).Select(d=>map.BlockedMove(x,y,d)).ToArray(),flags=ObjectFlags.Flag(map.Obj(x,y))})).ToArray();
var target=Content.Maps[330];var city=MapData.For(330,target.Xs,target.Ys)!;
var result=new{status=seen.Count<=2?"FAIL_REPRODUCED_CLOSED_COMPONENT":"OBSERVED_TOPOLOGY",map=m,reachable=seen.Select(p=>new{p.x,p.y}).ToArray(),incoming,cells,recovery_target=new{map=330,x=29,y=143,cell=city.At(29,143),blocked=Enumerable.Range(0,4).Select(d=>city.BlockedMove(29,143,d)).ToArray()}};
File.WriteAllText(args[2],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));return 0;
