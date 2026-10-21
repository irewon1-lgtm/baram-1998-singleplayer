using System.Diagnostics;
using System.Buffers;
using System.Text;
using System.Text.Json;
using Shared;

namespace Server;

public sealed partial class World
{
    /// <summary>Population, floor-item and settled creature continuity. Optional
    /// extensions preserve existing policy1 snapshots without inventing old state.</summary>
    public sealed record OfflineState(int Policy, GameClock.State Clock, long Heartbeat, PopulationState Population,
        OfflineFloorState? Floor = null, OfflineCreatureState? Creatures = null);
    public sealed record PopulationState(MapPopulation[] Maps, DeathState[] Deaths);
    public sealed record MapPopulation(ushort Map, PointState[] Points, GroupState[] Groups, SurvivorState[] GroupSurvivors);
    public sealed record PointState(int Index, int Def, ushort X, ushort Y, bool Placed, bool Alive, long RespawnTick, ushort LiveX, ushort LiveY, uint LiveId = 0);
    public sealed record GroupState(int Index, int TimerSeconds, long NextBatchUnix, MemberState[] Members);
    public sealed record MemberState(int Def, int Cap, int AliveMapWide, int Pending);
    public sealed record SurvivorState(int Def, ushort X, ushort Y);
    public sealed record DeathState(ushort Map, string Key, long UnixSeconds);
    public sealed record OfflineCaptureMetrics(double Milliseconds, int Utf8Bytes, int MaterializedMaps,
        int RetainedMonsters, int SerializedMonsters, int ReusedMonsters, int CachedMonsters,
        int ActiveMaps, int ActiveMonsters);
    private OfflineCaptureMetrics _lastOfflineCapture = new(0, 0, 0, 0, 0, 0, 0, 0, 0);
    public OfflineCaptureMetrics LastOfflineCapture => Volatile.Read(ref _lastOfflineCapture);
    private ArrayBufferWriter<byte> _offlineJsonBuffer = new();

    /// <summary>Host calls at a settled boundary; pause/stop freezes the clock before this capture.
    /// The returned string is stored with the character and session timers in one SQLite commit.</summary>
    public string CaptureOfflineStateJson() => CaptureOfflineStateJson(null);

    /// <summary>Append host extensions directly to the same JSON writer. Never build and traverse a
    /// second mutable JSON tree containing every saved monster on every input.</summary>
    public string CaptureOfflineStateJson(Action<Utf8JsonWriter>? appendProperties)
    {
        if (OfflineClock is null) throw new InvalidOperationException("An offline clock is required");
        long started = Stopwatch.GetTimestamp();
        lock (_lock)
        {
            var clock = OfflineClock.Capture();
            var population = _spawnDirector.CapturePopulation();
            var floor = CaptureOfflineFloor(clock.ElapsedMilliseconds);
            var creatures = CaptureOfflineCreatures();
            var buffer = _offlineJsonBuffer;
            buffer.Clear();
            using (var writer = new Utf8JsonWriter(buffer))
            {
                writer.WriteStartObject();
                writer.WriteNumber(nameof(OfflineState.Policy), 1);
                writer.WritePropertyName(nameof(OfflineState.Clock)); JsonSerializer.Serialize(writer, clock);
                writer.WriteNumber(nameof(OfflineState.Heartbeat), _tick);
                writer.WritePropertyName(nameof(OfflineState.Population)); JsonSerializer.Serialize(writer, population);
                writer.WritePropertyName(nameof(OfflineState.Floor)); JsonSerializer.Serialize(writer, floor);
                writer.WritePropertyName(nameof(OfflineState.Creatures)); JsonSerializer.Serialize(writer, creatures, OfflineCreatureWriteJson);
                appendProperties?.Invoke(writer);
                writer.WriteEndObject();
            }
            string result = Encoding.UTF8.GetString(buffer.WrittenSpan);
            Volatile.Write(ref _lastOfflineCapture, new(Stopwatch.GetElapsedTime(started).TotalMilliseconds,
                buffer.WrittenCount, population.Maps.Length, creatures.Maps.Sum(m => m.Mobs.Length),
                _offlineMobSerialized, _offlineMobReused, _offlineMobCache.Count,
                _maps.Values.Count(map => map.Players.Count > 0),
                _maps.Values.Where(map => map.Players.Count > 0).Sum(map => map.Mobs.Count(m => m.Alive && !m.IsNpc))));
            // Reuse normal save buffers; a one-off oversized diagnostic/save does not pin an unbounded
            // high-water allocation for the rest of the session.
            if (buffer.Capacity > 16 * 1024 * 1024) _offlineJsonBuffer = new();
            return result;
        }
    }

