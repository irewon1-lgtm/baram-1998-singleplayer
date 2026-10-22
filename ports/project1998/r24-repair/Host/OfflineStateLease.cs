namespace P1998.Embedded;

/// <summary>One process owns an offline state root until its final save and teardown settle.
/// The lease file is outside the state directory so an inactive backup restore can replace
/// that directory without dropping the lock. The empty file is retained; OS handle lifetime,
/// not its presence, decides ownership and automatically releases it after a process crash.</summary>
internal sealed class OfflineStateLease : IDisposable
{
    private FileStream? _file;

    private readonly string _state;
    private OfflineStateLease(FileStream file, string state) { _file = file; _state = state; }
    internal bool Owns(string state) => _file is not null && HostBootstrap.SamePath(_state, state);

    internal static OfflineStateLease Acquire(string stateDirectory)
    {
        string state = HostBootstrap.Normalize(stateDirectory);
        string parent = Path.GetDirectoryName(state)
            ?? throw new ArgumentException("An offline state root requires a parent directory.", nameof(stateDirectory));
        Directory.CreateDirectory(parent);
        string path = Path.Combine(parent, "." + Path.GetFileName(state) + ".offline.lock");
        try
        {
            // FileShare.None is backed by an OS advisory lock on Unix and exclusive sharing
            // on Windows. Every embedded play/backup owner must acquire this same lease.
            return new OfflineStateLease(new FileStream(path, FileMode.OpenOrCreate,
                FileAccess.ReadWrite, FileShare.None), state);
        }
        catch (IOException error)
        {
            throw new IOException("Another offline world or backup operation owns this save directory. "
                + "Existing saves were preserved; close that operation before retrying.", error);
        }
    }

    public void Dispose() => Interlocked.Exchange(ref _file, null)?.Dispose();
}
