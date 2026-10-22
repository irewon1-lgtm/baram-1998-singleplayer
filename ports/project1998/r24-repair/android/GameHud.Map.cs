using Godot;
using P1998.Embedded;
using Server;

public partial class GameHud
{
    private int _guideMap=-1;private long _guideLoad,_guideRouteLoad;
    private AreaGuide.Leg[] _guideRoute=Array.Empty<AreaGuide.Leg>();
    private AreaMapCanvas? _areaCanvas;private Label? _guideInfo;private AreaGuide.Place? _guidePoint;
    private readonly Label _areaLocation=new(){Name="CurrentRegionLocation",MouseFilter=MouseFilterEnum.Ignore};
    private void BuildMapAccess()
    {
        _areaLocation.Position=new(16,16);_areaLocation.Size=new(404,20);_areaLocation.AddThemeFontSizeOverride("font_size",12);
        _areaLocation.AddThemeColorOverride("font_color",new Color("fff0c7"));
        _areaLocation.AddThemeColorOverride("font_shadow_color",Colors.Black);_areaLocation.AddThemeConstantOverride("shadow_offset_x",1);_areaLocation.AddThemeConstantOverride("shadow_offset_y",1);
        NativeOverlay.AddChild(_areaLocation);
    }
    private void BuildAreaMap()
    {
        if(_scene is not {} scene)return;
        _guideRouteLoad++;_guideRoute=Array.Empty<AreaGuide.Leg>();
        if(_guideMap<0||!Content.Maps.ContainsKey((ushort)_guideMap))_guideMap=scene.Map;
        var mapRoot=new Control{Name="AreaMapPanel",ClipContents=true,SizeFlagsHorizontal=SizeFlags.ExpandFill,SizeFlagsVertical=SizeFlags.ExpandFill};_modalContent.AddChild(mapRoot);
        var heading=Text("지도 · "+AreaGuide.Region(scene.Map)+" · "+KoreanText.Display(scene.MapTitle)+$" ({scene.X}, {scene.Y})",20);mapRoot.AddChild(heading);
        var tools=new HBoxContainer();mapRoot.AddChild(tools);
        tools.AddChild(MapButton("area-current","현재 위치",()=>ShowGuideMap(scene.Map)));
        tools.AddChild(MapButton("area-city","도시 지도",()=>ShowGuideMap(AreaGuide.City(scene.Map))));
        tools.AddChild(MapButton("area-overview","전체보기",()=>_areaCanvas?.Overview()));
        tools.AddChild(MapButton("area-zoom-in","확대 +",()=>_areaCanvas?.Zoom(1.25f)));
        tools.AddChild(MapButton("area-zoom-out","축소 −",()=>_areaCanvas?.Zoom(.8f)));
        var legend=Text(AreaGuide.Region(_guideMap)+" · "+GuideMapName(_guideMap)+" | 노랑: 나 · 파랑: 문 · 초록: NPC · 번호: 목록",12);mapRoot.AddChild(legend);
        var split=new Control{ClipContents=true};mapRoot.AddChild(split);
        var left=new Control{ClipContents=true};split.AddChild(left);
        var right=new Control{ClipContents=true};split.AddChild(right);
        var info=Content.Maps[(ushort)_guideMap];var points=AreaGuide.Places(_guideMap);
        _areaCanvas=new AreaMapCanvas{Name="DetailedAreaMap",Art=Art!,Width=info.Xs,Height=info.Ys,Places=points,
            Player=_guideMap==scene.Map?new(scene.X,scene.Y):new(-1,-1),CustomMinimumSize=new(0,80),SizeFlagsVertical=SizeFlags.ExpandFill,SizeFlagsHorizontal=SizeFlags.ExpandFill};
        left.AddChild(_areaCanvas);_areaCanvas.TileSelected+=(x,y)=>SelectGuidePoint(points.OrderBy(p=>Math.Abs(p.X-x)+Math.Abs(p.Y-y)).FirstOrDefault(p=>Math.Abs(p.X-x)+Math.Abs(p.Y-y)<=2)??new("목적지","선택한 위치",_guideMap,x,y));
        _guideInfo=Text("지형을 읽는 중…",13);_guideInfo.Name="AreaRouteText";
        var routeScroll=new ScrollContainer{CustomMinimumSize=new(0,60),HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled};routeScroll.AddChild(_guideInfo);left.AddChild(routeScroll);
        var searchRow=new HBoxContainer();right.AddChild(searchRow);
        var search=new LineEdit{Name="AreaSearch",PlaceholderText="주술사, 주막, NPC·지도 이름",SizeFlagsHorizontal=SizeFlags.ExpandFill};searchRow.AddChild(search);
        var list=new ScrollContainer{CustomMinimumSize=new(0,100),SizeFlagsVertical=SizeFlags.ExpandFill,SizeFlagsHorizontal=SizeFlags.ExpandFill,HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled};
        var rows=new VBoxContainer{SizeFlagsHorizontal=SizeFlags.ExpandFill};list.AddChild(rows);right.AddChild(list);
        void Populate(string query)
        {
            foreach(var child in rows.GetChildren()){rows.RemoveChild(child);child.QueueFree();}
            var matches=new List<AreaGuide.Place>();
            if(query.Trim().Length==0)matches.AddRange(points);
            else
            {
                string term=query.Trim();bool tavernAlias=term is "부두막" or "부뚜막";
                bool Match(string n,int map=-1)=>KoreanText.Display(n).Contains(term,StringComparison.OrdinalIgnoreCase)||n.Contains(term,StringComparison.OrdinalIgnoreCase)||(map>=0&&GuideMapName(map).Contains(term,StringComparison.OrdinalIgnoreCase))||(tavernAlias&&n.Contains("Tavern",StringComparison.OrdinalIgnoreCase));
                matches.AddRange(points.Where(p=>Match(p.Name,p.Destination)));
                matches.AddRange(Content.Maps.Values.Where(m=>Match(m.Name,m.Id)).OrderBy(m=>Content.RegionOf(m.Id)==Content.RegionOf((ushort)scene.Map)?0:1).ThenBy(m=>m.Id)
                    .Take(60).Select(m=>new AreaGuide.Place("지도",m.Name,m.Id,-1,-1)));
                matches.AddRange(Content.Npcs.Where(n=>n.Enabled&&Match(n.Name)).Take(30).Select(n=>new AreaGuide.Place("NPC",n.Name,n.Map,n.X,n.Y)));
                if(tavernAlias&&_guideInfo is not null)_guideInfo.Text="‘"+term+"’은 등록된 지명이 없어 주막을 함께 찾았습니다.";
            }
            int index=0;
            foreach(var place in matches.Distinct().Take(80))
            {
                var p=place;string label=p.Map==_guideMap&&p.X>=0?$"{Array.IndexOf(points,p)+1}. ":"";
                label+=GuidePlaceName(p)+" · "+(p.Map==_guideMap?"":AreaGuide.Region(p.Map)+" · ")+(p.X>=0?$"({p.X}, {p.Y})":"지도 보기");
                var button=new Button{Text=label,TooltipText=label,ClipText=true,Alignment=HorizontalAlignment.Left,CustomMinimumSize=new(0,32)};button.AddThemeFontSizeOverride("font_size",14);
                button.Name="area-place-"+(index++);button.Pressed+=()=>{if(p.Map!=_guideMap||p.X<0){ShowGuideMap(p.Map,p);return;}SelectGuidePoint(p);_areaCanvas?.FocusTile(p.X,p.Y);};rows.AddChild(button);
                if(p.X>=0)rows.AddChild(Text($"({p.X}, {p.Y}) · "+(p.Map==_guideMap?p.Kind:AreaGuide.Region(p.Map)),12));
            }
            if(matches.Count==0)rows.AddChild(Text("일치하는 등록 장소가 없습니다.",14));
        }
        searchRow.AddChild(MapButton("area-search","찾기",()=>Populate(search.Text)));search.TextSubmitted+=Populate;Populate("");
        var bottom=new HBoxContainer();mapRoot.AddChild(bottom);
        var walkControl=MapButton("area-walk","선택한 곳으로 이동",()=>WalkToGuidePoint());walkControl.Disabled=true;bottom.AddChild(walkControl);bottom.AddChild(MapButton("area-close","닫기",CloseLocalPanel));
        var currentCanvas=_areaCanvas;
        void ArrangeMap()
        {
            float fullWidth=Math.Max(100,mapRoot.Size.X),fullHeight=Math.Max(280,mapRoot.Size.Y);
            heading.Position=Vector2.Zero;heading.Size=new(fullWidth,28);
            tools.Position=new(0,32);tools.Size=new(fullWidth,36);
            legend.Position=new(0,72);legend.Size=new(fullWidth,20);
            split.Position=new(0,96);split.Size=new(fullWidth,fullHeight-138);
            bottom.Position=new(0,fullHeight-36);bottom.Size=new(fullWidth,36);
            float width=split.Size.X,height=split.Size.Y,leftWidth=(width-10)*.6f;
            left.Size=new(leftWidth,height);right.Position=new(leftWidth+10,0);right.Size=new(width-leftWidth-10,height);
            currentCanvas.Position=Vector2.Zero;currentCanvas.Size=new(leftWidth,Math.Max(80,height-66));
            routeScroll.Position=new(0,Math.Max(80,height-60));routeScroll.Size=new(leftWidth,60);
            searchRow.Position=Vector2.Zero;searchRow.Size=new(right.Size.X,36);
            list.Position=new(0,42);list.Size=new(right.Size.X,Math.Max(100,height-42));
        }
        mapRoot.Resized+=ArrangeMap;ArrangeMap();
        long version=++_guideLoad;var canvas=_areaCanvas;int requested=_guideMap;
        // The owned snapshot travels through a synchronized queue; no Godot object is touched by the worker.
        _=LoadGuideTerrain(version,requested,scene,canvas);
    }
    private static string GuideMapName(int map)
    {
        string name=map switch{0=>"국내성",330=>"부여성",2500=>"낙랑성",_=>KoreanText.Display(AreaGuide.MapName(map))};
        string role=AreaGuide.Role(map);return role.Length==0?name:role+" · "+name;
    }
    private static string GuidePlaceName(AreaGuide.Place p)=>p.Destination>=0?GuideMapName(p.Destination):p.Kind=="지도"?GuideMapName(p.Map):KoreanText.Display(p.Name);
    private Button MapButton(string key,string text,Action action)
    {var button=ModalButton(key,text,action);button.CustomMinimumSize=new(0,36);button.AddThemeFontSizeOverride("font_size",14);return button;}
    private readonly System.Collections.Concurrent.ConcurrentDictionary<long,ModelTerrainSnapshot> _guideTerrain=new();
    private async Task LoadGuideTerrain(long version,int map,ClientSceneSnapshot scene,AreaMapCanvas canvas)
    {
        try{var terrain=await Task.Run(()=>AreaGuide.Terrain(map,scene));_guideTerrain[version]=terrain;CallDeferred(nameof(ApplyGuideTerrain),version,"");}
        catch(Exception){CallDeferred(nameof(ApplyGuideTerrain),version,"지형을 읽지 못했습니다.");}
    }
    private void ApplyGuideTerrain(long version,string error)
    {
        bool ready=_guideTerrain.TryRemove(version,out var terrain);
        if(version!=_guideLoad||_localPanel!="area-map"||_areaCanvas is null||!GodotObject.IsInstanceValid(_areaCanvas))return;
        if(error.Length>0){_guideInfo!.Text=error;return;}
        if(!ready||terrain is null)return;
        _areaCanvas.Terrain=terrain;
        if(_guideMap==_scene?.Map)_areaCanvas.FocusTile(_scene.X,_scene.Y);else _areaCanvas.Overview();
        _guideInfo!.Text=error.Length>0?error:"문·NPC를 누르거나 지도에서 위치를 선택하세요. 지도를 밀면 이동합니다.";
        if(_guidePoint is {} p&&p.Map==_guideMap)SelectGuidePoint(p);
        _areaCanvas.QueueRedraw();
    }
    private void ShowGuideMap(int map,AreaGuide.Place? selected=null){_guideMap=map;_guidePoint=selected;_modalKey="";RefreshModal();}
    private async void SelectGuidePoint(AreaGuide.Place point)
    {
        _guidePoint=point;if(_guideInfo is null||_scene is not {} scene)return;
        long version=++_guideRouteLoad;_guideRoute=Array.Empty<AreaGuide.Leg>();
        var walkButton=Buttons.GetValueOrDefault("area-walk");if(walkButton is not null)walkButton.Disabled=point.Map!=scene.Map||point.X<0;
        AreaGuide.Leg[] route=Array.Empty<AreaGuide.Leg>();
        if(point.Map!=scene.Map)
        {
            _guideInfo.Text=GuidePlaceName(point)+" · 걸어갈 문을 찾는 중…";
            try{route=await Task.Run(()=>AreaGuide.Route(scene,point.Map));}
            catch(Exception){if(version==_guideRouteLoad&&GodotObject.IsInstanceValid(_guideInfo))_guideInfo.Text="경로를 확인하지 못했습니다.";return;}
            if(version!=_guideRouteLoad||_localPanel!="area-map"||_scene?.MapEpoch!=scene.MapEpoch)return;
            _guideRoute=route;if(walkButton is not null&&GodotObject.IsInstanceValid(walkButton))walkButton.Disabled=route.Length==0;
        }
        var text=new List<string>{GuidePlaceName(point)+(point.X<0?"":$" · ({point.X}, {point.Y})")};
        if(point.Destination>=0)text.Add("이 문 → "+GuideMapName(point.Destination));
        if(scene.Map!=point.Map&&route.Length==0)text.Add("현재 위치에서 확인된 도보 경로가 없습니다. NPC·퀘스트 이동도 확인하세요.");
        foreach(var leg in route.Take(8))text.Add(GuideMapName(leg.Map)+$" ({leg.X}, {leg.Y}) 문 → "+GuideMapName(leg.Destination)+$" ({leg.ArrivalX}, {leg.ArrivalY})"+(leg.Requirements.Length>0?" · "+leg.Requirements:""));
        if(Buttons.TryGetValue("area-walk",out var walk))walk.Text=point.Map==scene.Map?"선택한 곳으로 이동":"첫 번째 문까지 이동";
        if(point.Map!=scene.Map&&route.Length>0)text.Add("첫 문까지 자동이동합니다. 지도 전환 후 다음 구간을 선택하세요.");
        text.Add("입장 시 원래 문·레벨·직업·퀘스트 조건이 적용됩니다.");_guideInfo.Text=string.Join("\n",text);
    }
    private void WalkToGuidePoint()
    {
        if(_scene is not {} scene||_guidePoint is not {} point||(point.X<0&&point.Map==scene.Map))return;
        int x=point.X,y=point.Y;
        if(point.Map!=scene.Map)
        {var first=_guideRoute.FirstOrDefault();if(first is null){_guideInfo!.Text="현재 지도에서 걸어갈 연결 문을 찾지 못했습니다.";return;}x=first.X;y=first.Y;}
        else if(point.Kind=="NPC")
        {
            var adjacent=new[]{(x,y-1),(x+1,y),(x,y+1),(x-1,y)}.OrderBy(p=>Math.Abs(p.Item1-scene.X)+Math.Abs(p.Item2-scene.Y));
            var target=adjacent.FirstOrDefault(p=>scene.Cells.Any(c=>c.X==p.Item1&&c.Y==p.Item2&&(c.Ground>>14)==0&&c.Object==0),(-1,-1));
            if(target.Item1<0){_guideInfo!.Text="NPC 옆의 안전한 칸을 찾지 못했습니다.";return;}x=target.Item1;y=target.Item2;
        }
        CloseLocalPanel();Command?.Invoke(new("map-walk",x,(uint)y,scene.Map.ToString(),scene.MapEpoch));
    }
}
