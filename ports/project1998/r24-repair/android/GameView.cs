using Godot;
using P1998.Embedded;

/// <summary>Original 24px scene, driven exclusively by decoded Session output. Native action pose
/// body/head frame dispatch follows selected native 4.95 evidence. Timing and same-row
/// occlusion parity remain unverified; see evidence/r6-animation.</summary>
public partial class GameView : Control
{
    private readonly WorldCanvas _world = new();
    private Control? _clip;
    public ArtCatalog Art { get; set; } = null!;
    public int SelfHairTone { get => _world.SelfHairTone; set => _world.SelfHairTone = value; }
    public int SelfSkinTone { get => _world.SelfSkinTone; set => _world.SelfSkinTone = value; }
    public event Action<uint>? TargetPressed;
    // A short tap on empty terrain requests automatic walking to the mapped tile.
    public event Action<int, int>? DestinationPressed;
    public event Action<int>? DirectionHeld;
    public event Action? WorldTouchCanceled;
    public float FrameWidth { get; private set; } = 640;
    public ClientSceneSnapshot? Scene { get; private set; }
    public object RenderObservations() => _world.Observations();
    public int[] ObservedAttackPhases() => _world.AttackPhases.ToArray();
    public uint SelectedTarget { get => _world.Selected; set { _world.Selected = value; _world.QueueRedraw(); } }
    public bool InitializationComplete { get; private set; }
    public override void _Ready()
    {
        Size = new(FrameWidth, 480); MouseFilter = MouseFilterEnum.Ignore; TextureFilter = TextureFilterEnum.Nearest;
        _clip = new Control { Position = new(14, 14), Size = new(408 + FrameWidth - 640, 360), ClipContents = true, MouseFilter = MouseFilterEnum.Ignore }; AddChild(_clip);
        _world.Size = _clip.Size; _world.TextureFilter = TextureFilterEnum.Nearest;
        _world.MouseFilter = MouseFilterEnum.Stop; _world.Art = Art;
        _world.TargetPressed += id => TargetPressed?.Invoke(id);
        _world.DestinationPressed += (x, y) => DestinationPressed?.Invoke(x, y);
        _world.DirectionHeld += direction => DirectionHeld?.Invoke(direction);
        _world.WorldTouchCanceled += () => WorldTouchCanceled?.Invoke(); _clip.AddChild(_world);
        InitializationComplete = true;
    }
    public void ConfigureFrame(float width)
    {
        if (!float.IsFinite(width) || width < 640) throw new ArgumentOutOfRangeException(nameof(width));
        FrameWidth = width; Size = new(width, 480);
        if (_clip is not null) { _clip.Size = new(width - 232, 360); FitWorld(); }
        QueueRedraw();
    }
    public bool TryGetTile(Vector2 localPosition, out Vector2I tile)
        => _world.TryGetTile((localPosition - new Vector2(14, 14)) / _world.Scale, out tile);
    public void CancelWorldTouch() => _world.CancelWorldTouch();
    public void ResetSession() { Scene = null; _world.ResetSession(); }
    public void Present(ClientSceneSnapshot scene, long gameMilliseconds)
    {
        // Map info and original terrain rectangles arrive separately. Keep the
        // last complete frame until the new map is fully available.
        if (scene.Width <= 0 || scene.Height <= 0 || scene.Cells.Count != (long)scene.Width * scene.Height) return;
        Scene = scene; FitWorld(); _world.Present(scene, gameMilliseconds);
    }
    private void FitWorld()
    {
        if (_clip is null) return;
        // A small interior uses the available height without cropping its real
        // terrain. No cells or collision are invented outside the source map.
        float zoom = Scene is { Width: > 0, Height: > 0 } scene
            ? Math.Clamp(Math.Min(_clip.Size.X / (scene.Width * 24), _clip.Size.Y / (scene.Height * 24)), 1, 2)
            : 1;
        Vector2 scale = new(zoom, zoom), size = _clip.Size / scale;
        if (_world.Scale == scale && _world.Size == size) return;
        _world.CancelWorldTouch(); _world.Scale = scale; _world.Size = size; _world.ViewportChanged();
    }
    // Snapshot capture is deliberately less frequent than rendering. The caller supplies the
    // original host clock each frame, so animation remains smooth and freezes with that clock.
    public void AdvanceFrame(long gameMilliseconds) => _world.AdvanceFrame(gameMilliseconds);
    public override void _Draw()
    {
        if (Art is null) return;
        if (FrameWidth == 640) { Art.Ui(this, "FRAME", 0, Vector2.Zero); return; }
        Art.DrawUiSlice(this, "FRAME", 0, new Rect2(0, 0, 14, 480), new Rect2(0, 0, 14, 480));
        Art.DrawUiSlice(this, "FRAME", 0, new Rect2(14, 0, 408, 480), new Rect2(14, 0, FrameWidth - 232, 480));
        Art.DrawUiSlice(this, "FRAME", 0, new Rect2(422, 0, 218, 480), new Rect2(FrameWidth - 218, 0, 218, 480));
    }

