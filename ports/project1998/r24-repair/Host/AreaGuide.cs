using Server;
namespace P1998.Embedded;

public static class AreaGuide
{
    public sealed record Place(string Kind,string Name,int Map,int X,int Y,int Destination=-1);
    public sealed record Leg(int Map,int X,int Y,int Destination,int ArrivalX,int ArrivalY,string Requirements);
    public static string Region(int map) => Content.RegionOf((ushort)map) switch
    { 0=>"고구려 · 국내",1=>"부여",2=>"신수계",3=>"낙랑",_=>"기타 지역" };
    public static int City(int map) => Content.RegionOf((ushort)map) switch {0=>0,1=>330,3=>2500,_=>map};
    public static string Role(int map)
    {
        var hall=Content.PathHalls.GetValueOrDefault((ushort)map)??Content.PathHalls.Values.FirstOrDefault(h=>h.GuildMap>0&&h.GuildMap==map);
        return hall?.BaseClass switch{1=>"전사 길드",2=>"도적 길드",3=>"주술사 길드",4=>"도사 길드",_=>""};
    }
    public static string MapName(int map)=>Content.Maps.TryGetValue((ushort)map,out var info)?info.Name:$"지도 {map}";
    public static Place[] Places(int map)
    {
        var points=new List<Place>();
        foreach(var n in Content.Npcs.Where(n=>n.Enabled&&n.Map==map))
            points.Add(new("NPC",n.Name,map,n.X,n.Y));
        foreach(var group in Content.Warps.Where(p=>p.Key.m==map).GroupBy(p=>p.Value.m))
        {
            // Adjacent tiles of one wide door share one label, but disconnected
            // doors into the same map remain separately selectable.
            var remaining=group.Select(p=>(p.Key.x,p.Key.y)).ToHashSet();
            while(remaining.Count>0)
            {
                var start=remaining.OrderBy(p=>p.y).ThenBy(p=>p.x).First();
                var queue=new Queue<(ushort x,ushort y)>();queue.Enqueue(start);remaining.Remove(start);
                while(queue.TryDequeue(out var p))
                    foreach(var d in new[]{(0,-1),(1,0),(0,1),(-1,0)})
                    {var next=((ushort)(p.x+d.Item1),(ushort)(p.y+d.Item2));if(remaining.Remove(next))queue.Enqueue(next);}
                points.Add(new("입구",MapName(group.Key),map,start.x,start.y,group.Key));
            }
        }
        foreach(var cave in Content.MythicCaves.Where(c=>c.EntranceMap==map))
            points.Add(new("조건부 입구",MapName(cave.DestMap),map,cave.Tiles[0].X,cave.Tiles[0].Y,cave.DestMap));
        foreach(var cave in Content.EventCaves.Where(c=>c.EntranceMap==map))
            points.Add(new("조건부 입구",cave.Key,map,cave.Tiles[0].X,cave.Tiles[0].Y,cave.TierMaps[0]));
        return points.OrderBy(p=>p.Kind).ThenBy(p=>p.Name,StringComparer.Ordinal).ToArray();
    }
    // A connection guide, never permission to warp. Original level/path/quest/door
    // checks still run at the actual entrance. No MapData/World loading in this graph.
    public static Leg[] Route(int origin,int destination)
    {
        if(origin==destination)return Array.Empty<Leg>();
        var edges=Content.Warps.GroupBy(w=>w.Key.m).ToDictionary(g=>(int)g.Key,g=>g.ToArray());
        var seen=new HashSet<int>{origin};var queue=new Queue<int>();queue.Enqueue(origin);
        var previous=new Dictionary<int,Leg>();
        while(queue.TryDequeue(out int map))
        {
            if(!edges.TryGetValue(map,out var exits))continue;
            foreach(var w in exits)
            {
                int next=w.Value.m;if(!seen.Add(next))continue;
                previous[next]=new(map,w.Key.x,w.Key.y,next,w.Value.x,w.Value.y,Requirements(next));
                if(next==destination)
                {var result=new List<Leg>();for(int at=destination;at!=origin;at=previous[at].Map)result.Add(previous[at]);result.Reverse();return result.ToArray();}
                queue.Enqueue(next);
            }
        }
        return Array.Empty<Leg>();
    }
    public static Leg[] Route(ClientSceneSnapshot scene,int destination)
    {
        var route=Route(scene.Map,destination);if(route.Length==0)return route;
        Leg? best=null;int bestCost=int.MaxValue;
        foreach(var exit in Content.Warps.Where(w=>w.Key.m==scene.Map&&w.Value.m==route[0].Destination)
                    .OrderBy(w=>Math.Abs(w.Key.x-scene.X)+Math.Abs(w.Key.y-scene.Y)))
        {
            if(Math.Abs(exit.Key.x-scene.X)+Math.Abs(exit.Key.y-scene.Y)>bestCost)continue;
            var plan=ClientNavigation.Plan(scene,exit.Key.x,exit.Key.y).Route;if(plan is null)continue;
            int facing=scene.Direction,cost=0;
            foreach(int direction in plan.Directions){cost+=1+(direction==facing?0:1);facing=direction;}
            if(cost>=bestCost)continue;bestCost=cost;
            best=new(scene.Map,exit.Key.x,exit.Key.y,exit.Value.m,exit.Value.x,exit.Value.y,Requirements(exit.Value.m));
        }
        if(best is null)return Array.Empty<Leg>();route[0]=best;return route;
    }
    public static string Requirements(int map)
    {
        if(!Content.MapMeta.TryGetValue((ushort)map,out var m))return "";
        var rules=new List<string>();
        if(m.ReqLvl>0)rules.Add($"레벨 {m.ReqLvl} 이상");
        if(m.LvlMax is >0 and <99)rules.Add($"레벨 {m.LvlMax} 이하");
        if(m.ReqPath>0)rules.Add($"직업 조건 {m.ReqPath}");
        if(m.ReqMark>0)rules.Add($"승급 {m.ReqMark} 이상");
        if(m.ReqVita>0)rules.Add($"HP {m.ReqVita} 이상");if(m.ReqMana>0)rules.Add($"MP {m.ReqMana} 이상");
        return string.Join(" · ",rules);
    }
    public static ModelTerrainSnapshot Terrain(int map,ClientSceneSnapshot current)
    {
        if(map==current.Map)return current.Cells;
        var terrain=MapData.For((ushort)map)??throw new InvalidDataException("지도 지형을 읽을 수 없습니다.");
        var cells=new List<ModelCell>(terrain.Xs*terrain.Ys);
        for(int y=0;y<terrain.Ys;y++)for(int x=0;x<terrain.Xs;x++)
            cells.Add(new(x,y,terrain.GroundWord(x,y),terrain.Obj(x,y)));
        return new(cells);
    }
}
