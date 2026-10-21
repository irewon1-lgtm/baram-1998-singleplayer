using Server;

namespace P1998.Embedded;

/// <summary>Presentation-only shortest-time route. Original TurnAsync/StepAsync remains
/// authoritative for movement, warps, doors, occupancy and quest restrictions.
/// Each movement step costs one action; changing facing costs another action.
/// Search never treats unknown map cells as walkable or a warp as a shortcut
/// through another map.</summary>
public static class ClientNavigation
{
    // Four possible facing states per cell. 300,000 covers a complete 256x256
    // map while bounding pathological or incorrectly decoded source worlds.
    public const int MaximumVisitedStates = 300_000;
    private readonly record struct State(int X, int Y, int Facing);
    public sealed record PlanResult(Route? Route, string Reason);

    /// <summary>Immutable route and source terrain identity. Dynamic occupants are
    /// checked again immediately before dispatching each original movement step.</summary>
    public sealed class Route
    {
        private readonly Dictionary<(int X, int Y), ModelCell> _terrain;
        internal Route(ClientSceneSnapshot scene, Dictionary<(int X, int Y), ModelCell> terrain, int[] directions)
        {
            Map = scene.Map; Terrain = scene.Cells; _terrain = terrain;
            Directions = directions;
            Positions = new (int X, int Y)[directions.Length + 1];
            Positions[0] = (scene.X, scene.Y);
            for (int i = 0; i < directions.Length; i++)
            {
                var (dx, dy) = Delta(directions[i]);
                Positions[i + 1] = (Positions[i].X + dx, Positions[i].Y + dy);
            }
        }
        public int Map { get; }
        public ModelTerrainSnapshot Terrain { get; }
        public int[] Directions { get; }
        public (int X, int Y)[] Positions { get; }
        public bool CanAdvance(ClientSceneSnapshot scene, int index)
        {
            if (index < 0 || index >= Directions.Length || Map != scene.Map
                || !ReferenceEquals(Terrain, scene.Cells)
                || Positions[index] != (scene.X, scene.Y)) return false;
            var occupied = Occupants(scene);
            return Open(scene.Map, Positions[index + 1], Directions[index], Positions[^1], _terrain, occupied);
        }
    }

    private static (int X, int Y) Delta(int direction) => direction switch
    {
        0 => (0, -1), 1 => (1, 0), 2 => (0, 1), 3 => (-1, 0),
        _ => throw new ArgumentOutOfRangeException(nameof(direction))
    };

    private static HashSet<(int X, int Y)> Occupants(ClientSceneSnapshot scene)
        => scene.Creatures.Select(c => (c.X, c.Y))
            .Concat(scene.Players.Where(p => p.Id != scene.SelfId).Select(p => (p.X, p.Y)))
            .ToHashSet();

    private static bool Open(int map, (int X, int Y) next, int direction, (int X, int Y) goal,
        Dictionary<(int X, int Y), ModelCell> cells, HashSet<(int X, int Y)> occupied)
    {
        if (!cells.TryGetValue(next, out var cell)) return false;
        bool warp = map is >= 0 and <= ushort.MaxValue
            && next.X is >= 0 and <= ushort.MaxValue && next.Y is >= 0 and <= ushort.MaxValue
            && Content.TryWarp((ushort)map, (ushort)next.X, (ushort)next.Y, out _);
        if (warp) return next == goal; // entering a warp changes maps; never route through one
        return !occupied.Contains(next) && (cell.Ground >> 14) == 0
            && !ObjectFlags.Blocks(cell.Object, direction);
    }

    public static PlanResult Plan(ClientSceneSnapshot scene, int targetX, int targetY, Func<bool>? cancelled = null)
    {
        if (!scene.EntryComplete || scene.Width <= 0 || scene.Height <= 0)
            return new(null, "지도가 아직 준비되지 않았습니다.");
        if (targetX < 0 || targetY < 0 || targetX >= scene.Width || targetY >= scene.Height)
            return new(null, "지도 밖의 위치입니다.");
        if (targetX == scene.X && targetY == scene.Y)
            return new(null, "이미 그 위치에 있습니다.");
        if (scene.Direction is < 0 or > 3)
            return new(null, "캐릭터 방향을 확인할 수 없습니다.");

        var cells = scene.Cells.ToDictionary(c => (c.X, c.Y));
        if (!cells.ContainsKey((targetX, targetY)))
            return new(null, "목적지 지형을 아직 받지 못했습니다.");
        var occupied = Occupants(scene);
        var goal = (X: targetX, Y: targetY);
        var initial = new State(scene.X, scene.Y, scene.Direction);
        var cost = new Dictionary<State, int> { [initial] = 0 };
        var previous = new Dictionary<State, State>();
        // Stable tie-breaking keeps equally fast routes deterministic, important
        // when older saves and synthetic probes expect the same doorway approach.
        var queue = new PriorityQueue<State, (int F, long Order)>();
        long order = 0;
        queue.Enqueue(initial, (Math.Abs(scene.X - targetX) + Math.Abs(scene.Y - targetY), order++));
        int visited = 0;
        while (queue.TryDequeue(out var current, out var priority))
        {
            // A new tap invalidates the old route. Do not let stale, large-map
            // planning tasks keep consuming CPU after the user has retargeted.
            if ((visited & 63) == 0 && cancelled?.Invoke() == true)
                return new(null, "이전 길찾기가 취소되었습니다.");
            int best = cost[current];
            if (priority.F != best + Math.Abs(current.X - targetX) + Math.Abs(current.Y - targetY)) continue;
            if (++visited > MaximumVisitedStates)
                return new(null, "지도가 너무 커 길찾기 탐색 범위를 초과했습니다.");
            if (current.X == targetX && current.Y == targetY)
            {
                var path = new List<int>();
                while (previous.TryGetValue(current, out var prior))
                {
                    path.Add(current.Facing); current = prior;
                }
                path.Reverse();
                return new(new Route(scene, cells, path.ToArray()), "");
            }
            for (int direction = 0; direction < 4; direction++)
            {
                var (dx, dy) = Delta(direction);
                var next = (X: current.X + dx, Y: current.Y + dy);
                if (next.X < 0 || next.Y < 0 || next.X >= scene.Width || next.Y >= scene.Height
                    || !Open(scene.Map, next, direction, goal, cells, occupied)) continue;
                var state = new State(next.X, next.Y, direction);
                int proposed = best + 1 + (current.Facing == direction ? 0 : 1);
                if (cost.TryGetValue(state, out int known) && proposed >= known) continue;
                cost[state] = proposed; previous[state] = current;
                queue.Enqueue(state, (proposed + Math.Abs(next.X - targetX) + Math.Abs(next.Y - targetY), order++));
            }
        }
        return new(null, "벽·장애물·출입구 때문에 이동 경로가 없습니다.");
    }

    // Historical test probe compatibility. Actual tap movement uses the cached
    // complete Route rather than repeatedly reconstructing a map every step.
    public static int? NextDirection(ClientSceneSnapshot scene, int targetX, int targetY)
    {
        var route = Plan(scene, targetX, targetY).Route;
        return route is not null && route.Directions.Length > 0 ? route.Directions[0] : null;
    }
}