    private partial class WorldCanvas : Control
    {
        public ArtCatalog Art { get; set; } = null!;
        public int SelfHairTone { get; set; }
        public int SelfSkinTone { get; set; }
        public event Action<uint>? TargetPressed;
        public event Action<int, int>? DestinationPressed;
        public event Action<int>? DirectionHeld;
        public event Action? WorldTouchCanceled;
        public uint Selected;
        private ClientSceneSnapshot? _scene;
        private long _time, _seen;
        private readonly Dictionary<uint, TileMotion> _walk = new();
        private readonly Dictionary<uint, (long Start, long End, int Action)> _actions = new();
        private readonly Dictionary<uint, (int Percent, long Start)> _health = new();
        private readonly Dictionary<uint, (long Start, bool Critical)> _hits = new();
        private readonly Queue<HealthObservation> _healthSamples = new();
        private sealed record HealthObservation(long GameMilliseconds, uint EntityId, int RemainingPercent, string Drawn, string Source);
        private readonly List<uint> _expired = new();
        public HashSet<int> AttackPhases { get; } = new();
        private readonly HashSet<int> _drawnEffects = new(), _drawnMaps = new();
        private readonly HashSet<(int Action, int Phase, int Body)> _drawnActions = new();
        private readonly Queue<MotionObservation> _motionSamples = new();
        private sealed record MotionObservation(long GameMilliseconds, int X, int Y, float VisibleX, float VisibleY, float CameraX, float CameraY, int Phase);
        public object Observations() => new { attack_phases_observed = AttackPhases.Order().ToArray(), action_poses_observed = _drawnActions.OrderBy(x => x.Action).ThenBy(x => x.Phase).ThenBy(x => x.Body).Select(x => new { action = x.Action, phase = x.Phase, body_frame = x.Body }).ToArray(), motion_samples = _motionSamples.ToArray(), health_feedback_observed = _healthSamples.ToArray(), effect_ids_observed = _drawnEffects.Order().ToArray(), map_ids_observed = _drawnMaps.Order().ToArray(), terrain_indexed_pieces = _terrain.Count, terrain_visible_pieces = _visibleTerrain.Count, terrain_index_rebuilds = _terrainRebuilds, terrain_visibility = "EXACT_ATLAS_RECTANGLES_SIGNED_ORIGIN_MULTIPART_STABLE_ORDER", world_view = new { native_width = Size.X, native_height = Size.Y, uniform_zoom = Scale.X, camera_x = Camera.X, camera_y = Camera.Y }, world_input = new { mode = "FLOATING_PRESS_CENTER_CARDINAL_DRAG", active_finger = _finger, direction = _stickDirection }, pose_dispatch = "SELECTED_BODY_HEAD_NATIVE_ACTIONS_0_TO_10_VERIFIED_FULL_VISUAL_NOT_RUN", camera_interpolation = "CONTINUOUS_JOINED_ACCEPTED_STEPS_SHARED_ACTOR_CAMERA_HOST_CLOCK_UI_REPEAT_CADENCE_NOT_NATIVE_TIMING_PARITY" };
        private readonly List<(uint Id, int Effect, long Start)> _effects = new();
        private readonly record struct TerrainPiece(ArtCatalog.ArtFrame Frame, Vector2 Position, int Row, bool Ground);
        private readonly record struct SceneActor(int X, int Y, bool Player, int Index);
        private readonly List<TerrainPiece> _terrain = new();
        private readonly TerrainViewportIndex _terrainIndex = new();
        private readonly List<int> _visibleTerrain = new();
        private IReadOnlyList<ModelCell>? _indexedCells;
        private int _indexedMap = -1, _indexedHeight, _terrainRebuilds;
        private void IndexTerrain(ClientSceneSnapshot scene)
        {
            if (ReferenceEquals(_indexedCells, scene.Cells) && _indexedMap == scene.Map && _indexedHeight == scene.Height) return;
            _terrain.Clear(); _terrainIndex.Clear(); _visibleTerrain.Clear();
            void Add(ArtCatalog.ArtFrame frame, ModelCell cell, bool ground)
            {
                Vector2 position = new(cell.X, cell.Y);
                _terrainIndex.Add(new Rect2(position * 24 - new Vector2(0, frame.TerrainLayer * 24) + frame.Origin, frame.Region.Size));
                _terrain.Add(new(frame, position, cell.Y, ground));
            }
            // Keep the old traversal's exact ground arrival order and stable row/X/layer order.
            foreach (var cell in scene.Cells)
                if (Art.GroundFrame(cell.Ground) is { } frame) Add(frame, cell, true);
            foreach (var cell in scene.Cells.Where(c => c.Y >= 0 && c.Y < scene.Height && c.Object != 0).OrderBy(c => c.Y).ThenBy(c => c.X))
                foreach (var frame in Art.ObjectFrames(cell.Object)) Add(frame, cell, false);
            _indexedCells = scene.Cells; _indexedMap = scene.Map; _indexedHeight = scene.Height; _terrainRebuilds++;
        }
        private int _map = -1;
        private Vector2 _camera;
        private Vector2 Camera => _camera;
        private void UpdateCamera()
        {
            if (_scene is not { } s) { _camera = Vector2.Zero; return; }
            Vector2 self = WorldPosition(s.X, s.Y, s.SelfId);
            float columns = Size.X / 24;
            float rows = Size.Y / 24;
            _camera = new(WalkPresentation.CameraAxis(self.X, (columns - 1) / 2, s.Width, columns),
                WalkPresentation.CameraAxis(self.Y, (rows - 1) / 2, s.Height, rows));
            // Atlas pixels, actors and terrain share one whole-pixel camera.
            // Fractional cell scrolling otherwise changes texel coverage at
            // every tile edge while nearest-filtered sprites are moving.
            _camera = (_camera * 24).Round() / 24;
        }
        public void ViewportChanged() { UpdateCamera(); QueueRedraw(); }
        public bool TryGetTile(Vector2 position, out Vector2I tile)
        {
            tile = default;
            if (_scene is null || position.X < 0 || position.Y < 0 || position.X >= Size.X || position.Y >= Size.Y) return false;
            Vector2 map = position / 24 + Camera;
            tile = new((int)Math.Floor(map.X), (int)Math.Floor(map.Y));
            return tile.X >= 0 && tile.Y >= 0 && tile.X < _scene.Width && tile.Y < _scene.Height;
        }
        public void ResetSession() { CancelWorldTouch(); _scene = null; _camera = Vector2.Zero; _time = _seen = 0; _map = -1; Selected = 0; _walk.Clear(); _actions.Clear(); _health.Clear(); _hits.Clear(); _healthSamples.Clear(); _effects.Clear(); _expired.Clear(); AttackPhases.Clear(); _drawnEffects.Clear(); _drawnMaps.Clear(); _drawnActions.Clear(); _motionSamples.Clear(); _terrain.Clear(); _terrainIndex.Clear(); _visibleTerrain.Clear(); _indexedCells = null; _indexedMap = -1; _terrainRebuilds = 0; QueueRedraw(); }
        public void Present(ClientSceneSnapshot scene, long time)
        {
            bool redraw = !SameScene(_scene, scene) || _walk.Count > 0 || _actions.Count > 0 || _effects.Count > 0 || _health.Count > 0;
            if (scene.Dialog is not null || scene.Shop is not null || scene.WorldMap is not null) CancelWorldTouch();
            if (scene.Map != _map) { CancelWorldTouch(); _walk.Clear(); _actions.Clear(); _health.Clear(); _hits.Clear(); _effects.Clear(); _map = scene.Map; Selected = 0; }
            bool selfDamaged = _scene is { } prior && prior.SelfId == scene.SelfId
                && prior.Map == scene.Map && scene.Stats.Hp < prior.Stats.Hp;
            _scene = scene; _time = time;
            if (selfDamaged && scene.Stats.MaxHp > 0)
            { _health[scene.SelfId] = (SelfHealthPercent(scene), time); redraw = true; }
            IndexTerrain(scene);
            foreach (var e in scene.Events.Where(e => e.Sequence > _seen))
            {
                if (e.Kind == "map") { _walk.Clear(); _actions.Clear(); _health.Clear(); _effects.Clear(); continue; }
                if (e.Kind is "walk" or "confirmed-local-walk") BeginWalk(scene, e, time);
                if (e.Kind == "action") _actions[e.EntityId] = (time, time + Math.Max(10, e.Auxiliary * 10L), e.Value);
                if (e.Kind == "effect") _effects.Add((e.EntityId, e.Value, time));
                // 0x13 carries remaining percent, not raw damage or a content-definition HP value.
                // Native 0x44e870 queues this widget for exactly0x1f4 host milliseconds.
                if (e.Kind == "damage" && e.Value is >= 0 and <= 100)
                {
                    if (e.EntityId == scene.SelfId && scene.Stats.MaxHp > 0)
                    { _health[e.EntityId] = (SelfHealthPercent(scene), time); redraw = true; }
                    else if (scene.Creatures.Any(c => c.Id == e.EntityId))
                    { _health[e.EntityId] = (e.Value, time); _hits[e.EntityId] = (time, e.Auxiliary == 255); redraw = true; }
                }
                if (e.Kind == "despawn")
                    for (int i = 0; e.Body.Length > 0 && i < e.Body[0] && 1 + i * 4 + 4 <= e.Body.Length; i++)
                    { int at = 1 + i * 4; uint id = ((uint)e.Body[at] << 24) | ((uint)e.Body[at + 1] << 16) | ((uint)e.Body[at + 2] << 8) | e.Body[at + 3]; _health.Remove(id); }
            }
            // A position correction (wall/refusal/warp) is authoritative. It does not become a
            // fresh step from a guessed tile, and must not keep sliding beyond the confirmed tile.
            if (_walk.TryGetValue(scene.SelfId, out var selfWalk)
                && selfWalk.Destination != new TileMotion.Point(scene.X, scene.Y)) _walk.Remove(scene.SelfId);
            _seen = scene.LastEventSequence;
            PruneAnimations();
            UpdateCamera();
            ObserveMotion();
            // Also redraw when a prior animation expires, so its final pose/effect is removed.
            if (redraw || _walk.Count > 0 || _actions.Count > 0 || _effects.Count > 0 || _health.Count > 0) QueueRedraw();
        }
        public void AdvanceFrame(long time)
        {
            _time = time;
            if (_scene is null || (_walk.Count == 0 && _actions.Count == 0 && _effects.Count == 0 && _health.Count == 0)) return;
            PruneAnimations();
            UpdateCamera();
            ObserveMotion();
            // Include the frame where an animation expires, to remove its final pose/effect.
            QueueRedraw();
        }
        private void PruneAnimations()
        {
            _expired.Clear();
            foreach (var pair in _walk) if (!pair.Value.Active(_time)) _expired.Add(pair.Key);
            foreach (uint id in _expired) _walk.Remove(id);
            _expired.Clear();
            foreach (var pair in _actions) if (_time >= pair.Value.End) _expired.Add(pair.Key);
            foreach (uint id in _expired) _actions.Remove(id);
            _expired.Clear();
            foreach (var pair in _health)
                if (_scene is null || (pair.Key == _scene.SelfId
                    ? _time - pair.Value.Start >= 2500 || _scene.Stats.Hp >= _scene.Stats.MaxHp
                    : _time - pair.Value.Start >= 500 || !_scene.Creatures.Any(c => c.Id == pair.Key))) _expired.Add(pair.Key);
            foreach (uint id in _expired) _health.Remove(id);
            foreach (uint id in _hits.Where(h => _time - h.Value.Start >= 120 || !_health.ContainsKey(h.Key)).Select(h => h.Key).ToArray()) _hits.Remove(id);
            _effects.RemoveAll(e => _time - e.Start >= Art.EffectDuration(e.Effect));
        }
        private void BeginWalk(ClientSceneSnapshot scene, SceneEvent e, long time)
        {
            int direction = e.Value;
            if (direction is < 0 or > 3) return;
            int dx = direction == 1 ? 1 : direction == 3 ? -1 : 0;
            int dy = direction == 2 ? 1 : direction == 0 ? -1 : 0;
            int fromX, fromY;
            if (e.Kind == "confirmed-local-walk" && e.PresentationSourceX is int localX && e.PresentationSourceY is int localY)
            { fromX = localX; fromY = localY; }
            else if (e.Opcode == 0x26 && e.Body.Length >= 5)
            { fromX = (e.Body[1] << 8) | e.Body[2]; fromY = (e.Body[3] << 8) | e.Body[4]; }
            else if (e.Opcode == 0x0c && e.Body.Length >= 9)
            { fromX = (e.Body[4] << 8) | e.Body[5]; fromY = (e.Body[6] << 8) | e.Body[7]; }
            else
            {
                // Older isolated render fixtures omit raw packet bytes. This fallback still uses
                // the decoded destination; production packets take the exact source fields above.
                var p = scene.Players.FirstOrDefault(p => p.Id == e.EntityId);
                var c = scene.Creatures.FirstOrDefault(c => c.Id == e.EntityId);
                if (e.EntityId == scene.SelfId) { fromX = scene.X - dx; fromY = scene.Y - dy; }
                else if (p is not null) { fromX = p.X - dx; fromY = p.Y - dy; }
                else if (c is not null) { fromX = c.X - dx; fromY = c.Y - dy; }
                else return;
            }
            var source = new TileMotion.Point(fromX, fromY);
            var destination = new TileMotion.Point(fromX + dx, fromY + dy);
            // UI pacing is retained, not added to the original movement rules. Matching the
            // visual cycle removes the old300ms-slide/400ms-gait/335ms-repeat disagreement.
            int duration = e.EntityId == scene.SelfId ? InputIntentState.DirectionRepeatMilliseconds : 300;
            if (_walk.TryGetValue(e.EntityId, out var track)) track.Begin(source, destination, direction, time, duration);
            else _walk[e.EntityId] = new(source, destination, direction, time, duration);
        }
        private void ObserveMotion()
        {
            if (_scene is not { } scene || !_walk.ContainsKey(scene.SelfId)) return;
            Vector2 position = WorldPosition(scene.X, scene.Y, scene.SelfId);
            _motionSamples.Enqueue(new(_time, scene.X, scene.Y, position.X, position.Y, Camera.X, Camera.Y, ActorPhase(scene.SelfId)));
            while (_motionSamples.Count > 128) _motionSamples.Dequeue();
        }
        private static bool SameScene(ClientSceneSnapshot? a, ClientSceneSnapshot b)
        {
            if (a is null || a.Map != b.Map || a.Width != b.Width || a.Height != b.Height
                || a.X != b.X || a.Y != b.Y || a.Direction != b.Direction || a.SelfId != b.SelfId
                || a.Stats.Hp != b.Stats.Hp || a.Stats.MaxHp != b.Stats.MaxHp
                || a.Cosmetics != b.Cosmetics
                || (!ReferenceEquals(a.Cells, b.Cells) && !a.Cells.SequenceEqual(b.Cells)) || !a.Creatures.SequenceEqual(b.Creatures)
                || !a.FloorItems.SequenceEqual(b.FloorItems) || a.Players.Length != b.Players.Length) return false;
            // CaptureScene deliberately clones appearance arrays. Compare their bytes rather
            // than record reference identity, while retaining changed equipment/direction.
            for (int i = 0; i < a.Players.Length; i++)
            {
                var x = a.Players[i]; var y = b.Players[i];
                if (x.Id != y.Id || x.X != y.X || x.Y != y.Y || x.Direction != y.Direction
                    || !x.Appearance.AsSpan().SequenceEqual(y.Appearance)) return false;
            }
            return true;
        }
        private Vector2 WorldPosition(int x, int y, uint id)
        {
            if (_walk.TryGetValue(id, out var w))
            {
                var position = w.At(_time);
                return new(position.X, position.Y);
            }
            return new(x, y);
        }
        private Vector2 Point(int x, int y, uint id = 0) => ((WorldPosition(x, y, id) - Camera) * 24).Round();
        private int CreaturePose(uint id) => _walk.TryGetValue(id, out var w) ? w.Phase(_time, 3) : 0;
        // The native actor table repeats its middle phase:[0,1,0,2]. All four counter
        // phases use the same visual duration as the accepted-step interpolation.
        private int ActorPhase(uint id) => _walk.TryGetValue(id, out var w) ? w.Phase(_time) : 0;
        public override void _Draw()
        {
            DrawRect(new(Vector2.Zero, Size), Colors.Black);
            if (_scene is not { } s) return;
            _drawnMaps.Add(s.Map);
            Vector2 cameraPixels = Camera * 24;
            // A one-pixel conservative margin absorbs floating point subtraction/multiplication
            // rounding at the bucket boundary. Actual draw positions retain the old expression.
            _terrainIndex.Query(new Rect2(cameraPixels, Size).Grow(1f), _visibleTerrain);
            int terrainAt = 0;
            while (terrainAt < _visibleTerrain.Count && _terrain[_visibleTerrain[terrainAt]].Ground)
            {
                var piece = _terrain[_visibleTerrain[terrainAt++]];
                Art.DrawTerrainFrame(this, piece.Frame, ((piece.Position - Camera) * 24).Round());
            }
            foreach (var item in s.FloorItems)
                if (Art.IconTexture(item.Icon) is { } icon) DrawTexture(icon, Point(item.X, item.Y, item.Id));
            // Native selected scene traversal: row -> actors by X -> objects by X -> front effects.
            // Equal-X original arrival order is unavailable in this snapshot; tie parity stays NOT_RUN.
            var actors = s.Creatures.Select((c, i) => new SceneActor(c.X, c.Y, false, i))
                .Concat(s.Players.Select((p, i) => new SceneActor(p.Id == s.SelfId ? s.X : p.X, p.Id == s.SelfId ? s.Y : p.Y, true, i)))
                .Where(a => a.Y >= 0 && a.Y < s.Height).OrderBy(a => a.Y).ThenBy(a => a.X).ToArray();
            int actorAt = 0;
            for (int row = 0; row < s.Height; row++)
            {
                foreach (var fx in _effects)
                {
                    var fxPlayer = s.Players.FirstOrDefault(p => p.Id == fx.Id); var fxCreature = s.Creatures.FirstOrDefault(c => c.Id == fx.Id);
                    int effectRow = fx.Id == s.SelfId ? s.Y : fxPlayer?.Y ?? fxCreature?.Y ?? -1;
                    if (effectRow != row) continue;
                    Vector2 point = fx.Id == s.SelfId ? Point(s.X, s.Y, s.SelfId)
                        : fxPlayer is not null ? Point(fxPlayer.X, fxPlayer.Y, fxPlayer.Id)
                        : fxCreature is not null ? Point(fxCreature.X, fxCreature.Y, fxCreature.Id) : new(-200, -200);
                    int frame = Art.EffectFrame(fx.Effect, _time - fx.Start, back: true);
                    if (frame >= 0) { Art.Effect(this, fx.Effect, frame, point); _drawnEffects.Add(fx.Effect); }
                }
                while (actorAt < actors.Length && actors[actorAt].Y == row)
                {
                    var actor = actors[actorAt++];
                    if (!actor.Player)
                    {
                        var c = s.Creatures[actor.Index];
                        int facing = _walk.TryGetValue(c.Id, out var movingCreature) ? movingCreature.DirectionAt(_time) : c.Direction;
                        Art.Creature(this, c.Look, c.Color, facing, CreaturePose(c.Id), Point(c.X, c.Y, c.Id));
                        continue;
                    }
                    var p = s.Players[actor.Index];
                    int x = p.Id == s.SelfId ? s.X : p.X, y = p.Id == s.SelfId ? s.Y : p.Y;
                    int dir = p.Id == s.SelfId ? s.Direction : p.Direction;
                    bool actionActive = _actions.TryGetValue(p.Id, out var action);
                    int actionType = actionActive ? action.Action : 0;
                    int phase = actionType is 1 or 2 or 3 ? Math.Clamp((int)((_time - action.Start) * 2 / Math.Max(1, action.End - action.Start)), 0, 1)
                        : actionType == 0 ? ActorPhase(p.Id) : 0;
                    if (actionType == 0 && _walk.TryGetValue(p.Id, out var walking)) dir = walking.DirectionAt(_time);
                    Art.Actor(this, p.Appearance, dir, phase, actionType, Point(x, y, p.Id),
                        p.Id == s.SelfId ? SelfHairTone : 0, p.Id == s.SelfId ? SelfSkinTone : 0,
                        p.Id == s.SelfId ? s.Cosmetics : default);
                    if (p.Id == s.SelfId && s.Equipment.FirstOrDefault(e => e.WireSlot == 4) is { } helmet
                        && Art.ActorBounds(p.Appearance, dir, phase, actionType, includeWeapon: false) is { } actorBounds)
                        Art.DrawHeadEquipment(this, helmet.Icon, Point(x, y, p.Id), actorBounds);
                    if (p.Id == s.SelfId)
                    {
                        if (actionType == 1) AttackPhases.Add(phase);
                        if (p.Appearance.Length == 7 && ActorPose.TryResolveAction(dir, phase, actionType, p.Appearance[5], out var pose)) _drawnActions.Add((actionType, phase, pose.Body));
                    }
                }
                while (terrainAt < _visibleTerrain.Count && _terrain[_visibleTerrain[terrainAt]].Row == row)
                {
                    var piece = _terrain[_visibleTerrain[terrainAt++]];
                    Art.DrawTerrainFrame(this, piece.Frame, ((piece.Position - Camera) * 24).Round());
                }
                foreach (var fx in _effects)
                {
                    var p = s.Players.FirstOrDefault(p => p.Id == fx.Id); var c = s.Creatures.FirstOrDefault(c => c.Id == fx.Id);
                    int y = fx.Id == s.SelfId ? s.Y : p is not null ? p.Y : c is not null ? c.Y : -1;
                    if (y != row) continue;
                    Vector2 point = fx.Id == s.SelfId ? Point(s.X, s.Y, s.SelfId) : p is not null ? Point(p.X, p.Y, p.Id) : c is not null ? Point(c.X, c.Y, c.Id) : new(-200, -200);
                    int frame = Art.EffectFrame(fx.Effect, _time - fx.Start);
                    if (frame >= 0) { Art.Effect(this, fx.Effect, frame, point); _drawnEffects.Add(fx.Effect); }
                }
            }
            var chosen = s.Creatures.FirstOrDefault(c => c.Id == Selected);
            if (chosen is not null) DrawRect(new(Point(chosen.X, chosen.Y, chosen.Id), new(24, 24)), new Color("ffd36b"), false, 1);
            foreach (var c in s.Creatures)
            {
                if (!_health.TryGetValue(c.Id, out var health)) continue;
                int facing = _walk.TryGetValue(c.Id, out var movement) ? movement.DirectionAt(_time) : c.Direction;
                if (Art.CreatureBounds(c.Look, c.Color, facing, CreaturePose(c.Id)) is not { } bounds) continue;
                Vector2 point = Point(c.X, c.Y, c.Id);
                // Match the actual sprite's signed top; tall creatures must not receive a
                // guessed tile-height offset. The same interpolation positions bar and body.
                Art.CombatHealth(this, health.Percent, point, bounds.Position.Y);
                if (_hits.TryGetValue(c.Id, out var hit))
                    Art.CombatHitFeedback(this, hit.Critical, _time - hit.Start, point, bounds);
                if (new Rect2(point + new Vector2(0, bounds.Position.Y - 11), new Vector2(24, 45)).Intersects(new Rect2(Vector2.Zero, Size)))
                {
                    _healthSamples.Enqueue(new(_time, c.Id, health.Percent, health.Percent == 0 ? "DEADSIGN" : "HP_BAR", "ORIGINAL_0x13_REMAINING_PERCENT"));
                    while (_healthSamples.Count > 128) _healthSamples.Dequeue();
                }
            }
            if (_health.ContainsKey(s.SelfId) && s.SelfLook is { } self
                && Art.ActorBounds(self.Appearance, s.Direction, ActorPhase(s.SelfId), 0, includeWeapon: false) is { } selfBounds
                && s.Stats.MaxHp > 0)
            {
                // Requested local-player feedback. The red fill is driven by the
                // original authoritative HP stat, never by guessed monster damage.
                Vector2 origin = Point(s.X, s.Y, s.SelfId) + new Vector2(-18, selfBounds.Position.Y - 10);
                DrawRect(new Rect2(origin, new Vector2(36, 6)), new Color("24100d"));
                float fraction = Math.Clamp(s.Stats.Hp / (float)s.Stats.MaxHp, 0, 1);
                if (fraction > 0) DrawRect(new Rect2(origin + Vector2.One, new Vector2(MathF.Ceiling(34 * fraction), 4)), new Color("ee3434"));
                _healthSamples.Enqueue(new(_time, s.SelfId, SelfHealthPercent(s), "SELF_RED_HP_BAR", "AUTHORITATIVE_0x08_SELF_HP"));
                while (_healthSamples.Count > 128) _healthSamples.Dequeue();
            }
            if (_finger != NoFinger)
            {
                // This is an Android touch affordance, not a claim about the old
                // desktop client's UI. It appears only while its owning finger is down.
                DrawCircle(_stickOrigin, StickRadius, new Color(0.12f, 0.09f, 0.04f, 0.26f));
                DrawArc(_stickOrigin, StickRadius, 0, MathF.Tau, 40, new Color(1, 0.86f, 0.55f, 0.65f), 1.5f, true);
                Vector2 offset = _stickPoint - _stickOrigin;
                if (offset.Length() > StickRadius) offset = offset.Normalized() * StickRadius;
                DrawCircle(_stickOrigin + offset, 10, new Color(1, 0.86f, 0.55f, 0.55f));
            }
        }
        private static int SelfHealthPercent(ClientSceneSnapshot scene)
            => scene.Stats.MaxHp == 0 ? 0 : (int)Math.Min(100, (ulong)scene.Stats.Hp * 100 / scene.Stats.MaxHp);
        private const int NoFinger = -2, MouseFinger = -1;
        private const float StickDeadzone = 10, StickRadius = 32;
        private int _finger = NoFinger, _stickDirection = -1;
        private Vector2 _stickOrigin, _stickPoint;
        private bool _dragged;
        public void CancelWorldTouch()
        {
            _finger = NoFinger; _dragged = false;
            SetStickDirection(-1); QueueRedraw();
        }
        private void SetStickDirection(int direction)
        {
            if (_stickDirection == direction) return;
            _stickDirection = direction; DirectionHeld?.Invoke(direction);
        }
        private void BeginPointer(int finger, Vector2 position)
        {
            if (_finger != NoFinger || _scene is null || _scene.Dialog is not null || _scene.Shop is not null || _scene.WorldMap is not null
                || !TryGetTile(position, out _)) return;
            _finger = finger; _stickOrigin = _stickPoint = position; _dragged = false;
            SetStickDirection(-1); QueueRedraw();
        }
        private void MovePointer(Vector2 position)
        {
            _stickPoint = position;
            Vector2 offset = position - _stickOrigin;
            if (offset.Length() < StickDeadzone) SetStickDirection(-1);
            else
            {
                _dragged = true;
                SetStickDirection(Math.Abs(offset.X) >= Math.Abs(offset.Y) ? offset.X < 0 ? 3 : 1 : offset.Y < 0 ? 0 : 2);
            }
            QueueRedraw();
        }
        private void EndPointer(Vector2 position, bool canceled)
        {
            bool tap = !canceled && !_dragged && (position - _stickOrigin).Length() < StickDeadzone;
            CancelWorldTouch();
            if (canceled) { WorldTouchCanceled?.Invoke(); return; }
            if (tap && !SelectTarget(position) && TryGetTile(position, out var tile))
                DestinationPressed?.Invoke(tile.X, tile.Y);
        }
        private bool SelectTarget(Vector2 position)
        {
            if (_scene is null) return false;
            bool Hit(Creature c)
            {
                Vector2 actor = Point(c.X, c.Y, c.Id);
                int facing = _walk.TryGetValue(c.Id, out var moving) ? moving.DirectionAt(_time) : c.Direction;
                var bounds = Art.CreatureBounds(c.Look, c.Color, facing, CreaturePose(c.Id));
                return (bounds is { } box && new Rect2(actor + box.Position, box.Size).HasPoint(position))
                    || new Rect2(actor, new Vector2(24, 24)).HasPoint(position);
            }
            var nearest = _scene.Creatures.Where(Hit).OrderByDescending(c => c.Y).ThenByDescending(c => c.X).FirstOrDefault();
            Selected = nearest?.Id ?? 0;
            if (nearest is not null) TargetPressed?.Invoke(Selected);
            QueueRedraw();
            return nearest is not null;
        }
        public override void _Input(InputEvent e)
        {
            if (_finger == NoFinger || !IsVisibleInTree()) return;
            Vector2 Local(Vector2 p) => GetGlobalTransformWithCanvas().AffineInverse() * p;
            // Own the matching release/drag even when it crosses the viewport's
            // edge or a HUD panel; a late or second finger cannot take over the stick.
            if (e is InputEventScreenDrag drag && drag.Index == _finger)
            { MovePointer(Local(drag.Position)); GetViewport().SetInputAsHandled(); }
            else if (e is InputEventScreenTouch touch && touch.Index == _finger && (!touch.Pressed || touch.Canceled))
            { EndPointer(Local(touch.Position), touch.Canceled); GetViewport().SetInputAsHandled(); }
            else if (_finger == MouseFinger && e is InputEventMouseMotion motion && e.Device != -1)
            { MovePointer(Local(motion.Position)); GetViewport().SetInputAsHandled(); }
            else if (_finger == MouseFinger && e is InputEventMouseButton button && button.ButtonIndex == MouseButton.Left && !button.Pressed && e.Device != -1)
            { EndPointer(Local(button.Position), false); GetViewport().SetInputAsHandled(); }
        }
        public override void _GuiInput(InputEvent e)
        {
            if (e is InputEventMouseButton { Device: -1 }) return; // Godot's emulated copy of a real touch.
            if (e is InputEventScreenTouch touch && touch.Pressed && !touch.Canceled)
            { BeginPointer(touch.Index, touch.Position); AcceptEvent(); }
            else if (e is InputEventMouseButton button && button.Pressed && button.ButtonIndex == MouseButton.Left)
            { BeginPointer(MouseFinger, button.Position); AcceptEvent(); }
        }
    }
}

