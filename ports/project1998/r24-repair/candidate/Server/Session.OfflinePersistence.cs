using System.Text.Json;
using System.Diagnostics;
using Shared;

namespace Server;

/// <summary>Committed means the captured state reached SQLite Commit, never merely FlushNow.</summary>
public sealed record OfflineSaveReceipt(bool Committed, bool NoChanges, string Reason,
    long CaptureSequence, long Revision, string? Error);

/// <summary>RollbackScope explicitly excludes world damage/doors/ground items.</summary>
public sealed record OfflineActionResult(bool Committed, OfflineSaveReceipt Receipt,
    bool CharacterRestored, string RollbackScope, string? Error, bool Cancelled = false);
public sealed record OfflineActionTiming(double StateWaitMs, double PrepareMs, double HandlerMs,
    double CaptureSerializeMs, double DatabaseMs, double TotalMs);

public sealed partial class Session
{
    private bool _offlinePersistence;
    private string? _offlineAbandoned;
    private Func<string>? _offlineCaptureExtra;
    private string? _offlineLoadedUser;
    private long _offlineRevision;
    private int _offlineActionDepth;
    private int _offlineActionThread;
    private Exception? _offlineHandlerFailure;
    private Action<OfflineActionResult>? _offlineDeferredFailure;
    private OfflineSaveReceipt _offlineReceipt = new(false, false, "not requested", 0, 0, null);
    private static readonly JsonSerializerOptions OfflineJson = new() { IncludeFields = true };
    private sealed record CommittedAppearance(Shared.RecoveredAppearance Value, long Sequence);
    private CommittedAppearance _committedAppearance = new(default, 0);
    public Shared.RecoveredAppearance CommittedRecoveredAppearance => Volatile.Read(ref _committedAppearance).Value;
    private double _captureMilliseconds, _databaseMilliseconds;
    private OfflineActionTiming _lastActionTiming = new(0, 0, 0, 0, 0, 0);
    public OfflineActionTiming LastOfflineActionTiming => Volatile.Read(ref _lastActionTiming);

    /// <summary>
    /// Enable only for the explicitly offline host. Extra state is captured under the session monitor,
    /// then committed with its character. Restoring extra state is the host's fresh-world startup task;
    /// it is deliberately not used as a generic in-place world rollback.
    /// </summary>
    public void EnableOfflinePersistence(Func<string>? captureExtra = null, Action<string>? restoreExtra = null,
        Action<OfflineActionResult>? deferredFailure = null)
    {
        _store.InitializeOfflinePersistence();
        using var held = EnterState();
        _offlinePersistence = true;
        _offlineCaptureExtra = captureExtra;
        _offlineDeferredFailure = deferredFailure;
        // Retained in the signature to make the startup responsibility explicit. Applying this callback
        // here would destroy a live world's roster; the host restores it before normal Arrival instead.
        _ = restoreExtra;
        if (_enteredWorld) LoadOfflineRuntime();
    }

    public OfflineSaveReceipt LastOfflineSaveReceipt => Volatile.Read(ref _offlineReceipt);

    /// <summary>Permanent fence for recovery: neither autosave nor teardown can publish failed live state.</summary>
    public void AbandonOfflinePersistence(string reason)
    {
        Volatile.Write(ref _offlineAbandoned, reason);
        _offlineReceipt = new(false, false, "abandon", _saveSeq, _offlineRevision, reason);
    }

    /// <summary>Force a real commit covering the snapshot at this call, including the paused clock.</summary>
    public OfflineSaveReceipt OfflineFlush(string reason = "manual")
    {
        if (!_offlinePersistence)
            return new(false, false, reason, 0, 0, "Offline persistence is not enabled.");
        CaptureAndWriteOffline(dirtyGated: false, reason, out var receipt);
        return receipt;
    }

