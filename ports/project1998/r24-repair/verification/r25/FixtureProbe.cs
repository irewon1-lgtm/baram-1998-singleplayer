using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using P1998.Embedded;

static class FixtureProbe
{
    static async Task<int> Main(string[] a)
    {
        string root = a[1]; Directory.CreateDirectory(root);
        var profiles = new LocalProfileStore(root);
        var checks = new List<object>();
        foreach (string id in new[] { "repairalpha", "repairbeta", "repairgamma" })
        {
            var p = new LocalCharacterProfile(id, "Synthetic25!", id);
            profiles.Stage(p);
            var options = new HostOptions(Path.Combine(root, "state"), a[0], p.Id, p.Password, p.Name, true, false);
            var play = await PlaySession.OpenAsync(options);
            if (!play.Host.Ready) throw new Exception("Fresh public entry failed");
            profiles.CommitSuccessful(p);
            await play.StopAsync();
            var reopened = await PlaySession.OpenAsync(options with { CreateIfMissing = false });
            if (!reopened.Host.Ready || reopened.Host.Faulted) throw new Exception("Saved public reopen failed");
            await reopened.StopAsync();
            checks.Add(new { scenario = "normal_creation_save_reopen", id, status = "PASS" });
        }
        var catalog = profiles.Load();
        if (catalog.Characters.Length != 3 || catalog.Characters.Any(c => !c.CanOpen)) throw new Exception("Three account catalog failed");
        profiles.Select("repairalpha");
        using var cn = new SqliteConnection("Data Source=" + Path.Combine(root, "state", "project1998.db")); cn.Open();
        using var cmd = cn.CreateCommand(); cmd.CommandText = "PRAGMA integrity_check";
        if ((string?)cmd.ExecuteScalar() != "ok") throw new Exception("Fixture integrity failed");
        cmd.CommandText = "SELECT username,json FROM characters ORDER BY username";
        using var reader = cmd.ExecuteReader(); var hashes = new Dictionary<string,string>();
        while (reader.Read()) hashes.Add(reader.GetString(0), Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(reader.GetString(1)))).ToLowerInvariant());
        File.WriteAllText(a[2], JsonSerializer.Serialize(new { status = "PASS", fixture = "NEW_R25_SYNTHETIC_BASELINE_NOT_OLD_R20_BYTES", checks, hashes, integrity = "ok", user_save_writes = 0 }, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
