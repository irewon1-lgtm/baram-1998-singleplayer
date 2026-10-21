using P1998.Embedded;
using Server;
using System.Reflection;
using System.Text.Json;

Environment.SetEnvironmentVariable("P1998_GAME_DATA",args[0]);Content.Load();
var checks=new List<object>();bool failed=false;
void Check(string name,bool pass,object? value=null){checks.Add(new{name,status=pass?"PASS":"FAIL",value});failed|=!pass;}
ModelTerrainSnapshot Terrain(IEnumerable<ModelCell> c)=>(ModelTerrainSnapshot)Activator.CreateInstance(typeof(ModelTerrainSnapshot),BindingFlags.NonPublic|BindingFlags.Instance,null,new object[]{c},null)!;
ClientSceneSnapshot Scene(HashSet<(int,int)> blocked,int sx=2,int sy=2,int facing=1)
 =>new(65534,5,5,"isolated",sx,sy,facing,1,null,new(0,0,1,100,100,3,3,3,100,100,0,0,false),Terrain(Enumerable.Range(0,25).Select(i=>new ModelCell(i%5,i/5,(ushort)(blocked.Contains((i%5,i/5))?0xc001:1),0))),Array.Empty<Creature>(),Array.Empty<PlayerLookSnapshot>(),Array.Empty<FloorItemSnapshot>(),Array.Empty<SceneItemSnapshot>(),Array.Empty<SceneItemSnapshot>(),Array.Empty<SceneSpellSnapshot>(),null,null,Array.Empty<SceneEvent>(),0,true);
int Optimal(ClientSceneSnapshot s,int tx,int ty,int? first=null)
{
 var cells=s.Cells.ToDictionary(c=>(c.X,c.Y));var q=new PriorityQueue<(int x,int y,int d,int first),int>();var seen=new Dictionary<(int,int,int),int>();
 q.Enqueue((s.X,s.Y,s.Direction,-1),0);int answer=int.MaxValue;
 while(q.TryDequeue(out var a,out int cost)){
  if(seen.TryGetValue((a.x,a.y,a.d),out int old)&&old<=cost)continue;seen[(a.x,a.y,a.d)]=cost;
  if(a.x==tx&&a.y==ty){if(first is null||a.first==first)answer=Math.Min(answer,cost);continue;}
  for(int d=0;d<4;d++){int x=a.x+(d==1?1:d==3?-1:0),y=a.y+(d==2?1:d==0?-1:0);
   if(x<0||y<0||x>=5||y>=5||!cells.TryGetValue((x,y),out var c)||(c.Ground>>14)!=0||ObjectFlags.Blocks(c.Object,d))continue;
   if(a.first<0&&first is not null&&first!=d)continue;q.Enqueue((x,y,d,a.first<0?d:a.first),cost+1+(a.d==d?0:1));}
 }return answer;
}
var fixture=Scene(new(){(0,1),(1,0),(1,4),(2,0),(2,3)});
int? actual=ClientNavigation.NextDirection(fixture,4,0);int optimal=Optimal(fixture,4,0);
Check("turn_cost_chooses_five_action_route_instead_of_eight",actual==1&&Optimal(fixture,4,0,actual)==optimal,new{actual,optimal});
var random=new Random(1998);int checkedCount=0,mismatches=0;
for(int n=0;n<200;n++){
 var walls=new HashSet<(int,int)>();for(int i=0;i<25;i++)if(random.Next(5)==0)walls.Add((i%5,i/5));walls.Remove((2,2));walls.Remove((4,0));
 var s=Scene(walls,facing:n%4);int best=Optimal(s,4,0);int? d=ClientNavigation.NextDirection(s,4,0);
 if((best==int.MaxValue)!=(d is null)||(d is not null&&Optimal(s,4,0,d)!=best))mismatches++;checkedCount++;
}
Check("independent_dijkstra_200_grids_first_action_optimal",mismatches==0,new{checkedCount,mismatches});
Check("same_position_no_step",ClientNavigation.NextDirection(Scene(new()),2,2) is null);
Check("outside_no_step",ClientNavigation.NextDirection(Scene(new()),5,2) is null);
Check("solid_destination_not_walkable",ClientNavigation.NextDirection(Scene(new(){(4,0)}),4,0) is null);
File.WriteAllText(args[2],JsonSerializer.Serialize(new{status=failed?"FAIL":"PASS",checks,physical_android="NOT_RUN",scope="compiled actual navigation, independent weighted search"},new JsonSerializerOptions{WriteIndented=true}));return failed?1:0;
