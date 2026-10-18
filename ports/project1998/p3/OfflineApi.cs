// Private build overlay: compiled WITH the pinned Server sources, never changes
// their rule bodies. The original desktop oracle uses reflection instead.
using Shared;

namespace Server;

public sealed partial class Session
{
    public int P3Give(int id, int amount) => WithState(() =>
        GivePlaced(Content.ItemById(id) ?? throw new ArgumentException("Unknown item"), amount));

    public void P3Use(byte slot, bool eat) => WithState(() =>
        HandleUseItem(new[] { checked((byte)(slot + 1)) }, eat));

    public bool P3Move(int dir) => WithState(() =>
    {
        if (dir is < 0 or > 3) return false;
        int[] dx = { 0, 1, 0, -1 }, dy = { -1, 0, 1, 0 };
        int x = _char.X + dx[dir], y = _char.Y + dy[dir];
        var map = MapData.For(_char.Map, _char.MapXs, _char.MapYs)
            ?? throw new InvalidOperationException("P3 terrain missing");
        _char.Dir = (byte)dir;
        bool blocked = x < 0 || y < 0 || x >= map.Xs || y >= map.Ys || map.BlockedMove(x, y, dir);
        return _world.TryMovePlayer(this, _char.Map, x, y, false, true, blocked, out _);
    });
}
