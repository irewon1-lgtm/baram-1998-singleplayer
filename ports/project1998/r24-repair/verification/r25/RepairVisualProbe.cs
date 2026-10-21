using Godot;
using P1998.Embedded;
using Shared;
using System.Diagnostics;
using System.Text.Json;
using IO=System.IO;

public partial class VisualProbe
{
    private string CropHash(Rect2I rect)
    {
        using var full=GetViewport().GetTexture().GetImage();using var crop=full.GetRegion(rect);return ImageHash(crop);
    }
    private async Task R25Appearance(ClientSceneSnapshot scene)
    {
        var app=scene.SelfLook!.Appearance.ToArray();app[2]=0;app[5]=0;
        var look=scene.SelfLook with {Appearance=app,Direction=2};
        scene=scene with {Direction=2,SelfLook=look,Players=new[]{look},Cosmetics=default};
        _view.Present(scene,0);_hud.Present(scene,"검증","",false);await Flush("r25-neutral");
        var field=new Rect2I(14,14,408,360);var panel=new Rect2I(460,118,146,132);
        string baseField=CropHash(field),basePanel=CropHash(panel);
        var variants=new[]{
            ("dye_green",new RecoveredAppearance(true,0x22CC55,0,0,-1,0,0,17477,0,0)),
            ("dye_purple_refresh",new RecoveredAppearance(true,0xCC22DD,0,0,-1,0,0,17478,0,0)),
            ("beard",new RecoveredAppearance(true,-1,2,0xCC4411,-1,0,0,0,17596,0)),
            ("weapon_skin",new RecoveredAppearance(true,-1,0,0,17,0,0,0,0,16001))};
        foreach(var (name,cosmetics) in variants)
        {
            var next=scene with {Cosmetics=cosmetics};_view.Present(next,0);_hud.Present(next,"검증","",false);await Flush("r25-"+name);
            string f=CropHash(field),p=CropHash(panel);
            Check("same_captured_cosmetic_visible_in_field_and_equipment_"+name,f!=baseField&&p!=basePanel,new{field=f,panel=p});
            _view.Present(scene,0);_hud.Present(scene,"검증","",false);await Flush();
            Check("removal_refresh_restores_equipment_"+name,CropHash(panel)==basePanel);
        }
        // Equipment portrait intentionally faces south. Direction/action changes in the field must
        // keep the same cosmetic state in the portrait; no invented native-animation parity claim.
        var combined=variants[0].Item2 with {BeardStyle=2,BeardRgb=0xCC4411,BeardItemId=17596};
        var decorated=scene with {Cosmetics=combined};_hud.Present(decorated,"검증","",false);await Flush();string heldPanel=CropHash(panel);
        for(int dir=0;dir<4;dir++)for(int phase=0;phase<4;phase++)
        {
            var s=decorated with {Direction=dir};_view.Present(s,phase*70);_hud.Present(s,"검증","",false);await Flush();
            Check("portrait_keeps_cosmetics_with_field_direction_phase_"+dir+"_"+phase,CropHash(panel)==heldPanel&&_art.Missing.Count==0);
        }
        _view.ResetSession();_view.Present(scene,0);_hud.Present(scene,"다른 캐릭터","",false);await Flush("r25-reset");
        Check("account_scene_reset_clears_cosmetic_pixels",CropHash(panel)==basePanel);
    }
    private async Task R25Performance(ClientSceneSnapshot scene)
    {
        _hud.Visible=false;_view.Visible=false;
        var gallery=new Gallery{Size=new(640,480),TextureFilter=TextureFilterEnum.Nearest};AddChild(gallery);
        // Fixed source heads, poses and colours, same order before/after. Draw completion is awaited.
        var samples=new List<object>();long startAllocated=GC.GetTotalAllocatedBytes(true);long startRss=Process.GetCurrentProcess().WorkingSet64;
        for(int i=0;i<72;i++)
        {
            int n=i;byte[] app={0,0,(byte)(n%8),0,0,0,255};int dir=(n/8)%4,phase=(n/32)%4;
            var cosmetic=new RecoveredAppearance(true,0x303030+n*1337,2,0x993322,-1,0,0,17477,17596,0);
            long alloc=GC.GetTotalAllocatedBytes(false);var watch=Stopwatch.StartNew();
            gallery.Paint=t=>_art.Actor(t,app,dir,phase,0,new Vector2(320,260),0,1,cosmetics:cosmetic);
            gallery.QueueRedraw();await Flush();watch.Stop();
            using var image=GetViewport().GetTexture().GetImage();
            samples.Add(new{index=i,milliseconds=watch.Elapsed.TotalMilliseconds,allocated=GC.GetTotalAllocatedBytes(false)-alloc,hash=ImageHash(image)});
        }
        IO.File.WriteAllText(IO.Path.Combine(_out,"PERFORMANCE.json"),JsonSerializer.Serialize(new{scope="72 fixed cold actor draws; actual X11 llvmpipe, not device FPS",samples,total_allocated=GC.GetTotalAllocatedBytes(true)-startAllocated,rss_before=startRss,rss_after=Process.GetCurrentProcess().WorkingSet64,physical_android="NOT_RUN",existing_game_performance="FAIL_RETAINED"},new JsonSerializerOptions{WriteIndented=true}));
        Check("all_72_fixed_actor_draws_execute",samples.Count==72&&_art.Missing.Count==0);
        gallery.QueueFree();_view.Visible=true;_hud.Visible=true;
    }
}
