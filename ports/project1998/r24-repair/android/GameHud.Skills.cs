using Godot;
using P1998.Embedded;
using System.Text.Json;

public partial class GameHud
{
    private const ulong SpellHoldMilliseconds=500;
    private SceneSpellSnapshot? _spellPress,_sortSpell;
    private int _spellPointer=-1;
    private Vector2 _spellOrigin;
    private ulong _spellPressedAt;
    private bool _spellDragged,_spellLongHeld;
    private long _spellSortEpoch,_spellPressEpoch;
    private string _spellSortBook="",_spellStyleVersion="",_spellPressBook="";
    private readonly Label _spellSortHint=new(){Name="SpellSortHint",Position=new(447,301),Size=new(166,23),
        MouseFilter=MouseFilterEnum.Ignore,ClipText=true,VerticalAlignment=VerticalAlignment.Center};

    private void BuildSpellSorting()
    {
        _spellSortHint.AddThemeFontSizeOverride("font_size",10);
        _spellSortHint.AddThemeColorOverride("font_color",new Color("352717"));
        _nativeRight.AddChild(_spellSortHint);RefreshSpellSortHint();
    }
    private static string SpellBookVersion(ClientSceneSnapshot scene)
        =>string.Join("|",scene.Spells.Select(s=>$"{s.WireSlot}:{s.Name}:{s.Type}"));
    private void CancelSpellSort()
    {
        _spellPress=_sortSpell=null;_spellPointer=-1;_spellLongHeld=_spellDragged=false;
        RefreshSpellSortHint();
    }
    private void RefreshSpellSortHint()
    {
        _spellSortHint.Visible=_nativePanel=="spells";
        _spellSortHint.Text=_sortSpell is null?"길게 누르기: 순서 변경":"옮길 위치 선택 · 바깥 누르면 취소";
        string styleVersion=_nativeRowsVersion+":"+(_sortSpell?.WireSlot.ToString()??"none");
        if(_spellStyleVersion==styleVersion)return;
        _spellStyleVersion=styleVersion;
        foreach(var pair in Buttons.Where(p=>p.Key.StartsWith("native-cast-",StringComparison.Ordinal)))
        {
            var style=(StyleBoxFlat)pair.Value.GetThemeStylebox("normal").Duplicate();
            bool selected=_sortSpell is not null&&pair.Key=="native-cast-"+_sortSpell.WireSlot;
            style.BgColor=selected?new Color("d8b775"):new Color(0,0,0,0);
            style.BorderColor=new Color("76512a");style.BorderWidthLeft=style.BorderWidthRight=style.BorderWidthTop=style.BorderWidthBottom=selected?1:0;
            pair.Value.AddThemeStyleboxOverride("normal",style);
        }
    }
    private void ArmSpellSort()
    {
        if(_spellPress is null||_spellDragged||!CanUseNativeRows||_scene is null)return;
        _spellLongHeld=true;_sortSpell=_spellPress;_spellSortEpoch=_scene.MapEpoch;_spellSortBook=SpellBookVersion(_scene);
        ResetHeld();InputCanceled?.Invoke();RefreshSpellSortHint();
    }
    public override void _Process(double delta)
    {
        if(_spellPointer!=-1&&!_spellLongHeld&&!_spellDragged&&Time.GetTicksMsec()-_spellPressedAt>=SpellHoldMilliseconds)ArmSpellSort();
    }
    private SceneSpellSnapshot? SpellAt(Vector2 point)
        =>_nativePanel!="spells"||!CanUseNativeRows||_scene is null?null:_scene.Spells.FirstOrDefault(s=>
            Buttons.TryGetValue("native-cast-"+s.WireSlot,out var b)&&b.IsVisibleInTree()&&b.GetGlobalRect().HasPoint(point));
    private bool HandleSpellPointer(InputEvent input)
    {
        int pointer;Vector2 point;bool down,up,canceled=false,motion=false;
        if(input is InputEventScreenTouch t){pointer=t.Index;point=t.Position;down=t.Pressed&&!t.Canceled;up=!t.Pressed||t.Canceled;canceled=t.Canceled;}
        else if(input is InputEventScreenDrag d){pointer=d.Index;point=d.Position;down=up=false;motion=true;}
        else if(input is InputEventMouseButton{Device:>=0,ButtonIndex:MouseButton.Left} m){pointer=-2;point=m.Position;down=m.Pressed;up=!m.Pressed;}
        else if(input is InputEventMouseMotion{Device:>=0} move){pointer=-2;point=move.Position;down=up=false;motion=true;}
        else return false;
        if(down&&_spellPointer==-1)
        {
            var spell=SpellAt(point);
            if(spell is null)
            {
                bool page=Buttons.Where(p=>p.Key is "native-page-prev" or "native-page-next").Any(p=>p.Value.IsVisibleInTree()&&p.Value.GetGlobalRect().HasPoint(point));
                if(!page&&_sortSpell is not null)CancelSpellSort();
                return false;
            }
            _spellPress=spell;_spellPointer=pointer;_spellOrigin=point;_spellPressedAt=Time.GetTicksMsec();_spellLongHeld=_spellDragged=false;
            _spellPressEpoch=_scene!.MapEpoch;_spellPressBook=SpellBookVersion(_scene);
        }
        else if(pointer==_spellPointer)
        {
            _spellDragged|=(point-_spellOrigin).Length()>8*NativeOverlay.GetGlobalTransformWithCanvas().Scale.X;
            if(up)
            {
                var spell=_spellPress;bool held=_spellLongHeld||Time.GetTicksMsec()-_spellPressedAt>=SpellHoldMilliseconds;
                if(canceled||_spellDragged||!CanUseNativeRows)CancelSpellSort();
                else if(held){if(!_spellLongHeld)ArmSpellSort();}
                else if(spell is not null&&SpellAt(point)?.WireSlot==spell.WireSlot)ActivateSpell(spell);
                _spellPointer=-1;_spellPress=null;
            }
            else if(!motion)return false;
        }
        else return false;
        GetViewport().SetInputAsHandled();return true;
    }
    private void ActivateSpell(SceneSpellSnapshot spell)
    {
        if(!CanUseNativeRows||_scene is null)return;
        if(_sortSpell is {} selected)
        {
            bool valid=_scene.MapEpoch==_spellSortEpoch&&SpellBookVersion(_scene)==_spellSortBook;
            CancelSpellSort();
            if(valid&&selected.WireSlot!=spell.WireSlot)
                Emit("swap-spells",selected.WireSlot,spell.WireSlot,JsonSerializer.Serialize(new[]{selected.Name,spell.Name}),_scene.MapEpoch);
            return;
        }
        if(spell.Type==1)OpenSpellInput(spell);
        else Emit("cast",spell.WireSlot,spell.Type==2?SelectedTarget:0);
    }
    private void ValidateSpellSort(ClientSceneSnapshot scene)
    {
        if((_spellPress is not null&&(scene.MapEpoch!=_spellPressEpoch||SpellBookVersion(scene)!=_spellPressBook))
            ||(_sortSpell is not null&&(scene.MapEpoch!=_spellSortEpoch||SpellBookVersion(scene)!=_spellSortBook))
            ||scene.Dialog is not null||scene.Shop is not null||scene.WorldMap is not null||!scene.EntryComplete)CancelSpellSort();
    }
}