    /// <summary>Restore a fresh paused world BEFORE Arrival/map materialization. A future/corrupt save
    /// fails visibly; no startup refill or empty new save is substituted.</summary>
    public void RestoreOfflineStateJson(string json)
    {
        if (OfflineClock is null || !OfflineClock.IsPaused)
            throw new InvalidOperationException("Restore needs a fresh paused offline world");
        // Only an absent extension is a legacy population-only save. Explicit
        // null is damaged new state and must not silently erase committed loot.
        using var document = JsonDocument.Parse(json);
        if (document.RootElement.TryGetProperty(nameof(OfflineState.Floor), out var floor)
            && floor.ValueKind == JsonValueKind.Null)
            throw new InvalidDataException("Explicit null offline floor state is not a legacy checkpoint.");
        if (document.RootElement.TryGetProperty(nameof(OfflineState.Creatures), out var creatures)
            && creatures.ValueKind == JsonValueKind.Null)
            throw new InvalidDataException("Explicit null offline creature state is not a legacy checkpoint.");
        var state = JsonSerializer.Deserialize<OfflineState>(json) ?? throw new InvalidDataException("Missing offline world state");
        if (state.Policy != 1 || state.Heartbeat < 0 || state.Clock.Policy != GameClock.PolicyVersion)
            throw new InvalidDataException("Unsupported offline world policy");
        lock (_lock)
        {
            if (_spawnDirector.HasMaterializedMaps || Online.Count != 0 || _maps.Values.Any(m => m.Items.Count != 0))
                throw new InvalidOperationException("Restore before Arrival, not into a running world");
            state = NormalizeLegacyMuseumPositions(state);
            state = NormalizeKnownInvalidRoomPositions(state);
            state = state with { Population = _spawnDirector.NormalizeR22HorsePopulation(state.Population) };
            _spawnDirector.ValidatePopulation(state.Population);
            ValidateOfflineFloor(state.Floor, state.Clock.ElapsedMilliseconds);
            var decoded = ValidateOfflineCreatures(state.Creatures, state.Population);
            OfflineClock.Restore(state.Clock);
            _tick = state.Heartbeat;
            _spawnDirector.RestorePopulation(state.Population);
            RestoreOfflineCreatures(state.Creatures, decoded);
            RestoreOfflineFloor(state.Floor, state.Clock.ElapsedMilliseconds);
            if (state.Creatures is not null) ClearUnknownOfflineFloorOwners();
            Clock.Sync();
        }
    }

    internal sealed partial class SpawnDirector
    {
        internal bool HasMaterializedMaps => _materialized.Count != 0;

        // R18 adds one previously missing quest producer, not a replacement roster. Older valid
        // Fox Plateau saves have zero point spawns and the same fifteen-fox batch group. Admit only
        // that exact append; every original group/member/clock and all other rosters are still checked.
        private static bool IsR18FoxPointAppend(MapPopulation saved, IReadOnlyList<Spawn> points)
            => saved.Map == 79 && saved.Points.Length == 0 && points.Count == 1
                && points[0].Def.Id == 693 && points[0].Def.Key == "nine_tailed_fox"
                && !points[0].Placed && !points[0].Rare && points[0].RespawnEvery > 0
                && points[0].MinX == 16 && points[0].MinY == 13
                && points[0].MaxX == 18 && points[0].MaxY == 16;

