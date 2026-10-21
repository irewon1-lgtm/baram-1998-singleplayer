using Godot;
using P1998.Embedded;
using Server;
using System.Globalization;

public partial class GameHud
{
    private const long ItemDoubleTapMilliseconds = 400;
    private readonly PanelContainer _itemCard = new() { Name = "ItemDetailsCard", Visible = false,
        MouseFilter = MouseFilterEnum.Stop, ZIndex = 12, Position = new(24, 22), Size = new(388, 338) };
    private readonly Label _itemDetailsText = new() { Name = "ItemDetailsText" };
    private readonly Label _itemDetailsTitle = new() { Name = "ItemDetailsTitle" };
    private SceneItemSnapshot? _lastItemTap, _shownInspection;
    private SceneItemSnapshot[] _shownComparison = Array.Empty<SceneItemSnapshot>();
    private PlayerStatsSnapshot? _shownInspectionStats;
    private long _lastItemTapAt, _itemPressAt;
    private Vector2 _itemPressOrigin;
    private byte _inspectedBagSlot;
    private int _inspectedItemId;

    private void BuildItemInspection()
    {
        var style = new StyleBoxFlat { BgColor = new Color("362719"), BorderColor = new Color("bf925e"),
            BorderWidthLeft=2,BorderWidthRight=2,BorderWidthTop=2,BorderWidthBottom=2,
            ContentMarginLeft=10,ContentMarginRight=10,ContentMarginTop=8,ContentMarginBottom=8 };
        _itemCard.AddThemeStyleboxOverride("panel",style);
        var column=new VBoxContainer();_itemCard.AddChild(column);column.AddThemeConstantOverride("separation",5);
        var heading=new HBoxContainer();column.AddChild(heading);
        _itemDetailsTitle.SizeFlagsHorizontal=SizeFlags.ExpandFill;_itemDetailsTitle.AutowrapMode=TextServer.AutowrapMode.WordSmart;
        _itemDetailsTitle.AddThemeFontSizeOverride("font_size",14);_itemDetailsTitle.AddThemeColorOverride("font_color",new Color("ffdfa1"));
        heading.AddChild(_itemDetailsTitle);
        var close=Button("item-inspection-close","닫기",ClearItemInspection,11);close.CustomMinimumSize=new(44,25);close.SizeFlagsHorizontal=SizeFlags.ShrinkEnd;heading.AddChild(close);
        var scroll=new ScrollContainer { Name="ItemDetailsScroll",CustomMinimumSize=new(0,245),SizeFlagsVertical=SizeFlags.ExpandFill,
            HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled };
        _itemDetailsText.AutowrapMode=TextServer.AutowrapMode.WordSmart;_itemDetailsText.SizeFlagsHorizontal=SizeFlags.ExpandFill;
        _itemDetailsText.MouseFilter=MouseFilterEnum.Ignore;_itemDetailsText.AddThemeFontSizeOverride("font_size",12);
        _itemDetailsText.AddThemeColorOverride("font_color",new Color("fff0cf"));scroll.AddChild(_itemDetailsText);column.AddChild(scroll);
        column.AddChild(Text("한 번: 정보  ·  두 번: 장착 / 먹기 / 사용",11));
        var other=Button("item-other-actions","놓기 · 건네기 등",()=>OpenLocal("inventory"),11);
        other.CustomMinimumSize=new(0,25);column.AddChild(other);NativeOverlay.AddChild(_itemCard);
    }

    private void ResetItemTap() { _lastItemTap=null;_lastItemTapAt=0; }
    private void ClearItemInspection()
    { ResetItemTap();_inspectedBagSlot=0;_inspectedItemId=0;_shownInspection=null;_itemCard.Visible=false; }
    private bool IsBagRowPoint(Vector2 point) => Buttons.Any(pair=>pair.Key.StartsWith("native-item-",StringComparison.Ordinal)
        &&pair.Value.IsVisibleInTree()&&pair.Value.GetGlobalRect().HasPoint(point));
    private void TrackItemPointer(InputEvent input)
    {
        Vector2? pressed=input switch { InputEventScreenTouch { Pressed:true,Canceled:false } touch=>touch.Position,
            InputEventMouseButton { ButtonIndex:MouseButton.Left,Pressed:true,Device:not -1 } mouse=>mouse.Position,_=>null };
        if(pressed is { } point)
        {
            _itemPressAt=System.Environment.TickCount64;
            _itemPressOrigin=point;
            if(!IsBagRowPoint(point))ResetItemTap();
        }
        if(input is InputEventScreenDrag || input is InputEventScreenTouch { Canceled:true })ResetItemTap();
        if(input is InputEventMouseMotion { ButtonMask:MouseButtonMask.Left } mouseDrag&&mouseDrag.Position.DistanceTo(_itemPressOrigin)>4)ResetItemTap();
    }
    private void TapBagItem(byte wireSlot)
    {
        if(!CanUseNativeRows||_scene is null)return;
        var item=_scene.Inventory.FirstOrDefault(value=>value.WireSlot==wireSlot);
        if(item is null){ClearItemInspection();return;}
        long now=System.Environment.TickCount64;
        bool activate=_lastItemTap==item&&now-_lastItemTapAt<=ItemDoubleTapMilliseconds&&now-_itemPressAt<=ItemDoubleTapMilliseconds;
        _inspectedBagSlot=wireSlot;_inspectedItemId=item.Details?.Definition.Id??0;
        ResetHeld();InputCanceled?.Invoke();RefreshItemInspection();
        if(activate&&item.Details is { } inspection)
        {
            ClearItemInspection();Command?.Invoke(new("activate-item",wireSlot,Item:inspection));
        }
        else
        {
            _lastItemTap=item;_lastItemTapAt=now;
            if(now-_itemPressAt>ItemDoubleTapMilliseconds)ResetItemTap();
        }
    }

