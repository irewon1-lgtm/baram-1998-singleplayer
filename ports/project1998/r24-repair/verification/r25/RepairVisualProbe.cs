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
            Check("portrait_keeps_cosmetics_with_direction_scene_refresh_"+dir+"_"+phase,CropHash(panel)==heldPanel&&_art.Missing.Count==0);
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
        IO.File.WriteAllText(IO.Path.Combine(_out,"PERFORMANCE.json"),JsonSerializer.Serialize(new{scope="72 fixed cold actor draws; actual X11 llvmpipe, not device FPS",samples,total_allocated=GC.GetTotalAllocatedBytes(true)-startAllocated,rss_before=startRss,rss_after=Process.GetCurrentProcess().WorkingSet64,physical_android="NOT_RUN",existing_game_performance="FAIL_RETAINED",customization=_art.GetType().GetMethod("CustomizationDiagnostics")?.Invoke(_art,null)},new JsonSerializerOptions{WriteIndented=true}));
        Check("all_72_fixed_actor_draws_execute",samples.Count==72&&_art.Missing.Count==0);
        gallery.QueueFree();_view.Visible=true;_hud.Visible=true;
    }
    private async Task R25Cache(ClientSceneSnapshot scene)
    {
        _view.Visible=false;_hud.Visible=false;
        var gallery=new Gallery{Size=new(640,480),TextureFilter=TextureFilterEnum.Nearest};AddChild(gallery);
        for(int page=0;page<60;page++)
        {
            int batch=page;
            gallery.Paint=t=>
            {
                for(int col=0;col<12;col++)
                {
                    int i=batch*12+col;byte[] app={0,0,(byte)(i%32),0,0,0,255};
                    var cosmetic=new RecoveredAppearance(true,0x304050+i*1451,0,0,-1,0,0,17477,0,0);
                    _art.Actor(t,app,i%4,i%4,0,new Vector2(30+col*50,230),0,1,cosmetics:cosmetic);
                }
            };
            gallery.QueueRedraw();await Flush();
        }
        using var doc=JsonDocument.Parse(JsonSerializer.Serialize(_art.GetType().GetMethod("CustomizationDiagnostics")!.Invoke(_art,null)));
        var d=doc.RootElement;Check("720_colours_keep_incremental_512_entry_texture_budget",d.GetProperty("texture_entries").GetInt32()==512&&d.GetProperty("texture_rgba_bytes").GetInt64()<=4194304&&d.GetProperty("texture_evictions").GetInt64()>0,d.Clone());
        Check("source_frame_cache_respects_256_entry_2MiB_budget",d.GetProperty("source_entries").GetInt32()<=256&&d.GetProperty("source_rgba_bytes").GetInt64()<=2097152);
        Check("cache_pressure_never_reads_original_gpu_atlas",d.GetProperty("atlas_reads").GetInt64()==0&&_art.Missing.Count==0);
        gallery.QueueFree();_view.Visible=true;_hud.Visible=true;
    }
    private async Task R25SkinFamilies(ClientSceneSnapshot scene)
    {
        _view.Visible=false;_hud.Visible=false;
        var gallery=new Gallery{Size=new(640,480),TextureFilter=TextureFilterEnum.Nearest};AddChild(gallery);
        // Independently selected existing source-item aliases. These are compatible original sword
        // animations, NOT evidence that the unavailable later skin used these historical graphics.
        var aliases=new[]{(16001,61),(16002,61),(16003,68),(16004,47),(16005,9),(16006,66)};
        foreach(var (skin,art) in aliases)for(int dir=0;dir<4;dir++)for(int action=0;action<2;action++)for(int phase=0;phase<(action==0?4:2);phase++)
        {
            byte[] app={0,0,0,0,0,0,255};var cosmetic=new RecoveredAppearance(true,-1,0,0,5209,0,0,0,0,skin);
            gallery.Paint=t=>_art.Actor(t,app,dir,phase,action,new Vector2(320,260),cosmetics:cosmetic);gallery.QueueRedraw();await Flush();string actual=ImageHash(GetViewport().GetTexture().GetImage());
            app[5]=(byte)art;gallery.Paint=t=>_art.Actor(t,app,dir,phase,action,new Vector2(320,260));gallery.QueueRedraw();await Flush();string original=ImageHash(GetViewport().GetTexture().GetImage());
            Check("adapted_skin_uses_existing_native_pose_"+skin+"_"+dir+"_"+action+"_"+phase,actual==original&&_art.Missing.Count==0,new{actual,original});
        }
        byte[] ghost={0,1,0,0,0,0,255};
        gallery.Paint=t=>_art.Actor(t,ghost,2,0,0,new Vector2(320,260));gallery.QueueRedraw();await Flush();string death=ImageHash(GetViewport().GetTexture().GetImage());
        gallery.Paint=t=>_art.Actor(t,ghost,2,0,0,new Vector2(320,260),cosmetics:new(true,-1,2,0xAA2200,5209,0,0,0,17596,16001));gallery.QueueRedraw();await Flush();
        Check("death_uses_original_ghost_without_stray_cosmetic_layers",ImageHash(GetViewport().GetTexture().GetImage())==death);
        gallery.QueueFree();_view.Visible=true;_hud.Visible=true;
    }
}
