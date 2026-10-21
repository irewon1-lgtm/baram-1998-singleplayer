using P1998.Embedded;
using Server;
using System.Reflection;
using System.Diagnostics;
using System.Text.Json;

var play=await PlaySession.OpenAsync(new(Path.Combine(args[1],"state"),args[0],"snaptest","Synthetic26!","snaptest",true,false));
var session=(Session)typeof(EmbeddedHost).GetField("_session",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(play.Host)!;
using var acquired=new ManualResetEventSlim();using var release=new ManualResetEventSlim();
var blocker=new Thread(()=>{using var held=session.EnterState();acquired.Set();release.Wait(TimeSpan.FromSeconds(5));});blocker.Start();acquired.Wait();
var timer=Stopwatch.StartNew();var capture=Task.Run(()=>play.Capture());bool responsive=await Task.WhenAny(capture,Task.Delay(120))==capture;double ms=timer.Elapsed.TotalMilliseconds;release.Set();blocker.Join();await capture;
await play.StopAsync();File.WriteAllText(args[2],JsonSerializer.Serialize(new{status=responsive?"PASS":"FAIL",render_capture_completed_while_action_state_locked=responsive,observed_ms=ms,physical_android="NOT_RUN",scope="Actual Session monitor contention. No user save, no synthetic product lock implementation."}));return responsive?0:1;
