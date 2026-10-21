using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;

/// <summary>Measures actual foreground render-callback intervals. Godot's game delta may be
/// smoothed or clamped and is deliberately not an input. This sampler never changes game timing.</summary>
public sealed class MonotonicFrameMetrics
{
    public const int MeasurementSeconds = 31;
    public const string ClockSource = "STOPWATCH_MONOTONIC_CALLBACK_INTERVALS";
    private readonly long _frequency, _limitTicks, _quarterTicks, _minimumWindowTicks;
    private readonly Queue<(long Tick, double Value)> _frames = new(), _rolling = new();
    public long TotalFrames { get; private set; }
    public long SessionLongFrames { get; private set; }
    public double SessionMaximumMilliseconds { get; private set; }
    public double SessionMinimumRollingFps { get; private set; } = double.PositiveInfinity;
    private readonly Queue<long> _window = new();
    private long? _lastTimestamp;
    private long _activeTicks, _windowTicks, _nextSampleTicks;

    public MonotonicFrameMetrics() : this(Stopwatch.Frequency) { }
    public MonotonicFrameMetrics(long timestampFrequency)
    {
        if (timestampFrequency < 4 || timestampFrequency > long.MaxValue / MeasurementSeconds)
            throw new ArgumentOutOfRangeException(nameof(timestampFrequency));
        _frequency = timestampFrequency;
        _limitTicks = timestampFrequency * MeasurementSeconds;
        _quarterTicks = Math.Max(1, timestampFrequency / 4);
        // Ceiling makes the existing >=950ms window rule exact at any timer frequency.
        _minimumWindowTicks = (timestampFrequency / 100) * 95 + (timestampFrequency % 100 * 95 + 99) / 100;
    }

    public long Frequency => _frequency;
    public double ActiveSeconds => _activeTicks / (double)_frequency;
    public bool MeasurementComplete => _activeTicks >= _limitTicks;
    public IReadOnlyList<double> FramesMilliseconds => _frames.Select(x => x.Value).ToArray();
    public IReadOnlyList<double> RollingFps => _rolling.Select(x => x.Value).ToArray();
    public double MinimumRollingFps => _rolling.Count == 0 ? 0 : _rolling.Min(x => x.Value);

    public void Track(long timestamp, bool active)
    {
        if (!active) { BreakContinuity(); return; }
        if (_lastTimestamp is not { } previous) { _lastTimestamp = timestamp; return; }
        if (timestamp < previous) throw new ArgumentOutOfRangeException(nameof(timestamp), "Monotonic clock moved backwards.");
        long elapsed = timestamp - previous; _lastTimestamp = timestamp;
        if (elapsed == 0) return;
        _activeTicks = checked(_activeTicks + elapsed);
        double milliseconds = elapsed * (1000d / _frequency);
        TotalFrames++; SessionMaximumMilliseconds = Math.Max(SessionMaximumMilliseconds, milliseconds);
        if (milliseconds > 100) SessionLongFrames++;
        _frames.Enqueue((_activeTicks, milliseconds));
        while (_frames.Count > 8192 || (_frames.Count > 1 && _frames.Peek().Tick <= _activeTicks - _limitTicks)) _frames.Dequeue();
        _window.Enqueue(elapsed); _windowTicks = checked(_windowTicks + elapsed);
        while (_window.Count > 1 && _windowTicks - _window.Peek() >= _frequency)
            _windowTicks -= _window.Dequeue();
        if (_activeTicks >= _nextSampleTicks)
        {
            if (_windowTicks >= _minimumWindowTicks)
            {
                double fps = _window.Count * (double)_frequency / _windowTicks;
                _rolling.Enqueue((_activeTicks, fps));
                SessionMinimumRollingFps = Math.Min(SessionMinimumRollingFps, fps);
            }
            while (_rolling.Count > 128 || (_rolling.Count > 1 && _rolling.Peek().Tick <= _activeTicks - _limitTicks)) _rolling.Dequeue();
            _nextSampleTicks = checked(_activeTicks + _quarterTicks);
        }
    }

    /// <summary>Call immediately on pause AND resume notifications, as a suspended app may
    /// receive no callbacks while inactive. Otherwise the first resumed frame counts the pause.</summary>
    public void BreakContinuity()
    {
        _lastTimestamp = null; _window.Clear(); _windowTicks = 0; _nextSampleTicks = _activeTicks;
    }

    public void Reset()
    {
        _frames.Clear(); _rolling.Clear(); _activeTicks = 0; BreakContinuity();
        TotalFrames = SessionLongFrames = 0; SessionMaximumMilliseconds = 0; SessionMinimumRollingFps = double.PositiveInfinity;
    }

    public string Status(bool rendererAvailable)
        => !MeasurementComplete ? "NOT_RUN_30_SECONDS" : !rendererAvailable ? "NOT_RUN_RENDERER"
            : _rolling.Count == 0 ? "NOT_RUN_NO_FPS_WINDOW"
            : MinimumRollingFps < 30 ? "FAIL_MEASURED_SCENE_MINIMUM_FPS" : "PASS_MEASURED_SCENE_MINIMUM_FPS";
}
