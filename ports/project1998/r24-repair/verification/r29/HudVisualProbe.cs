using Godot;
using P1998.Embedded;
using System.Reflection;

public partial class VisualProbe
{
    private async Task R29Touch(Button button,int milliseconds=40,bool cancel=false)
    {
        var p=button.GetGlobalRect().GetCenter();
        GetViewport().PushInput(new InputEventScreenTouch{Index=0,Position=p,Pressed=true},true);
        await ToSignal(GetTree().CreateTimer(milliseconds/1000.0),SceneTreeTimer.SignalName.Timeout);
        GetViewport().PushInput(new InputEventScreenTouch{Index=0,Position=p,Pressed=false,Canceled=cancel},true);
        await Flush();
    }
    private async Task R29Hud(ClientSceneSnapshot source)
    {
        _hud.ConfigureFrame(640);
        var model=source with {
            Events=Enumerable.Range(1,5).Select(n=>new SceneEvent(n,"message",0,0,0,0,"채팅 기록 "+n,Array.Empty<byte>())).ToArray(),
            Spells=Enumerable.Range(1,14).Select(n=>new SceneSpellSnapshot((byte)n,"검사 기술 "+n,5)).ToArray(),
            Equipment=new[]{new SceneItemSnapshot(1,"검","검",1,0,102),new SceneItemSnapshot(3,"방패","방패",1,0,103)},
            Dialog=null,Shop=null,WorldMap=null,EntryComplete=true
        };
        _hud.Present(model,"검증","원본 응답 수신 · 검사",false);await Flush();
        var chat=(Label)typeof(GameHud).GetField("_chat",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(_hud)!;
        Check("r29_chat_retains_five_messages",Enumerable.Range(1,5).All(n=>chat.Text.Contains("채팅 기록 "+n)),chat.Text);
        Check("r29_five_lines_are_visible",chat.GetVisibleLineCount()>=5,new{lines=chat.GetLineCount(),visible=chat.GetVisibleLineCount(),rect=chat.GetGlobalRect().ToString(),line_height=chat.GetLineHeight(),spacing=chat.GetThemeConstant("line_spacing")});
        var font=_hud.Buttons["talk"].GetThemeFont("font");
        Check("r29_hud_uses_readable_font_weight",font is FontVariation v&&v.VariationOpentype.ContainsKey("wght")&&v.VariationOpentype["wght"].AsDouble()>=450);
        var tabs=new[]{"native-inventory","native-equipment","native-spells"}.Select(k=>_hud.Buttons[k]).ToArray();
        Check("r29_tabs_clear_scroll_artwork",tabs.All(b=>b.Position.Y>=326&&b.Position.Y+b.Size.Y<=353),tabs.Select(b=>new{b.Name,rect=b.GetRect().ToString(),minimum=b.GetCombinedMinimumSize().ToString()}).ToArray());
        Check("r29_action_cells_have_visible_boundaries",new[]{"area-map","talk","menu","door","save","chat","pickup","attack"}.All(k=>_hud.Buttons[k].GetThemeStylebox("normal") is StyleBoxFlat s&&s.BorderWidthLeft>=1&&s.BgColor.A>.9f));
        var ids=_hud.Buttons.Where(p=>p.Key.StartsWith("native-")||p.Key is "talk" or "save" or "area-map").ToDictionary(p=>p.Key,p=>(id:p.Value.GetInstanceId(),disabled:p.Value.Disabled));
        bool stable=true;
        for(int n=0;n<12;n++)
        {
            _hud.Present(model with{X=model.X+n},"검증","원본 응답 수신 · 이동",n%2==0);
            stable&=ids.All(p=>_hud.Buttons.TryGetValue(p.Key,out var b)&&b.GetInstanceId()==p.Value.id&&b.Disabled==p.Value.disabled);
        }
        _hud.Present(model,"검증","원본 응답 수신 · 검사",false);await Flush("r29-equipment-chat");
        Check("r29_movement_keeps_control_identity_and_visual_state",stable);
        var pixels=GetViewport().GetTexture().GetImage();int flicker=0;
        foreach(bool busy in new[]{true,false,true,false})
        {
            _hud.Present(model with{X=model.X+1},"검증","원본 응답 수신 · 이동",busy);await Flush();
            var frame=GetViewport().GetTexture().GetImage();
            foreach(var rect in new[]{new Rect2I(23,448,388,25),new Rect2I(443,328,174,24)})
                if(!pixels.GetRegion(rect).GetData().AsSpan().SequenceEqual(frame.GetRegion(rect).GetData()))flicker++;
        }
        Check("r29_static_control_pixels_do_not_flicker_during_movement",flicker==0,new{changed_regions=flicker});
        _hud.Present(model,"검증","원본 응답 수신 · 검사",false);
        Check("r29_weapon_and_shield_cells_exist",_hud.Buttons.ContainsKey("native-equipment-slot-1")&&_hud.Buttons.ContainsKey("native-equipment-slot-3"));
        if(_hud.Buttons.TryGetValue("native-equipment-slot-1",out var weapon))Check("r29_weapon_cell_describes_actual_equipped_item",weapon.TooltipText.Contains("검"));
        await R29Touch(_hud.Buttons["native-spells"]);
        var emitted=new List<HudCommand>();_hud.Command+=emitted.Add;
        var first=_hud.Buttons["native-cast-1"];
        Check("r29_spell_ink_remains_dark_on_hover",first.GetThemeColor("font_hover_color").R<.45f&&first.GetThemeColor("font_pressed_color").R<.45f);
        await R29Touch(first,650);await Flush("r29-spell-selected");
        Check("r29_long_hold_never_casts",emitted.Count==0,emitted.Select(x=>x.Kind).ToArray());
        Check("r29_long_hold_shows_destination_instruction",_hud.FindChild("SpellSortHint",true,false) is Label hint&&hint.IsVisibleInTree()&&hint.Text.Contains("위치"));
        await R29Touch(_hud.Buttons["native-cast-3"]);
        Check("r29_destination_tap_emits_one_original_swap",emitted.Count==1&&emitted[0].Kind=="swap-spells"&&emitted[0].Number==1&&emitted[0].EntityId==3,emitted.Select(x=>new{x.Kind,x.Number,x.EntityId}).ToArray());
        emitted.Clear();await R29Touch(_hud.Buttons["native-cast-2"],650,true);
        await R29Touch(_hud.Buttons["native-inventory"]);await R29Touch(_hud.Buttons["native-spells"]);
        Check("r29_canceled_hold_and_panel_change_do_not_swap_or_cast",emitted.Count==0);
        emitted.Clear();await R29Touch(_hud.Buttons["native-cast-4"]);
        Check("r29_ordinary_short_tap_still_casts_original_slot",emitted.Count==1&&emitted[0].Kind=="cast"&&emitted[0].Number==4);
        _hud.Command-=emitted.Add;
        await Flush("r29-spells");
    }
}