        internal PopulationState CapturePopulation()
        {
            Debug.Assert(world.HoldsWorldLock, LockNote);
            var maps = new List<MapPopulation>();
            foreach (ushort mapId in _materialized.Order())
            {
                var map = world.Map(mapId);
                var points = _spawns.TryGetValue(mapId, out var ps) ? ps : new List<Spawn>();
                var groups = _groups.TryGetValue(mapId, out var gs) ? gs : new List<SpawnGroup>();
                var liveCounts = map.Mobs.Where(m => m.Alive && !m.IsNpc).GroupBy(m => m.DefId).ToDictionary(g => g.Key, g => g.Count());
                var groupDefs = groups.SelectMany(g => g.Members).Select(m => m.Def.Id).ToHashSet();
                var survivors = map.Mobs.Where(m => m.Alive && m.WorldSpawned && !m.IsNpc && groupDefs.Contains(m.DefId) && !_mobSpawn.ContainsKey(m.Id))
                    .Select(m => new SurvivorState(m.DefId, m.X, m.Y)).ToArray();
                maps.Add(new MapPopulation(mapId,
                    points.Select((p, i) => new PointState(i, p.Def.Id, p.X, p.Y, p.Placed, p.Live is { Alive: true }, p.RespawnTick, p.Live?.X ?? p.X, p.Live?.Y ?? p.Y, p.Live?.Id ?? 0)).ToArray(),
                    groups.Select((g, i) => new GroupState(i, g.TimerSec, g.NextBatchUnix,
                        g.Members.Select(m => new MemberState(m.Def.Id, m.Cap, liveCounts.GetValueOrDefault(m.Def.Id),
                            Math.Max(0, m.Cap - liveCounts.GetValueOrDefault(m.Def.Id)))).ToArray())).ToArray(), survivors));
            }
            return new PopulationState(maps.ToArray(), _lastDeath.OrderBy(k => k.Key.Map).ThenBy(k => k.Key.Key)
                .Select(k => new DeathState(k.Key.Map, k.Key.Key, k.Value)).ToArray());
        }

        internal void ValidatePopulation(PopulationState state)
        {
            Debug.Assert(world.HoldsWorldLock, LockNote);
            if (state.Maps is null || state.Deaths is null || state.Maps.Select(m => m.Map).Distinct().Count() != state.Maps.Length)
                throw new InvalidDataException("Invalid population maps");
            foreach (var saved in state.Maps)
            {
                if (!Content.Maps.ContainsKey(saved.Map) || saved.Points is null || saved.Groups is null || saved.GroupSurvivors is null)
                    throw new InvalidDataException("Unknown or incomplete population map");
                var points = _spawns.TryGetValue(saved.Map, out var ps) ? ps : new List<Spawn>();
                var groups = _groups.TryGetValue(saved.Map, out var gs) ? gs : new List<SpawnGroup>();
                bool appendedFox = IsR18FoxPointAppend(saved, points);
                if ((saved.Points.Length != points.Count && !appendedFox) || saved.Groups.Length != groups.Count)
                    throw new InvalidDataException("Spawn content changed: roster length");
                for (int i = 0; i < saved.Points.Length; i++)
                {
                    var p = saved.Points[i];
                    if (p.Index != i || p.Def != points[i].Def.Id || p.RespawnTick < 0 || (p.Alive && p.RespawnTick != 0))
                        throw new InvalidDataException("Invalid fixed spawn state");
                }
                var counts = saved.GroupSurvivors.GroupBy(s => s.Def).ToDictionary(g => g.Key, g => g.Count());
                foreach (var p in saved.Points.Where(p => p.Alive)) counts[p.Def] = counts.GetValueOrDefault(p.Def) + 1;
                var groupDefs = groups.SelectMany(g => g.Members).Select(m => m.Def.Id).ToHashSet();
                if (saved.GroupSurvivors.Any(s => !groupDefs.Contains(s.Def)))
                    throw new InvalidDataException("Unknown group survivor");
                for (int i = 0; i < groups.Count; i++)
                {
                    var g = groups[i]; var s = saved.Groups[i];
                    if (s.Index != i || s.TimerSeconds != g.TimerSec || s.NextBatchUnix < 0 || s.Members is null || s.Members.Length != g.Members.Count)
                        throw new InvalidDataException("Spawn content changed: group");
                    for (int j = 0; j < g.Members.Count; j++)
                    {
                        var m = s.Members[j]; var original = g.Members[j];
                        if (m.Def != original.Def.Id || m.Cap != original.Cap || m.AliveMapWide != counts.GetValueOrDefault(m.Def)
                            || m.Pending != Math.Max(0, m.Cap - m.AliveMapWide))
                            throw new InvalidDataException("Invalid group alive/pending share");
                    }
                }
            }
            if (state.Deaths.Any(d => d.UnixSeconds < 0 || !Content.MobSpawnRules.ContainsKey(d.Key)))
                throw new InvalidDataException("Invalid spawn death clock");
        }

