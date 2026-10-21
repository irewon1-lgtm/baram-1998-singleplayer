using P1998.Embedded;
using System.Collections.Concurrent;
using System.Text.Json;

static class DiagnosticsProbe
{
    static async Task<int> Main(string[] a)
    {
        var play=await PlaySession.OpenAsync(new(a[1],a[0],"diagprobe","Synthetic25!","diagprobe",true,false));
        var host=play.Host;var errors=new ConcurrentQueue<string>();
        const int samples=100000;
        var writer=Task.Run(()=>{for(int i=0;i<samples;i++){host.InputMilliseconds.Add(i);host.TickMilliseconds.Add(i);host.CommitObservations.Add(new{index=i});}});
        var reader=Task.Run(()=>{try{while(!writer.IsCompleted){_ = host.InputMilliseconds.ToArray();_ = host.TickMilliseconds.ToArray();_ = host.CommitObservations.ToArray();}}catch(Exception e){errors.Enqueue(e.GetType().Name);}});
        await Task.WhenAll(writer,reader);
        bool bounded=host.InputMilliseconds.Count<=512&&host.TickMilliseconds.Count<=512&&host.CommitObservations.Count<=256;
        var input=host.InputMilliseconds.ToArray();bool tail=input.Length>0&&input[^1]==samples-1;
        var summary=host.InputMilliseconds.GetType().GetMethod("Snapshot")?.Invoke(host.InputMilliseconds,null);
        bool pass=bounded&&tail&&errors.Count==0&&summary is not null;
        await play.StopAsync();
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=pass?"PASS":"FAIL",scope="concurrent recorder stress, synthetic samples, not gameplay latency",samples,bounded,tail,errors=errors.ToArray(),input=host.InputMilliseconds.Count,ticks=host.TickMilliseconds.Count,commits=host.CommitObservations.Count,summary},new JsonSerializerOptions{WriteIndented=true}));return pass?0:1;
    }
}
