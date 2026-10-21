using System.Diagnostics;
using System.Text.Json;
using Shared;

namespace Server;

public sealed partial class World
{
    // One settled live roster preserves ownership without duplicating a charmed
    // spawn as an extra summon. Fields retain the same restored active-clock epoch.
    // No callbacks, Lua stack or pending damage operation is serialized.
    public sealed record OfflineCreatureState(int Policy, uint NextMobId, uint NextTrapId,
        OfflineCreatureMap[] Maps, OfflinePlayerTrap[] Traps, Dictionary<uint, string>? PlayerKeys = null);
    public sealed record OfflineCreatureMap(ushort Map, OfflineCreature[] Mobs);
    public sealed record OfflineCreature(JsonElement Data, uint OwnerId, string OwnerKey,
        bool Summoned, long PetExpiresAt, long FrozenUntil, double DamageAmp,
        long DamageAmpUntil, uint AmnesiaBy, long AmnesiaUntil)
    {
        // Produced only by the original serializer while locked. Never accepted from a caller or save.
        internal byte[]? CapturedUtf8 { get; init; }
    }
    public sealed record OfflinePlayerTrap(ushort Map, uint Id, ushort X, ushort Y,
        string Kind, uint OwnerId, string OwnerKey, long ExpiresAt);
    private static readonly JsonSerializerOptions CreatureJson = new() { IncludeFields = true };
    private readonly Dictionary<uint, string> _offlineOwnerKeys = new();

    private string OwnerKey(uint id)
        => id == 0 ? "" : Online.ById(id)?.UserKey ?? _offlineOwnerKeys.GetValueOrDefault(id, "");

    private OfflineCreatureState CaptureOfflineCreatures()
    {
        Debug.Assert(HoldsWorldLock);
        BeginOfflineMobCapture();
        var maps = _maps.OrderBy(x => x.Key).Select(map => new OfflineCreatureMap(map.Key,
            map.Value.Mobs.Where(m => m.Alive && !m.IsNpc).Select(m => new OfflineCreature(
                default, m.OwnerId, OwnerKey(m.OwnerId), m.Summoned,
                m.PetExpiresAt, m.FrozenUntil, m.DamageAmp, m.DamageAmpUntil, m.AmnesiaBy, m.AmnesiaUntil) { CapturedUtf8 = CaptureOfflineMob(m) }).ToArray()))
            .Where(m => m.Mobs.Length != 0).ToArray();
        var traps = _maps.OrderBy(x => x.Key).SelectMany(map => map.Value.Traps.Where(t => t.OwnerId != 0)
            .Select(t => new OfflinePlayerTrap(map.Key, t.Id, t.X, t.Y, t.Kind, t.OwnerId, OwnerKey(t.OwnerId), t.ExpiresAt))).ToArray();
        var playerKeys = new Dictionary<uint, string>();
        void Remember(uint id)
        {
            string key = OwnerKey(id);
            if (id != 0 && key.Length != 0) playerKeys[id] = key;
        }
        foreach (var m in _maps.Values.SelectMany(map => map.Mobs).Where(m => m.Alive && !m.IsNpc))
        {
            Remember(m.OwnerId); Remember(m.PoisonOwnerId); Remember(m.HarvestClaimBy);
            Remember(m.AmnesiaBy); Remember(m.TargetId);
            if (m.Threat is not null) foreach (uint id in m.Threat.Keys) Remember(id);
        }
        foreach (var t in traps) Remember(t.OwnerId);
        foreach (var item in _maps.Values.SelectMany(map => map.Items)) Remember(item.LooterId);
        EndOfflineMobCapture();
        return new(1, _nextMobId, _nextTrapId, maps, traps, playerKeys);
    }

