using System.Buffers.Binary;
using System.Diagnostics;
using System.Net;
using System.Text;
using Protocol.Tk495;
using Server;
using Shared;

namespace P1998.Embedded;

public sealed record HostOptions(string StateDirectory, string ContentDirectory, string InternalId,
    string Password, string DisplayName, bool CreateIfMissing = false, bool AutomaticTicks = true,
    int OutputCapacity = 2048, int RetainedWireCapacity = 0, byte[]? CreationAppearance = null);
public sealed record WireObservation(string Channel, string Direction, byte Op, byte Inc, string Raw, string Decoded);
public sealed record PausedHostObservation(long GameMilliseconds, long Generation, long LifecycleVersion,
    bool Paused, bool Ready, bool Faulted, int TeardownCount, int WireCount,
    string CharacterJson, string WorldJson, OfflineSaveReceipt LastSave, OfflineStoredSnapshot? Stored);

/// <summary>One offline world, one original Session. The UI supplies input and receives immutable frames.
/// Failed mutations fence the old world permanently; recovery reconstructs the last committed world.</summary>
public sealed class EmbeddedHost
{
    private static readonly SemaphoreSlim Instance = new(1, 1);
    private static string? _processState;
    private static bool _contentLoaded;
    private readonly SemaphoreSlim _serial = new(1, 1);
    private readonly object _stopGate = new();
    private readonly object _lifecycleGate = new(); // leaf fence: never DB, executor wait or Lua
    private long _lifecycleVersion;
    private bool _resumeWanted;
    private readonly CancellationTokenSource _tickerStop = new();
    private readonly HostOptions _options;
    private readonly World _world;
    private readonly CharacterStore _store;
    private readonly Session _session;
    private readonly BoundedOutbound _out;
    private readonly List<WireObservation> _wire = new();
    private readonly object _wireGate = new(); // immutable wire copies only
    private readonly object _visitedMapGate = new(); // copied map IDs only, never Session/DB callbacks
    private readonly HashSet<ushort> _visitedMaps = new();
    private Task? _ticker, _stopTask;
    private OfflineStateLease? _stateLease;
    private byte _inputIncrement = 1;
    private bool _faulted;
    private long _lastCommitReal = Environment.TickCount64;
    public ClientModel Model { get; } = new();
    public IReadOnlyList<WireObservation> Wire { get { lock (_wireGate) return _wire.ToArray(); } }
    public bool Ready { get; private set; }
    public bool Faulted => _faulted;
    public bool Paused => _session.OfflinePaused;
    public long Generation => _session.OfflineGeneration;
    public long LifecycleVersion { get { lock (_lifecycleGate) return _lifecycleVersion; } }
    public long GameMilliseconds => _world.OfflineClock!.ElapsedMilliseconds;
    public int TeardownCount { get; private set; }
    public OfflineSaveReceipt LastSave => _session.LastOfflineSaveReceipt;
    public string CharacterJson => _session.CaptureOfflineCharacterJson();
    public RecoveredAppearance RecoveredAppearance => _session.CommittedRecoveredAppearance;
    public OfflineInventoryInspection ItemInspection => _session.CommittedInventoryInspection;
    public string WorldJson => CaptureOfflineExtra();
    public BoundedHistory<double> InputMilliseconds { get; } = new(512, value => value);
    public BoundedHistory<double> TickMilliseconds { get; } = new(512, value => value);
    public BoundedHistory<object> MapTransitions { get; } = new(64);
    public BoundedHistory<object> InputStages { get; } = new(512);
    public BoundedHistory<object> RuntimePerformance { get; } = new(128);
    private long _nextRuntimeSample;
    public BoundedHistory<object> CommitObservations { get; } = new(256);
    public double InitializationMilliseconds { get; private set; }
    public EntryDiagnostics? StartupDiagnostics { get; private set; }
    internal bool EntryEnteredWorld => _session.EmbeddedEnteredWorld;
    internal bool EntrySessionOpen => !_session.EmbeddedClosed;
    internal bool EntryOutboundOpen => !_out.Closed;

    private EmbeddedHost(HostOptions options, World world, CharacterStore store, Session session, BoundedOutbound outbound)
    { _options = options; _world = world; _store = store; _session = session; _out = outbound; }

