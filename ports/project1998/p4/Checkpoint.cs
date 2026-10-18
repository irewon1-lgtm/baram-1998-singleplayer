using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using Server;
using Shared;

namespace P1998.P4;

public sealed class CheckpointData
{
    public int schema_version = 1;
    public Character character = new();
    public P4WorldState world = new();
    public long revision;
}

// The authoritative P4 checkpoint commits character + world in one SQLite
// transaction. The original CharacterStore is a disposable runtime cache.
public sealed class Checkpoint
{
    public const string Schema = "project1998.p4.vertical-slice";
    public const string Head = "65cb3ef28f289ee35d19abfb6829d6120b9ec0cd";
    private readonly string _path;
    private long _revision;

    public static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    public static void Guard(string root, string contentHash)
    {
        if (!Path.IsPathFullyQualified(root)) throw new InvalidDataException("Absolute P4 save path required");
        string dir = Path.Combine(root, "v1"), identity = Path.Combine(dir, "identity.json");
        if (File.Exists(identity))
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(identity)); var p = doc.RootElement;
            if (p.GetProperty("schema_id").GetString() != Schema || p.GetProperty("schema_version").GetInt32() != 1 ||
                p.GetProperty("engine_head").GetString() != Head || p.GetProperty("content_sha256").GetString() != contentHash)
                throw new InvalidDataException("EXISTING_SAVE_PROTECTED: P4 identity/version/content mismatch");
            return;
        }
        if (Directory.Exists(dir) && Directory.EnumerateFiles(dir, "*.db*").Any())
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: P4 database without identity");
        Directory.CreateDirectory(dir);
        AtomicText(identity, JsonSerializer.Serialize(new { schema_id = Schema, schema_version = 1,
            engine_head = Head, content_sha256 = contentHash }));
    }

    public Checkpoint(string root)
    {
        SQLitePCL.Batteries_V2.Init();
        _path = Path.Combine(root, "v1/progress.db");
    }

    public CheckpointData? Read()
    {
        if (!File.Exists(_path)) return null;
        using var cn = Open(readOnly: true); using var cmd = cn.CreateCommand();
        cmd.CommandText = "SELECT json,sha256 FROM checkpoint WHERE slot=1";
        using var row = cmd.ExecuteReader();
        if (!row.Read()) throw new InvalidDataException("EXISTING_SAVE_PROTECTED: checkpoint row missing");
        string text = row.GetString(0);
        if (Hash(Encoding.UTF8.GetBytes(text)) != row.GetString(1))
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: checkpoint checksum mismatch");
        using var doc = JsonDocument.Parse(text); var p = doc.RootElement;
        if (p.GetProperty("schema_version").GetInt32() != 1 ||
            p.GetProperty("character").GetProperty("SchemaVersion").GetInt32() != Character.CurrentSchemaVersion ||
            p.GetProperty("world").GetProperty("schema_version").GetInt32() != 1)
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: future checkpoint/character/world");
        var value = JsonSerializer.Deserialize<CheckpointData>(text, P4Json.Options)
            ?? throw new InvalidDataException("Checkpoint decode failed");
        _revision = value.revision;
        return value;
    }

    public long Save(Character character, P4WorldState world)
    {
        var payload = new CheckpointData { character = character, world = world, revision = _revision + 1 };
        string text = JsonSerializer.Serialize(payload, P4Json.Options);
        using var cn = Open(readOnly: false);
        using (var setup = cn.CreateCommand())
        {
            setup.CommandText = "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS checkpoint(slot INTEGER PRIMARY KEY,json TEXT NOT NULL,sha256 TEXT NOT NULL);";
            setup.ExecuteNonQuery();
        }
        using (var tx = cn.BeginTransaction())
        using (var cmd = cn.CreateCommand())
        {
            cmd.Transaction = tx;
            cmd.CommandText = "INSERT OR REPLACE INTO checkpoint SELECT 2,json,sha256 FROM checkpoint WHERE slot=1; INSERT OR REPLACE INTO checkpoint VALUES(1,$json,$hash);";
            cmd.Parameters.AddWithValue("$json", text); cmd.Parameters.AddWithValue("$hash", Hash(Encoding.UTF8.GetBytes(text)));
            cmd.ExecuteNonQuery(); tx.Commit();
        }
        _revision = payload.revision;
        return _revision;
    }

    private SqliteConnection Open(bool readOnly)
    {
        var cn = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _path,
            Mode = readOnly ? SqliteOpenMode.ReadOnly : SqliteOpenMode.ReadWriteCreate, Pooling = false }.ToString());
        cn.Open(); return cn;
    }

    public static void PrepareRuntimeCache(string root)
    {
        string path = Path.Combine(root, "cache"), marker = Path.Combine(path, "owned.txt");
        const string owner = "project1998.p4.disposable-runtime-cache.v1";
        if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any() &&
            (!File.Exists(marker) || File.ReadAllText(marker) != owner))
            throw new InvalidDataException("EXISTING_SAVE_PROTECTED: unknown runtime cache");
        Directory.CreateDirectory(path);
        foreach (string file in Directory.EnumerateFiles(path, "project1998.db*")) File.Delete(file);
        File.WriteAllText(marker, owner);
    }

    public static void AtomicText(string path, string text)
    {
        string pending = path + ".pending." + Guid.NewGuid().ToString("N");
        using (var file = new FileStream(pending, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        using (var writer = new StreamWriter(file)) { writer.Write(text); writer.Flush(); file.Flush(true); }
        File.Move(pending, path, true);
    }
}
