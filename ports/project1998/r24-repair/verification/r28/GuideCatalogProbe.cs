using System.Text;
using System.Text.Json;
using P1998.Embedded;
using Server;
static class GuideCatalogProbe
{
    static int Main(string[] a)
    {
        Environment.SetEnvironmentVariable("P1998_GAME_DATA",a[0]);Environment.SetEnvironmentVariable("P1998_STATE",a[1]);Directory.CreateDirectory(a[1]);Content.Load();
        var before=MapData.ObserveCache();var maps=new List<object>();var pois=new List<object>();int invalid=0;
        var folder=Path.GetDirectoryName(a[2])!;
        var mapCsv=new StringBuilder("map_id,source_name,region,guild_role,width,height,guide_points,runtime_traversal\n");
        var poiCsv=new StringBuilder("map_id,kind,name,x,y,destination,status\n");
        string Csv(string value)=>"\""+value.Replace("\"","\"\"")+"\"";
        foreach(var m in Content.Maps.Values.OrderBy(m=>m.Id))
        {
            var points=AreaGuide.Places(m.Id);
            maps.Add(new{m.Id,m.Name,region=AreaGuide.Region(m.Id),role=AreaGuide.Role(m.Id),m.Xs,m.Ys,points=points.Length,runtime_traversal="NOT_RUN_THIS_METADATA_PROBE"});
            mapCsv.AppendLine($"{m.Id},{Csv(m.Name)},{Csv(AreaGuide.Region(m.Id))},{Csv(AreaGuide.Role(m.Id))},{m.Xs},{m.Ys},{points.Length},NOT_RUN_THIS_METADATA_PROBE");
            foreach(var p in points)
            {
                bool valid=p.X>=0&&p.Y>=0&&p.X<m.Xs&&p.Y<m.Ys;if(!valid)invalid++;
                string status=valid?"REGISTERED_STATIC_POINT_NOT_TRAVERSED":"REVIEW_SOURCE_COORDINATE";
                pois.Add(new{p.Kind,p.Name,p.Map,p.X,p.Y,p.Destination,status});poiCsv.AppendLine($"{p.Map},{Csv(p.Kind)},{Csv(p.Name)},{p.X},{p.Y},{p.Destination},{status}");
            }
        }
        var after=MapData.ObserveCache();bool pass=before==after&&Content.Maps.Count==7948&&AreaGuide.Role(342)=="주술사 길드"&&AreaGuide.Role(0)==""&&AreaGuide.Region(330)=="부여"&&AreaGuide.Region(0).Contains("고구려");
        File.WriteAllText(Path.Combine(folder,"guide-maps.csv"),mapCsv.ToString());File.WriteAllText(Path.Combine(folder,"guide-points.csv"),poiCsv.ToString());
        File.WriteAllText(Path.Combine(folder,"guide-catalog.json"),JsonSerializer.Serialize(new{maps,pois}));
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=pass?"PASS_METADATA_ONLY_NO_TERRAIN_LOADING":"FAIL",registered_maps=maps.Count,guide_points=pois.Count,source_coordinate_reviews=invalid,cache_before=before,cache_after=after,effective_warps=Content.Warps.Count,enabled_npcs=Content.Npcs.Count(n=>n.Enabled),full_runtime_traversal="NOT_RUN_THIS_PROBE",physical_android="NOT_RUN"},new JsonSerializerOptions{WriteIndented=true}));return pass?0:1;
    }
}