    // The worker/state machine references beforefieldinit game classes. Configure in a
    // System-only call BEFORE asking the runtime to compile/enter that worker.
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    public static Task<EmbeddedHost> OpenAsync(HostOptions options, Action<EmbeddedHost>? prepared = null, Func<Task>? admission = null)
    {
        try
        {
            // The creation screen owns a mutable draft. Freeze its original five-byte
            // 0x04 appearance body before handing it to a worker. Existing characters
            // are never re-decoded from this draft on login.
            if (options.CreationAppearance is { } appearance)
            {
                if (appearance.Length != 5) throw new ArgumentException("Original creation appearance requires five bytes.");
                options = options with { CreationAppearance = appearance.ToArray() };
            }
            HostBootstrap.Configure(options.ContentDirectory, options.StateDirectory);
            return OpenWorkerAsync(options, prepared, admission);
        }
        catch (Exception primary)
        {
            var trace = new EntryTrace(options); trace.Mark("bootstrap_environment");
            return Task.FromException<EmbeddedHost>(new EmbeddedStartupException(trace.Capture(null, false, false, primary), primary));
        }
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static Task<EmbeddedHost> OpenWorkerAsync(HostOptions options, Action<EmbeddedHost>? prepared, Func<Task>? admission) => Task.Run(async () =>
    {
        var trace = new EntryTrace(options);
        var watch = Stopwatch.StartNew();
        EmbeddedHost? opening = null;
        bool instanceAcquired = false;
        OfflineStateLease? stateLease = null;
        try
        {
            trace.Mark("instance_admission");
            if (!Instance.Wait(0)) throw new InvalidOperationException("Only one embedded world may be active in this process.");
            instanceAcquired = true;
            trace.Mark("effective_configuration_validation");
            var requested = HostBootstrap.Requested ?? throw new InvalidOperationException("Bootstrap did not publish paths.");
            trace.ConfigurationObserved = true;
            EffectiveConfigurationGuard.Validate(requested);
            string state = requested.State;
            trace.Mark("offline_state_ownership");
            stateLease = OfflineStateLease.Acquire(state);
            trace.Mark("durable_save_watermark_validation");
            OfflineSaveWatermark.ValidateBeforeOpen(state, options.InternalId);
            if (_processState is not null && _processState != state)
                throw new InvalidOperationException("A process uses one SQLite root; run another probe process for another root.");
            _processState = state;
            Directory.CreateDirectory(state);
            trace.Mark("content_load");
            if (!_contentLoaded) { Content.Load(); _contentLoaded = true; }
            trace.Mark("offline_persistence_initialization");
            OfflineAccounts.Initialize();
            var store = new CharacterStore(Path.Combine(state, "chars"));
            store.InitializeOfflinePersistence();
            // Program.cs performs this original bootstrap for TCP; the embedded process does not run it.
            // One host owns the process here and the previous host has fully stopped before admission.
            Doors.LoadUnlocks();
            MapData.Invalidate(); // discard any failed/prior world's uncommitted process-wide map cache
            var clock = new GameClock();
            var world = new World(clock); // remains paused: no tick/refill before restore and Arrival
            trace.Mark("normal_character_creation");
            if (options.CreateIfMissing && !CharacterStore.CharacterExists(options.InternalId))
            {
                var created = OfflineAccounts.Create("g1b-v4-" + options.InternalId, options.InternalId,
                    options.Password, options.DisplayName, options.CreationAppearance ?? new byte[] { 0x29, 0, 2, 1, 0 }, world.CaptureOfflineStateJson());
                if (!created.Committed) throw new InvalidOperationException("Normal creation did not commit: " + created.Error);
            }
            trace.Mark("normal_authentication");
            if (LoginAuth.Authenticate(options.InternalId, options.Password) != LoginResult.Ok)
                throw new InvalidOperationException("Normal password/character authentication refused.");
            trace.Mark("committed_world_restore");
            var saved = store.ReadOfflineSnapshot(options.InternalId);
            string? extra = saved?.ExtraJson ?? OfflineAccounts.InitialWorld(options.InternalId);
            ushort[] restoredMapIds = Array.Empty<ushort>();
            if (extra is not null)
            {
                restoredMapIds = OfflineMapState.Restore(extra); // authored baseline exists before runtime deltas
                world.RestoreOfflineStateJson(extra); // original reader ignores the optional host extension
            }
            trace.Mark("original_session_construction");
            var outbound = new BoundedOutbound(options.OutputCapacity);
            var session = new Session(outbound, 2005, store, world); // character:null: only original Arrival may load it
            session.EnableOfflineLifecycle();
            var host = opening = new EmbeddedHost(options, world, store, session, outbound);
            host._stateLease = stateLease;
            stateLease = null; // the admitted host releases it only after final teardown
            lock (host._visitedMapGate) foreach (ushort id in restoredMapIds) host._visitedMaps.Add(id);
            session.EnableOfflinePersistence(host.CaptureOfflineExtra,
                deferredFailure: result => host.Fault("Delayed action commit failed: " + result.Error));
            trace.Mark("prepared_callback_and_lifecycle_admission");
            prepared?.Invoke(host);
            if (admission is not null) await admission();
            if (session.OfflineStopped) throw new OperationCanceledException("Stopped during initialization.");
            byte[] token = HandoffTokens.Mint(options.InternalId, IPAddress.None.ToString());
            byte[] name = Encoding.ASCII.GetBytes(options.InternalId);
            byte[] body = new byte[2 + TkCrypt.LoginKey.Length + name.Length + token.Length];
            body[0] = (byte)TkCrypt.LoginKey.Length; TkCrypt.LoginKey.CopyTo(body, 1);
            body[1 + TkCrypt.LoginKey.Length] = (byte)name.Length;
            name.CopyTo(body, 2 + TkCrypt.LoginKey.Length); token.CopyTo(body, 2 + TkCrypt.LoginKey.Length + name.Length);
            trace.Mark("original_arrival_dispatch");
            host.RecordInput(0x10, 0, body, true);
            while (true)
            {
                if (admission is not null) await admission();
                await host._serial.WaitAsync();
                try
                {
                    if (session.OfflinePaused && admission is not null) continue;
                    session.ReceiveEmbeddedFrame(TkPacket.Build(0x10, 0, body)); host.Drain(); break;
                }
                finally { host._serial.Release(); }
            }
            trace.Mark("original_arrival_acceptance");
            if (!session.EmbeddedEnteredWorld || session.EmbeddedClosed) throw new InvalidOperationException("Original Arrival rejected.");
            world.BindRestoredOfflineOwner(options.InternalId, session.PlayerId);
            trace.Mark("offline_bag_compaction");
            trace.Mark("arrival_snapshot_commit");
            var compact = session.ExecuteOfflineAction(session.CompactOfflineInventory, host._out.CompleteStage, host._out.BeginStage);
            if (!compact.Committed) throw new IOException("Bag compaction did not commit: " + compact.Error);
            host.Drain();
            lock (host._lifecycleGate) if (!session.OfflinePaused && !session.OfflineStopped) clock.Resume();
            // A real map request starts armed music. Do not equate a login SFX with BGM.
            trace.Mark("original_map_request");
            int entryMap = host.Model.Map, entryWidth = host.Model.Width, entryHeight = host.Model.Height;
            long entryGeneration = host.Generation;
            bool largeEntryMap = (long)entryWidth * entryHeight > PlaySession.MaximumMapCellsPerRequest;
            foreach (byte[] map in PlaySession.MapRequests(entryWidth, entryHeight, requestBytes: 10))
            {
                while (true)
                {
                    if (admission is not null) await admission();
                    try
                    {
                        if (largeEntryMap)
                        {
                            if (host.Model.Map != entryMap || host.Generation != entryGeneration)
                                throw new InvalidOperationException("Startup map changed during terrain loading.");
                            var mapResult = await host.ReceiveAsync(5, map, expectedGeneration: entryGeneration,
                                expectedLifecycleVersion: host.LifecycleVersion);
                            if (!mapResult.Committed)
                            {
                                if (admission is not null && host.Paused && !host.Faulted) continue;
                                throw new InvalidDataException("Startup terrain request did not commit.");
                            }
                        }
                        else await host.ReceiveAsync(5, map);
                        break;
                    }
                    catch (InvalidOperationException) when (admission is not null && host.Paused && !host.Faulted) { }
                }
            }
            trace.Mark("entry_model_validation");
            var loaded = CharacterStore.Deserialize(host.CharacterJson);
            host.Ready = host.Model.EntryComplete && host.Model.MusicTrack is not null &&
                host.Model.Inventory.Count == loaded.Inventory.Count && host.Model.Equipment.Count == loaded.Equipment.Count &&
                host.Model.Spells.Count == loaded.Spells.Count &&
                (!largeEntryMap || host.Model.Cells.Count == entryWidth * entryHeight);
            if (!host.Ready) throw new InvalidDataException("Entry/map/self/inventory/equipment/spell model is incomplete.");
            host.InitializationMilliseconds = watch.Elapsed.TotalMilliseconds;
            trace.Mark("ready");
            host.StartupDiagnostics = trace.Capture(host, _contentLoaded, true);
            host.SampleRuntimePerformance();
            if (options.AutomaticTicks) host._ticker = host.TickLoopAsync();
            return host;
        }
        catch (Exception primary)
        {
            // Capture while the failed model/session/save receipt still describe the primary failure.
            // Teardown may close the session, add frames or commit, so it must follow this capture.
            var diagnostics = trace.Capture(opening, _contentLoaded, false, primary);
            var teardownErrors = new List<Exception>();
            if (opening is not null) { try { await opening.StopAsync(); } catch (Exception error) { teardownErrors.Add(error); } }
            else if (instanceAcquired)
            {
                try { stateLease?.Dispose(); } catch (Exception error) { teardownErrors.Add(error); }
                try { Instance.Release(); } catch (Exception error) { teardownErrors.Add(error); }
            }
            diagnostics = trace.WithTeardown(diagnostics, teardownErrors);
            if (opening is not null) opening.StartupDiagnostics = diagnostics;
            throw new EmbeddedStartupException(diagnostics, primary);
        }
    });

    public Task<OfflineActionResult> ReceiveAsync(byte opcode, byte[] plaintext, byte? increment = null, long? expectedGeneration = null,
        long? expectedLifecycleVersion = null, long? expectedMapEpoch = null, OfflineItemInspection? expectedBagItem = null) => Task.Run(async () =>
    {
        long queueStarted = Stopwatch.GetTimestamp();
        await _serial.WaitAsync();
        double queueWaitMs = Stopwatch.GetElapsedTime(queueStarted).TotalMilliseconds;
        var elapsed = Stopwatch.StartNew();
        bool localWalkPresentation = false;
        long localWalkLifecycle = 0;
        try
        {
            if (expectedGeneration is not null && expectedGeneration.Value != Generation)
                throw new InvalidOperationException("Stale host generation; input refused.");
            if (expectedLifecycleVersion is not null && expectedLifecycleVersion.Value != LifecycleVersion)
                throw new InvalidOperationException("Stale application lifecycle; queued input refused.");
            if (expectedMapEpoch is not null && expectedMapEpoch != Model.MapEpoch)
                throw new InvalidOperationException("Stale map generation; queued input refused.");
            if (_faulted || _session.OfflineStopped || !_session.OfflineInputAllowed)
                throw new InvalidOperationException("Input is not admitted in the current host state.");
            byte inc = increment ?? _inputIncrement++;
            RecordInput(opcode, inc, plaintext, false);
            var frame = TkPacket.Build(opcode, inc, TkCrypt.Crypt(plaintext, inc, TkCrypt.LoginKey));
            int oldX = Model.X, oldY = Model.Y, oldMap = Model.Map;
            long oldEpoch = Model.MapEpoch;
            if (opcode is 6 or 0x32 && plaintext.Length > 0)
            {
                localWalkLifecycle = LifecycleVersion;
                localWalkPresentation = Model.BeginLocalWalkPresentation(plaintext[0] & 3);
                Model.PredictWalk(plaintext[0] & 3);
            }
            var result = _session.ExecuteOfflineAction(() => _session.ReceiveEmbeddedFrame(frame), _out.CompleteStage, _out.BeginStage, expectedBagItem);
            if (!result.Committed) Model.CancelPrediction(oldX, oldY);
            if (!result.Committed && !result.Cancelled) Fault("Action commit failed: " + result.Error);
            else if (result.Committed) _lastCommitReal = Environment.TickCount64;
            long outputStarted = Stopwatch.GetTimestamp();
            _session.AfterEmbeddedRead(); Drain();
            InputStages.Add(new { opcode, queue_wait_ms = queueWaitMs, action = _session.LastOfflineActionTiming,
                world_capture = _world.LastOfflineCapture,
                output_drain_ms = Stopwatch.GetElapsedTime(outputStarted).TotalMilliseconds, result.Committed });
            int inputDirection = plaintext.Length > 0 ? plaintext[0] & 3 : -1;
            int entryX = oldX + (inputDirection == 1 ? 1 : inputDirection == 3 ? -1 : 0);
            int entryY = oldY + (inputDirection == 2 ? 1 : inputDirection == 0 ? -1 : 0);
            bool entrance = opcode is 6 or 0x32 && oldMap is >= 0 and <= ushort.MaxValue
                && entryX is >= 0 and <= ushort.MaxValue && entryY is >= 0 and <= ushort.MaxValue
                && Content.TryWarp((ushort)oldMap, (ushort)entryX, (ushort)entryY, out _);
            if (Model.MapEpoch != oldEpoch || entrance)
                MapTransitions.Add(new { from_map = oldMap, from_x = oldX, from_y = oldY,
                    entrance_x = entryX, entrance_y = entryY, to_map = Model.Map, to_x = Model.X, to_y = Model.Y,
                    input_map_generation = oldEpoch, output_map_generation = Model.MapEpoch, lifecycle = LifecycleVersion,
                    result.Committed, original_condition_enforced = true,
                    reason = Model.CaptureScene().Events.Where(e => e.Kind is "minitext" or "chat").TakeLast(2).Select(e => e.Text).ToArray() });
            if (_out.Closed || _session.EmbeddedClosed) Fault("Original Session closed the bounded output channel.");
            SampleRuntimePerformance();
            if (localWalkPresentation)
            {
                Model.EndLocalWalkPresentation(result.Committed && !_faulted && !Paused && !_session.OfflineStopped
                    && LifecycleVersion == localWalkLifecycle);
                localWalkPresentation = false;
            }
            return result;
        }
        finally
        {
            if (localWalkPresentation) Model.EndLocalWalkPresentation(false);
            InputMilliseconds.Add(elapsed.Elapsed.TotalMilliseconds); _serial.Release();
        }
    });

    private void RecordInput(byte op, byte inc, byte[] body, bool plain)
    {
        // Arrival contains the login key/account handoff nonce. Keep its occurrence and ordering,
        // never its credential bytes; this applies equally to live Wire and failure snapshots.
        if (op == 0x10)
        {
            AppendWire(new("game", "send", op, inc, "[REDACTED_ARRIVAL_HANDOFF]", "[REDACTED_ARRIVAL_HANDOFF]"));
            return;
        }
        byte[] raw = TkPacket.Build(op, inc, plain ? body : TkCrypt.Crypt(body, inc, TkCrypt.LoginKey));
        AppendWire(new("game", "send", op, inc, Convert.ToHexString(raw).ToLowerInvariant(), Convert.ToHexString(body).ToLowerInvariant()));
    }
    private void AppendWire(WireObservation observation)
    {
        lock (_wireGate)
        {
            _wire.Add(observation);
            if (_options.RetainedWireCapacity > 0 && _wire.Count > _options.RetainedWireCapacity)
                _wire.RemoveRange(0, _wire.Count - _options.RetainedWireCapacity);
        }
    }
    private void Drain()
    {
        foreach (var output in _out.DrainPresentation())
        {
            byte[] frame = output.Frame;
            if (!TkPacket.TryParse(frame, out var packet, out _)) throw new InvalidDataException("Invalid original output frame.");
            byte[] decoded = TkCrypt.Crypt(packet.Body, packet.Increment, TkCrypt.LoginKey);
            if (packet.Opcode == 0x15)
                lock (_visitedMapGate) _visitedMaps.Add(BinaryPrimitives.ReadUInt16BigEndian(decoded));
            AppendWire(new("game", "receive", packet.Opcode, packet.Increment, Convert.ToHexString(frame).ToLowerInvariant(), Convert.ToHexString(decoded).ToLowerInvariant()));
            Model.Apply(packet.Opcode, decoded, output.SystemGenerated);
        }
        Model.SetItemInspection(ItemInspection);
    }
    private string CaptureOfflineExtra()
    {
        ushort[] maps;
        lock (_visitedMapGate) maps = _visitedMaps.Order().ToArray();
        return OfflineMapState.Capture(_world, maps);
    }
    private void SampleRuntimePerformance()
    {
        long now = Environment.TickCount64;
        if (now < _nextRuntimeSample) return;
        _nextRuntimeSample = now + 5000;
        double? cpuMs = null; long? rss = null; string? error = null;
        try
        {
            using var process = Process.GetCurrentProcess();
            cpuMs = process.TotalProcessorTime.TotalMilliseconds; rss = process.WorkingSet64;
        }
        catch (Exception failure) { error = failure.GetType().Name + ": " + failure.Message; }
        int visited;
        lock (_visitedMapGate) visited = _visitedMaps.Count;
        RuntimePerformance.Add(new { monotonic_ms = now, game_ms = GameMilliseconds, current_map = Model.Map,
            visited_maps = visited, terrain_cache = MapData.ObserveCache(), world_capture = _world.LastOfflineCapture,
            process_cpu_total_ms = cpuMs, process_rss_bytes = rss, process_metric_error = error,
            managed_bytes = GC.GetTotalMemory(false), allocated_bytes_total = GC.GetTotalAllocatedBytes(),
            gc0 = GC.CollectionCount(0), gc1 = GC.CollectionCount(1), gc2 = GC.CollectionCount(2),
            last_committed_revision = LastSave.Revision, scope = "PROCESS_COUNTERS_BOUNDED_128_SAMPLES_AT_MOST_EVERY5_SECONDS; THERMAL_NOT_MEASURED" });
    }
    private void Fault(string reason)
    {
        _faulted = true; Ready = false; RequestPause();
        _session.AbandonOfflinePersistence(reason); // no teardown/autosave can publish the failed world's state
    }
    private async Task TickLoopAsync()
    {
        using var timer = new PeriodicTimer(TimeSpan.FromMilliseconds(World.OfflineTickMilliseconds));
        try
        {
            while (await timer.WaitForNextTickAsync(_tickerStop.Token))
            {
                if (Paused || _faulted) continue;
                await _serial.WaitAsync(_tickerStop.Token);
                try
                {
                    if (Paused || _faulted || _session.OfflineStopped) continue;
                    var tickWatch = Stopwatch.StartNew();
                    _session.RunEmbeddedWork(_world.TickOffline);
                    TickMilliseconds.Add(tickWatch.Elapsed.TotalMilliseconds);
                    _session.AfterEmbeddedRead();
                    if (Environment.TickCount64 - _lastCommitReal >= 10_000)
                    {
                        var saveWatch = Stopwatch.StartNew();
                        var save = _session.OfflineFlush("periodic");
                        CommitObservations.Add(new { reason = "periodic", game_ms = GameMilliseconds, real_ms = Environment.TickCount64, latency_ms = saveWatch.Elapsed.TotalMilliseconds, save.Committed, save.Revision });
                        if (!save.Committed) Fault("Periodic commit failed: " + save.Error);
                        else _lastCommitReal = Environment.TickCount64;
                    }
                    Drain();
                    SampleRuntimePerformance();
                    if (_out.Closed) Fault("Tick output saturated.");
                }
                catch (OfflinePausedException) { /* pause won admission; the ticker remains resumable */ }
                finally { _serial.Release(); }
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception e) { Fault("Tick failed: " + e.Message); }
    }
    public void RequestPause()
    {
        lock (_lifecycleGate) { _lifecycleVersion++; _resumeWanted = false; _session.PauseOffline(); _world.OfflineClock!.Pause(); }
    }
    public void RequestStop()
    {
        lock (_lifecycleGate) { _lifecycleVersion++; _resumeWanted = false; _session.StopOffline(); _world.OfflineClock!.Pause(); Ready = false; }
    }
    public async Task<OfflineSaveReceipt> PauseAsync()
    {
        RequestPause(); // immediate admission/time fence, no UI DB wait
        await _session.WaitForOfflineQuiescenceAsync();
        return await Task.Run(async () =>
        {
            await _serial.WaitAsync();
            try
            {
                if (_session.OfflineStopped) return RefusedSave("pause", "The offline world has stopped; no later save was admitted.");
                if (!_session.EmbeddedEnteredWorld) return new OfflineSaveReceipt(false, true, "pause-before-arrival", 0, 0, "NOT_READY: clock/input fenced; no character admitted yet.");
                var saved = _session.OfflineFlush("pause");
                if (!saved.Committed) Fault("Pause commit failed: " + saved.Error); else RecordSaveWatermark(saved);
                Drain(); return saved;
            }
            finally { _serial.Release(); }
        });
    }
    public async Task ResumeAsync(long? expectedControlVersion = null)
    {
        long request;
        lock (_lifecycleGate)
        {
            if (expectedControlVersion is not null && expectedControlVersion.Value != _lifecycleVersion) return;
            request = ++_lifecycleVersion; _resumeWanted = true;
        }
        await _serial.WaitAsync();
        try
        {
            if (_faulted || _session.OfflineStopped) throw new InvalidOperationException("Recover a fresh host from committed state before resuming.");
            lock (_lifecycleGate)
            {
                if (request != _lifecycleVersion || !_resumeWanted) return;
                _world.OfflineClock!.Resume(); _session.ResumeOffline(); Ready = Model.EntryComplete;
            }
        }
        finally { _serial.Release(); }
    }
    public Task<OfflineSaveReceipt> SaveAsync() => Task.Run(async () =>
    {
        await _serial.WaitAsync();
        try
        {
            if (_session.OfflineStopped) return RefusedSave("manual", "The offline world has stopped; no later save was admitted.");
            var save = _session.OfflineFlush("manual");
            if (!save.Committed) Fault("Manual commit failed: " + save.Error); else RecordSaveWatermark(save);
            return save;
        }
        finally { _serial.Release(); }
    });
    /// <summary>Immutable evidence from a settled paused host and a fresh SQLite read transaction.
    /// This never resumes, saves, changes the character or substitutes a restored snapshot.</summary>
    public Task<PausedHostObservation> ObservePausedAsync() => Task.Run(async () =>
    {
        await _session.WaitForOfflineQuiescenceAsync();
        await _serial.WaitAsync();
        try
        {
            if (!Paused || _faulted || !_session.EmbeddedEnteredWorld || _session.OfflineStopped)
                throw new InvalidOperationException("Observation requires an entered, paused, nonfaulted live host.");
            return new PausedHostObservation(GameMilliseconds, Generation, LifecycleVersion,
                Paused, Ready, Faulted, TeardownCount, Wire.Count, CharacterJson, WorldJson,
                LastSave, _store.ReadOfflineSnapshot(_options.InternalId));
        }
        finally { _serial.Release(); }
    });
    public Task StopAsync() { RequestStop(); lock (_stopGate) return _stopTask ??= Task.Run(StopCoreAsync); }
    private async Task StopCoreAsync()
    {
        RequestStop(); _tickerStop.Cancel();
        try
        {
            await _session.WaitForOfflineQuiescenceAsync(); await _serial.WaitAsync();
            try
            {
                if (!_faulted && _session.EmbeddedEnteredWorld) { var save = _session.OfflineFlush("stop"); if (!save.Committed) Fault("Stop commit failed: " + save.Error); }
                await _session.EndEmbeddedSessionAsync(); TeardownCount++; Drain();
                if (!_faulted && _session.EmbeddedEnteredWorld) RecordSaveWatermark(_session.LastOfflineSaveReceipt);
            }
            finally { _serial.Release(); }
            if (_ticker is not null) await _ticker;
        }
        finally
        {
            try { Interlocked.Exchange(ref _stateLease, null)?.Dispose(); }
            finally { Instance.Release(); }
        }
    }
    public async Task<EmbeddedHost> RecoverAsync()
    { if (!_faulted) throw new InvalidOperationException("Recovery requires a faulted host."); await StopAsync(); return await OpenAsync(_options with { CreateIfMissing = false }); }

    private void RecordSaveWatermark(OfflineSaveReceipt receipt)
    {
        try { OfflineSaveWatermark.Record(_options.StateDirectory, _options.InternalId, _store,
            receipt, () => _session.LastOfflineSaveReceipt); }
        catch (Exception error) { Fault("Durable save watermark failed: " + error.Message); throw; }
    }

    private OfflineSaveReceipt RefusedSave(string reason, string error)
    {
        var saved = _session.LastOfflineSaveReceipt;
        return new OfflineSaveReceipt(false, false, reason, saved.CaptureSequence, saved.Revision, error);
    }
}