    private void LoadOfflineRuntime()
    {
        string user = CharacterStore.Key(_char.Name);
        if (_offlineLoadedUser == user) return;
        var stored = _store.ReadOfflineSnapshot(user);
        _offlineLoadedUser = user;
        _offlineRevision = stored?.Revision ?? 0;
        _saveSeq = Math.Max(_saveSeq, stored?.CaptureSequence ?? 0);
        if (stored is not null) RestoreOfflineRuntime(stored.RuntimeJson);
    }

    private bool CaptureAndWriteOffline(bool dirtyGated, string reason)
        => CaptureAndWriteOffline(dirtyGated, reason, out _);

    private bool CaptureAndWriteOffline(bool dirtyGated, string reason, out OfflineSaveReceipt receipt)
    {
        string user, json, extra, runtime;
        Shared.RecoveredAppearance appearance;
        if (_offlineAbandoned is { } abandoned)
        {
            _offlineReceipt = receipt = new(false, false, reason, _saveSeq, _offlineRevision, "Abandoned session: " + abandoned);
            return false;
        }
        long seq;
        long captureStarted = Stopwatch.GetTimestamp();
        using (EnterState())
        {
            if (Volatile.Read(ref _replaced) != 0 || !_enteredWorld)
            {
                _offlineReceipt = receipt = new(false, false, reason, _saveSeq, _offlineRevision,
                    "Session is replaced or has not entered the world.");
                return false;
            }
            LoadOfflineRuntime();
            if (_offlineActionDepth > 0 && _offlineActionThread == Environment.CurrentManagedThreadId)
            {
                // Handler-level SaveChar/StoreSave must not commit a half-completed reward. The outer
                // action owns its commit and stages its success frames until that commit returns.
                _dirty = true;
                _offlineReceipt = receipt = new(false, false, reason, _saveSeq, _offlineRevision,
                    "Deferred to outer action; this request has not committed.");
                return true;
            }
            if (dirtyGated && !_dirty)
            {
                _offlineReceipt = receipt = new(false, true, reason, _saveSeq, _offlineRevision, null);
                return true;
            }
            _dirty = false;
            try
            {
                CaptureTimedEffects();
                json = CharacterStore.Serialize(_char);
                user = CharacterStore.Key(_char.Name);
                extra = _offlineCaptureExtra?.Invoke() ?? "{}";
                runtime = CaptureOfflineRuntime();
                appearance = CaptureRecoveredAppearance();
                seq = ++_saveSeq;
            }
            catch (Exception e)
            {
                _dirty = true;
                _offlineReceipt = receipt = new(false, false, reason, _saveSeq, _offlineRevision, e.Message);
                return false;
            }
        }
        _captureMilliseconds = Stopwatch.GetElapsedTime(captureStarted).TotalMilliseconds;
        OfflineCommitResult commit;
        lock (_writeGate)
        {
            if (_offlineAbandoned is { } fenced)
            {
                _offlineReceipt = receipt = new(false, false, reason, seq, _offlineRevision, "Abandoned session: " + fenced);
                return false;
            }
            if (seq < _writtenSeq)
            {
                _offlineReceipt = receipt = new(false, false, reason, seq, _offlineRevision,
                    "Capture was superseded; this request did not commit.");
                return false;
            }
            long databaseStarted = Stopwatch.GetTimestamp();
            commit = _store.SaveOfflineSnapshot(user, json, extra, runtime, seq, _offlineRevision);
            _databaseMilliseconds = Stopwatch.GetElapsedTime(databaseStarted).TotalMilliseconds;
            if (commit.Committed)
            {
                _offlineRevision = commit.Revision;
                _writtenSeq = seq;
                _lastSaveAtMs = Environment.TickCount64;
                Volatile.Write(ref _committedAppearance, new(appearance, seq));
            }
            _offlineReceipt = receipt = new(commit.Committed, false, reason, seq, commit.Revision, commit.Error);
        }
        if (!commit.Committed) _dirty = true;
        return commit.Committed;
    }

