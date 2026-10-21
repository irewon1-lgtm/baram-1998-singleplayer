using System.Text.Json;
var m=new MonotonicFrameMetrics(1000);m.Track(0,true);
for(int i=1;i<=2100;i++)m.Track(i*16L,true);
int count=m.FramesMilliseconds.Count;m.Track(34100,true);
bool late=m.FramesMilliseconds.Any(x=>x>=400);
for(int i=1;i<=10000;i++)m.Track(34100+i*16L,true);
bool bounded=m.FramesMilliseconds.Count<=8192;
var report=new{status=late&&bounded?"PASS":"FAIL",late_hitch_retained=late,bounded_samples=bounded,samples=m.FramesMilliseconds.Count,before=count,active_seconds=m.ActiveSeconds,physical_android="NOT_RUN"};
File.WriteAllText(args[0],JsonSerializer.Serialize(report));return late&&bounded?0:1;
