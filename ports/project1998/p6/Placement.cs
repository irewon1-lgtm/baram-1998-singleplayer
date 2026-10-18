using System.Text.Json;
using Shared;

namespace Server;

// User-authorized placement repair. Native definitions, scripts, map bytes,
// collision and saved mobs remain unchanged. NPCs are not checkpointed by P4.
public sealed partial class World
{
    public readonly List<object> P6PlacementAudit = new();
    public void P6PlaceAccessibleNpcs(string json)
    {
        using var document = JsonDocument.Parse(json);
        lock (_lock)
        foreach (var row in document.RootElement.EnumerateArray())
        {
            int nid=row.GetProperty("npc").GetInt32(); ushort mid=row.GetProperty("map").GetUInt16();
            var mob=Map(mid).Mobs.FirstOrDefault(m=>m.IsNpc && m.NpcDefId==nid);
            if (mob is null || !Content.TryMap(mid,out var info)) continue;
            var md=MapData.For(mid,info.Xs,info.Ys)!;
            var taken=Map(mid).Mobs.Where(m=>m.IsNpc && m.Id!=mob.Id).Select(m=>((int)m.X,(int)m.Y)).ToHashSet();
            bool Open(int x,int y) => x>0 && y>0 && x<info.Xs-1 && y<info.Ys-1 && !taken.Contains((x,y)) && Enumerable.Range(0,4).All(d=>!md.BlockedMove(x,y,d));
            // The largest walk component is the room/town floor rather than
            // a sealed roof or an isolated decorative pocket.
            var remaining=new HashSet<(int x,int y)>();
            for(int y=1;y<info.Ys-1;y++)for(int x=1;x<info.Xs-1;x++)if(Open(x,y))remaining.Add((x,y));
            var main=new HashSet<(int x,int y)>();
            var dirs=new (int x,int y)[]{(0,-1),(1,0),(0,1),(-1,0)};
            while(remaining.Count>0)
            {
                var seed=remaining.First();remaining.Remove(seed);var q=new Queue<(int x,int y)>();q.Enqueue(seed);var part=new HashSet<(int x,int y)>{seed};
                while(q.Count>0){var a=q.Dequeue();foreach(var d in dirs){var b=(a.x+d.x,a.y+d.y);if(remaining.Remove(b)){part.Add(b);q.Enqueue(b);}}}
                if(part.Count>main.Count)main=part;
            }
            bool Accessible(int x,int y)=>main.Contains((x,y)) && dirs.Count(d=>main.Contains((x+d.x,y+d.y)) && !taken.Contains((x+d.x,y+d.y)))>=2;
            var before=new[]{(int)mob.X,(int)mob.Y};var source=row.GetProperty("source");
            bool sourceGood=Accessible(mob.X,mob.Y) && row.GetProperty("source_visual_coverage").GetDouble()<=0.04 && md.Obj(mob.X,mob.Y)==0;
            bool changed=false;
            if(!sourceGood)
            foreach(var c in row.GetProperty("candidates").EnumerateArray())
            {
                int x=c[0].GetInt32(),y=c[1].GetInt32();
                if(!Accessible(x,y) || taken.Any(t=>Math.Abs(t.Item1-x)+Math.Abs(t.Item2-y)<3) || Content.TryWarp(mid,(ushort)x,(ushort)y,out _))continue;
                mob.X=mob.HomeX=(ushort)x;mob.Y=mob.HomeY=(ushort)y;changed=true;Map(mid).ViewGen++;break;
            }
            // Repaired merchants stand alone instead of pacing back under the
            // same scenery. Source-defined roaming animals retain their AI.
            if(changed){mob.Wander=false;mob.Leash=0;}
            P6PlacementAudit.Add(new{npc=nid,map=mid,key=row.GetProperty("key").GetString(),source=new[]{source[0].GetInt32(),source[1].GetInt32()},before,position=new[]{(int)mob.X,(int)mob.Y},changed,accessible=Accessible(mob.X,mob.Y),source_visible=sourceGood,component_cells=main.Count});
        }
    }
}
