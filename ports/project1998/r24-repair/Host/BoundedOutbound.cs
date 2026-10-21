using Shared;

namespace P1998.Embedded;

/// <summary>Bounded/nonblocking. The lock never calls game state, a host callback, DB or UI.</summary>
public sealed class BoundedOutbound : IPresentationOutbound, IOfflineTransactionalOutbound
{
    private readonly object _gate = new();
    public sealed record PresentationFrame(byte[] Frame, bool SystemGenerated);
    private readonly Queue<PresentationFrame> _frames = new();
    private List<PresentationFrame>? _staged;
    private bool _closed;
    private long _bytes;
    public string Remote => "embedded:singleplayer";
    public int Capacity { get; }
    public int QueueDepth { get { lock (_gate) return _frames.Count + (_staged?.Count ?? 0); } }
    public bool Closed { get { lock (_gate) return _closed; } }
    public long MaximumBytes { get; }
    public BoundedOutbound(int capacity = 2048, long maximumBytes = 4 * 1024 * 1024)
    { Capacity = capacity; MaximumBytes = maximumBytes; }
    public bool Send(byte[] frame) => Enqueue(frame, false);
    public bool SendSystemLog(byte[] frame) => Enqueue(frame, true);
    private bool Enqueue(byte[] frame, bool systemGenerated)
    {
        lock (_gate)
        {
            if (_closed || _frames.Count + (_staged?.Count ?? 0) >= Capacity || _bytes + frame.Length > MaximumBytes) return false;
            // Sender-owned memory cannot later mutate an already-enqueued wire frame.
            var copy = new PresentationFrame((byte[])frame.Clone(), systemGenerated); _bytes += copy.Frame.Length;
            if (_staged is not null) _staged.Add(copy); else _frames.Enqueue(copy);
            return true;
        }
    }
    public void BeginStage()
    {
        lock (_gate)
        {
            if (_closed || _staged is not null) throw new InvalidOperationException("Output stage unavailable.");
            _staged = new();
        }
    }
    public void CompleteStage(bool commit)
    {
        lock (_gate)
        {
            if (_staged is null) return;
            foreach (var frame in _staged)
                if (commit) _frames.Enqueue(frame); else _bytes -= frame.Frame.Length;
            _staged = null;
        }
    }
    public byte[][] Drain() => DrainPresentation().Select(p => p.Frame).ToArray();
    public PresentationFrame[] DrainPresentation()
    {
        lock (_gate)
        {
            var result = _frames.ToArray(); _frames.Clear();
            _bytes -= result.Sum(f => (long)f.Frame.Length); return result;
        }
    }
    public void Close() { lock (_gate) _closed = true; }
}
