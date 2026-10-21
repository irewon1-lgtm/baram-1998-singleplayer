using P1998.Embedded;
using System.Text.Json;

static class NormalEntryProbe
{
    static async Task<int> Main(string[] a)
    {
        string result=await HostProbe.RunAsync(a[0],a[1]);File.WriteAllText(a[2],result);
        using var doc=JsonDocument.Parse(result);return doc.RootElement.GetProperty("status").GetString()=="OBSERVED_CHECKS_PASS"?0:1;
    }
}
