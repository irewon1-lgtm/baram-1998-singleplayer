using System.Collections;

namespace P1998.Embedded;

public sealed record HistorySnapshot<T>(T[] Recent, long TotalCount, double? SessionMaximum, int Capacity);

/// <summary>Fixed retention and one lock for writers, recent copies and cumulative observations.
/// Enumeration always uses an immutable copy; percentiles describe Recent, never the whole session.</summary>
public sealed class BoundedHistory<T> : IReadOnlyCollection<T>
{
    private readonly object _gate = new();
    private readonly T[] _ring;
    private readonly Func<T, double>? _measure;
    private int _start, _count;
    private long _total;
    private double? _maximum;
    public BoundedHistory(int capacity, Func<T, double>? measure = null)
    {
        if (capacity <= 0) throw new ArgumentOutOfRangeException(nameof(capacity));
        _ring = new T[capacity]; _measure = measure;
    }
    public int Count { get { lock (_gate) return _count; } }
    public void Add(T value)
    {
        lock (_gate)
        {
            int index = (_start + _count) % _ring.Length;
            _ring[index] = value;
            if (_count == _ring.Length) _start = (_start + 1) % _ring.Length; else _count++;
            _total++;
            if (_measure is not null)
            {
                double observation = _measure(value);
                if (double.IsFinite(observation)) _maximum = _maximum is null ? observation : Math.Max(_maximum.Value, observation);
            }
        }
    }
    public HistorySnapshot<T> Snapshot()
    {
        lock (_gate)
        {
            var recent = new T[_count];
            for (int i = 0; i < _count; i++) recent[i] = _ring[(_start + i) % _ring.Length];
            return new(recent, _total, _maximum, _ring.Length);
        }
    }
    public T[] ToArray() => Snapshot().Recent;
    public IEnumerator<T> GetEnumerator() => ((IEnumerable<T>)ToArray()).GetEnumerator();
    IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
}