    private void RefreshItemInspection()
    {
        if(_scene is null||_inspectedBagSlot==0){_itemCard.Visible=false;return;}
        var item=_scene.Inventory.FirstOrDefault(value=>value.WireSlot==_inspectedBagSlot);
        if(item is null||(item.Details?.Definition.Id??0)!=_inspectedItemId){ClearItemInspection();return;}
        _itemCard.Visible=_nativePanel=="inventory"&&!ModalOpen&&!_hostFaulted&&_scene.Dialog is null&&_scene.Shop is null&&_scene.WorldMap is null;
        if(!_itemCard.Visible)return;
        if(_shownInspection==item&&_shownInspectionStats==_scene.Stats&&_shownComparison.SequenceEqual(_scene.Equipment))return;
        _shownInspection=item;_shownInspectionStats=_scene.Stats;_shownComparison=_scene.Equipment;
        _itemDetailsTitle.Text=KoreanText.Display(item.Name);
        _itemDetailsText.Text=ItemInspectionText(item,_scene);
    }

    private static string Signed(int value)=>value.ToString("+0;-0;0",CultureInfo.InvariantCulture);
    private static string ItemKind(byte type)=>type switch {0=>"음식",1=>"사용 물품",2=>"음료 · 담배",3=>"무기",4=>"갑옷",5=>"방패",6=>"투구",
        7 or 8=>"반지 · 손 장비",9 or 10=>"보조 장비",11=>"얼굴 장식",12=>"관",13=>"망토",14=>"목걸이",15=>"신발",16=>"겉옷",21=>"재료 주머니",23=>"화살통",_=>"기타 물품"};
    private static string ItemInspectionText(SceneItemSnapshot item,ClientSceneSnapshot scene)
    {
        if(item.Details is not { } held)return "상세 정보를 아직 받지 못했습니다. 잠시 후 다시 선택하세요.";
        var d=held.Definition;var lines=new List<string>{$"{ItemKind(d.Type)}  ·  수량 {item.Amount:N0}"};
        if(d.IsEquip)
        {
            uint dura=held.Dura==0?d.Durability:held.Dura;
            lines.Add(d.Indestructible?"내구도: 손상되지 않음":d.Durability==0?"내구도: 제한 없음":$"내구도 {dura:N0} / {d.Durability:N0} ({100d*dura/d.Durability:F1}%)");
            if(d.Type==3)lines.Add($"공격력  소형 {d.MinSDam:N0}~{d.MaxSDam:N0} / 대형 {d.MinLDam:N0}~{d.MaxLDam:N0}");
            lines.Add($"필요 레벨 {d.Level} (현재 {scene.Stats.Level})  ·  필요 힘 {d.MightReq} (현재 {scene.Stats.Might})");
            lines.Add("직업: "+(d.PathId==0?"제한 없음":held.PathName.Length>0?KoreanText.Display(held.PathName):$"직업 번호 {d.PathId}"));
            lines.Add("성별: "+(d.Sex==0?"남성":d.Sex==1?"여성":"공용")+$"  ·  필요 승급 {d.Mark}");
            lines.Add($"방어 AC {Signed(d.Armor)}  (낮을수록 피해 감소)");
            lines.Add($"명중 {Signed(d.Hit)}  ·  공격 보정 {Signed(d.Dam)}");
            lines.Add($"최대 HP {Signed(d.Vita)}  ·  최대 MP {Signed(d.Mana)}");
            lines.Add($"힘 {Signed(d.Might)}  ·  지력 {Signed(d.Will)}  ·  민첩 {Signed(d.Grace)}");
            lines.Add($"마법 방어 {Signed(d.Protection)}");
            lines.Add($"HP 재생 {Signed(d.Healing)}%  ·  MP 재생 {Signed(d.Wisdom)}%");
            if(d.Type==3&&d.Look is >=10000 and <=29999)lines.Add("양손 무기: 방패와 함께 장착 불가");
            lines.Add(d.Repairable?"수리 가능":"수리 불가");
            byte slot=d.EquipSlot;
            if(slot==7&&scene.Equipment.Any(e=>e.WireSlot==7)&&scene.Equipment.All(e=>e.WireSlot!=8))slot=8;
            var worn=scene.Equipment.FirstOrDefault(e=>e.WireSlot==slot);
            if(worn?.Details is { } current)
            {
                var old=current.Definition;lines.Add("");lines.Add("현재 장비와 비교: "+KoreanText.Display(worn.Name));
                if(d.Type==3)lines.Add($"소형 공격 {Signed(d.MinSDam-old.MinSDam)}~{Signed(d.MaxSDam-old.MaxSDam)} / 대형 {Signed(d.MinLDam-old.MinLDam)}~{Signed(d.MaxLDam-old.MaxLDam)}");
                lines.Add($"AC {Signed(d.Armor-old.Armor)}  ·  명중 {Signed(d.Hit-old.Hit)}  ·  공격 보정 {Signed(d.Dam-old.Dam)}");
                lines.Add($"HP {Signed(d.Vita-old.Vita)}  ·  MP {Signed(d.Mana-old.Mana)}");
                lines.Add($"힘 {Signed(d.Might-old.Might)}  ·  지력 {Signed(d.Will-old.Will)}  ·  민첩 {Signed(d.Grace-old.Grace)}");
            }
            else lines.Add("비교: 해당 장비 칸이 비어 있습니다.");
        }
        else
        {
            lines.Add(held.UseVerb switch {
                "heal"=>held.UseFull.Length>0&&held.UseFull!="0"?"효과: HP 전체 회복":"효과: HP "+held.UseAmount+" 회복",
                "drink"=>"효과: MP "+held.UseAmount+" 회복"+(held.UseHpCost.Length==0?"":" / HP "+held.UseHpCost+" 소모"),
                "fatal"=>"효과: 사용 시 사망",
                "warphome"=>"효과: 소속 국가의 주막으로 귀환",
                "ward" or "hardenbody"=>"효과: "+(held.UseName.Length>0?KoreanText.Display(held.UseName):"상태 보호")+(held.UseStat.Length>0?" / "+EffectStat(held.UseStat)+" "+held.UseAmount:"")+DurationText(held.UseDuration),
                "cure"=>"별도 회복 효과가 구현되지 않은 소모품",
                _=>d.Text.Length>0?KoreanText.Display(d.Text):"기타 물품의 효과는 사용 규칙에 따릅니다."});
            if(d.IsCharged)lines.Add($"남은 사용 횟수 {(held.Dura==0?d.Durability:held.Dura):N0} / {d.Durability:N0}");
            else if(d.Type==21)lines.Add($"보관량 {held.Dura:N0} / {d.Durability:N0}");
            else if(d.Type==23)lines.Add($"남은 화살 {(held.Dura==0?d.Durability:held.Dura):N0}");
            else lines.Add("내구도: 해당 없음");
            if(d.PathId!=0)lines.Add("사용 직업: "+KoreanText.Display(held.PathName));
            if(d.Type is 24 or 25 or 27 or 28 or 29)lines.Add($"필요 레벨 {d.Level} (현재 {scene.Stats.Level})");
        }
        if(d.BuyText.Length>0)lines.Add(KoreanText.Display(d.BuyText));
        if(held.Owner.Length>0)lines.Add("귀속 소유자: "+held.Owner);
        if(d.BreakOnDeath)lines.Add("사망 시 파괴될 수 있습니다.");
        if(d.NoDrop)lines.Add("버리기 불가");if(d.NoTrade)lines.Add("교환 불가");if(d.NoDeposit)lines.Add("은행 보관 불가");
        if(held.Protected>0)lines.Add($"파괴 보호 {held.Protected}회");
        lines.Add($"기준 구매가 {d.BuyPrice:N0}전 / 판매가 {d.SellPrice:N0}전");
        return string.Join("\n",lines);
    }
    private static string EffectStat(string stat)=>stat switch {"armor"=>"방어 AC","might"=>"힘","will"=>"지력","grace"=>"민첩","hp"=>"HP","mp"=>"MP",_=>stat};
    private static string DurationText(string value)=>double.TryParse(value,NumberStyles.Float,CultureInfo.InvariantCulture,out double milliseconds)?$" / {milliseconds/1000d:0.###}초":"";
}
