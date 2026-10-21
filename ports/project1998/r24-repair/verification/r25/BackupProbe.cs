using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using P1998.Embedded;

static class BackupProbe
{
    static string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
    static string Tables(string root)
    {
        using var cn=new SqliteConnection("Data Source="+Path.Combine(root,"state","project1998.db")+";Mode=ReadOnly");cn.Open();
        using var list=cn.CreateCommand();list.CommandText="SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name";
        var names=new List<string>();using(var r=list.ExecuteReader())while(r.Read())names.Add(r.GetString(0));
        var tables=new Dictionary<string,string[]>();
        foreach(var name in names){using var cmd=cn.CreateCommand();cmd.CommandText="SELECT * FROM \""+name.Replace("\"","\"\"")+"\"";using var r=cmd.ExecuteReader();var rows=new List<string>();while(r.Read()){var values=new object[r.FieldCount];r.GetValues(values);rows.Add(JsonSerializer.Serialize(values));}tables[name]=rows.Order().ToArray();}
        return JsonSerializer.Serialize(tables);
    }
    static Dictionary<string,string> Metadata(string root)=>Directory.GetFiles(root,"*.json",SearchOption.AllDirectories)
        .Where(p=>p.Contains(Path.DirectorySeparatorChar+"profiles"+Path.DirectorySeparatorChar)||p.Contains("offline-save-watermarks")||Path.GetFileName(p)is "g2-local-profile.json"or "local-character-selection-v1.json")
        .Order().ToDictionary(p=>Path.GetRelativePath(root,p),Hash);
    static async Task<int> Main(string[] a)
    {
        string source=a[3],outDir=a[1];Directory.CreateDirectory(outDir);var checks=new List<object>();bool failed=false;
        void Check(string name,bool ok){checks.Add(new{name,status=ok?"PASS":"FAIL"});failed|=!ok;}
        string? sourceArchive=File.Exists(source)?source:null;
        string? archiveBefore=sourceArchive is null?null:Hash(sourceArchive);
        if(sourceArchive is not null){source=Path.Combine(outDir,"closed-ui-source");OfflineBackupStore.RestoreNew(sourceArchive,source);}
        string before=Tables(source),meta=JsonSerializer.Serialize(Metadata(source));
        string archive=Path.Combine(outDir,"backup.zip"),restored=Path.Combine(outDir,"restored");
        OfflineBackupStore.Create(source,archive);OfflineBackupStore.RestoreNew(archive,restored);
        Check("all_sqlite_tables_roundtrip",Tables(restored)==before);Check("profiles_selection_and_save_witnesses_roundtrip",JsonSerializer.Serialize(Metadata(restored))==meta);
        bool refused=false;try{OfflineBackupStore.RestoreNew(archive,restored);}catch(IOException){refused=true;}
        Check("restore_refuses_existing_directory_without_changes",refused&&Tables(restored)==before);
        var profiles=new LocalProfileStore(restored);var catalog=profiles.Load();var profile=profiles.Get(catalog.SelectedId!);
        var play=await PlaySession.OpenAsync(new(Path.Combine(restored,"state"),a[0],profile.Id,profile.Password,profile.Name,false,false));
        Check("restored_actual_play_session_opens",play.Ready&&!play.Faulted);await play.StopAsync();
        Check("closed_source_tables_and_profiles_unchanged",Tables(source)==before&&JsonSerializer.Serialize(Metadata(source))==meta);
        if(sourceArchive is not null)Check("source_ui_backup_archive_bytes_preserved",Hash(sourceArchive)==archiveBefore);
        File.WriteAllText(a[2],JsonSerializer.Serialize(new{status=failed?"FAIL":"PASS",checks,physical_android="NOT_RUN",scope="public backup/restore/reopen on new synthetic test root only",sourceArchiveSha256=archiveBefore},new JsonSerializerOptions{WriteIndented=true}));return failed?1:0;
    }
}