    private static Dictionary<uint, Mob>? ValidateOfflineCreatures(OfflineCreatureState? state, PopulationState population)
    {
        if (state is null) return null; // Exact legacy policy1 files remain readable.
        if (state.Policy != 1 || state.NextMobId < 100000 || state.NextMobId == uint.MaxValue
            || state.NextTrapId == 0 || state.NextTrapId == uint.MaxValue || state.Maps is null || state.Traps is null
            || state.Maps.Any(m => m is null || m.Mobs is null)
            || state.Maps.Select(m => m.Map).Distinct().Count() != state.Maps.Length
            || (state.PlayerKeys is not null && state.PlayerKeys.Any(p => p.Key == 0 || string.IsNullOrWhiteSpace(p.Value))))
            throw new InvalidDataException("Invalid offline creature extension.");
        var result = new Dictionary<uint, Mob>();
        foreach (var map in state.Maps)
        {
            if (!Content.Maps.TryGetValue(map.Map, out var info)) throw new InvalidDataException("Unknown creature map.");
            foreach (var saved in map.Mobs)
            {
                if (saved is null || saved.Data.ValueKind != JsonValueKind.Object || saved.OwnerKey is null
                    || (saved.OwnerId != 0 && saved.OwnerKey.Length == 0))
                    throw new InvalidDataException("Invalid creature payload or owner.");
                var m = saved.Data.Deserialize<Mob>(CreatureJson) ?? throw new InvalidDataException("Missing creature payload.");
                if (m.Id < 100000 || m.Id >= state.NextMobId || m.IsNpc || !m.Alive || m.MaxHp <= 0 || m.Hp > m.MaxHp
                    || m.X >= info.Xs || m.Y >= info.Ys || m.Name is null || m.Key is null || m.MoveTime <= 0
                    || (m.DefId != 0 && Content.MobById(m.DefId) is null) || !result.TryAdd(m.Id, m)
                    || saved.PetExpiresAt < 0 || saved.FrozenUntil < 0 || saved.DamageAmpUntil < 0 || saved.AmnesiaUntil < 0
                    || !double.IsFinite(saved.DamageAmp) || saved.DamageAmp < 0)
                    throw new InvalidDataException("Invalid living creature identity, content or state.");
                m.OwnerId = saved.OwnerId; m.Summoned = saved.Summoned; m.PetExpiresAt = saved.PetExpiresAt;
                m.FrozenUntil = saved.FrozenUntil; m.DamageAmp = saved.DamageAmp; m.DamageAmpUntil = saved.DamageAmpUntil;
                m.AmnesiaBy = saved.AmnesiaBy; m.AmnesiaUntil = saved.AmnesiaUntil;
                // System.Text.Json includes this public getter but cannot set its
                // internal setter. Preserve it explicitly, then resolve its account below.
                if (saved.Data.TryGetProperty(nameof(Mob.TargetId), out var target))
                    m.TargetId = target.GetUInt32();
            }
        }
        foreach (var map in population.Maps)
            foreach (var point in map.Points.Where(p => p.Alive))
                if (point.LiveId == 0 || !result.TryGetValue(point.LiveId, out var mob) || mob.DefId != point.Def || !mob.WorldSpawned)
                    throw new InvalidDataException("Population and living creature extension disagree.");
        var ids = new HashSet<uint>();
        foreach (var t in state.Traps)
            if (t is null || !Content.Maps.TryGetValue(t.Map, out var info) || t.Id == 0 || t.Id >= state.NextTrapId
                || !ids.Add(t.Id) || t.X >= info.Xs || t.Y >= info.Ys || t.OwnerId == 0 || string.IsNullOrEmpty(t.OwnerKey)
                || string.IsNullOrEmpty(t.Kind) || t.ExpiresAt < 0)
                throw new InvalidDataException("Invalid offline player trap.");
        return result;
    }

