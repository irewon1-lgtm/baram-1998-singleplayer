using Shared;

namespace Server;

public sealed partial class Session
{
    public sealed record P6Pose(long sequence, uint entity, int type, ushort time);
    public readonly List<P6Pose> P6Poses = new();
    private long _p6PoseSequence;
    private void P6ObserveAction(uint id, ActionType type, ushort time)
    {
        P6Poses.Add(new(++_p6PoseSequence, id, (byte)type, time));
        if (P6Poses.Count > 64) P6Poses.RemoveAt(0);
    }

    public object P6Stats() => WithState(() =>
    {
        var e = Totals();
        uint next = Content.ExpToNext(CharBasePathId, _char.Level);
        return (object)new { max_hp = Math.Max(1, (int)_char.MaxHp + e.hp), max_mp = Math.Max(0, (int)_char.MaxMp + e.mp),
            might = Math.Clamp(_char.Might + e.might, 0, 255), will = Math.Clamp(_char.Will + e.will, 0, 255),
            grace = Math.Clamp(_char.Grace + e.grace, 0, 255), ac = _char.Ac + e.armor,
            hit = _char.Hit + e.hit, dam = _char.Dam + e.dam, tnl = next > _char.Exp ? next - _char.Exp : 0 };
    });

    // Explicit user-authorized offline choice. No rewards are synthesized.
    // The caller commits character+world once, using the existing checkpoint.
    public bool P6SkipTutorial() => WithState(() =>
    {
        if (_char.Map is < 4711 or > 4718 || P4Dialog is not null) return false;
        if (!Content.TryMap(0, out _)) return false;
        _char.Quests["newbie_area_quest"] = Math.Max(10, P4Stage);
        Warp(0, 87, 147); // original Warps.csv #589: Kugnae tutor-home exit into town
        P4Message = "초보자 수련을 건너뛰고 국내성에 도착했습니다.";
        return true;
    });
}
