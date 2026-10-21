namespace Server;

/// <summary>An embedded host's pause fence interrupted work before it could start a new effect.</summary>
public sealed class OfflinePausedException : OperationCanceledException
{
    public OfflinePausedException() : base("The embedded session is paused; no new effect was admitted.") { }
}

/// <summary>Stopping is cancellation, never a synthetic NPC answer.</summary>
public sealed class OfflineStoppedException : OperationCanceledException
{
    public OfflineStoppedException() : base("The embedded session has stopped or the continuation is stale.") { }
}

public sealed partial class Session
{
    private OfflineLifecycle? _offlineLifecycle;
    private static long _nextOfflineGeneration;
    private static readonly AsyncLocal<OfflineExecution?> OfflineExecutionContext = new();
    private sealed record OfflineExecution(Session Owner, long Generation);

    /// <summary>Opt in before admission. Normal TCP sessions retain the upstream behaviour.</summary>
    public void EnableOfflineLifecycle() =>
        Interlocked.CompareExchange(ref _offlineLifecycle, new OfflineLifecycle(), null);

    public long OfflineGeneration => _offlineLifecycle?.Generation ?? 0;
    public bool OfflinePaused => _offlineLifecycle?.Paused ?? false;
    public bool OfflineStopped => _offlineLifecycle?.Stopped ?? false;
    public bool OfflineInputAllowed => _offlineLifecycle?.InputAllowed ?? true;

    /// <summary>Fence first; does not wait for the Lua gate or any session monitor.</summary>
    public void PauseOffline() => _offlineLifecycle?.Pause();
    public void ResumeOffline() => _offlineLifecycle?.Resume();

    /// <summary>Invalidate continuations and cancel a pending prompt without submitting a false/empty answer.
    /// The host subsequently settles its executor and saves; this method performs no DB or teardown work.</summary>
    public void StopOffline()
    {
        _offlineLifecycle?.Stop();
        if (_offlineLifecycle is not null)
        {
            Interlocked.Exchange(ref _dlgReply, null)?.TrySetException(new OfflineStoppedException());
            Interlocked.Exchange(ref _shopReply, null)?.TrySetException(new OfflineStoppedException());
        }
    }

    /// <summary>Wait for effects already admitted BEFORE the pause fence. Lua gate waiters are not effects,
    /// so a held gate cannot make this wait unbounded. The host also settles its own input/tick executor.</summary>
    public Task WaitForOfflineQuiescenceAsync() => _offlineLifecycle?.Quiescence ?? Task.CompletedTask;

    /// <summary>Carry the current generation through async NPC awaits. This is context, not an effect lease:
    /// a call blocked waiting for the Lua gate must never prevent pause from settling.</summary>
    internal IDisposable EnterOfflineExecution()
    {
        var previous = OfflineExecutionContext.Value;
        OfflineExecutionContext.Value = previous?.Owner == this ? previous : new OfflineExecution(this, OfflineGeneration);
        return new OfflineContextGuard(previous);
    }

    private sealed class OfflineContextGuard(OfflineExecution? previous) : IDisposable
    {
        public void Dispose() => OfflineExecutionContext.Value = previous;
    }

    internal long CaptureOfflineGeneration()
    {
        var ambient = OfflineExecutionContext.Value;
        return ambient?.Owner == this ? ambient.Generation : OfflineGeneration;
    }

    internal IDisposable EnterOfflineEffect(long generation) =>
        _offlineLifecycle?.EnterEffect(generation) ?? EmptyOfflineGuard.Instance;

    internal Task WaitForOfflineResumeAsync(long generation) =>
        _offlineLifecycle?.WaitForResume(generation) ?? Task.CompletedTask;

    // Explicit context owners cover direct host calls, while the ambient generation covers an old
    // continuation whose parent Receive has long since returned. Neither is inferred from a display name.
    internal static IDisposable EnterOfflineContextEffect(Session owner)
    {
        var ambient = OfflineExecutionContext.Value;
        return owner.EnterOfflineEffect(ambient?.Owner == owner ? ambient.Generation : owner.OfflineGeneration);
    }

    internal static IDisposable EnterOfflineLuaContextEffect(object ctx) => ctx switch
    {
        ItemContext item => EnterOfflineContextEffect(item.OfflineOwner),
        SpellContext spell => EnterOfflineContextEffect(spell.OfflineOwner),
        _ => EmptyOfflineGuard.Instance
    };

