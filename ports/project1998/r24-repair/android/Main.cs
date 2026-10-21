using Godot;
using P1998.Embedded;
using System.Collections.Concurrent;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using IO = System.IO;

/// <summary>Stage7 G6 region-expansion client. All authoritative actions enter PlaySession; UI state,
/// local credentials and Korean display metadata never replace original game rules.</summary>
public partial class Main : Control
{
    public const string BuildId = "P1998-G7-V4-20261021-r26";
    private sealed record Profile(string Id, string Password, string Name, int HairTone = 0, int SkinTone = 0);
    private sealed record UiLatency(string Kind, double Milliseconds, bool Committed, bool HostFaulted);
    private readonly ConcurrentQueue<Action> _ui = new();
    private readonly object _lifeOrder = new(), _reportGate = new(), _intentGate = new();
    private Task _lifeTail = Task.CompletedTask;
    private Task? _opening;
    private CancellationTokenSource _stop = new();
    private volatile PlaySession? _play;
    private volatile bool _background, _exiting;
    private long _applicationTicket;
    private string _root = "", _content = "", _statusText = "새 게임 또는 이어하기를 선택하세요.", _fatal = "";
    private bool _busy, _playing;
    private ArtCatalog _art = null!;
    private GameView _view = null!;
    private GameHud _hud = null!;
    private GameAudio _audio = null!;
    private OriginalEntryScreen _entry = null!;
    private BackupPanel _backupPanel = null!;
    private Button _backupButton = null!;
    private OfflineRecoveryStore _recovery = null!;
    private bool _rootSelectionBlocked, _restartRequired;
    private string? _rootSelectionError;
    private LineEdit _display = null!;
    private FileDialog _exportDialog = null!;
    private Profile? _profile;
    private LocalProfileStore _profiles = null!;
    private LocalProfileCatalog _reportProfileCatalog = new(null, Array.Empty<LocalCharacterEntry>(), Array.Empty<string>());
    private DateTimeOffset? _reportProfileCatalogObservedUtc;
    private readonly List<object> _actions = new(), _lifecycle = new(), _failures = new();
    private readonly MonotonicFrameMetrics _performance = new();
    private readonly List<UiLatency> _uiLatencies = new();
    private double _poll;
    private int _lastMap = -1, _confirmedFacing = -1;
    private readonly InputIntentState _input = new();
    private (int Map, int X, int Y)? _destination;
    private ClientNavigation.Route? _destinationRoute;
    private int _destinationRouteIndex, _destinationRetries;
    private long _destinationVersion, _nextDestinationStep, _destinationPlanningVersion = -1;
    private bool _hudAttackHeld, _keyboardAttackHeld;
    private long _lastDialog;
    private string _smokeResult = "NOT_RUN", _apkSha = "NOT_RUN_PC", _package = "NOT_RUN_PC";
    private string _startupPhase = "managed_ready_entered";
    private bool _startupComplete;
    private readonly List<Button> _entryActions = new();
    private void StartupPhase(string phase)
    {
        _startupPhase = phase;
        if (GetParent()?.HasMethod("managed_phase") == true) GetParent().Call("managed_phase", phase);
    }
    private void StartupFailure(Exception e)
    {
        _startupComplete = false;
        _entry?.SetBusy(true);
        foreach (var button in _entryActions) button.Disabled = true;
        Failure("startup/" + _startupPhase, e);
        if (GetParent()?.HasMethod("managed_failed") == true) GetParent().Call("managed_failed", _startupPhase, e.ToString());
    }
    public override void _Ready()
    {
        try
        {
            StartupPhase("user_directory");
            _root = OS.GetEnvironment("P1998_G2_DATA");
            if (_root.Length == 0) _root = ProjectSettings.GlobalizePath("user://");
            IO.Directory.CreateDirectory(_root);
            _recovery = new OfflineRecoveryStore(_root);
            var selectedRoot = _recovery.ResolveSelected();
            _rootSelectionBlocked = selectedRoot.Blocked; _rootSelectionError = selectedRoot.Error;
            _root = selectedRoot.Root;
            _profiles = new LocalProfileStore(_root);
            StartupPhase("entry_controls");
            Theme = new Theme { DefaultFontSize = 20 };
            BuildEntry(); Resized += Layout; Layout();
            GetTree().AutoAcceptQuit = false; GetTree().QuitOnGoBack = false;
            CallDeferred(nameof(InitializePresentation));
        }
        catch (Exception e) { StartupFailure(e); }
    }
    private void InitializePresentation()
    {
        try
        {
            StartupPhase("font");
            Theme.DefaultFont = GD.Load<Font>("res://assets/NotoSansKR.ttf") ?? throw new IO.InvalidDataException("Bundled font did not load.");
            StartupPhase("asset_catalog"); _art = new ArtCatalog();
            _entry.Art = _art; _entry.QueueRedraw();
            StartupPhase("game_view"); _view = new GameView { Art = _art, Visible = false }; AddChild(_view);
            if (!_view.InitializationComplete) throw new InvalidOperationException("Game view initialization did not complete; inspect the engine log.");
            StartupPhase("game_audio"); _audio = new GameAudio(); AddChild(_audio);
            if (!_audio.InitializationComplete) throw new InvalidOperationException("Game audio initialization did not complete; inspect the engine log.");
            StartupPhase("game_hud"); _hud = new GameHud { Visible = false, Art = _art, IconTexture = _art.IconTexture }; AddChild(_hud);
            if (!_hud.InitializationComplete) throw new InvalidOperationException("Game HUD initialization did not complete; inspect the engine log.");
            _hud.DirectionHeld += HoldDirection;
            _hud.InputCanceled += ResetInput;
            _hud.DirectionCanceled += _input.CancelDirection;
            _hud.AttackHeld += held => { if (held) CancelDestination(); _hudAttackHeld = held; _input.SetAttackHeld(_hudAttackHeld || _keyboardAttackHeld); };
            _hud.Command += command => _ = Handle(command);
            _view.TargetPressed += id => { ResetInput(); _hud.SelectedTarget = id; _view.SelectedTarget = id; };
            _view.DestinationPressed += BeginDestination;
            _view.DirectionHeld += HoldDirection;
            _view.WorldTouchCanceled += ResetInput;
            StartupPhase("entry_layout"); Layout(); ObservePackage();
            _startupComplete = true; _startupPhase = "entry_ready";
            RefreshProfiles(); _entry.SetBusy(_rootSelectionBlocked || _restartRequired);
            if (_rootSelectionBlocked) Status("저장 선택을 확인하지 못했습니다. ‘백업·복구’에서 사용할 저장을 선택하세요.");
            _backupButton.Disabled = false;
            if (GetParent()?.HasMethod("managed_ready") == true) GetParent().Call("managed_ready");
            if (OS.GetCmdlineUserArgs().Contains("--g4-smoke")) CallDeferred(nameof(BeginTutorialSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--r14-repair" or "--r14-reopen")) CallDeferred(nameof(BeginStage7R14Smoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--r15-repair" or "--r15-reopen")) CallDeferred(nameof(BeginStage7R15Smoke));
            if (OS.GetCmdlineUserArgs().Contains("--r16-earned-reopen")) CallDeferred(nameof(BeginStage7R16EarnedResumeSmoke));
            if (OS.GetCmdlineUserArgs().Contains("--ko-localization-smoke")) CallDeferred(nameof(BeginLocalizationSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--r13-stage7-repair-smoke" or "--r13-stage7-reopen")) CallDeferred(nameof(BeginStage7RepairSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--r12-repair-smoke" or "--r12-repair-resume" or "--r12-repair-reopen")) CallDeferred(nameof(BeginRepairSmoke));
            if (OS.GetCmdlineUserArgs().Contains("--r12-final-visual-smoke")) CallDeferred(nameof(BeginRepairVisualSmoke));
            if (OS.GetCmdlineUserArgs().Contains("--r12-confirmed-walk-smoke")) CallDeferred(nameof(BeginConfirmedWalkSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--g6-region-smoke" or "--g6-region-reopen")) CallDeferred(nameof(BeginRegionSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--g6-level5-smoke" or "--g6-class-smoke" or "--g6-class-reopen")) CallDeferred(nameof(BeginClassSmoke));
            if (OS.GetCmdlineUserArgs().Contains("--g6-bank-coin-smoke")) CallDeferred(nameof(BeginBankCoinSmoke));
            if (OS.GetCmdlineUserArgs().Contains("--g2-input-smoke")) CallDeferred(nameof(BeginInputSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--g5-ui-smoke" or "--g5-ui-fault-smoke" or "--g5-ui-dialog-smoke" or "--g5-ui-name-smoke" or "--g5-ui-gear-resume")) CallDeferred(nameof(BeginUsabilitySmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--g2-combat-smoke" or "--g2-smoke" or "--g2-continue-smoke" or "--g2-reopen-smoke" or "--g2-fault-smoke")) CallDeferred(nameof(BeginSmoke));
            if (OS.GetCmdlineUserArgs().Any(a => a is "--g2-combined-smoke" or "--g2-combined-reopen-smoke")) CallDeferred(nameof(BeginCombinedSmoke));
        }
        catch (Exception e) { StartupFailure(e); }
    }
    private void BuildEntry()
    {
        _entry = new OriginalEntryScreen(); AddChild(_entry);
        _display = _entry.DisplayNameInput; // retained public input for historical explicit probes
        _entry.ContinueRequested += ContinueCharacter;
        _entry.CreationRequested += CreateCharacter;
        _entry.LoginRequested += LoginCharacter;
        _entry.PasswordChangeRequested += ChangeLocalPassword;
        _entry.CancelRequested += () => { DismissTextInput(); RefreshProfiles(); };
        _entry.ExportRequested += Export;
        _entry.ExitRequested += () => _ = End(true);
        _entry.NewIdentityProblem = NewIdentityProblem;
        _entry.SetStatus(_statusText); _entry.SetBusy(true);
        _exportDialog = new FileDialog { FileMode = FileDialog.FileModeEnum.SaveFile, Access = FileDialog.AccessEnum.Filesystem, UseNativeDialog = true,
            Title = "실행 결과 저장", CurrentFile = "P1998-G6-result.json" };
        _exportDialog.FileSelected += path =>
        {
            try
            {
                // Native Android picker paths can be content://, owned by Godot's URI bridge.
                using var file = Godot.FileAccess.Open(path, Godot.FileAccess.ModeFlags.Write)
                    ?? throw new IO.IOException("Report destination open failed: " + Godot.FileAccess.GetOpenError());
                file.StoreString(GetStartupReport()); file.Flush();
                if (file.GetError() != Error.Ok) throw new IO.IOException("Report write failed: " + file.GetError());
                Status("실행 결과 저장 완료");
            }
            catch (Exception e) { Failure("export", e); }
        };
        AddChild(_exportDialog);
        var home = _entry.FindChild("HomePage", true, false) as Control ?? throw new InvalidOperationException("Original entry home is absent.");
        _backupButton = new Button { Name = "EntryBackupButton", Text = "백업 · 복구", Position = new(188,444), Size = new(130,24), FocusMode = FocusModeEnum.None, Disabled = true };
        _backupButton.AddThemeFontSizeOverride("font_size",12); _backupButton.Pressed += OpenBackupPanel; home.AddChild(_backupButton);
        _backupPanel = new BackupPanel(); AddChild(_backupPanel);
        _backupPanel.Closed += () => { _busy = false; _entry.SetBusy(_rootSelectionBlocked || _restartRequired); RefreshProfiles(); if (_restartRequired) Status("앱을 완전히 종료한 뒤 다시 실행하면 선택한 저장을 사용합니다."); };
        _backupPanel.SelectionChanged += () => _restartRequired = true;
        _backupPanel.ExitRequested += () => _ = End(true);
        _backupPanel.OperationFailed += (phase,error) => { Record(_failures,new { phase, error = error.ToString(), utc = DateTimeOffset.UtcNow }); GD.PushError("Backup operation: " + error.Message); };
    }
    private void OpenBackupPanel()
    {
        if (!_startupComplete || _busy || _playing || _play is not null || _exiting) return;
        DismissTextInput(); _busy = true; _entry.SetBusy(true); _backupButton.Disabled = true;
        _backupPanel.Open(_recovery, _root, _rootSelectionError);
    }
    private void RememberProfileCatalog(LocalProfileCatalog catalog)
    {
        lock (_reportGate)
        {
            _reportProfileCatalog = catalog with { Characters = catalog.Characters.ToArray(), Warnings = catalog.Warnings.ToArray() };
            _reportProfileCatalogObservedUtc = DateTimeOffset.UtcNow;
        }
    }
    private void RefreshProfiles()
    {
        var catalog = _profiles.Load(); RememberProfileCatalog(catalog);
        _entry.SetProfiles(catalog.Characters.Select(c => new EntryProfile(c.Id, c.Name, c.CanOpen, c.Level, c.Issue)).ToArray(), catalog.SelectedId);
        _entryActions.Clear();
        if (_entry.FindChild("EntryNewButton", true, false) is Button create) _entryActions.Add(create);
        if (_entry.FindChild("EntryContinueButton", true, false) is Button resume) _entryActions.Add(resume);
    }
    private void Layout()
    {
        if (_entry is null) return;
        // Keep the original panels and tile aspect. Extra landscape width belongs
        // to the world/chat area instead of becoming black side gutters.
        float scale = Math.Min(Math.Max(1, Size.X) / 640f, Math.Max(1, Size.Y) / 480f);
        float logicalWidth = Math.Max(640, Size.X / scale);
        if (_view is not null)
        { _view.ConfigureFrame(logicalWidth); _view.Scale = new(scale, scale); _view.Position = new(0, (Size.Y - 480 * scale) / 2); }
        if (_view is not null && _hud?.NativeOverlay is not null)
        { _hud.ConfigureFrame(logicalWidth); _hud.NativeOverlay.Scale = _view.Scale; _hud.NativeOverlay.Position = _view.Position; }
        _entry.Size = Size; _entry.Position = Vector2.Zero;
    }
    private void Status(string text) { _statusText = text; _entry?.SetStatus(text); }
    private string ProfilePath => IO.Path.Combine(_root, "g2-local-profile.json");
    private static string Letters(int length) => new(Enumerable.Range(0, length).Select(_ => (char)('a' + System.Security.Cryptography.RandomNumberGenerator.GetInt32(26))).ToArray());
    private void Start(bool continuing)
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        if (!continuing) { _entry.BeginCreate(); return; }
        var id = _profiles.Load().SelectedId;
        if (id is null) { Status("저장된 캐릭터를 선택하거나 새 캐릭터를 만드세요."); return; }
        ContinueCharacter(id);
    }
    private string? NewIdentityProblem(string id)
    {
        if (Shared.NameRules.ShapeProblem(id) is { } shape) return shape;
        var catalog = _profiles.Load();
        if (catalog.Warnings.Contains("CHARACTER_DATABASE_READ_FAILED")) return "기존 저장을 읽지 못했습니다. 새 생성으로 덮지 않고 중지했습니다.";
        return catalog.Characters.Any(c => string.Equals(c.Id, id, StringComparison.OrdinalIgnoreCase) && c.Issue != "CREATION_INCOMPLETE")
            ? "이미 저장되었거나 생성 중인 아이디입니다. 목록에서 선택하거나 다른 아이디를 입력하세요." : null;
    }
    private void ContinueCharacter(string id)
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        try
        {
            var p = _profiles.Get(id); DismissTextInput(); Open(new(p.Id, p.Password, p.Name, p.HairTone, p.SkinTone), false);
        }
        catch (Exception e) when (e is ArgumentException or InvalidOperationException or IO.IOException)
        { Status(e.Message); RefreshProfiles(); }
    }
    private void CreateCharacter(EntryCreation draft)
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        try
        {
            if (NewIdentityProblem(draft.Id) is { } invalid) { _entry.SetBusy(false); Status(invalid); return; }
            if (Shared.CreationRules.PasswordProblem(draft.Password) is { } passwordProblem) { _entry.SetBusy(false); Status(passwordProblem); return; }
            if (string.IsNullOrWhiteSpace(draft.DisplayName)) { _entry.SetBusy(false); Status("표시 이름을 입력하세요."); return; }
            if (draft.Appearance.Length != 5 || draft.Appearance[0] >= 90 || draft.Appearance[1] > 1 || draft.Appearance[2] >= Shared.Character.Nations.Length || draft.Appearance[3] > 3)
            { _entry.SetBusy(false); Status("원본에서 지원하는 외형을 선택하세요."); return; }
            var p = new LocalCharacterProfile(draft.Id, draft.Password, draft.DisplayName.Trim(), draft.HairTone, draft.SkinTone);
            _profiles.Stage(p); // durable old/draft credentials BEFORE original account creation
            DismissTextInput(); Open(new(p.Id, p.Password, p.Name, p.HairTone, p.SkinTone), true, draft.Appearance);
        }
        catch (Exception e) { _entry.SetBusy(false); Failure("profile/create", e); RefreshProfiles(); }
    }
    private void LoginCharacter(string id, string password)
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        if (Shared.NameRules.ShapeProblem(id) is { } invalid) { Status(invalid); return; }
        if (password.Length == 0) { Status("기존 아이디의 비밀번호를 입력하세요."); return; }
        string name = _profiles.Load().Characters.FirstOrDefault(c => string.Equals(c.Id, id, StringComparison.OrdinalIgnoreCase))?.Name ?? id;
        LocalCharacterProfile? prior = null;
        try { prior = _profiles.Get(id); } catch (InvalidOperationException) { }
        DismissTextInput(); Open(new(id, password, name, prior?.HairTone ?? 0, prior?.SkinTone ?? 0), false);
    }
    private void ChangeLocalPassword(string id, string oldPassword, string newPassword)
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        _busy = true; _entry.SetBusy(true); DismissTextInput();
        _ = Task.Run(() =>
        {
            try
            {
                _profiles.ChangePassword(id, oldPassword, newPassword);
                _ui.Enqueue(() => { _busy = false; _entry.SetBusy(false); RefreshProfiles(); _entry.ShowHome(); Status("암호를 변경했습니다. 기존 캐릭터와 진행은 유지됩니다."); });
            }
            catch (Exception e)
            { _ui.Enqueue(() => { _busy = false; _entry.SetBusy(false); Status(e.Message); }); }
        });
    }
    private void StartPrevious()
    {
        if (!_startupComplete || _busy || _play is not null || _exiting || _rootSelectionBlocked || _restartRequired) return;
        // Existing stage3 accounts only. No test checkpoint is installed on a user's device.
        string database = IO.Path.Combine(_root, "state", "project1998.db");
        if (!IO.File.Exists(database)) { Status("이 기기에 이전 검사 저장이 없습니다. 새 게임을 선택하세요."); return; }
        Open(new("gionetest", "g1test1", "이전 검사 저장"), false);
    }
    private void Open(Profile profile, bool create, byte[]? appearance = null)
    {
        _audio.StopPlayback(); _view.ResetSession(); _lastMap = -1; _lastDialog = 0; _hud.SelectedTarget = 0; _performance.Reset(); _busy = true; _entry.SetBusy(true); _profile = profile; Status("원본 자료 확인 및 저장 불러오는 중…");
        _opening = Task.Run(async () =>
        {
            PlaySession? opened = null;
            try
            {
                _content = PrepareContent(); _stop.Token.ThrowIfCancellationRequested();
                var play = await PlaySession.OpenAsync(new(IO.Path.Combine(_root, "state"), _content, profile.Id, profile.Password, profile.Name, create, CreationAppearance: appearance), _stop.Token,
                    prepared => { lock (_intentGate) { _play = prepared; if (_background) prepared.RequestPause(); if (_exiting) prepared.RequestStop(); } });
                opened = play;
                var successfulCatalog = _profiles.CommitSuccessful(new(profile.Id, profile.Password, profile.Name, profile.HairTone, profile.SkinTone));
                _ui.Enqueue(() => { RememberProfileCatalog(successfulCatalog); if (_exiting) return; _view.SelfHairTone = _hud.SelfHairTone = profile.HairTone; _view.SelfSkinTone = _hud.SelfSkinTone = profile.SkinTone; _fatal = ""; _playing = true; _busy = false; _entry.SetBusy(false); _entry.Visible = false; _view.Visible = _hud.Visible = true; Status("원본 세계 진입 완료 · 저장 버튼은 확정 저장 후 완료를 표시합니다."); });
            }
            catch (Exception e) { if (opened is not null) { try { await opened.StopAsync(); } catch (Exception stopError) { e = new AggregateException(e, stopError); } } _ui.Enqueue(() => { _busy = false; _play = null; _entry.SetBusy(false); RefreshProfiles(); Failure("entry", e); }); }
        });
    }
    public override void _Process(double delta)
    {
        long frameTimestamp = System.Diagnostics.Stopwatch.GetTimestamp();
        while (_ui.TryDequeue(out var callback)) callback();
        if (!_startupComplete) return;
        var play = _play;
        _backupButton.Disabled = !_startupComplete || _busy || _playing || _play is not null || _exiting;
        _performance.Track(frameTimestamp, _playing && play?.Ready == true && !_background);
        if (!_playing || play is null) return;
        if (!play.Ready || _background) ResetInput();
        _poll += delta;
        if (play.Ready && !_background) _view.AdvanceFrame(play.Host.GameMilliseconds);
        if (_poll >= .05)
        {
            _poll = 0; var scene = play.Capture(); _confirmedFacing = scene.Direction;
            long dialog = scene.Dialog?.Sequence ?? scene.Shop?.Sequence ?? scene.WorldMap?.Sequence ?? 0;
            if (scene.Map != _lastMap) { _hud.SelectedTarget = 0; _view.SelectedTarget = 0; }
            // HUD cancels synchronously when opening a modal; while it is open the
            // per-frame fence below clears held input. Closing must not cancel a new
            // gesture later merely because this 50ms scene poll noticed it last.
            if (scene.Map != _lastMap || dialog != _lastDialog)
            { ResetInput(); _lastMap = scene.Map; _lastDialog = dialog; }
            _view.Present(scene, play.Host.GameMilliseconds); if (!_exiting) _audio.Present(scene);
            _hud.Present(scene, play.DisplayName, _statusText, _busy || !play.Ready, play.Faulted);
        }
        if (_hud.ModalOpen || !play.Ready || _background || _exiting) { ResetInput(); return; }
        if (_destination is not null) { ProcessDestination(play); return; }
        if (_input.TakeNext(_confirmedFacing, play.Host.GameMilliseconds, _busy) is { } intent)
        {
            if (intent.Kind == "turn") _ = Execute("turn", p => p.TurnAsync(intent.Direction));
            else if (intent.Kind == "walk") _ = Execute("walk", p => p.StepAsync(intent.Direction));
            else _ = Execute("attack", p => p.AttackAsync());
        }
    }
    private void CancelDestination()
    {
        _destination = null; _destinationRoute = null; _destinationRouteIndex = _destinationRetries = 0;
        _destinationVersion++; _nextDestinationStep = 0; _destinationPlanningVersion = -1;
    }
    private void ResetInput()
    { CancelDestination(); _input.Clear(); _view?.CancelWorldTouch(); _hudAttackHeld = _keyboardAttackHeld = false; _hud?.ResetHeld(); }
    private void HoldDirection(int direction)
    { if (direction >= 0) { CancelDestination(); _input.SetDirection(direction); } else _input.CancelDirection(); }
    private void BeginDestination(int x, int y)
    {
        var play = _play;
        if (!_playing || play?.Ready != true || _background || _exiting || _hud.ModalOpen) return;
        var scene = play.Capture();
        if (scene.Dialog is not null || scene.Shop is not null || scene.WorldMap is not null) return;
        // A new tap wins, even while an old movement receipt is still in flight.
        // Its previous in-flight step may commit once; the new route is planned
        // from the confirmed position as soon as that receipt clears _busy.
        ResetInput();
        _hud.SelectedTarget = 0;
        _view.SelectedTarget = 0;
        if (x == scene.X && y == scene.Y) return;
        _destination = (scene.Map, x, y);
        _nextDestinationStep = 0;
        // The potentially large A* search is dispatched by ProcessDestination
        // off the frame/UI thread after any in-flight old move has settled.
    }
    private void ProcessDestination(PlaySession play)
    {
        if (_busy || _destination is not { } target || play.Host.GameMilliseconds < _nextDestinationStep) return;
        var scene = play.Capture();
        if (scene.Map != target.Map || scene.Dialog is not null || scene.Shop is not null || scene.WorldMap is not null
            || (scene.X == target.X && scene.Y == target.Y)) { CancelDestination(); return; }
        // Replan if a creature moved, a door/collision tile changed, or another
        // action changed our position. The route's immutable terrain is indexed
        // once per plan, not on every step like the old per-frame BFS.
        if (_destinationRoute is null || !_destinationRoute.CanAdvance(scene, _destinationRouteIndex))
        {
            _destinationRoute = null;
            if (_destinationPlanningVersion != _destinationVersion)
            {
                long requestVersion = _destinationVersion;
                _destinationPlanningVersion = requestVersion;
                _ = PlanDestinationAsync(play, scene, target.X, target.Y, requestVersion);
            }
            return;
        }
        int direction = _destinationRoute.Directions[_destinationRouteIndex];
        long version = _destinationVersion;
        int routeIndex = _destinationRouteIndex;
        _nextDestinationStep = play.Host.GameMilliseconds + InputIntentState.DirectionRepeatMilliseconds;
        _ = ExecuteDestination(play, scene, direction, version, routeIndex);
    }
    private async Task PlanDestinationAsync(PlaySession play, ClientSceneSnapshot scene, int x, int y, long version)
    {
        ClientNavigation.PlanResult result;
        try { result = await Task.Run(() => ClientNavigation.Plan(scene, x, y,
            () => Volatile.Read(ref _destinationVersion) != version)); }
        catch (Exception error)
        {
            _ui.Enqueue(() =>
            {
                if (version != _destinationVersion || !ReferenceEquals(play, _play)) return;
                CancelDestination(); Status("길찾기 오류: " + error.Message);
            });
            return;
        }
        _ui.Enqueue(() =>
        {
            if (version != _destinationVersion || !ReferenceEquals(play, _play)) return;
            _destinationPlanningVersion = -1;
            if (result.Route is null) { CancelDestination(); Status(result.Reason); return; }
            // On the next frame CanAdvance rechecks the original confirmed
            // position, current terrain and dynamic creature occupancy.
            _destinationRoute = result.Route;
            _destinationRouteIndex = 0;
        });
    }
    private async Task ExecuteDestination(PlaySession play, ClientSceneSnapshot before, int direction, long version, int routeIndex)
    {
        bool turn = before.Direction != direction;
        await Execute(turn ? "touch-turn" : "touch-walk", p => turn ? p.TurnAsync(direction) : p.StepAsync(direction));
        var after = play.Capture();
        _ui.Enqueue(() =>
        {
            // An old receipt must never resurrect a canceled or retargeted walk.
            if (version != _destinationVersion || !ReferenceEquals(play, _play)) return;
            bool advanced = after.X == before.X + (direction == 1 ? 1 : direction == 3 ? -1 : 0)
                && after.Y == before.Y + (direction == 2 ? 1 : direction == 0 ? -1 : 0);
            if (!play.Ready || after.Map != before.Map || after.Dialog is not null || after.Shop is not null
                || after.WorldMap is not null || (turn && after.Direction != direction))
            { CancelDestination(); return; }
            if (turn) return; // Original 4.95 turns in place before moving.
            if (!advanced)
            {
                // The original handler can reject a now-occupied tile even when
                // the client route was clear. Replan from authoritative state,
                // but do not loop forever against an invisible solid wall.
                if (after.X == before.X && after.Y == before.Y && ++_destinationRetries <= 2)
                { _destinationRoute = null; _nextDestinationStep = 0; return; }
                CancelDestination(); Status("길이 막혀 자동이동을 멈췄습니다. 지도 충돌을 확인하세요."); return;
            }
            _destinationRouteIndex = routeIndex + 1;
            _destinationRetries = 0;
            if (_destination is { } target && after.X == target.X && after.Y == target.Y)
                CancelDestination();
        });
    }
    private void DismissTextInput()
    {
        GetViewport().GuiReleaseFocus();
        if (DisplayServer.HasFeature(DisplayServer.Feature.VirtualKeyboard)) DisplayServer.VirtualKeyboardHide();
    }
    public override void _Input(InputEvent e)
    {
        // _UnhandledKeyInput is too late: a focused LineEdit can consume Escape itself.
        // A composing IME receives the first Escape; a subsequent Back closes its panel.
        if (e is InputEventKey { Keycode: Key.Escape, Pressed: true, Echo: false })
        { RequestBack(); GetViewport().SetInputAsHandled(); }
    }
    private void RequestBack()
    {
        if (_backupPanel?.Visible == true) { _backupPanel.TryBack(); return; }
        // A fallback in-engine picker must own Back before any underlying original prompt.
        // The native Android picker may handle Back outside this viewport (device NOT_RUN).
        if (_exportDialog?.Visible == true) { _exportDialog.Hide(); DismissTextInput(); return; }
        if (GetViewport().GuiGetFocusOwner() is LineEdit { } input && input.HasImeText()) { input.CancelIme(); return; }
        if (_busy && _play?.Faulted != true) return;
        ResetInput(); DismissTextInput(); var scene = _play?.Capture();
        if (_playing && _play?.Faulted == true) _hud.OpenMenu();
        else if (scene?.Dialog is { } d) _ = Handle(new("dialog-cancel", Sequence: d.Sequence));
        else if (scene?.Shop is { } shop) _ = Handle(new("shop-cancel", Sequence: shop.Sequence));
        else if (scene?.WorldMap is { } world) _ = Handle(new("worldmap-cancel", Sequence: world.Sequence));
        else if (_playing && _hud.ModalOpen) _hud.CloseLocalPanel();
        else if (_playing) _hud.OpenMenu();
        else if (!_exiting && _entry.Page != "home") { _entry.ShowHome(); RefreshProfiles(); }
        else if (!_exiting) _ = End(true);
    }
    public override void _UnhandledKeyInput(InputEvent e)
    {
        if (e is not InputEventKey key || key.Echo || !_playing || _hud.ModalOpen || GetViewport().GuiGetFocusOwner() is LineEdit) return;
        int direction = key.Keycode switch { Key.Up or Key.W => 0, Key.Right or Key.D => 1, Key.Down or Key.S => 2, Key.Left or Key.A => 3, _ => -1 };
        if (direction >= 0)
        { if (key.Pressed) { CancelDestination(); _input.SetDirection(direction); } else if (_input.Direction == direction) _input.CancelDirection(); GetViewport().SetInputAsHandled(); }
        else if (key.Keycode == Key.Space)
        { if (key.Pressed) CancelDestination(); _keyboardAttackHeld = key.Pressed; _input.SetAttackHeld(_hudAttackHeld || _keyboardAttackHeld); GetViewport().SetInputAsHandled(); }
    }
    private async Task Handle(HudCommand command)
    {
        var p = _play;
        if (command.Kind == "attack")
        {
            CancelDestination();
            if (p?.Ready == true && !_background && !_exiting && !_hud.ModalOpen) _input.QueueAttackTap();
            return;
        }
        if (command.Kind == "export") { ResetInput(); Export(); return; }
        if (command.Kind is "menu" or "exit") { ResetInput(); await End(command.Kind == "exit"); return; }
        ResetInput(); if (p is null || _busy) return;
        try
        {
            switch (command.Kind)
            {
                case "save": _busy = true; long saveStarted = System.Diagnostics.Stopwatch.GetTimestamp(); var saved = await p.SaveAsync(); double saveMs = System.Diagnostics.Stopwatch.GetElapsedTime(saveStarted).TotalMilliseconds; RecordLatency("save", saveMs, saved.Committed, p.Faulted); Record(_actions, new { kind = "save", receipt = saved, dispatch_to_receipt_ms = saveMs }); _ui.Enqueue(() => { if (!saved.Committed && p.Faulted) Failure("save", new IO.IOException(saved.Error ?? "SQLite commit failed.")); else Status(saved.Committed ? "저장 완료 · " + saved.Reason : "저장 실패 · " + saved.Error); }); break;
                case "talk":
                    var s = p.Capture(); uint id = _hud.SelectedTarget;
                    if (id == 0) id = s.Creatures.Where(c => Math.Abs(c.X - s.X) <= 2 && Math.Abs(c.Y - s.Y) <= 2).OrderBy(c => Math.Abs(c.X - s.X) + Math.Abs(c.Y - s.Y)).FirstOrDefault()?.Id ?? 0;
                    if (id == 0) { _ui.Enqueue(() => Status("가까운 NPC를 화면에서 선택하세요.")); break; }
                    await Execute("talk", q => q.ClickAsync(id)); break;
                case "pickup": await Execute("pickup", q => q.PickupAsync()); break;
                case "original-help": await Execute("original-help", q => q.ClickAsync(uint.MaxValue)); break;
                case "door": await Execute("door", q => q.OpenDoorAsync()); break;
                case "use": await Execute("use", q => q.UseAsync(checked((byte)command.Number))); break;
                case "eat": await Execute("eat", q => q.EatAsync(checked((byte)command.Number))); break;
                case "equip": await Execute("equip", q => q.EquipAsync(checked((byte)command.Number))); break;
                case "unequip": await Execute("unequip", q => q.UnequipAsync(checked((byte)command.Number))); break;
                case "drop": case "drop-all": await Execute(command.Kind, q => q.DropAsync(checked((byte)command.Number), command.Kind == "drop-all")); break;
                case "hand": case "hand-all": await Execute(command.Kind, q => q.HandItemAsync(checked((byte)command.Number), command.Kind == "hand-all")); break;
                case "ride": await Execute("ride", q => q.RideAsync()); break;
                case "cast": await Execute("cast", q => q.CastAsync(checked((byte)command.Number), command.EntityId == 0 ? null : command.EntityId, command.Text.Length == 0 ? null : command.Text)); break;
                case "chat": await Execute("chat", q => q.ChatAsync(command.Text)); break;
                case "dialog-next": case "dialog-previous":
                    await Execute(command.Kind, q => q.ReplyAsync(q.Capture().Dialog?.Kind ?? 1, command.Number, expectedDialogSequence: command.Sequence)); break;
                case "dialog-menu": await Execute(command.Kind, q => q.ReplyAsync(2, menu: command.Number, expectedDialogSequence: command.Sequence)); break;
                case "dialog-input": await Execute(command.Kind, q => q.ReplyAsync(4, text: command.Text, expectedDialogSequence: command.Sequence)); break;
                case "dialog-cancel": case "shop-cancel":
                    var closing = p.Capture();
                    if ((closing.Dialog?.Sequence ?? closing.Shop?.Sequence) != command.Sequence) throw new InvalidOperationException("지난 창의 취소 입력은 무시되었습니다.");
                    if (closing.Shop is { } closingShop) await Execute(command.Kind, q => q.ShopReplyAsync(closingShop.Tag, expectedDialogSequence: command.Sequence));
                    else if (closing.Dialog is { } closingDialog) await Execute(command.Kind, q => q.ReplyAsync(closingDialog.Kind == 2 ? 2 : 1, step: 0, menu: 0, expectedDialogSequence: command.Sequence));
                    break;
                case "shop-select": case "shop-amount":
                    var shop = p.Capture().Shop ?? throw new InvalidOperationException("상점 창이 닫혔습니다.");
                    await Execute(command.Kind, q => q.ShopReplyAsync(shop.Tag, command.Text, checked((byte)command.Number), expectedDialogSequence: command.Sequence)); break;
                case "worldmap-select": await Execute(command.Kind, q => q.WorldMapSelectAsync(command.Number, command.Sequence)); break;
                case "worldmap-cancel": await Execute(command.Kind, q => q.CancelWorldMapAsync(command.Sequence)); break;
            }
        }
        catch (Exception e) { _ui.Enqueue(() => Failure(command.Kind, e)); }
        finally { _ui.Enqueue(() => _busy = false); }
    }
    private async Task Execute(string kind, Func<PlaySession, Task<Server.OfflineActionResult>> action)
    {
        var play = _play; if (play is null || _background || _exiting) return;
        _busy = true;
        try
        {
            long started = System.Diagnostics.Stopwatch.GetTimestamp(); long mapEpoch = play.Model.MapEpoch; var before = play.Capture(); var result = await action(play); double elapsedMs = System.Diagnostics.Stopwatch.GetElapsedTime(started).TotalMilliseconds; RecordLatency(kind, elapsedMs, result.Committed, play.Faulted); var after = play.Capture();
            if (play.Model.MapEpoch != mapEpoch)
                _ui.Enqueue(() => { if (ReferenceEquals(play, _play)) ResetInput(); });
            Record(_actions, new { kind, result, dispatch_to_receipt_ms = elapsedMs, before = new { before.Map, before.X, before.Y }, after = new { after.Map, after.X, after.Y }, t = play.Host.GameMilliseconds });
            _ui.Enqueue(() =>
            {
                _confirmedFacing = after.Direction;
                if (play.Faulted) Failure(kind, new IO.IOException(result.Error ?? result.Receipt.Error
                    ?? (result.Committed ? "Output/session fault after the original action; inspect the committed receipt."
                        : "Original action was not committed.")));
                else if (!kind.StartsWith("touch-", StringComparison.Ordinal) || !result.Committed)
                    Status(result.Committed ? "원본 응답 수신 · " + kind : "입력이 처리되지 않았습니다 · " + kind);
            });
        }
        catch (Exception e) when (e is ArgumentException or InvalidOperationException or OperationCanceledException && !play.Faulted)
        { Record(_actions, new { kind, status = "INPUT_REJECTED", error = e.Message }); _ui.Enqueue(() => Status(e.Message)); }
        catch (Exception e) { _ui.Enqueue(() => Failure(kind, e)); }
        finally { _ui.Enqueue(() => _busy = false); }
    }
    public override void _Notification(int what)
    {
        if (what == NotificationApplicationPaused || what == NotificationApplicationFocusOut)
        {
            _performance.BreakContinuity();
            long ticket; PlaySession? target;
            lock (_intentGate)
            {
                _background = true; if (_exiting) return;
                ticket = ++_applicationTicket; target = _play; target?.RequestPause();
                QueueLifecycle(async () => { if (target is not null) { var receipt = await target.PauseAsync(); Record(_lifecycle, new { kind = "pause", ticket, t = target.Host.GameMilliseconds, receipt }); } });
            }
            if (_hud is not null) ResetInput(); _audio?.PausePlayback();
        }
        else if (what == NotificationApplicationResumed || what == NotificationApplicationFocusIn)
        {
            _performance.BreakContinuity();
            lock (_intentGate)
            {
                _background = false; if (_exiting) return;
                long ticket = ++_applicationTicket; var target = _play;
                QueueLifecycle(async () =>
                {
                    long version;
                    lock (_intentGate) { if (target is null || !ReferenceEquals(target, _play) || ticket != _applicationTicket || _background || _exiting) return; version = target.Host.LifecycleVersion; }
                    await target.ResumeAsync(version);
                    Record(_lifecycle, new { kind = "resume", ticket, t = target.Host.GameMilliseconds, version });
                    _ui.Enqueue(() => { if (!_background && !_exiting && target.Ready) _audio.ResumePlayback(); });
                });
            }
        }
        else if (what == NotificationWMGoBackRequest)
            RequestBack();
        else if (what == NotificationWMCloseRequest && !_exiting) _ = End(true);
    }
    private void QueueLifecycle(Func<Task> operation)
    { lock (_lifeOrder) _lifeTail = _lifeTail.ContinueWith(async _ => { try { await operation(); } catch (Exception e) { _ui.Enqueue(() => Failure("lifecycle", e)); } }, TaskScheduler.Default).Unwrap(); }
    private async Task End(bool quit)
    {
        Task lifecycle;
        lock (_intentGate) { if (_exiting) return; _exiting = true; _busy = true; _stop.Cancel(); ++_applicationTicket; _play?.RequestStop(); lock (_lifeOrder) lifecycle = _lifeTail; }
        ResetInput(); _audio?.StopPlayback();
        try
        {
            if (_opening is not null) await _opening;
            await lifecycle;
            bool savedCleanly = false;
            if (_play is { } p)
            {
                await p.StopAsync(); Record(_lifecycle, new { kind = "stop", p.Host.LastSave, p.Host.TeardownCount });
                savedCleanly = !p.Faulted && p.Host.LastSave.Committed;
                if (!savedCleanly && p.Capture().EntryComplete) { _fatal = "stop: final save was not committed"; Record(_failures, new { phase = "stop", error = _fatal, p.Host.LastSave }); }
            }
            _ui.Enqueue(() => { WriteReport(IO.Path.Combine(_root, "g2-last-result.json")); if (quit) GetTree().Quit(_smokeResult == "FAIL" ? 1 : 0); else { _play = null; _playing = false; _view.Visible = _hud.Visible = false; _entry.Visible = true; _exiting = _busy = false; RefreshProfiles(); _entry.ShowHome(); _entry.SetBusy(false); _stop.Dispose(); _stop = new(); _hud.CloseLocalPanel(); Status(savedCleanly ? "저장 후 종료했습니다. 이어하기로 복원할 수 있습니다." : "마지막 확정 저장만 유지했습니다. 실행 결과를 확인하세요."); } });
        }
        catch (Exception e) { _ui.Enqueue(() => { _exiting = _busy = false; Failure("stop", e); }); }
    }
    private void RecordLatency(string kind, double milliseconds, bool committed, bool hostFaulted)
    { lock (_reportGate) { _uiLatencies.Add(new(kind, milliseconds, committed, hostFaulted)); if (_uiLatencies.Count > 512) _uiLatencies.RemoveAt(0); } }
    private void Record(List<object> destination, object item)
    { lock (_reportGate) { destination.Add(item); if (destination.Count > 512) destination.RemoveAt(0); } }
    private void Failure(string phase, Exception e)
    {
        _fatal = phase + ": " + e.GetType().Name + ": " + e.Message;
        Record(_failures, new { utc = DateTimeOffset.UtcNow, phase, exception = e.ToString() }); Status("FAIL · " + _fatal); GD.PushError(_fatal);
        try { WriteReport(IO.Path.Combine(_root, "g2-last-failure.json")); } catch (Exception saveError) { GD.PushError("Failure report: " + saveError.Message); }
    }
    private static object Percentiles(IEnumerable<double> values)
    {
        var a = values.Order().ToArray(); double P(double p) => a.Length == 0 ? 0 : a[Math.Min(a.Length - 1, (int)Math.Ceiling(p * a.Length) - 1)];
        return new { count = a.Length, p50 = P(.5), p95 = P(.95), p99 = P(.99), max = a.Length == 0 ? 0 : a[^1] };
    }
    private void WriteReport(string path) => AtomicWrite(path, GetStartupReport());
    private static object HostTimingReport(BoundedHistory<double>? history)
    {
        var snapshot = history?.Snapshot();
        return new { scope = "RECENT_BOUNDED_SAMPLES_PERCENTILES_WITH_SEPARATE_SESSION_TOTAL_AND_MAXIMUM",
            recent_ms = Percentiles(snapshot?.Recent ?? Array.Empty<double>()),
            session_total_count = snapshot?.TotalCount ?? 0, session_maximum_ms = snapshot?.SessionMaximum,
            capacity = snapshot?.Capacity ?? 512 };
    }
    public string GetStartupReport()
    {
        var p = _play; var s = p?.Capture(); object[] actions, lifecycle, failures; UiLatency[] latencies;
        LocalProfileCatalog profileCatalog; DateTimeOffset? profileCatalogObservedUtc;
        lock (_reportGate) { actions = _actions.ToArray(); lifecycle = _lifecycle.ToArray(); failures = _failures.ToArray(); latencies = _uiLatencies.ToArray(); profileCatalog = _reportProfileCatalog; profileCatalogObservedUtc = _reportProfileCatalogObservedUtc; }
        var report = new { schema = "P1998-G6-result-v1", build_id = BuildId, utc = DateTimeOffset.UtcNow, pid = System.Environment.ProcessId,
            os = OS.GetName(), device = OS.GetModelName(), renderer = DisplayServer.GetName(), processor = System.Runtime.InteropServices.RuntimeInformation.ProcessArchitecture.ToString(),
            apk_sha256 = _apkSha, package = _package, godot = Engine.GetVersionInfo()["string"].AsString(), dotnet = System.Environment.Version.ToString(), release = !OS.IsDebugBuild(),
            startup = new { phase = _startupPhase, status = _startupComplete ? "READY" : _fatal.Length > 0 ? "FAIL" : "STARTING" },
            stage = 8, stage5 = "G4_PRIOR_PARTIAL_WITH_DEFERRED_ISSUES", stage6 = "G5_PRIOR_DEVICE_PASS_SCOPED_WITH_DEFERRED_ISSUES", stage7 = "G6_REGION_CLASS_EXPANSION_PARTIAL", stage8 = "G7_QUALITY_IN_PROGRESS_NOT_WHOLE_STAGE_PASS", airplane_mode = "REMOVED_BY_USER", status = _fatal.Length > 0 || p?.Faulted == true ? "FAIL" : "REVIEW_REQUIRED", smoke = _smokeResult,
            input = new { direction = _input.Direction, attack_held = _input.AttackHeld, pending_attack_press = _input.PendingAttackPress, pending_direction_press = _input.PendingDirectionPress, bounded_intent = true, direction_repeat_ms = InputIntentState.DirectionRepeatMilliseconds, attack_repeat_ms = InputIntentState.AttackRepeatMilliseconds, native_input_timing_parity = "NOT_RUN", destination = _destination is { } destination ? new { destination.Map, destination.X, destination.Y } : null, destination_route = "TAP_TO_MOVE_ASTAR_CARDINAL_ORIGINAL_TURN_STEP", movement_control = "TAP_SHORTEST_ROUTE_OR_DRAG_MANUAL_ORIGINAL_HANDLER", local_characters = profileCatalog, local_characters_observed_utc = profileCatalogObservedUtc,
                local_characters_scope = "LAST_EXPLICIT_PROFILE_DISCOVERY_SNAPSHOT; CURRENT_PLAYING_CHARACTER_IS_REPORTED_SEPARATELY; ORIGINAL_LOGIN_AUTHENTICATION_UNCHANGED", fullscreen = new { viewport = new { Size.X, Size.Y }, frame_width = _view?.FrameWidth, controller_gutters = false, native_bitmap_font_parity = "NOT_RUN" } },
            character = s is null ? null : new { s.Map, s.X, s.Y, s.Direction, s.Stats, s.EntryComplete, inventory = s.Inventory, equipment = s.Equipment, spells = s.Spells },
            save = p?.Host.LastSave, t = p?.Host.GameMilliseconds, actions, lifecycle, failures, latency_samples = latencies,
            performance = new { status = _performance.Status(DisplayServer.GetName() != "headless"), clock = MonotonicFrameMetrics.ClockSource, timestamp_frequency = _performance.Frequency, measurement_seconds = MonotonicFrameMetrics.MeasurementSeconds, active_seconds = _performance.ActiveSeconds, frame_ms = Percentiles(_performance.FramesMilliseconds), minimum_rolling_fps = _performance.MinimumRollingFps, target_minimum_fps = 30, application_dispatch_to_receipt_ms = Percentiles(latencies.Where(x => x.Kind != "save" && x.Committed && !x.HostFaulted).Select(x => x.Milliseconds)), application_save_to_receipt_ms = Percentiles(latencies.Where(x => x.Kind == "save" && x.Committed && !x.HostFaulted).Select(x => x.Milliseconds)), latency_status = latencies.Any(x => x.Committed && !x.HostFaulted) ? "MEASURED_REVIEW_REQUIRED" : "NOT_RUN_NO_SUCCESSFUL_RECEIPT", latency_failed_or_uncommitted_count = latencies.Count(x => !x.Committed || x.HostFaulted), latency_scope = "SUCCESSFUL_NONFAULTED_RECEIPTS_ONLY_IN_AGGREGATES; RAW_FAILED_SAMPLES_RETAINED; APP_DISPATCH_TO_ORIGINAL_RECEIPT_INCLUDES_QUEUE_COMMIT_DRAIN_NOT_PHYSICAL_TOUCH_OR_DRAW; SAVE_CALL_TO_ORIGINAL_SAVE_RECEIPT_NOT_RAW_SQLITE_COMMIT", physical_touch_to_display_latency = "NOT_RUN", host_input_ms = HostTimingReport(p?.Host.InputMilliseconds), host_tick_ms = HostTimingReport(p?.Host.TickMilliseconds) },
            render_observations = _view?.RenderObservations(), audio = _audio?.SnapshotStatus(), missing_asset_keys = _art?.Missing.ToArray(), substituted_asset_keys = _art?.Substitutions.ToArray(), native495_visual_parity = "NOT_RUN", fixture = OS.GetCmdlineUserArgs().Any(a => a is "--g2-combined-smoke" or "--g2-combined-reopen-smoke") ? "ISOLATED_PRIOR_NORMAL_GUI_COMBAT_PENDING_SPAWN_PRESSURE_NOT_STAGE5" : OS.GetCmdlineUserArgs().Contains("--g2-door-fixture") ? "SYNTHETIC_UNLOCK_ISOLATED_HANDLER_FIXTURE_NOT_NORMAL_QUEST_UNLOCK_NOT_STAGE5_ACCEPTANCE" : (OS.GetCmdlineUserArgs().Contains("--g2-continue-smoke") || OS.GetCmdlineUserArgs().Contains("--g2-combat-smoke")) ? "ISOLATED_NORMAL_EARNED_CHECKPOINT_UI_ONLY_NOT_STAGE5_ACCEPTANCE" : "NO_FIXTURE_DEFAULT_NORMAL_PLAY", physical_s10fe = OS.GetName() == "Android" ? "MEASURED_REVIEW_REQUIRED" : "NOT_RUN",
            assemblies = new { ui_mvid = typeof(Main).Assembly.ManifestModule.ModuleVersionId, host_mvid = typeof(PlaySession).Assembly.ManifestModule.ModuleVersionId } };
        return JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
    }
    private void Export()
    {
        string local = IO.Path.Combine(_root, "P1998-G6-result-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".json");
        try { WriteReport(local); _exportDialog.CurrentFile = IO.Path.GetFileName(local); _exportDialog.PopupCenteredRatio(.8f); Status("결과 생성 완료 · 저장 위치를 선택하세요."); }
        catch (Exception e) { Failure("export", e); }
    }
    private static void AtomicWrite(string path, string text)
    {
        IO.Directory.CreateDirectory(IO.Path.GetDirectoryName(IO.Path.GetFullPath(path))!); string pending = path + ".pending-" + Guid.NewGuid().ToString("N");
        using (var f = new IO.FileStream(pending, IO.FileMode.CreateNew, IO.FileAccess.Write, IO.FileShare.None)) { byte[] b = System.Text.Encoding.UTF8.GetBytes(text); f.Write(b); f.Flush(true); }
        IO.File.Move(pending, path, true);
    }
    private string PrepareContent()
    {
        byte[] bytes = Godot.FileAccess.GetFileAsBytes("res://assets/game-data.zip"); if (bytes.Length == 0) throw new IO.InvalidDataException("Bundled original content absent.");
        string hash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        using var manifest = JsonDocument.Parse(Godot.FileAccess.GetFileAsString("res://assets/content-manifest.json"));
        if (manifest.RootElement.GetProperty("archive_sha256").GetString() != hash) throw new IO.InvalidDataException("Original content hash mismatch.");
        string target = IO.Path.Combine(_root, "content-" + hash[..16]), complete = IO.Path.Combine(target, "complete.sha256");
        if (!IO.File.Exists(complete))
        {
            string staging = target + "-extract-" + Guid.NewGuid().ToString("N"); IO.Directory.CreateDirectory(staging);
            using var stream = new IO.MemoryStream(bytes, false); using var zip = new ZipArchive(stream, ZipArchiveMode.Read);
            foreach (var entry in zip.Entries)
            {
                _stop.Token.ThrowIfCancellationRequested(); string output = IO.Path.GetFullPath(IO.Path.Combine(staging, entry.FullName));
                if (!entry.FullName.StartsWith("game-data/", StringComparison.Ordinal) || !output.StartsWith(staging + IO.Path.DirectorySeparatorChar, StringComparison.Ordinal)) throw new IO.InvalidDataException("Unsafe content path.");
                IO.Directory.CreateDirectory(IO.Path.GetDirectoryName(output)!); using var input = entry.Open(); using var file = IO.File.Create(output); input.CopyTo(file);
            }
            IO.File.WriteAllText(IO.Path.Combine(staging, "complete.sha256"), hash); IO.Directory.Move(staging, target);
        }
        if (IO.File.ReadAllText(complete) != hash) throw new IO.InvalidDataException("Content receipt mismatch.");
        string data = IO.Path.Combine(target, "game-data");
        foreach (var file in manifest.RootElement.GetProperty("files").EnumerateArray())
        {
            _stop.Token.ThrowIfCancellationRequested(); string path = IO.Path.Combine(data, file.GetProperty("path").GetString()!);
            using var input = IO.File.OpenRead(path); if (Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant() != file.GetProperty("sha256").GetString()) throw new IO.InvalidDataException("Original content changed: " + file.GetProperty("path").GetString());
        }
        return data;
    }
    private void ObservePackage()
    {
        if (!OS.HasFeature("android")) return;
        _apkSha = "PENDING";
        try
        {
            var activity = Engine.GetSingleton("AndroidRuntime").Call("getActivity").AsGodotObject();
            string path = activity.Call("getPackageCodePath").AsString(); _package = activity.Call("getPackageName").AsString();
            _ = Task.Run(() => { try { using var file = IO.File.OpenRead(path); _apkSha = Convert.ToHexString(SHA256.HashData(file)).ToLowerInvariant(); } catch (Exception e) { _apkSha = "FAIL: " + e.GetType().Name; } });
        }
        catch (Exception e) { _apkSha = "FAIL: " + e.GetType().Name; }
    }
}