    private void RestoreOfflineCreatures(OfflineCreatureState? state, Dictionary<uint, Mob>? decoded)
    {
        Debug.Assert(HoldsWorldLock);
        if (state is null || decoded is null) return;
        if (state.PlayerKeys is not null)
            foreach (var player in state.PlayerKeys) _offlineOwnerKeys[player.Key] = player.Value;
        var npcs = _maps.Values.SelectMany(m => m.Mobs).Where(m => m.IsNpc).Select(m => m.Id).ToHashSet();
        if (decoded.Keys.Any(npcs.Contains)) throw new InvalidDataException("Creature entity collides with an NPC.");
        foreach (var map in _maps.Values) map.Mobs.RemoveAll(m => !m.IsNpc);
        foreach (var savedMap in state.Maps)
        {
            var map = Map(savedMap.Map);
            foreach (var saved in savedMap.Mobs)
            {
                var mob = decoded[saved.Data.GetProperty(nameof(Mob.Id)).GetUInt32()];
                map.Mobs.Add(mob);
                if (saved.OwnerId != 0) _offlineOwnerKeys[saved.OwnerId] = saved.OwnerKey;
            }
            map.ViewGen++;
        }
        _spawnDirector.RebindRestoredCreatures(decoded);
        foreach (var t in state.Traps)
        {
            var map = Map(t.Map);
            // World-owned ambush traps are rebuilt by original map materialization.
            // Player traps retain their own IDs after those independent hazards.
            if (map.Traps.Any(existing => existing.Id == t.Id))
                throw new InvalidDataException("Restored player trap id collides with an authored hazard.");
            map.Traps.Add(new Trap { Id = t.Id, X = t.X, Y = t.Y, Kind = t.Kind, OwnerId = t.OwnerId, ExpiresAt = t.ExpiresAt });
            _offlineOwnerKeys[t.OwnerId] = t.OwnerKey;
        }
        // Missing keys in older extensions or departed players must never bind
        // to an unrelated new arrival that happens to reuse the same numeric ID.
        foreach (var m in decoded.Values)
        {
            if (!_offlineOwnerKeys.ContainsKey(m.PoisonOwnerId)) m.PoisonOwnerId = 0;
            if (!_offlineOwnerKeys.ContainsKey(m.HarvestClaimBy)) { m.HarvestClaimBy = 0; m.HarvestClaimUntil = 0; }
            if (!_offlineOwnerKeys.ContainsKey(m.AmnesiaBy)) { m.AmnesiaBy = 0; m.AmnesiaUntil = 0; }
            if (!_offlineOwnerKeys.ContainsKey(m.TargetId)) m.TargetId = 0;
            if (m.TargetMobId != 0 && !decoded.ContainsKey(m.TargetMobId)) m.TargetMobId = 0;
            if (m.Threat is not null)
                foreach (uint id in m.Threat.Keys.Where(id => !_offlineOwnerKeys.ContainsKey(id)).ToArray()) m.Threat.Remove(id);
        }
        _nextMobId = state.NextMobId;
        _nextTrapId = Math.Max(_nextTrapId, state.NextTrapId);
    }

    private void ClearUnknownOfflineFloorOwners()
    {
        Debug.Assert(HoldsWorldLock);
        foreach (var item in _maps.Values.SelectMany(map => map.Items))
            if (item.LooterId != 0 && !_offlineOwnerKeys.ContainsKey(item.LooterId))
            { item.LooterId = 0; item.LockedUntil = 0; }
    }

    /// <summary>Bind the stable saved account to its new entity after original Arrival,
    /// before any active tick, pet AI, or arrival snapshot may run.</summary>
    public void BindRestoredOfflineOwner(string userKey, uint entityId)
    {
        lock (_lock)
        {
            var prior = _offlineOwnerKeys.Where(x => string.Equals(x.Value, userKey, StringComparison.OrdinalIgnoreCase)).Select(x => x.Key).ToHashSet();
            foreach (var map in _maps.Values)
            {
                foreach (var m in map.Mobs)
                {
                    if (prior.Contains(m.OwnerId)) m.OwnerId = entityId;
                    if (prior.Contains(m.PoisonOwnerId)) m.PoisonOwnerId = entityId;
                    if (prior.Contains(m.HarvestClaimBy)) m.HarvestClaimBy = entityId;
                    if (prior.Contains(m.AmnesiaBy)) m.AmnesiaBy = entityId;
                    if (prior.Contains(m.TargetId)) m.TargetId = entityId;
                    if (m.Threat is not null)
                        foreach (uint old in prior.Where(m.Threat.ContainsKey))
                        {
                            long amount = m.Threat[old]; m.Threat.Remove(old);
                            m.Threat[entityId] = Math.Max(m.Threat.GetValueOrDefault(entityId), amount);
                        }
                }
                foreach (var t in map.Traps.Where(t => prior.Contains(t.OwnerId))) t.OwnerId = entityId;
                foreach (var item in map.Items.Where(item => prior.Contains(item.LooterId))) item.LooterId = entityId;
            }
            foreach (uint old in prior) _offlineOwnerKeys.Remove(old);
            _offlineOwnerKeys[entityId] = userKey;
        }
    }
}
