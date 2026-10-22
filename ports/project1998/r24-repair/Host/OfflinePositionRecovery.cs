using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Server;
using Shared;

namespace P1998.Embedded;

public sealed record PositionRecoveryReceipt(string Status,string Account,string Scope,string BackupPath,string BackupSha256,
    string CharacterBeforeSha256,string CharacterAfterSha256,string NonPositionBeforeSha256,string NonPositionAfterSha256,
    string[] ChangedFields,long RevisionBefore,long RevisionAfter,int FromMap,int FromX,int FromY,int Map,int X,int Y);

/// <summary>One explicitly authorised incident, operating on the existing joined save tuple.
/// Never reconstruct a Character from a diagnostic export or touch any other account.</summary>
internal static class OfflinePositionRecovery
{
    private static readonly string[] PositionFields={"Map","MapXs","MapYs","X","Y"};
    private static string Hash(byte[] bytes)=>Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    private static string Hash(string text)=>Hash(Encoding.UTF8.GetBytes(text));
    private static byte[] Rewrite(string raw,IReadOnlyDictionary<string,int> values)
    {
        byte[] bytes=Encoding.UTF8.GetBytes(raw);var reader=new Utf8JsonReader(bytes);
        var spans=new List<(int Start,int End,string Value)>();var found=new HashSet<string>(StringComparer.Ordinal);
        while(reader.Read())
        {
            if(reader.TokenType!=JsonTokenType.PropertyName||reader.CurrentDepth!=1)continue;
            string key=reader.GetString()!;
            if(!values.TryGetValue(key,out int value))continue;
            if(!found.Add(key)||!reader.Read()||reader.TokenType!=JsonTokenType.Number||!reader.TryGetInt32(out _))
                throw new InvalidDataException("Ambiguous position field; original character was preserved.");
            spans.Add((checked((int)reader.TokenStartIndex),checked((int)reader.BytesConsumed),value.ToString(System.Globalization.CultureInfo.InvariantCulture)));
        }
        if(found.Count!=PositionFields.Length)throw new InvalidDataException("Incomplete saved position; original character was preserved.");
        using var output=new MemoryStream();int cursor=0;
        foreach(var part in spans.OrderBy(p=>p.Start))
        {output.Write(bytes,cursor,part.Start-cursor);output.Write(Encoding.UTF8.GetBytes(part.Value));cursor=part.End;}
        output.Write(bytes,cursor,bytes.Length-cursor);return output.ToArray();
    }
    internal static PositionRecoveryReceipt? TryRecover(CharacterStore store,string state,string account,OfflineStateLease lease)
    {
        if(!string.Equals(account,"totogo",StringComparison.OrdinalIgnoreCase))return null;
        if(!lease.Owns(state))throw new IOException("Position recovery requires the owned inactive save lease.");
        OfflineSaveWatermark.ValidateBeforeOpen(state,account);
        var before=store.ReadOfflineSnapshot(account);if(before is null)return null;
        using var document=JsonDocument.Parse(before.CharacterJson);var c=document.RootElement;
        if(c.GetProperty("Map").GetInt32()!=1014||c.GetProperty("X").GetInt32()!=0||c.GetProperty("Y").GetInt32()!=17||c.GetProperty("Level").GetInt32()!=17)return null;
        // Refuse unsupported/corrupt character schemas before making any recovery write.
        // Validation does not serialise or replace the original bytes.
        _ = CharacterStore.Deserialize(before.CharacterJson);
        var target=Content.Maps[330];var terrain=MapData.For(target.Id,target.Xs,target.Ys)
            ??throw new InvalidDataException("Recovery destination terrain is unavailable; save was preserved.");
        if(Enumerable.Range(0,4).Any(d=>terrain.BlockedMove(29,143,d))||Content.Npcs.Any(n=>n.Enabled&&n.Map==330&&n.X==29&&n.Y==143))
            throw new InvalidDataException("Recovery destination is blocked; save was preserved.");
        string root=Path.GetDirectoryName(Path.GetFullPath(state))!;
        string backups=Path.Combine(root,"backups");Directory.CreateDirectory(backups);
        string backup=Path.Combine(backups,"totogo-before-position-recovery-"+DateTimeOffset.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N")+".zip");
        // Existing backup implementation uses SQLite BackupDatabase, includes the live WAL,
        // verifies integrity/watermarks and flushes the finished archive before returning.
        OfflineBackupStore.CreateWithOwnedLease(root,backup,lease);
        var zero=PositionFields.ToDictionary(p=>p,_=>0,StringComparer.Ordinal);
        var position=new Dictionary<string,int>{{"Map",330},{"MapXs",target.Xs},{"MapYs",target.Ys},{"X",29},{"Y",143}};
        string repaired=Encoding.UTF8.GetString(Rewrite(before.CharacterJson,position));
        string originalOther=Hash(Rewrite(before.CharacterJson,zero)),repairedOther=Hash(Rewrite(repaired,zero));
        if(originalOther!=repairedOther)throw new InvalidDataException("Non-position bytes differ; recovery refused.");
        var commit=store.SaveOfflineSnapshot(account,repaired,before.ExtraJson,before.RuntimeJson,checked(before.CaptureSequence+1),before.Revision);
        if(!commit.Committed)throw new IOException("Position recovery did not commit; original data and backup preserved: "+commit.Error);
        var after=store.ReadOfflineSnapshot(account);
        if(after is null||after.CharacterJson!=repaired||after.ExtraJson!=before.ExtraJson||after.RuntimeJson!=before.RuntimeJson||after.Revision!=commit.Revision)
            throw new IOException("Recovery commit readback failed; stop and preserve the backup.");
        var witness=new OfflineSaveReceipt(true,false,"position-only-recovery",commit.CaptureSequence,commit.Revision,null);
        OfflineSaveWatermark.Record(state,account,store,witness,()=>witness);
        using var archive=File.OpenRead(backup);string archiveHash=Convert.ToHexString(SHA256.HashData(archive)).ToLowerInvariant();
        var result=new PositionRecoveryReceipt("APPLIED_AND_VERIFIED_ON_THIS_SAVE",account,"FIVE_POSITION_FIELDS_ONLY_BEFORE_NORMAL_ARRIVAL",backup,archiveHash,
            Hash(before.CharacterJson),Hash(repaired),originalOther,repairedOther,PositionFields,before.Revision,after.Revision,1014,0,17,330,29,143);
        string audit=Path.Combine(root,"position-recovery");Directory.CreateDirectory(audit);
        string final=Path.Combine(audit,"totogo-1014-0-17.json"),pending=final+".pending-"+Guid.NewGuid().ToString("N");
        byte[] receipt=JsonSerializer.SerializeToUtf8Bytes(result,new JsonSerializerOptions{WriteIndented=true});
        using(var file=new FileStream(pending,FileMode.CreateNew,FileAccess.Write,FileShare.None)){file.Write(receipt);file.Flush(true);}File.Move(pending,final,true);
        return result;
    }
}
