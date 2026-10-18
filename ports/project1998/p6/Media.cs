namespace Server;

// Observe source-selected outgoing sounds without changing sound selection,
// combat, packets or saved game data. A bounded sequence survives repeated
// ReadState calls; the presentation consumer deduplicates by sequence number.
public sealed partial class Session
{
    public sealed record P6Sound(long sequence, int sound, uint entity, byte volume);
    public readonly List<P6Sound> P6Media = new();
    private long _p6MediaSequence;
    private void P6ObserveSound(int sound, uint entity, byte volume)
    {
        P6Media.Add(new(++_p6MediaSequence, sound, entity, volume));
        if (P6Media.Count > 64) P6Media.RemoveAt(0);
    }
}
