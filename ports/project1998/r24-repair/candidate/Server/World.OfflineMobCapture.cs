using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Shared;

namespace Server;

public sealed partial class World
{
    // Exact value comparison, never a collision-prone hash or viewport generation. Nested mutable
    // collections take the original full serialization path. The contract guard disables reuse if
    // Mob gains any new serialized member, so a future change cannot silently omit durable state.
    private const int OfflineMobCacheLimit = 4096;
    private readonly Dictionary<uint, OfflineMobCapture> _offlineMobCache = new();
    private readonly HashSet<uint> _offlineMobSeen = new();
    private int _offlineMobSerialized, _offlineMobReused;
    private sealed record OfflineMobCapture(MobValues Values, byte[] Data);
    private readonly record struct MobValues(
        uint Id,
        string Name,
        string Key,
        int DefId,
        uint HarvestClaimBy,
        long HarvestClaimUntil,
        ushort Sprite,
        byte Extra,
        byte Color,
        ushort X,
        ushort Y,
        byte Dir,
        int Hp,
        int MaxHp,
        int Exp,
        bool IsNpc,
        int NpcDefId,
        ushort HomeX,
        ushort HomeY,
        bool Wander,
        int Leash,
        int MoveTime,
        int MoveTimer,
        long FrozenUntil,
        long PoisonUntil,
        long PoisonNextTick,
        int PoisonTickDam,
        uint PoisonOwnerId,
        uint OwnerId,
        long PetExpiresAt,
        bool Summoned,
        bool WorldSpawned,
        long BlindUntil,
        double DamageAmp,
        long DamageAmpUntil,
        long FxRepeatUntil,
        long FxRepeatNext,
        int FxRepeatEvery,
        int FxRepeatAnim,
        int FxRepeatSound,
        uint TargetId,
        uint AmnesiaBy,
        long AmnesiaUntil,
        long SpellReadyAt,
        long LastStandUntil,
        bool SecondWindUsed,
        long ParaBreakAt,
        long CurseShrugAt,
        bool Returning,
        uint TargetMobId,
        bool Aggressive,
        bool Flees,
        long PanicUntil,
        byte SutePhase,
        long SutePhaseUntil,
        int SuteSwingsLeft,
        int SuteRetreatLeft,
        long SuteHealReadyAt,
        bool SuteCornered,
        long SuteRetaliateLockedUntil,
        byte SuteBeat,
        int Level,
        int AttackTime,
        int AttackTimer,
        int BaseAttackTime,
        int MinDam,
        int MaxDam,
        int Hit,
        bool IsBoss,
        int Grace,
        int Will,
        int Protection,
        int Ac);
    private static MobValues ReadMobValues(Mob m) => new(m.Id, m.Name, m.Key, m.DefId, m.HarvestClaimBy, m.HarvestClaimUntil, m.Sprite, m.Extra, m.Color, m.X, m.Y, m.Dir, m.Hp, m.MaxHp, m.Exp, m.IsNpc, m.NpcDefId, m.HomeX, m.HomeY, m.Wander, m.Leash, m.MoveTime, m.MoveTimer, m.FrozenUntil, m.PoisonUntil, m.PoisonNextTick, m.PoisonTickDam, m.PoisonOwnerId, m.OwnerId, m.PetExpiresAt, m.Summoned, m.WorldSpawned, m.BlindUntil, m.DamageAmp, m.DamageAmpUntil, m.FxRepeatUntil, m.FxRepeatNext, m.FxRepeatEvery, m.FxRepeatAnim, m.FxRepeatSound, m.TargetId, m.AmnesiaBy, m.AmnesiaUntil, m.SpellReadyAt, m.LastStandUntil, m.SecondWindUsed, m.ParaBreakAt, m.CurseShrugAt, m.Returning, m.TargetMobId, m.Aggressive, m.Flees, m.PanicUntil, m.SutePhase, m.SutePhaseUntil, m.SuteSwingsLeft, m.SuteRetreatLeft, m.SuteHealReadyAt, m.SuteCornered, m.SuteRetaliateLockedUntil, m.SuteBeat, m.Level, m.AttackTime, m.AttackTimer, m.BaseAttackTime, m.MinDam, m.MaxDam, m.Hit, m.IsBoss, m.Grace, m.Will, m.Protection, m.Ac);
    private static readonly bool MobCaptureContractMatches = CheckMobCaptureContract();
    private static bool CheckMobCaptureContract()
    {
        var expected = new HashSet<string> { nameof(Mob.Id), nameof(Mob.Name), nameof(Mob.Key), nameof(Mob.DefId), nameof(Mob.HarvestClaimBy), nameof(Mob.HarvestClaimUntil), nameof(Mob.Sprite), nameof(Mob.Extra), nameof(Mob.Color), nameof(Mob.X), nameof(Mob.Y), nameof(Mob.Dir), nameof(Mob.Hp), nameof(Mob.MaxHp), nameof(Mob.Exp), nameof(Mob.IsNpc), nameof(Mob.NpcDefId), nameof(Mob.HomeX), nameof(Mob.HomeY), nameof(Mob.Wander), nameof(Mob.Leash), nameof(Mob.MoveTime), nameof(Mob.MoveTimer), nameof(Mob.FrozenUntil), nameof(Mob.PoisonUntil), nameof(Mob.PoisonNextTick), nameof(Mob.PoisonTickDam), nameof(Mob.PoisonOwnerId), nameof(Mob.OwnerId), nameof(Mob.PetExpiresAt), nameof(Mob.Summoned), nameof(Mob.WorldSpawned), nameof(Mob.BlindUntil), nameof(Mob.DamageAmp), nameof(Mob.DamageAmpUntil), nameof(Mob.FxRepeatUntil), nameof(Mob.FxRepeatNext), nameof(Mob.FxRepeatEvery), nameof(Mob.FxRepeatAnim), nameof(Mob.FxRepeatSound), nameof(Mob.TargetId), nameof(Mob.AmnesiaBy), nameof(Mob.AmnesiaUntil), nameof(Mob.SpellReadyAt), nameof(Mob.LastStandUntil), nameof(Mob.SecondWindUsed), nameof(Mob.ParaBreakAt), nameof(Mob.CurseShrugAt), nameof(Mob.Returning), nameof(Mob.TargetMobId), nameof(Mob.Aggressive), nameof(Mob.Flees), nameof(Mob.PanicUntil), nameof(Mob.SutePhase), nameof(Mob.SutePhaseUntil), nameof(Mob.SuteSwingsLeft), nameof(Mob.SuteRetreatLeft), nameof(Mob.SuteHealReadyAt), nameof(Mob.SuteCornered), nameof(Mob.SuteRetaliateLockedUntil), nameof(Mob.SuteBeat), nameof(Mob.Level), nameof(Mob.AttackTime), nameof(Mob.AttackTimer), nameof(Mob.BaseAttackTime), nameof(Mob.MinDam), nameof(Mob.MaxDam), nameof(Mob.Hit), nameof(Mob.IsBoss), nameof(Mob.Grace), nameof(Mob.Will), nameof(Mob.Protection), nameof(Mob.Ac), nameof(Mob.Alive), nameof(Mob.Handed), nameof(Mob.Statuses), nameof(Mob.Threat), nameof(Mob.Buffs) };
        var actual = typeof(Mob).GetFields(BindingFlags.Public | BindingFlags.Instance).Select(f => f.Name)
            .Concat(typeof(Mob).GetProperties(BindingFlags.Public | BindingFlags.Instance).Where(p => p.GetMethod is not null).Select(p => p.Name));
        return expected.SetEquals(actual);
    }
    private void BeginOfflineMobCapture()
    {
        Debug.Assert(HoldsWorldLock);
        _offlineMobSeen.Clear(); _offlineMobSerialized = _offlineMobReused = 0;
    }
    private byte[] CaptureOfflineMob(Mob mob)
    {
        bool reusable = MobCaptureContractMatches && mob.Handed is null && mob.Statuses is null
            && mob.Threat is null && mob.Buffs is null;
        if (reusable)
        {
            var values = ReadMobValues(mob);
            _offlineMobSeen.Add(mob.Id);
            if (_offlineMobCache.TryGetValue(mob.Id, out var previous) && previous.Values.Equals(values))
            { _offlineMobReused++; return previous.Data; }
            var data = JsonSerializer.SerializeToUtf8Bytes(mob, CreatureJson);
            _offlineMobSerialized++;
            if (_offlineMobCache.Count < OfflineMobCacheLimit || _offlineMobCache.ContainsKey(mob.Id))
                _offlineMobCache[mob.Id] = new(values, data);
            return data;
        }
        _offlineMobCache.Remove(mob.Id);
        _offlineMobSerialized++;
        return JsonSerializer.SerializeToUtf8Bytes(mob, CreatureJson);
    }
    private void EndOfflineMobCapture()
    {
        foreach (uint id in _offlineMobCache.Keys.Where(id => !_offlineMobSeen.Contains(id)).ToArray())
            _offlineMobCache.Remove(id);
    }
}
