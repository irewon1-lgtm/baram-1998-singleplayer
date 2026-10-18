using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using Shared;

namespace P1998.P3;

/// <summary>P3-only namespace and version fence around the original SQLite store.</summary>
public sealed class ProbeStore
{
    public const string SchemaId = "project1998.p3.core-probe";
    public const int Version = 1;
    public const string OriginalHead = "65cb3ef28f289ee35d19abfb6829d6120b9ec0cd";
    private readonly string _root;
    public CharacterStore Store { get; }

    public static void Guard(string root, string contentHash)
    {
        string path = Path.Combine(root, "identity.json");
        if (File.Exists(path))
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            var m = doc.RootElement;
            if (m.GetProperty("schema_id").GetString() != SchemaId || m.GetProperty("schema_version").GetInt32() != Version ||
                m.GetProperty("engine_head").GetString() != OriginalHead || m.GetProperty("content_sha256").GetString() != contentHash)
                throw new InvalidDataException("EXISTING_SAVE_PROTECTED: P3 identity/version/content mismatch");
            return;
        }
        if (Directory.Exists(root) && Directory.EnumerateFiles(root, "*.db*").Any())
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: database without identity");
        Directory.CreateDirectory(root);
        AtomicText(path, JsonSerializer.Serialize(new { schema_id = SchemaId, schema_version = Version,
            engine_head = OriginalHead, content_sha256 = contentHash, character_schema = Character.CurrentSchemaVersion }));
    }

    public ProbeStore(string root) { _root = root; Store = new CharacterStore(Path.Combine(root, "chars")); }

    public bool Save(Character c)
    {
        var prior = Store.Load(c.Name);
        if (prior.Status is not (CharacterLoadStatus.Ok or CharacterLoadStatus.NotFound))
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: " + prior.Status);
        if (prior.Status == CharacterLoadStatus.Ok) Backup();
        return Store.Save(c);
    }

    public void Backup()
    {
        string pending = Path.Combine(_root, "backup-" + Guid.NewGuid().ToString("N") + ".pending.db");
        using (var source = Db.Open())
        using (var target = new SqliteConnection("Data Source=" + pending + ";Pooling=False"))
        {
            target.Open(); source.BackupDatabase(target);
            using var cmd = target.CreateCommand(); cmd.CommandText = "PRAGMA journal_mode=DELETE;"; cmd.ExecuteScalar();
            cmd.CommandText = "PRAGMA integrity_check;";
            if ((string?)cmd.ExecuteScalar() != "ok") throw new InvalidDataException("Backup integrity check failed");
        }
        File.Move(pending, Path.Combine(_root, "p3-v1.backup.db"), true);
    }

    // Read a rollback snapshot without replacing the current save. A future game
    // migration must restore into a new version directory after explicit choice.
    public Character? ReadBackup(string name)
    {
        using var cn = new SqliteConnection("Data Source=" + Path.Combine(_root, "p3-v1.backup.db") + ";Mode=ReadOnly;Pooling=False");
        cn.Open(); using var cmd = cn.CreateCommand();
        cmd.CommandText = "SELECT json FROM characters WHERE username=$u";
        cmd.Parameters.AddWithValue("$u", CharacterStore.Key(name));
        return cmd.ExecuteScalar() is string json ? JsonSerializer.Deserialize<Character>(json, Scenario.Json) : null;
    }

    public static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    public static void AtomicText(string path, string text)
    {
        string pending = path + ".pending." + Guid.NewGuid().ToString("N");
        using (var f = new FileStream(pending, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        using (var writer = new StreamWriter(f)) { writer.Write(text); writer.Flush(); f.Flush(true); }
        File.Move(pending, path, true);
    }
}