        internal void RestorePopulation(PopulationState state)
        {
            Debug.Assert(world.HoldsWorldLock, LockNote);
            foreach (var saved in state.Maps)
            {
                // Crucially set this BEFORE any future EnsureMaterialized call. Its refill-before-first-entry
                // path now sees restored clocks and survivors, so a pending room never starts at full cap.
                _materialized.Add(saved.Map);
                var points = _spawns.TryGetValue(saved.Map, out var ps) ? ps : new List<Spawn>();
                foreach (var p in saved.Points)
                {
                    var sp = points[p.Index];
                    sp.X = p.X; sp.Y = p.Y; sp.Placed = p.Placed; sp.RespawnTick = p.RespawnTick;
                    if (!p.Alive) continue;
                    var m = world.BuildMob(saved.Map, sp.Def, p.LiveX, p.LiveY, sp.X, sp.Y, restoring: true);
                    if (p.LiveId != 0) m.Id = p.LiveId;
                    sp.Live = m; _mobSpawn[m.Id] = sp;
                }
                if (IsR18FoxPointAppend(saved, points))
                {
                    // Do not spawn before settled creatures/IDs/owners are restored. The first active
                    // original respawn pass on this map materializes this one new authored point.
                    points[0].RespawnTick = world.SpawnNowTick + 1;
                }
                var groups = _groups.TryGetValue(saved.Map, out var gs) ? gs : new List<SpawnGroup>();
                foreach (var g in saved.Groups) groups[g.Index].NextBatchUnix = g.NextBatchUnix;
                foreach (var survivor in saved.GroupSurvivors)
                {
                    var def = groups.SelectMany(g => g.Members).First(m => m.Def.Id == survivor.Def).Def;
                    world.BuildMob(saved.Map, def, survivor.X, survivor.Y, restoring: true);
                }
            }
            _lastDeath.Clear();
            foreach (var death in state.Deaths) _lastDeath[(death.Map, death.Key)] = death.UnixSeconds;
        }

        internal void RebindRestoredCreatures(IReadOnlyDictionary<uint, Mob> restored)
        {
            Debug.Assert(world.HoldsWorldLock, LockNote);
            _mobSpawn.Clear();
            foreach (var list in _spawns.Values)
                foreach (var point in list)
                    if (point.Live is { Alive: true } previous)
                    {
                        if (!restored.TryGetValue(previous.Id, out var mob))
                            throw new InvalidDataException("Restored living spawn has no creature state.");
                        point.Live = mob; _mobSpawn[mob.Id] = point;
                    }
        }
    }
}
