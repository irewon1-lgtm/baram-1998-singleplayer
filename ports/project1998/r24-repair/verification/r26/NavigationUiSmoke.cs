using Godot;
using P1998.Embedded;
using Shared;
using System.Text.Json;
using IO=System.IO;

// Test-only Main partial, copied into an isolated desktop project, never the APK.
public partial class Main
{
 private readonly List<object> _r26Checks=new();
 private void R26Check(string name,bool pass,object? observed=null){_r26Checks.Add(new{name,status=pass?"PASS":"FAIL",observed});if(!pass)throw new InvalidOperationException(name);}
 private Vector2 R26Point(int x,int y)=>_view.GetGlobalTransformWithCanvas()*R21WorldTileCenter(x,y);
 private async Task R26Tap(int x,int y){var point=R26Point(x,y);R15Touch(point,true);await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);R15Touch(point,false);await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);}
 private async Task R26At(int map,int x,int y){await WaitUi(()=>_play?.Capture() is{}s&&s.Map==map&&s.X==x&&s.Y==y&&!_busy,"Tap destination not reached "+map+":"+x+","+y,20);await InputDelay(120);}
 private async void BeginR26NavigationSmoke(){
  string status="FAIL";string? error=null;
  try{
   using var contract=JsonDocument.Parse(IO.File.ReadAllText(IO.Path.Combine(_root,"ko-contract.json")));string id=contract.RootElement.GetProperty("id").GetString()!;
   await R15Continue(id);await R15Return();
   var store=new CharacterStore(IO.Path.Combine(_root,"state","chars"));var saved=store.ReadOfflineSnapshot(id)!;var c=CharacterStore.Deserialize(saved.CharacterJson);
   c.Map=330;c.MapXs=Server.Content.Maps[330].Xs;c.MapYs=Server.Content.Maps[330].Ys;c.X=110;c.Y=137;c.Level=30;c.Coins=123456;
   var receipt=store.SaveOfflineSnapshot(id,CharacterStore.Serialize(c),saved.ExtraJson,saved.RuntimeJson,saved.CaptureSequence+1,saved.Revision);
   R26Check("isolated_fixture_location_commit",receipt.Committed);await R15Continue(id);await InputDelay(250);var p=_play!;
   await R26Tap(110,135);await R26At(330,110,135);R26Check("one_floor_tap_continues_after_release",_destination is null&&p.Capture().Y==135);
   await R26Tap(110,137);await R26Tap(111,135);await R26At(330,111,135);R26Check("latest_tap_replaces_inflight_destination",_destination is null&&p.Capture().X==111&&p.Capture().Y==135);
   await R26Tap(110,137);_hud.Buttons["menu"].EmitSignal(BaseButton.SignalName.Pressed);await WaitUi(()=>_hud.ModalOpen&&_destination is null,"Menu did not cancel navigation");
   R26Check("menu_cancels_old_automatic_path",_destination is null);await Click(_hud.Buttons["local-close"]);await InputSettle();
   long beforeEpoch=p.Model.MapEpoch;await R26Tap(110,133);await WaitUi(()=>p.Capture().Map==331&&p.Ready&&!_busy,"Visible Kan Shop entrance",20);await InputDelay(250);
   R26Check("visible_facade_entered_from_ordinary_road",p.Capture().Map==331&&_destination is null&&_input.Direction<0);
   bool refused=false;try{await p.Host.ReceiveAsync(0x11,new byte[]{1},expectedMapEpoch:beforeEpoch);}catch(InvalidOperationException){refused=true;}
   R26Check("old_map_input_rejected_after_committed_transition",refused);
   await R26Tap(5,8);await R26At(331,5,8);await CaptureScreen("r26-shop-interior");
   await R26Tap(5,11);await WaitUi(()=>p.Capture().Map==330&&p.Ready&&!_busy,"Normal shop exit",20);var outside=p.Capture();await InputDelay(900);
   R26Check("normal_exit_stops_on_outside_safe_tile_no_adjacent_reentry",p.Capture().Map==330&&p.Capture().X==outside.X&&p.Capture().Y==outside.Y&&_destination is null,new{outside.X,outside.Y});
   await R26Tap(110,136);await R26At(330,110,136);R26Check("normal_walking_after_exit",p.Capture().Y==136);await CaptureScreen("r26-shop-outside");
   R26Check("transition_journal_retains_entries",p.Host.MapTransitions.Count>=2,new{count=p.Host.MapTransitions.Count});
   await Click(_hud.Buttons["save"]);await InputSettle();R26Check("money_and_existing_progress_preserved",G4Character(p).Coins==123456&&G4Character(p).Level==30&&p.Host.LastSave.Committed);
   // User replaced stage4: no new BGM comparison in this run.
   await InputDelay(34000);await R26Tap(110,135);await R26At(330,110,135);
   R26Check("actual_game_sampler_continues_after31_active_seconds",_performance.ActiveSeconds>31&&_performance.TotalFrames>_performance.FramesMilliseconds.Count,new{_performance.ActiveSeconds,_performance.TotalFrames,recent=_performance.FramesMilliseconds.Count});
   R26Check("cumulative_cpu_ram_gc_world_samples_continue_during_play",p.Host.RuntimePerformance.Snapshot().TotalCount>=2&&p.Host.RuntimePerformance.Count<=128,p.Host.RuntimePerformance.Snapshot());
   status="PASS_SCOPED_ACTUAL_PC_TOUCH_NAVIGATION_AND_NORMAL_SHOP_ROUNDTRIP";
  }catch(Exception e){error=e.ToString();}
  AtomicWrite(IO.Path.Combine(_root,"ko-checks.json"),JsonSerializer.Serialize(new{status,checks=_r26Checks,error,physical_android="NOT_RUN",scope="Actual indexed touch -> Godot GameView -> Main -> original PlaySession/Session/SQLite. Synthetic prerequisite save, no user data."},new JsonSerializerOptions{WriteIndented=true}));
  WriteReport(IO.Path.Combine(_root,"r26-input-result.json"));await End(true);
 }
}