    /// <summary>
    /// A short, synchronous character action boundary, not a dialog lifetime. The host begins an output
    /// stage first, calls this around an actual original handler, and publishes only on commit success.
    /// Full character graph, supported live timers and dirty state roll back together on failure.
    /// World mutations require their own rollback and are NOT claimed by this narrow primitive.
    /// </summary>
    public OfflineActionResult ExecuteOfflineAction(Action body, Action<bool> publishOrDiscard, Action? beginStage = null)
    {
        ArgumentNullException.ThrowIfNull(body);
        ArgumentNullException.ThrowIfNull(publishOrDiscard);
        long actionStarted = Stopwatch.GetTimestamp();
        using var held = EnterState();
        double stateWaitMs = Stopwatch.GetElapsedTime(actionStarted).TotalMilliseconds;
        if (!_offlinePersistence || !_enteredWorld || _offlineActionDepth != 0)
        {
            publishOrDiscard(false);
            var refused = new OfflineSaveReceipt(false, false, "action", _saveSeq, _offlineRevision,
                "Offline action requires an entered, configured session with no nested action.");
            return new(false, refused, false, "character-and-supported-session-timers", refused.Error);
        }
        LoadOfflineRuntime();
        CaptureTimedEffects();
        string before = CharacterStore.Serialize(_char);
        string runtimeBefore = CaptureOfflineRuntime();
        bool dirtyBefore = _dirty;
        long actionGeneration = OfflineGeneration;
        // Host inputs and delayed mutations must acquire state BEFORE opening an output stage.
        // Otherwise a delayed writer could race the next input's stage while it waits for this monitor.
        beginStage?.Invoke();
        Exception? failure = null;
        _offlineHandlerFailure = null;
        _offlineActionThread = Environment.CurrentManagedThreadId;
        _offlineActionDepth++;
        double prepareMs = Stopwatch.GetElapsedTime(actionStarted).TotalMilliseconds - stateWaitMs;
        long handlerStarted = Stopwatch.GetTimestamp();
        try { body(); }
        catch (Exception e) { failure = e; }
        finally { _offlineActionDepth--; if (_offlineActionDepth == 0) _offlineActionThread = 0; }
        double handlerMs = Stopwatch.GetElapsedTime(handlerStarted).TotalMilliseconds;
        _captureMilliseconds = _databaseMilliseconds = 0;
        failure ??= _offlineHandlerFailure;
        if (failure is null && OfflineGeneration != actionGeneration)
            failure = new OperationCanceledException("Offline lifecycle changed before action commit.");
        OfflineSaveReceipt actionReceipt;
        bool ok;
        if (failure is null) ok = CaptureAndWriteOffline(dirtyGated: false, "action", out actionReceipt);
        else
        {
            actionReceipt = new(false, false, "action", _saveSeq, _offlineRevision, failure.Message);
            ok = false;
        }
        Volatile.Write(ref _lastActionTiming, new(stateWaitMs, prepareMs, handlerMs,
            _captureMilliseconds, _databaseMilliseconds, Stopwatch.GetElapsedTime(actionStarted).TotalMilliseconds));
        if (!ok)
        {
            _char = CharacterStore.Deserialize(before);
            ResetOfflineTimedFields();
            RestoreTimedEffects();
            RestoreOfflineRuntime(runtimeBefore);
            _dirty = dirtyBefore;
            InvalidateEquipTotals();
            publishOrDiscard(false);
            _offlineReceipt = actionReceipt;
            return new(false, actionReceipt, true, "character-and-supported-session-timers",
                actionReceipt.Error, failure is OperationCanceledException);
        }
        publishOrDiscard(true);
        return new(true, actionReceipt, false, "character-and-supported-session-timers", null);
    }