    private static void WaitForOfflineScriptGate()
    {
        var ambient = OfflineExecutionContext.Value;
        bool offline = ambient?.Owner._offlineLifecycle is not null ||
                       (_held?.Any(s => s._offlineLifecycle is not null) ?? false);
        if (!offline) { Monitor.Enter(ScriptGateLock); return; } // upstream TCP wait is unchanged
        while (true)
        {
            // This check is deliberately BEFORE the bounded wait; a held Lua gate must not keep an
            // abandoned input alive and thereby hold the host's input executor during pause/stop.
            if (ambient is not null) using (ambient.Owner.EnterOfflineEffect(ambient.Generation)) { }
            if (_held is not null)
                foreach (var session in _held)
                    if (ambient?.Owner != session && session._offlineLifecycle is not null)
                        using (session.EnterOfflineEffect(session.OfflineGeneration)) { }
            if (Monitor.TryEnter(ScriptGateLock, 10)) return;
        }
    }

    private static IDisposable[] EnterOfflineScriptEffects()
    {
        List<IDisposable>? leases = null;
        try
        {
            var ambient = OfflineExecutionContext.Value;
            if (ambient is not null)
            {
                OfflineGateBeforeAdmissionForTest?.Invoke(ambient.Owner);
                (leases ??= new()).Add(ambient.Owner.EnterOfflineEffect(ambient.Generation));
            }
            if (_held is not null)
                foreach (var session in _held)
                    if (ambient?.Owner != session && session._offlineLifecycle is not null)
                    {
                        OfflineGateBeforeAdmissionForTest?.Invoke(session);
                        (leases ??= new()).Add(session.EnterOfflineEffect(session.OfflineGeneration));
                    }
            return leases?.ToArray() ?? Array.Empty<IDisposable>();
        }
        catch
        {
            if (leases is not null) foreach (var lease in leases) lease.Dispose();
            throw;
        }
    }

    // Deterministic interleaves only. Null in the app; invoked after the Lua gate has been acquired but
    // before effect admission, so the check-versus-pause test does not rely on a scheduling sleep.
    internal static Action<Session>? OfflineGateBeforeAdmissionForTest;
    internal static Action<Session?>? OfflineGateWaitingForTest;

    private sealed class EmptyOfflineGuard : IDisposable
    {
        internal static readonly EmptyOfflineGuard Instance = new();
        public void Dispose() { }
    }

    private sealed class OfflineLifecycle
    {
        private readonly object _sync = new();
        private long _generation = Interlocked.Increment(ref _nextOfflineGeneration);
        private bool _paused, _stopped;
        private int _activeEffects;
        private TaskCompletionSource _resume = NewCompletion();
        private TaskCompletionSource? _quiet;
        private static TaskCompletionSource NewCompletion() => new(TaskCreationOptions.RunContinuationsAsynchronously);

        internal long Generation { get { lock (_sync) return _generation; } }
        internal bool Paused { get { lock (_sync) return _paused; } }
        internal bool Stopped { get { lock (_sync) return _stopped; } }
        internal bool InputAllowed { get { lock (_sync) return !_paused && !_stopped; } }
        internal Task Quiescence { get { lock (_sync) return _activeEffects == 0 ? Task.CompletedTask : (_quiet ??= NewCompletion()).Task; } }

        internal void Pause() { lock (_sync) if (!_stopped) _paused = true; }
        internal void Resume()
        {
            TaskCompletionSource? resumed = null;
            lock (_sync)
            {
                if (_stopped || !_paused) return;
                _paused = false;
                resumed = _resume;
                _resume = NewCompletion();
            }
            resumed.TrySetResult();
        }
        internal void Stop()
        {
            TaskCompletionSource stopped;
            lock (_sync)
            {
                if (_stopped) return;
                _stopped = true;
                _paused = true;
                _generation = Interlocked.Increment(ref _nextOfflineGeneration);
                stopped = _resume;
            }
            stopped.TrySetException(new OfflineStoppedException());
        }
        internal Task WaitForResume(long generation)
        {
            lock (_sync)
            {
                if (_stopped || generation != _generation) return Task.FromException(new OfflineStoppedException());
                return _paused ? _resume.Task : Task.CompletedTask;
            }
        }
        internal IDisposable EnterEffect(long generation)
        {
            lock (_sync)
            {
                if (_stopped || generation != _generation) throw new OfflineStoppedException();
                if (_paused) throw new OfflinePausedException();
                _activeEffects++;
                return new EffectLease(this);
            }
        }
        private void ExitEffect()
        {
            TaskCompletionSource? quiet = null;
            lock (_sync)
            {
                if (--_activeEffects == 0) { quiet = _quiet; _quiet = null; }
            }
            quiet?.TrySetResult();
        }
        private sealed class EffectLease(OfflineLifecycle owner) : IDisposable
        {
            private OfflineLifecycle? _owner = owner;
            public void Dispose() => Interlocked.Exchange(ref _owner, null)?.ExitEffect();
        }
    }
}
