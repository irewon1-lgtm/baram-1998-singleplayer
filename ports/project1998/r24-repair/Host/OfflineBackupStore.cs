using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Data.Sqlite;

namespace P1998.Embedded;

/// <summary>Offline-only backup of the entire save tuple. Restore creates a new root;
/// it never replaces an existing player's root or invents lost progress.</summary>
public static class OfflineBackupStore
{
    private sealed record Entry(string Path, long Bytes, string Sha256);
    private sealed record Manifest(int Policy, string Database, Entry[] Files);
    private static readonly JsonSerializerOptions Json = new()
    { WriteIndented = true, UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow };
    private const long Limit = 512L * 1024 * 1024;
    private const string Database = "state/project1998.db";
    private static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    /// <summary>Validate an inactive save without migrating, authenticating, creating accounts
    /// or changing selection. The caller may preview a separately restored candidate afterwards.</summary>
    public static void ValidateRoot(string rootDirectory)
    {
        string root = Path.GetFullPath(rootDirectory);
        if (!Directory.Exists(root) || !File.Exists(Path.Combine(root, Database)))
            throw new InvalidDataException("A complete existing game save is required for validation.");
        foreach (string path in SaveFiles(root)) RejectLinks(root, Path.Combine(root, path));
        using var lease = OfflineStateLease.Acquire(Path.Combine(root, "state"));
        using var profiles = new FileStream(Path.Combine(root, ".local-profile-write.lock"),
            FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        ValidateTuple(root);
    }

    public static void Create(string rootDirectory, string archivePath) => CreateCore(rootDirectory,archivePath,null);
    internal static void CreateWithOwnedLease(string rootDirectory,string archivePath,OfflineStateLease lease)
        => CreateCore(rootDirectory,archivePath,lease);
    private static void CreateCore(string rootDirectory, string archivePath, OfflineStateLease? owned)
    {
        string root = Path.GetFullPath(rootDirectory), output = Path.GetFullPath(archivePath);
        string state = Path.Combine(root, "state");
        if (!Directory.Exists(root) || !File.Exists(Path.Combine(root, Database)))
            throw new InvalidDataException("A complete existing game save is required for backup.");
        if (File.Exists(output)) throw new IOException("An existing backup is never overwritten.");
        if (owned is not null && !owned.Owns(state)) throw new IOException("Backup lease does not own this save.");
        using var lease = owned is null ? OfflineStateLease.Acquire(state) : null;
        using var profiles = new FileStream(Path.Combine(root, ".local-profile-write.lock"),
            FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        string temporary = Path.Combine(Path.GetDirectoryName(output)!, ".p1998-backup-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporary);
        string pending = output + ".pending-" + Guid.NewGuid().ToString("N");
        try
        {
            foreach (string relative in SaveFiles(root))
            {
                string source = Path.Combine(root, relative), destination = Path.Combine(temporary, relative);
                RejectLinks(root, source); Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                if (relative == Database) BackupDatabase(source, destination);
                else File.Copy(source, destination, overwrite: false);
            }
            ValidateTuple(temporary);
            var files = SaveFiles(temporary).Select(p => new Entry(p, new FileInfo(Path.Combine(temporary, p)).Length,
                Hash(Path.Combine(temporary, p)))).ToArray();
            if (files.Length > 4096 || files.Sum(p => p.Bytes) > Limit) throw new InvalidDataException("Backup exceeds the supported size.");
            File.WriteAllText(Path.Combine(temporary, "backup-manifest.json"), JsonSerializer.Serialize(new Manifest(1, Database, files), Json));
            ZipFile.CreateFromDirectory(temporary, pending, CompressionLevel.Optimal, includeBaseDirectory: false);
            using (var file = new FileStream(pending, FileMode.Open, FileAccess.ReadWrite, FileShare.None)) file.Flush(true);
            File.Move(pending, output, overwrite: false);
        }
        finally { Directory.Delete(temporary, recursive: true); if (File.Exists(pending)) File.Delete(pending); }
    }

    public static void RestoreNew(string archivePath, string newRootDirectory)
    {
        string root = Path.GetFullPath(newRootDirectory);
        if (Directory.Exists(root) || File.Exists(root)) throw new IOException("Restore requires a new directory; existing saves are preserved.");
        Directory.CreateDirectory(Path.GetDirectoryName(root)!);
        using var lease = OfflineStateLease.Acquire(root);
        string staging = root + ".restoring-" + Guid.NewGuid().ToString("N");
        Directory.CreateDirectory(staging);
        try
        {
            using (var zip = ZipFile.OpenRead(archivePath))
            {
                if (zip.Entries.Count is < 2 or > 4097 || zip.Entries.Sum(p => p.Length) > Limit)
                    throw new InvalidDataException("Unsupported backup size or entry count.");
                var names = new HashSet<string>(StringComparer.Ordinal);
                foreach (var entry in zip.Entries)
                {
                    string name = entry.FullName;
                    if (!names.Add(name) || !Allowed(name) && name != "backup-manifest.json" || name.Contains('\\')
                        || name.StartsWith('/') || name.Split('/').Any(p => p is "" or "." or "..")
                        || entry.Length is < 0 or > Limit || (entry.ExternalAttributes >> 16 & 0xF000) == 0xA000)
                        throw new InvalidDataException("Invalid, duplicate or unsupported backup entry.");
                    string target = Path.Combine(staging, name);
                    Directory.CreateDirectory(Path.GetDirectoryName(target)!); entry.ExtractToFile(target, overwrite: false);
                }
                using var metadata = File.OpenRead(Path.Combine(staging, "backup-manifest.json"));
                using var document = JsonDocument.Parse(metadata);
                RejectDuplicateFields(document.RootElement);
                var manifest = document.RootElement.Deserialize<Manifest>(Json);
                if (manifest is null || manifest.Policy != 1 || manifest.Database != Database || manifest.Files is null
                    || manifest.Files.Length + 1 != names.Count || manifest.Files.Select(p => p.Path).Distinct(StringComparer.Ordinal).Count() != manifest.Files.Length)
                    throw new InvalidDataException("Unsupported or incomplete backup manifest.");
                foreach (var entry in manifest.Files)
                    if (!Allowed(entry.Path) || !names.Contains(entry.Path) || entry.Bytes != new FileInfo(Path.Combine(staging, entry.Path)).Length
                        || entry.Sha256 != Hash(Path.Combine(staging, entry.Path)))
                        throw new InvalidDataException("Backup hash or file list mismatch.");
            }
            ValidateTuple(staging);
            File.Delete(Path.Combine(staging, "backup-manifest.json"));
            // Same-parent rename publishes all profiles, DB and witnesses together.
            Directory.Move(staging, root);
        }
        finally { if (Directory.Exists(staging)) Directory.Delete(staging, recursive: true); }
    }

    private static bool Allowed(string path) => path == Database || path is "g2-local-profile.json" or "local-character-selection-v1.json"
        || path.StartsWith("profiles/", StringComparison.Ordinal) && path.EndsWith(".json", StringComparison.Ordinal) && path.Split('/').Length == 2
        || path.StartsWith("state/offline-save-watermarks/", StringComparison.Ordinal) && path.EndsWith(".json", StringComparison.Ordinal) && path.Split('/').Length == 3;
    private static void RejectDuplicateFields(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in element.EnumerateObject())
            {
                if (!names.Add(property.Name)) throw new InvalidDataException("Duplicate backup metadata field.");
                RejectDuplicateFields(property.Value);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
            foreach (var value in element.EnumerateArray()) RejectDuplicateFields(value);
    }
    private static string[] SaveFiles(string root)
    {
        var result = new List<string>();
        foreach (string file in new[] { Database, "g2-local-profile.json", "local-character-selection-v1.json" })
            if (File.Exists(Path.Combine(root, file))) result.Add(file);
        foreach (string folder in new[] { "profiles", "state/offline-save-watermarks" })
            if (Directory.Exists(Path.Combine(root, folder)))
                result.AddRange(Directory.GetFiles(Path.Combine(root, folder), "*.json")
                    .Select(p => Path.GetRelativePath(root, p).Replace('\\', '/')));
        return result.Order(StringComparer.Ordinal).ToArray();
    }
    private static void RejectLinks(string root, string file)
    {
        for (string? path = file; path is not null; path = Path.GetDirectoryName(path))
        {
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("A linked save path cannot be backed up.");
            if (HostBootstrap.SamePath(path, root)) return;
        }
        throw new IOException("Save is outside its root.");
    }
    private static SqliteConnection Open(string path, SqliteOpenMode mode)
    {
        var cn = new SqliteConnection(new SqliteConnectionStringBuilder
        { DataSource = path, Mode = mode, Cache = SqliteCacheMode.Private, Pooling = false }.ToString());
        cn.Open(); return cn;
    }
    private static void BackupDatabase(string source, string destination)
    {
        using var read = Open(source, SqliteOpenMode.ReadOnly);
        using var write = Open(destination, SqliteOpenMode.ReadWriteCreate);
        // SQLite reads the main file AND committed WAL. No immutable mode or raw DB copy.
        read.BackupDatabase(write);
        using var command = write.CreateCommand(); command.CommandText = "PRAGMA journal_mode=DELETE;"; command.ExecuteScalar();
    }
    private static void ValidateTuple(string root)
    {
        using (var db = Open(Path.Combine(root, Database), SqliteOpenMode.ReadOnly))
        {
            using var check = db.CreateCommand(); check.CommandText = "PRAGMA integrity_check;";
            if (Convert.ToString(check.ExecuteScalar()) != "ok") throw new InvalidDataException("Backup database integrity check failed.");
            check.CommandText = "SELECT username FROM characters;";
            using var rows = check.ExecuteReader(); var accounts = new List<string>();
            while (rows.Read()) accounts.Add(rows.GetString(0));
            foreach (string account in accounts) OfflineSaveWatermark.ValidateBeforeOpen(Path.Combine(root, "state"), account);
        }
        var catalog = new LocalProfileStore(root).Load();
        // Password changes deliberately retain the old credential archive. A current
        // matching credential still makes that account openable; keep its history too.
        if (catalog.Warnings.Any(p => !p.StartsWith("CONFLICTING_ARCHIVED_CREDENTIALS:", StringComparison.Ordinal))
            || catalog.Characters.Length == 0 || catalog.Characters.Any(p => !p.CanOpen))
            throw new InvalidDataException("Backup profiles and saved accounts are incomplete or inconsistent.");
    }
}