// Camera clamp shared by the terrain and actors. PositionAxis remains available for historical
// geometry comparisons; live accepted-step interpolation is owned by TileMotion above.
internal static class WalkPresentation
{
    public static float PositionAxis(float destination, int direction, long elapsedMilliseconds)
        => destination - direction * (1 - Math.Clamp(elapsedMilliseconds / 300f, 0, 1));
    public static float CameraAxis(float selfPosition, float center, int mapCells, float viewCells)
        => mapCells < viewCells ? (mapCells - viewCells) / 2
            : Math.Clamp(selfPosition - center, 0, mapCells - viewCells);
}


// Spatial buckets contain atlas rectangles rather than owner tiles. Query returns insertion
// ordinals, so removing wholly clipped pieces cannot reorder any remaining overlapping pixels.
// This is an acceleration index only; it neither truncates the client model nor changes collision.
internal sealed class TerrainViewportIndex
{
    private const int BucketPixels = 24;
    private readonly List<Rect2> _bounds = new();
    private readonly Dictionary<Vector2I, List<int>> _buckets = new();
    private readonly HashSet<int> _seen = new();
    public void Clear() { _bounds.Clear(); _buckets.Clear(); _seen.Clear(); }
    public void Add(Rect2 bounds)
    {
        int ordinal = _bounds.Count;
        _bounds.Add(bounds);
        int minX = (int)Math.Floor(bounds.Position.X / BucketPixels), minY = (int)Math.Floor(bounds.Position.Y / BucketPixels);
        int maxX = (int)Math.Ceiling(bounds.End.X / BucketPixels) - 1, maxY = (int)Math.Ceiling(bounds.End.Y / BucketPixels) - 1;
        for (int y = minY; y <= maxY; y++)
            for (int x = minX; x <= maxX; x++)
            {
                Vector2I key = new(x, y);
                if (!_buckets.TryGetValue(key, out var bucket)) _buckets.Add(key, bucket = new());
                bucket.Add(ordinal);
            }
    }
    public void Query(Rect2 viewport, List<int> result)
    {
        result.Clear(); _seen.Clear();
        int minX = (int)Math.Floor(viewport.Position.X / BucketPixels), minY = (int)Math.Floor(viewport.Position.Y / BucketPixels);
        int maxX = (int)Math.Ceiling(viewport.End.X / BucketPixels) - 1, maxY = (int)Math.Ceiling(viewport.End.Y / BucketPixels) - 1;
        for (int y = minY; y <= maxY; y++)
            for (int x = minX; x <= maxX; x++)
                if (_buckets.TryGetValue(new(x, y), out var bucket))
                    foreach (int ordinal in bucket)
                        if (_seen.Add(ordinal) && _bounds[ordinal].Intersects(viewport)) result.Add(ordinal);
        result.Sort();
    }
}