    /// <summary>Commit one post-await character mutation, or join the original input action.
    /// Never crosses an await and never claims to undo world changes.</summary>
    private void RunOfflineMutation(long generation, Action body)
    {
        using var held = EnterState();
        using var effect = EnterOfflineEffect(generation);
        if (!_offlinePersistence || (_offlineActionDepth > 0 && _offlineActionThread == Environment.CurrentManagedThreadId))
        { body(); return; }
        if (_out is not IOfflineTransactionalOutbound staged)
            throw new InvalidOperationException("Delayed offline mutation requires transactional output.");
        var result = ExecuteOfflineAction(body, staged.CompleteStage, staged.BeginStage);
        if (result.Committed) return;
        // The restored character is safe, but world rollback is not supported. Fence this world so
        // teardown/autosave cannot turn a failed action into a later successful write.
        PauseOffline();
        AbandonOfflinePersistence("Delayed action failed: " + result.Error);
        _offlineDeferredFailure?.Invoke(result);
        throw new IOException("Delayed offline action was not committed: " + result.Error);
    }

    /// <summary>Read-only diagnostic capture; it never injects a replacement character.</summary>
    public string CaptureOfflineCharacterJson()
    {
        using var held = EnterState();
        CaptureTimedEffects();
        return CharacterStore.Serialize(_char);
    }

    private void RecordOfflineHandlerFailure(Exception failure)
    {
        if (_offlinePersistence && _offlineActionDepth > 0 && _offlineActionThread == Environment.CurrentManagedThreadId)
            _offlineHandlerFailure = failure;
    }

    private sealed class OfflineRuntime
    {
        public int Policy = 1;
        public Dictionary<string, long> Aether = new();
        public long ActionWindow;
        public int ActionCount;
        public long NextActionTick;
        public long SlotArmedAt;
        public bool SlotGraceUsed;
        public double EnchantAmount = 1;
        public List<OfflineQueuedCast> QueuedCasts = new();
    }

    private sealed class OfflineQueuedCast
    {
        public byte[] Body = Array.Empty<byte>();
        public long Tick;
    }

    private string CaptureOfflineRuntime() => JsonSerializer.Serialize(new OfflineRuntime
    {
        Aether = new Dictionary<string, long>(_aether), ActionWindow = _actionWindow,
        ActionCount = _actionCount, NextActionTick = _nextActionTick, SlotArmedAt = _slotArmedAt,
        SlotGraceUsed = _slotGraceUsed, EnchantAmount = _enchantAmount,
        QueuedCasts = _queuedCasts.Select(q => new OfflineQueuedCast { Body = q.Body.ToArray(), Tick = q.Tick }).ToList(),
    }, OfflineJson);

    private void RestoreOfflineRuntime(string json)
    {
        var runtime = JsonSerializer.Deserialize<OfflineRuntime>(json, OfflineJson)
            ?? throw new InvalidDataException("Missing offline session runtime.");
        if (runtime.Policy != 1) throw new InvalidDataException("Unsupported offline session timer policy.");
        _aether.Clear();
        foreach (var entry in runtime.Aether) _aether.Add(entry.Key, entry.Value);
        _actionWindow = runtime.ActionWindow; _actionCount = runtime.ActionCount;
        _nextActionTick = runtime.NextActionTick; _slotArmedAt = runtime.SlotArmedAt;
        _slotGraceUsed = runtime.SlotGraceUsed; _enchantAmount = runtime.EnchantAmount;
        _queuedCasts.Clear();
        foreach (var queued in runtime.QueuedCasts) _queuedCasts.Enqueue((queued.Body, queued.Tick));
    }

    private void ResetOfflineTimedFields()
    {
        BuffClear(); ClearStatusFlags();
        _rageUntil = 0; _rageAmount = 1; _rageName = ""; _crRageTier = 0;
        _sancDeductUntil = 0; _sancDeduct = 1; _sancDeductName = "";
        _cunningDeductUntil = 0; _cunningDeduct = 1;
        _backstabUntil = _flankUntil = _fourWayUntil = _stealthUntil = _morphUntil = 0;
        _stealthShown = false; _stealthName = "Invisible";
        _morphLook = 0; _morphColor = 0; _morphKey = "";
    }
}
