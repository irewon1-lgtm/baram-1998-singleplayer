using Godot;
using P1998.Embedded;

public sealed record HudCommand(string Kind, int Number = 0, uint EntityId = 0, string Text = "", long Sequence = 0);

/// <summary>Touch presentation over the original FRAME.EPF. All numbers, inventory slots and
/// choices originate in ClientSceneSnapshot. This control emits intentions and never edits game state.</summary>
public partial class GameHud : Control
{
    public bool MusicEnabled { get; set; } = true;
    public event Action<HudCommand>? Command;
    public event Action<int>? DirectionHeld;
    public event Action<bool>? AttackHeld;
    public event Action? InputCanceled;
    public event Action? DirectionCanceled;
    public ArtCatalog? Art { get; set; }
    public Control NativeOverlay { get; } = new NativeHudCanvas() { Name = "NativeHud", MouseFilter = MouseFilterEnum.Ignore, TextureFilter = TextureFilterEnum.Nearest, Size = new(640, 480) };
    public Dictionary<string, Button> Buttons { get; } = new();
    public Func<int, Texture2D?>? IconTexture { get; set; }
    public int SelfHairTone { get; set; }
    public int SelfSkinTone { get; set; }
    public uint SelectedTarget { get; set; }
    public bool ModalOpen => _modal.Visible;

    private readonly Control _nativeRight = new() { Name = "OriginalRightPanel", MouseFilter = MouseFilterEnum.Ignore };
    private readonly HBoxContainer _actions = new() { Name = "InFrameActions", MouseFilter = MouseFilterEnum.Ignore };
    private Control _pad = null!;
    private float _frameWidth = 640;
    private bool _showPad;
    private readonly PanelContainer _modal = new() { Visible = false };
    private readonly VBoxContainer _modalContent = new();
    private readonly Label _identity = new(), _equipment = new(), _location = new(), _chat = new(), _status = new(), _nameLine = new(), _nativeEntries = new();
    private readonly Control _nativeRows = new() { Name = "ScrollRows", MouseFilter = MouseFilterEnum.Ignore };
    private readonly HashSet<string> _nativeRowKeys = new();
    private readonly HashSet<string> _dynamicKeys = new();
    private readonly Label[] _attributes = { new() { Name = "MightValue" }, new() { Name = "WillValue" }, new() { Name = "GraceValue" } };
    private readonly Label _hp = new() { Name = "HpValue" }, _mp = new() { Name = "MpValue" },
        _level = new() { Name = "LevelValue" }, _coordinates = new() { Name = "CoordinatesValue" },
        _experience = new() { Name = "ExperienceValue" }, _coins = new() { Name = "CoinsValue" };
    private ClientSceneSnapshot? _scene;
    private string _localPanel = "", _modalKey = "", _inventoryKey = "";
    private int _held = -1, _directionPointer = -1, _attackPointer = -1;
    private int _uiTouchPointer = -1;
    private Vector2 _uiTouchPosition, _uiTouchOrigin;
    private bool _uiTouchDragged;
    private ScrollContainer? _uiTouchScroll;
    private bool _attackHeld, _mouseDirection, _mouseAttack;
    private string _nativePanel = "equipment";
    private string _nativeRowsVersion = "";
    private int _nativePage;
    private byte[]? _nativeLook;
    private (uint Hp, uint MaxHp, uint Mp, uint MaxMp) _nativeVitals;
    private string _nativeCanvasVersion = "", _nativeEntryStyle = "";
    private Texture2D _nativeHpBar = null!, _nativeMpBar = null!, _nativeDigits = null!, _nativeChat = null!;
    private Texture2D _nativeProfile2 = null!, _nativeProfile3 = null!;
    private Texture2D[] _legendIcons = Array.Empty<Texture2D>();
    private bool _busy, _hostFaulted;
    private string _name = "";
    private SceneSpellSnapshot? _spellPrompt;
    private Label? _inputError, _recoveryStatus;
    // Native SELFLOOK page1, draw0x473960. The client's RECT order is
    // top,left,bottom,right; these are the translated x,y source coordinates.
    // Weapon/armor/shield are composite sprite layers, not extra ground-icon boxes.
    private static readonly (byte Slot, Vector2 Center, string Name)[] NativeEquipmentCells = {
        (4, new(97, 133), "투구"), (7, new(123, 189), "왼손"), (8, new(72, 189), "오른손")
    };

    public bool InitializationComplete { get; private set; }
    public override void _Ready()
    {
        Name = "GameHud"; MouseFilter = MouseFilterEnum.Ignore;
        SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect);
        AddThemeFontSizeOverride("font_size", 18);
        ((NativeHudCanvas)NativeOverlay).OwnerHud = this;
        _nativeHpBar = ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/bar-hp.png")
            ?? throw new System.IO.InvalidDataException("Original HP bar resource is missing.");
        _nativeMpBar = ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/bar-mp.png")
            ?? throw new System.IO.InvalidDataException("Original MP bar resource is missing.");
        _nativeDigits = ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/digits-original.png")
            ?? throw new System.IO.InvalidDataException("Original numeric glyph resource is missing.");
        _nativeChat = ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/chatback-original.png")
            ?? throw new System.IO.InvalidDataException("Original chat row resource is missing.");
        _nativeProfile2 = ResourceLoader.Load<Texture2D>("res://assets/runtime/r15-hud/selflok2.png")
            ?? throw new System.IO.InvalidDataException("Original second profile page is missing.");
        _nativeProfile3 = ResourceLoader.Load<Texture2D>("res://assets/runtime/r15-hud/selflok3.png")
            ?? throw new System.IO.InvalidDataException("Original third profile page is missing.");
        _legendIcons = Enumerable.Range(0, 16).Select(i => ResourceLoader.Load<Texture2D>("res://assets/runtime/r15-hud/legend-icon-" + i + ".png")
            ?? throw new System.IO.InvalidDataException("Original legend icon is missing: " + i)).ToArray();
        AddChild(NativeOverlay); NativeOverlay.AddChild(_nativeRight);
        BuildNativePanel(); BuildTouchControls();
        var style = new StyleBoxFlat { BgColor = new Color("362719"), BorderColor = new Color("bf925e"), BorderWidthLeft = 2,
            BorderWidthTop = 2, BorderWidthRight = 2, BorderWidthBottom = 2,
            ContentMarginLeft = 18, ContentMarginTop = 16, ContentMarginRight = 18, ContentMarginBottom = 16 };
        _modal.AddThemeStyleboxOverride("panel", style);
        _modal.MouseFilter = MouseFilterEnum.Stop; _modal.ZIndex = 20;
        _modal.AddChild(_modalContent); _modalContent.AddThemeConstantOverride("separation", 10); AddChild(_modal);
        _status.MouseFilter = MouseFilterEnum.Ignore; _status.AutowrapMode = TextServer.AutowrapMode.WordSmart;
        _status.AddThemeFontSizeOverride("font_size", 15); _status.AddThemeColorOverride("font_color", new Color("f1d5a0"));
        AddChild(_status);
        Resized += Layout; VisibilityChanged += () => { if (!IsVisibleInTree()) CancelInputs(); };
        ConfigureFrame(_frameWidth); Layout();
        InitializationComplete = true;
    }

    private void BuildNativePanel()
    {
        // These are the already-decoded original panels, at native 640x480 coordinates.
        // Snapshot values replace only the text; the scroll artwork is not generated.
        NativeLabel(_identity, new(504, 87), new(108, 16), 10);
        NativeLabel(_nativeEntries, new(449, 31), new(164, 236), 10); _nativeEntries.Visible = false;
        NativeLabel(_equipment, new(445, 222), new(169, 49), 10);
        NativeLabel(_location, new(445, 330), new(173, 42), 10);
        NativeLabel(_nameLine, new(439, 377), new(180, 15), 10);
        // USERSTAT's authored rows are only 13px high. Independent labels keep the
        // font's line spacing from drifting into icons, later rows or outside the frame.
        // Exact 4.95 USERSTAT field offsets from native 0x497060/0x4973d0,
        // relative to the already-used USERSTAT origin (434,376).
        NativeValue(_level, new(594, 379), new(27, 11));
        NativeValue(_attributes[0], new(509, 393), new(27, 11));
        NativeValue(_attributes[1], new(554, 393), new(27, 11));
        NativeValue(_attributes[2], new(597, 393), new(27, 11));
        NativeValue(_hp, new(535, 406), new(91, 11));
        NativeValue(_mp, new(535, 419), new(91, 11));
        NativeValue(_experience, new(535, 432), new(91, 11));
        NativeValue(_coins, new(535, 445), new(91, 11));
        NativeValue(_coordinates, new(535, 458), new(91, 11));
        NativeLabel(_chat, new(23, 392), new(388, 48), 11); _chat.ClipText = true;
        _chat.AutowrapMode = TextServer.AutowrapMode.WordSmart;
        _chat.AddThemeColorOverride("font_color", Colors.Black);
        _chat.AddThemeConstantOverride("shadow_offset_x", 0); _chat.AddThemeConstantOverride("shadow_offset_y", 0);
        _nativeRight.RemoveChild(_chat); NativeOverlay.AddChild(_chat);
        _nativeRight.AddChild(_nativeRows);
        foreach (var label in new[] { _identity, _equipment, _location })
        {
            label.AddThemeColorOverride("font_color", new Color("352717"));
            label.AddThemeConstantOverride("shadow_offset_x", 0); label.AddThemeConstantOverride("shadow_offset_y", 0);
        }
        string[] tabs = { "가방", "장비", "기술" }; string[] kinds = { "inventory", "equipment", "spells" };
        for (int i = 0; i < tabs.Length; i++)
        {
            string panel = kinds[i];
            var button = Button("native-" + panel, tabs[i], () => SelectNativePanel(panel), 10);
            // Keep the source panel's own bottom page arrows visible.
            button.CustomMinimumSize = new(0, 23); button.Position = new(443 + i * 59, 302); button.Size = new(56, 23);
            foreach (string state in new[] { "normal", "hover", "pressed", "disabled" })
            {
                var compact = (StyleBoxFlat)button.GetThemeStylebox(state).Duplicate();
                compact.ContentMarginTop = compact.ContentMarginBottom = 1;
                button.AddThemeStyleboxOverride(state, compact);
            }
            button.Size = new(56, 23);
            _nativeRight.AddChild(button);
        }
    }

    private void NativeLabel(Label label, Vector2 position, Vector2 size, int fontSize)
    {
        label.AddThemeFontSizeOverride("font_size", fontSize);
        label.Position = position; label.Size = size; label.MouseFilter = MouseFilterEnum.Ignore;
        label.AutowrapMode = TextServer.AutowrapMode.WordSmart;
        label.AddThemeColorOverride("font_color", new Color("fff0c7"));
        label.AddThemeColorOverride("font_shadow_color", new Color("211608"));
        label.AddThemeConstantOverride("shadow_offset_x", 1); label.AddThemeConstantOverride("shadow_offset_y", 1);
        _nativeRight.AddChild(label);
    }

    private void NativeValue(Label label, Vector2 position, Vector2 size)
    {
        NativeLabel(label, position, size, 11);
        label.AutowrapMode = TextServer.AutowrapMode.Off; label.ClipText = true;
        label.HorizontalAlignment = HorizontalAlignment.Right; label.VerticalAlignment = VerticalAlignment.Center;
        // Text stays available in the public presentation tree, while the canvas
        // draws the original 9x11 palette glyphs instead of a platform font.
        label.SelfModulate = new Color(1, 1, 1, 0); label.Size = size;
    }

    private void BuildTouchControls()
    {
        // Touch targets live inside the original chat/footer area. No screen space is
        // reserved for external left/right controller gutters. Map touches are the
        // default movement input; an optional pad stays inside the scene.
        NativeOverlay.AddChild(_actions); _actions.AddThemeConstantOverride("separation", 2);
        var pad = new GridContainer { Columns = 3, Name = "InFrameDirectionPad", Visible = false }; _pad = pad;
        NativeOverlay.AddChild(pad); pad.AddThemeConstantOverride("h_separation", 1); pad.AddThemeConstantOverride("v_separation", 1);
        for (int i = 0; i < 9; i++)
        {
            int direction = i switch { 1 => 0, 5 => 1, 7 => 2, 3 => 3, _ => -1 };
            if (direction < 0) { pad.AddChild(new Control { CustomMinimumSize = new(28, 28), MouseFilter = MouseFilterEnum.Ignore }); continue; }
            string text = direction switch { 0 => "↑", 1 => "→", 2 => "↓", _ => "←" };
            var button = Button("direction-" + direction, text, null, 14); button.CustomMinimumSize = new(28, 28);
            foreach (string state in new[] { "normal", "hover", "pressed", "disabled" })
            {
                var compact = (StyleBoxFlat)button.GetThemeStylebox(state).Duplicate();
                compact.ContentMarginLeft = compact.ContentMarginRight = compact.ContentMarginTop = compact.ContentMarginBottom = 1;
                button.AddThemeStyleboxOverride(state, compact);
            }
            button.ButtonDown += () => Hold(direction);
            button.ButtonUp += () => { if (_held == direction) Hold(-1); };

            pad.AddChild(button);
        }
        InFrameButton("talk", "말하기", () => Emit("talk"));
        InFrameButton("menu", "메뉴", () => OpenLocal("menu"));
        InFrameButton("door", "문열기", () => Emit("door"));
        InFrameButton("save", "저장", () => Emit("save"));
        InFrameButton("chat", "채팅", () => OpenLocal("chat"));
        InFrameButton("pickup", "줍기", () => Emit("pickup"));
        var attack = InFrameButton("attack", "공격", () => Emit("attack"));
        // Global indexed touch/mouse handling below owns physical holds. Pressed stays available
        // for keyboard and programmatic single-attack callers.
        attack.ButtonDown += () => HoldAttack(true);
        attack.ButtonUp += () => HoldAttack(false);
        // Historical keyboard/test callers retain their actions; the visible controls
        // are the original scroll tabs and the menu's export action.
        foreach (var entry in new[] { ("inventory", "가방"), ("equipment", "장비"), ("spells", "기술") })
        { string panel = entry.Item1; var legacy = Button(panel, entry.Item2, () => OpenLocal(panel)); legacy.Visible = false; NativeOverlay.AddChild(legacy); }
        var export = Button("export", "결과 내보내기", () => Emit("export")); export.Visible = false; NativeOverlay.AddChild(export);
    }

    private Button InFrameButton(string key, string text, Action pressed)
    {
        var button = Button(key, text, pressed, 10); button.Name = "InFrame-" + key;
        button.CustomMinimumSize = new(0, 24); button.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        foreach (string state in new[] { "normal", "hover", "pressed", "disabled" })
        {
            var style = new StyleBoxFlat { BgColor = state == "pressed" ? new Color("48321f") : new Color(0, 0, 0, 0),
                ContentMarginLeft = 1, ContentMarginRight = 1, ContentMarginTop = 1, ContentMarginBottom = 1 };
            button.AddThemeStyleboxOverride(state, style);
        }
        button.AddThemeColorOverride("font_color", Colors.Black);
        button.AddThemeColorOverride("font_hover_color", Colors.Black);
        button.AddThemeColorOverride("font_pressed_color", new Color("fff0c7"));
        _actions.AddChild(button); return button;
    }

    public void ConfigureFrame(float width)
    {
        if (!float.IsFinite(width) || width < 640) throw new ArgumentOutOfRangeException(nameof(width));
        _frameWidth = width; NativeOverlay.Size = new(width, 480); _nativeRight.Position = new(width - 640, 0);
        _chat.Size = new(width - 252, 48); _actions.Position = new(23, 442); _actions.Size = new(width - 252, 26);
        if (_pad is not null) { _pad.Position = new(22, 276); _pad.Size = new(86, 86); }
        NativeOverlay.QueueRedraw();
    }

    private Button Button(string key, string text, Action? pressed, int size = 18, bool dynamic = false)
    {
        var button = new Button { Text = KoreanText.Display(text), TooltipText = KoreanText.Display(text), ClipText = true, CustomMinimumSize = new(0, 54), FocusMode = FocusModeEnum.None,
            MouseFilter = MouseFilterEnum.Stop, SizeFlagsHorizontal = SizeFlags.ExpandFill };
        button.AddThemeFontSizeOverride("font_size", size);
        button.AddThemeColorOverride("font_color", new Color("ffedc1"));
        var normal = new StyleBoxFlat { BgColor = new Color("48321f"), BorderColor = new Color("9a7247"),
            BorderWidthLeft = 1, BorderWidthTop = 1, BorderWidthRight = 1, BorderWidthBottom = 1,
            CornerRadiusTopLeft = 3, CornerRadiusTopRight = 3, CornerRadiusBottomLeft = 3, CornerRadiusBottomRight = 3,
            ContentMarginLeft = 8, ContentMarginRight = 8, ContentMarginTop = 6, ContentMarginBottom = 6 };
        button.AddThemeStyleboxOverride("normal", normal);
        var hover = (StyleBoxFlat)normal.Duplicate(); hover.BgColor = new Color("674a2c"); button.AddThemeStyleboxOverride("hover", hover);
        var down = (StyleBoxFlat)normal.Duplicate(); down.BgColor = new Color("2e2115"); button.AddThemeStyleboxOverride("pressed", down);
        if (pressed is not null) button.Pressed += () => { if (key != "attack") ResetHeld(); if (!_busy || key is "attack" or "menu" or "export" or "menu-return" or "menu-export" or "local-close") pressed(); };
        Buttons[key] = button; if (dynamic) _dynamicKeys.Add(key); return button;
    }

    private bool CanHold => IsVisibleInTree() && !ModalOpen && !_hostFaulted && _scene?.EntryComplete == true;
    private void Hold(int direction)
    {
        if (direction >= 0 && !CanHold) return;
        if (_held != direction)
        {
            if (Buttons.TryGetValue("direction-" + _held, out var prior)) prior.Modulate = Colors.White;
            _held = direction;
            if (Buttons.TryGetValue("direction-" + direction, out var current)) current.Modulate = new Color("ffe3a4");
            DirectionHeld?.Invoke(direction);
        }
    }
    private void HoldAttack(bool held)
    {
        if (held && !CanHold) return;
        if (_attackHeld != held)
        {
            _attackHeld = held;
            if (Buttons.TryGetValue("attack", out var attack)) attack.Modulate = held ? new Color("ffe3a4") : Colors.White;
            AttackHeld?.Invoke(held);
        }
    }
    private int PadDirection(Vector2 point)
    {
        if (!_pad.IsVisibleInTree()) return -1;
        Rect2 bounds = _pad.GetGlobalRect();
        if (!bounds.HasPoint(point)) return -1;
        Vector2 delta = point - bounds.GetCenter();
        if (Mathf.Abs(delta.X) < bounds.Size.X / 7 && Mathf.Abs(delta.Y) < bounds.Size.Y / 7) return -1;
        return Mathf.Abs(delta.X) > Mathf.Abs(delta.Y) ? (delta.X > 0 ? 1 : 3) : (delta.Y > 0 ? 2 : 0);
    }
    public override void _Input(InputEvent e)
    {
        if (!IsVisibleInTree() || _pad is null) return;
        // Physical holds retain their own indexed paths below. Other native UI
        // controls receive the first finger through the same GUI mouse path as
        // desktop input; this does not depend on platform mouse emulation.
        if (e is InputEventMouse { Device: -1 } emulated &&
            (_uiTouchPointer >= 0 || IsGuiTouchPoint(emulated.Position)))
        { GetViewport().SetInputAsHandled(); return; }
        if (e is InputEventScreenTouch touch)
        {
            bool owned = false;
            if (touch.Index == _uiTouchPointer && (!touch.Pressed || touch.Canceled))
            {
                _uiTouchPointer = -1;
                TouchGuiMouse(touch.Canceled || _uiTouchDragged ? new(-10000, -10000) : touch.Position, false);
                _uiTouchScroll = null; owned = true;
            }
            else if (touch.Pressed && !touch.Canceled && _uiTouchPointer < 0 && IsGuiTouchPoint(touch.Position))
            {
                _uiTouchPointer = touch.Index; _uiTouchPosition = _uiTouchOrigin = touch.Position; _uiTouchDragged = false;
                _uiTouchScroll = FindChildren("*", "ScrollContainer", true, false).OfType<ScrollContainer>()
                    .LastOrDefault(s => s.IsVisibleInTree() && s.GetGlobalRect().HasPoint(touch.Position));
                TouchGuiMouse(touch.Position, true); owned = true;
            }
            else if (touch.Canceled && (touch.Index == _directionPointer || touch.Index == _attackPointer))
            { CancelInputs(); owned = true; }
            else if (touch.Pressed && !touch.Canceled && CanHold)
            {
                if (_directionPointer < 0 && !_mouseDirection && (_pad.IsVisibleInTree() && _pad.GetGlobalRect().HasPoint(touch.Position)))
                { _directionPointer = touch.Index; Hold(PadDirection(touch.Position)); owned = true; }
                else if (_attackPointer < 0 && !_mouseAttack && Buttons["attack"].GetGlobalRect().HasPoint(touch.Position))
                { _attackPointer = touch.Index; HoldAttack(true); owned = true; }
            }
            else if (!touch.Pressed || touch.Canceled)
            {
                if (_directionPointer == touch.Index) { _directionPointer = -1; Hold(-1); owned = true; }
                if (_attackPointer == touch.Index) { _attackPointer = -1; HoldAttack(false); owned = true; }
            }
            if (owned) GetViewport().SetInputAsHandled();
        }
        else if (e is InputEventScreenDrag uiDrag && uiDrag.Index == _uiTouchPointer)
        {
            Vector2 delta = uiDrag.Position - _uiTouchPosition; _uiTouchPosition = uiDrag.Position;
            if (uiDrag.Position.DistanceTo(_uiTouchOrigin) > 4) _uiTouchDragged = true;
            if (_uiTouchScroll is not null && GodotObject.IsInstanceValid(_uiTouchScroll))
                _uiTouchScroll.ScrollVertical -= (int)Math.Round(delta.Y / Math.Max(.1f, _uiTouchScroll.GetGlobalTransformWithCanvas().Scale.Y));
            GetViewport().PushInput(new InputEventMouseMotion { Position = uiDrag.Position, GlobalPosition = uiDrag.Position,
                Relative = delta, ButtonMask = MouseButtonMask.Left, Device = -2 }, true);
            GetViewport().SetInputAsHandled();
        }
        else if (e is InputEventScreenDrag drag && drag.Index == _directionPointer)
        {
            int direction = PadDirection(drag.Position);
            if (direction < 0) { Hold(-1); DirectionCanceled?.Invoke(); } else Hold(direction);
            GetViewport().SetInputAsHandled();
        }
        else if (e is InputEventScreenDrag attackDrag && attackDrag.Index == _attackPointer)
        { GetViewport().SetInputAsHandled(); }
        else if (e is InputEventMouseButton mouse && mouse.ButtonIndex == MouseButton.Left)
        {
            // Godot marks synthetic touch-to-mouse events with DEVICE_ID_EMULATION (-1).
            // Consuming them here prevents a second pointer from replaying the same attack.
            bool hit = (_pad.IsVisibleInTree() && _pad.GetGlobalRect().HasPoint(mouse.Position)) || Buttons["attack"].GetGlobalRect().HasPoint(mouse.Position);
            if (mouse.Device == -1 && (hit || _directionPointer >= 0 || _attackPointer >= 0))
            { GetViewport().SetInputAsHandled(); return; }
            bool owned = false;
            if (mouse.Pressed && CanHold)
            {
                if (_directionPointer < 0 && (_pad.IsVisibleInTree() && _pad.GetGlobalRect().HasPoint(mouse.Position)))
                { _mouseDirection = true; Hold(PadDirection(mouse.Position)); owned = true; }
                else if (_attackPointer < 0 && Buttons["attack"].GetGlobalRect().HasPoint(mouse.Position))
                { _mouseAttack = true; HoldAttack(true); owned = true; }
            }
            else if (!mouse.Pressed)
            {
                if (_mouseDirection) { _mouseDirection = false; Hold(-1); owned = true; }
                if (_mouseAttack) { _mouseAttack = false; HoldAttack(false); owned = true; }
            }
            if (owned) GetViewport().SetInputAsHandled();
        }
        else if (e is InputEventMouseMotion motion && _mouseDirection)
        {
            int direction = PadDirection(motion.Position);
            if (direction < 0) { Hold(-1); DirectionCanceled?.Invoke(); } else Hold(direction);
            GetViewport().SetInputAsHandled();
        }
    }
    private bool IsGuiTouchPoint(Vector2 point)
    {
        if (ModalOpen) return true;
        if (_pad.IsVisibleInTree() && _pad.GetGlobalRect().HasPoint(point)) return false;
        if (Buttons["attack"].IsVisibleInTree() && Buttons["attack"].GetGlobalRect().HasPoint(point)) return false;
        return ModalOpen || Buttons.Values.Any(b => b.IsVisibleInTree() && b.GetGlobalRect().HasPoint(point))
            || _nativeRows.FindChildren("*", "ScrollContainer", true, false).OfType<ScrollContainer>()
                .Any(s => s.IsVisibleInTree() && s.GetGlobalRect().HasPoint(point));
    }
    private void TouchGuiMouse(Vector2 position, bool pressed)
    {
        GetViewport().PushInput(new InputEventMouseMotion { Position = position, GlobalPosition = position, Device = -2 }, true);
        GetViewport().PushInput(new InputEventMouseButton { Position = position, GlobalPosition = position,
            ButtonIndex = MouseButton.Left, ButtonMask = pressed ? MouseButtonMask.Left : 0, Pressed = pressed, Device = -2 }, true);
    }
    public void ResetHeld()
    {
        _directionPointer = _attackPointer = -1; _mouseDirection = _mouseAttack = false;
        Hold(-1); HoldAttack(false);
    }
    private void CancelInputs()
    {
        // A cancel must also discard the controller's one pending press. Ordinary pointer-up
        // only releases its level intent, so a valid short tap can survive a slow render poll.
        if (_uiTouchPointer >= 0)
        {
            _uiTouchPointer = -1; _uiTouchScroll = null;
            TouchGuiMouse(new(-10000, -10000), false);
        }
        ResetHeld(); InputCanceled?.Invoke();
    }
    public override void _Notification(int what)
    { if (what == NotificationApplicationFocusOut || what == NotificationApplicationPaused) CancelInputs(); }
    public override void _ExitTree() => CancelInputs();

    private void Emit(string kind, int number = 0, uint entityId = 0, string text = "", long sequence = 0)
    {
        if (kind != "attack") ResetHeld();
        if (ModalOpen && kind is "attack" or "talk" or "pickup" or "door") return;
        Command?.Invoke(new(kind, number, entityId, text, sequence));
    }

    public void Present(ClientSceneSnapshot scene, string displayName, string status, bool busy, bool hostFaulted = false)
    {
        bool newFault = hostFaulted && !_hostFaulted;
        _scene = scene; _name = displayName; _busy = busy; _hostFaulted = hostFaulted;
        if (newFault)
        {
            // The existing recovery menu may cover a pending authoritative prompt, but it
            // never answers/hides that prompt in ClientModel. Stop owns its cancellation.
            _localPanel = "menu"; _spellPrompt = null; _modalKey = ""; CancelInputs();
        }
        // A single original action can span several render polls. Keep an already-held direction
        // until release; Main fences dispatch while that action is pending and resets on host pause.
        if (!scene.EntryComplete || hostFaulted) ResetHeld();
        // The snapshot has no authoritative title; do not substitute the display name.
        _identity.Text = "";
        _nameLine.Text = displayName;
        _level.Text = scene.Stats.Level.ToString().PadLeft(3);
        _coordinates.Text = $"{scene.X:D4}/{scene.Y:D4}";
        _attributes[0].Text = scene.Stats.Might.ToString().PadLeft(3);
        _attributes[1].Text = scene.Stats.Will.ToString().PadLeft(3);
        _attributes[2].Text = scene.Stats.Grace.ToString().PadLeft(3);
        _hp.Text = scene.Stats.Hp.ToString();
        _hp.TooltipText = $"체력 {scene.Stats.Hp}/{scene.Stats.MaxHp}";
        _mp.Text = scene.Stats.Mp.ToString();
        _mp.TooltipText = $"기력 {scene.Stats.Mp}/{scene.Stats.MaxMp}";
        _experience.Text = scene.Stats.Experience.ToString();
        _coins.Text = scene.Stats.Coins.ToString();
        var vitals = (scene.Stats.Hp, scene.Stats.MaxHp, scene.Stats.Mp, scene.Stats.MaxMp);
        if (_nativeVitals != vitals) { _nativeVitals = vitals; NativeOverlay.QueueRedraw(); }
        _equipment.Text = scene.Equipment.Length == 0 ? "장착 장비 없음" : string.Join("\n", scene.Equipment.Take(3).Select(e => KoreanText.Display(e.Name)));
        _location.Text = $"{KoreanText.Display(scene.MapTitle)}\n{scene.X}, {scene.Y}  ·  지도 {scene.Map}";
        // Original 0x0D bytes cannot distinguish self speech from SendLog. Only the
        // embedded frame's explicit provenance permits system-log translation; typed speech stays opaque.
        var chatLines = scene.Events.Where(e => e.Kind is "message" or "speech").TakeLast(1)
            .Select(e => e.Kind == "speech"
                ? KoreanText.Speech(e.Text, e.SystemGenerated, e.EntityId == scene.SelfId || scene.Players.Any(p => p.Id == e.EntityId))
                : KoreanText.Display(e.Text));
        bool routineStatus = status.StartsWith("원본 응답 수신 · ", StringComparison.Ordinal);
        _chat.Text = string.Join("\n", routineStatus ? chatLines : chatLines.Append(KoreanText.Display(status)));
        _status.Text = KoreanText.Display(status);
        if (_recoveryStatus is not null) _recoveryStatus.Text = KoreanText.Display(status);
        foreach (var pair in Buttons)
            pair.Value.Disabled = (hostFaulted && pair.Key is "menu-save" or "menu-ride" or "menu-original-help") || (busy && !pair.Key.StartsWith("direction-", StringComparison.Ordinal) && pair.Key is not ("attack" or "menu" or "export" or "menu-return" or "menu-export" or "local-close"))
                || (_nativeRowKeys.Contains(pair.Key) && !CanUseNativeRows);
        UpdateNativePanel();
        byte[]? look = scene.SelfLook?.Appearance;
        if ((look is null) != (_nativeLook is null) || (look is not null && (_nativeLook is null || !look.AsSpan().SequenceEqual(_nativeLook))))
        { _nativeLook = look?.ToArray(); NativeOverlay.QueueRedraw(); }
        // Native draw commands persist between frames. Invalidate only when one of
        // DrawNativePanel's inputs changes; labels and modal controls keep their own
        // independent redraws. Rebuilding identical atlas/digit commands every50ms
        // adds UI/render-thread work without changing any visible pixel.
        string canvasVersion = $"{_nativePanel}:{_nativePage}:{scene.Stats.Totem}:{SelfHairTone}:{SelfSkinTone}:{scene.Stats.Hp}:{scene.Stats.MaxHp}:{scene.Stats.Mp}:{scene.Stats.MaxMp}:"
            + $"{_level.Text}:{_attributes[0].Text}:{_attributes[1].Text}:{_attributes[2].Text}:{_experience.Text}:{_coins.Text}:{_coordinates.Text}:"
            + (look is null ? "no-look" : Convert.ToHexString(look)) + ":"
            + string.Join("|", scene.Equipment.Select(e => $"{e.WireSlot}:{e.Icon}")) + ":" + scene.Cosmetics;
        if (_nativeCanvasVersion != canvasVersion)
        { _nativeCanvasVersion = canvasVersion; NativeOverlay.QueueRedraw(); }
        RefreshModal();
    }

    private partial class NativeHudCanvas : Control
    {
        public GameHud? OwnerHud { get; set; }
        public override void _Draw() => OwnerHud?.DrawNativePanel(this);
    }
    private void DrawNativePanel(CanvasItem target)
    {
        if (Art is null) return;
        // Native chat: default white base and original CHATBACK frame0 repeated
        // per 13px row. The bottom action row is an Android touch adaptation.
        var chatRect = new Rect2(14, 390, _frameWidth - 220, 78);
        target.DrawRect(chatRect, Colors.White);
        target.DrawTextureRect(_nativeChat, chatRect, tile: true);
        target.DrawSetTransform(new Vector2(_frameWidth - 640, 0));
        string panel = _nativePanel == "inventory" ? "ITEMINV" : _nativePanel == "spells" ? "SPELLINV" : "SELFLOOK";
        // SELFLOOK stores its signed origin at (-96,-144); other panels start at (0,0).
        int backdrop = panel == "SELFLOOK" && _scene is { } backdropScene ? Math.Clamp(backdropScene.Stats.Totem, 0, 3) : 0;
        if (panel == "SELFLOOK" && _nativePage > 0)
            target.DrawTexture(_nativePage == 1 ? _nativeProfile2 : _nativeProfile3, new Vector2(434, 12));
        else
            Art.Ui(target, panel, backdrop, new Vector2(434, 12) + (panel == "SELFLOOK" ? new Vector2(96, 144) : Vector2.Zero));
        Art.Ui(target, "USERSTAT", 0, new(434, 376));
        if (_scene is { } scene)
        {
            // USERSTAT's original red-heart and blue-mana rows. The requested touch
            // adaptation preserves their exact numbers and adds a bounded ratio fill.
            DrawVital(target, new Vector2(524, 408), scene.Stats.Hp, scene.Stats.MaxHp, _nativeHpBar);
            DrawVital(target, new Vector2(524, 421), scene.Stats.Mp, scene.Stats.MaxMp, _nativeMpBar);
        }
        if (panel == "SELFLOOK" && _nativePage == 0 && _scene is { } equipmentScene)
        {
            if (equipmentScene.SelfLook is { } look && Art.ActorBounds(look.Appearance, includeWeapon: false) is { } bounds)
            {
                // Native0x473b2c/0x473b51 centres the BODY+HEAD rectangle at97,167,
                // using integer halves. A fixed foot anchor shifts different hair/gear.
                var center = bounds.Position + new Vector2((int)bounds.Size.X / 2, (int)bounds.Size.Y / 2);
                Art.Actor(target, look.Appearance, 2, 0, 0, new Vector2(434 + 97, 12 + 167) - center,
                    SelfHairTone, SelfSkinTone, cosmetics: equipmentScene.Cosmetics);
            }
            foreach (var cell in NativeEquipmentCells)
            {
                var item = equipmentScene.Equipment.FirstOrDefault(e => e.WireSlot == cell.Slot);
                var icon = item is null ? null : IconTexture?.Invoke(item.Icon);
                if (icon is not null)
                    target.DrawTexture(icon, new Vector2(434, 12) + cell.Center - new Vector2(icon.GetWidth() / 2, icon.GetHeight() / 2));
            }
        }
        DrawNativeNumber(target, _level, 2);
        foreach (var attribute in _attributes) DrawNativeNumber(target, attribute, 1);
        DrawNativeNumber(target, _hp, 0); DrawNativeNumber(target, _mp, 0);
        DrawNativeNumber(target, _experience, 0); DrawNativeNumber(target, _coins, 2);
        DrawNativeNumber(target, _coordinates, 2);
        target.DrawSetTransform(Vector2.Zero);
    }

    private void DrawNativeNumber(CanvasItem target, Label field, int variant)
    {
        string text = field.Text;
        if (text.Length == 0) return;
        // Native renderer starts at the field's LEFT edge and advances 9 pixels.
        // Level/attributes use %3u leading spaces. Slash/space are deliberately
        // blank, matching native 0x497426; source USERSTAT provides its separator.
        float advance = Math.Min(9, field.Size.X / text.Length);
        for (int i = 0; i < text.Length; i++)
        {
            int digit = text[i] - '0'; if (digit is < 0 or > 9) continue;
            target.DrawTextureRectRegion(_nativeDigits, new Rect2(field.Position + new Vector2(i * advance, 0), new Vector2(advance, 11)),
                new Rect2(digit * 9, variant * 11, 9, 11));
        }
    }

    private static void DrawVital(CanvasItem target, Vector2 position, uint current, uint maximum, Texture2D originalBar)
    {
        target.DrawRect(new Rect2(position, new Vector2(100, 11)), new Color("281d19"));
        float ratio = maximum == 0 ? 0 : Math.Clamp((float)current / maximum, 0, 1);
        float width = Mathf.Floor(100 * ratio);
        // Clip the original BAR.EPF pixels. Scaling the complete gradient into
        // the remaining fraction would alter its source pixels and border.
        if (width > 0) target.DrawTextureRectRegion(originalBar, new Rect2(position, new Vector2(width, 11)), new Rect2(0, 0, width, 11));
    }

    private void UpdateNativePanel()
    {
        bool equipment = _nativePanel == "equipment";
        _identity.Visible = equipment; _equipment.Visible = _nativeEntries.Visible = false;
        if (_nativeEntryStyle != _nativePanel)
        {
            _nativeEntryStyle = _nativePanel;
            _nativeEntries.AddThemeColorOverride("font_color", _nativePanel == "spells" ? new Color("352717") : new Color("fff0c7"));
            _nativeEntries.AddThemeConstantOverride("shadow_offset_x", _nativePanel == "spells" ? 0 : 1);
            _nativeEntries.AddThemeConstantOverride("shadow_offset_y", _nativePanel == "spells" ? 0 : 1);
        }
        if (_scene is null) return;
        int total = equipment ? _scene.Equipment.Length : _nativePanel == "spells" ? _scene.Spells.Length : _scene.Inventory.Length;
        int pageSize = equipment ? Math.Max(1, total) : 10;
        int pages = equipment ? 3 : Math.Max(1, (total + pageSize - 1) / pageSize);
        _nativePage = Math.Clamp(_nativePage, 0, pages - 1);
        string version = _nativePanel + ":" + _nativePage + ":" + string.Join("|", _scene.Equipment.Select(i => $"{i.WireSlot}:{i.Name}:{i.Icon}"))
            + ";" + string.Join("|", _scene.Spells.Select(i => $"{i.WireSlot}:{i.Name}:{i.Type}"))
            + ";" + string.Join("|", _scene.Inventory.Select(i => $"{i.WireSlot}:{i.Name}:{i.Icon}:{i.Amount}"))
            + ";" + ProfileVersion(_scene.Profile) + $";{_scene.Stats.MaxHp}:{_scene.Stats.MaxMp}:{_scene.Stats.Nation}";
        if (version != _nativeRowsVersion)
        {
            _nativeRowsVersion = version;
            foreach (string key in _nativeRowKeys) Buttons.Remove(key);
            _nativeRowKeys.Clear();
            foreach (Node child in _nativeRows.GetChildren()) { _nativeRows.RemoveChild(child); child.QueueFree(); }
            if (equipment)
            {
                _nativeRows.Position = Vector2.Zero; _nativeRows.Size = new(640, 300);
                BuildProfilePage();
                if (_nativePage == 0)
                {
                    var body = NativeRow("native-equipment-details", "", () => { if (CanUseNativeRows) OpenLocal("equipment"); }, 12 + 141, 48, 52);
                    body.Position = new(434 + 73, 12 + 141);
                    body.TooltipText = _scene.Equipment.Length == 0 ? "장착 장비 보기" : string.Join("\n", _scene.Equipment.Select(e => KoreanText.Display(e.Name)));
                    foreach (var cell in NativeEquipmentCells)
                    {
                        var item = _scene.Equipment.FirstOrDefault(e => e.WireSlot == cell.Slot);
                        var button = NativeRow("native-equipment-slot-" + cell.Slot, "", () => { if (CanUseNativeRows) OpenLocal("equipment"); }, 0, 26, 26);
                        button.Position = new Vector2(434, 12) + cell.Center - new Vector2(13, 13);
                        button.TooltipText = cell.Name + " · " + (item is null ? "비어 있음" : KoreanText.Display(item.Name)) + " · 터치하여 장비 보기";
                    }
                }
            }
            else if (_nativePanel == "spells")
            {
                _nativeRows.Position = new(450, 36); _nativeRows.Size = new(158, 230);
                int row = 0;
                foreach (var spell in _scene.Spells.Skip(_nativePage * 10).Take(10))
                    NativeRow("native-cast-" + spell.WireSlot, $"{spell.WireSlot}. {KoreanText.Spell(spell.Name, _scene.Stats.Nation)}", () =>
                    {
                        if (!CanUseNativeRows) return;
                        if (spell.Type == 1) OpenSpellInput(spell);
                        else Emit("cast", spell.WireSlot, spell.Type == 2 ? SelectedTarget : 0);
                    }, row++ * 23, 158, 23);
                if (_scene.Spells.Length == 0)
                { var empty = Text("배운 기술 없음", 10); empty.Position = Vector2.Zero; empty.Size = _nativeRows.Size; empty.AddThemeColorOverride("font_color", new Color("352717")); _nativeRows.AddChild(empty); }
            }
            else
            {
                _nativeRows.Position = new(450, 36); _nativeRows.Size = new(158, 230);
                int row = 0;
                foreach (var item in _scene.Inventory.Skip(_nativePage * 10).Take(10))
                {
                    var button = NativeRow("native-item-" + item.WireSlot, $"{item.WireSlot}. {KoreanText.Display(item.Name)} ×{item.Amount:N0}", () => { if (CanUseNativeRows) OpenLocal("inventory"); }, row++ * 23, 158, 23);
                    button.Icon = IconTexture?.Invoke(item.Icon); button.ExpandIcon = true; button.AddThemeConstantOverride("icon_max_width", 18); button.Size = new(158, 23);
                }
                if (_scene.Inventory.Length == 0)
                { var empty = Text("가방이 비어 있습니다", 10); empty.Position = Vector2.Zero; empty.Size = _nativeRows.Size; _nativeRows.AddChild(empty); }
            }
            NativePageButton("native-page-prev", -1, new Vector2(519, 276), _nativePage > 0);
            NativePageButton("native-page-next", 1, new Vector2(531, 276), _nativePage + 1 < pages);
        }
        if (Buttons.TryGetValue("native-page-prev", out var previous)) previous.Disabled = !CanUseNativeRows || _nativePage == 0;
        if (Buttons.TryGetValue("native-page-next", out var next)) next.Disabled = !CanUseNativeRows || _nativePage + 1 >= pages;
        _nativeEntries.Text = _nativePanel == "spells"
            ? (_scene.Spells.Length == 0 ? "배운 기술 없음" : string.Join("\n", _scene.Spells.Take(10).Select(i => $"{i.WireSlot}. {KoreanText.Spell(i.Name, _scene.Stats.Nation)}")))
            : (_scene.Inventory.Length == 0 ? "가방이 비어 있습니다" : string.Join("\n", _scene.Inventory.Take(10).Select(i => $"{i.WireSlot}. {KoreanText.Display(i.Name)} ×{i.Amount}")));
    }

    private static string ProfileVersion(SceneProfileSnapshot? profile) => profile is null ? "profile-pending"
        : $"{profile.Ac}:{profile.Dam}:{profile.Hit}:{profile.Tnl}:{profile.Title}:{profile.ClanName}:{profile.ClanTitle}:{profile.ClassName}:{profile.GroupText}:{profile.BuffText}:{profile.Grouped}:{profile.Exchange}:"
            + string.Join("|", profile.Legends.Select(l => $"{l.Icon}:{l.Color}:{l.Text}"));

    private Label ProfileLabel(string name, string value, Rect2 rectangle, bool right = false)
    {
        var label = new Label { Name = name, Text = value, Position = rectangle.Position, Size = rectangle.Size,
            MouseFilter = MouseFilterEnum.Ignore, ClipText = true, AutowrapMode = TextServer.AutowrapMode.Off,
            HorizontalAlignment = right ? HorizontalAlignment.Right : HorizontalAlignment.Left,
            VerticalAlignment = VerticalAlignment.Center };
        label.AddThemeFontSizeOverride("font_size", 10);
        label.AddThemeColorOverride("font_color", new Color("352717"));
        _nativeRows.AddChild(label); return label;
    }

    private void ProfileTextBox(string name, string value, Rect2 rectangle)
    {
        var scroll = new ScrollContainer { Name = name + "Scroll", Position = rectangle.Position, Size = rectangle.Size,
            MouseFilter = MouseFilterEnum.Stop, HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
            VerticalScrollMode = ScrollContainer.ScrollMode.ShowNever };
        // Preserve the original authored scrollbar pixels: the native arrow strip
        // remains visible outside this inset touch scroll area.
        scroll.AddThemeConstantOverride("scroll_deadzone", 3);
        var label = ProfileLabel(name, value, new Rect2(Vector2.Zero, rectangle.Size));
        _nativeRows.RemoveChild(label); label.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        label.CustomMinimumSize = new Vector2(rectangle.Size.X, 0); label.AutowrapMode = TextServer.AutowrapMode.WordSmart;
        label.VerticalAlignment = VerticalAlignment.Top; label.ClipText = false;
        scroll.AddChild(label); _nativeRows.AddChild(scroll);
        ProfileScrollArrows(name, scroll, rectangle);
    }

    private void ProfileScrollArrows(string name, ScrollContainer scroll, Rect2 rectangle)
    {
        foreach (int step in new[] { -1, 1 })
        {
            var arrow = NativeRow("native-" + name + (step < 0 ? "-up" : "-down"), "", () =>
            {
                if (CanUseNativeRows) scroll.ScrollVertical += step * 24;
            }, 0, 12, 14);
            arrow.Position = new Vector2(598, step < 0 ? rectangle.Position.Y : rectangle.End.Y - 14);
            arrow.TooltipText = step < 0 ? "위로 스크롤" : "아래로 스크롤";
        }
    }

    private void ProfileLegendBox(SceneProfileSnapshot? profile)
    {
        if (profile is null || profile.Legends.Length == 0)
        {
            ProfileTextBox("ProfileLegendText", profile is null ? "정보 수신 중" : "전설 기록 없음", new(453, 84, 142, 182));
            return;
        }
        var rectangle = new Rect2(453, 84, 142, 182);
        var scroll = new ScrollContainer { Name = "ProfileLegendTextScroll", Position = rectangle.Position, Size = rectangle.Size,
            MouseFilter = MouseFilterEnum.Stop, HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled,
            VerticalScrollMode = ScrollContainer.ScrollMode.ShowNever };
        var rows = new VBoxContainer { Name = "ProfileLegendText", SizeFlagsHorizontal = SizeFlags.ExpandFill };
        rows.AddThemeConstantOverride("separation", 3); scroll.AddChild(rows); _nativeRows.AddChild(scroll);
        for (int i = 0; i < profile.Legends.Length; i++)
        {
            var mark = profile.Legends[i]; var line = new HBoxContainer { Name = "LegendRow-" + i };
            line.AddThemeConstantOverride("separation", 3); rows.AddChild(line);
            int icon = mark.Icon is >= 0 and < 16 ? mark.Icon : 0;
            line.AddChild(new TextureRect { Name = "LegendIcon-" + i, Texture = _legendIcons[icon],
                TextureFilter = TextureFilterEnum.Nearest, MouseFilter = MouseFilterEnum.Ignore,
                StretchMode = TextureRect.StretchModeEnum.Keep, SizeFlagsVertical = SizeFlags.ShrinkBegin,
                TooltipText = $"원본 아이콘 {mark.Icon} · 색상 코드 {mark.Color}" });
            var text = ProfileLabel("LegendText-" + i, KoreanText.Display(mark.Text), new(0, 0, 127, 16));
            _nativeRows.RemoveChild(text); text.AutowrapMode = TextServer.AutowrapMode.WordSmart;
            text.ClipText = false; text.SizeFlagsHorizontal = SizeFlags.ExpandFill; line.AddChild(text);
        }
        ProfileScrollArrows("ProfileLegendText", scroll, rectangle);
    }

    private void BuildProfilePage()
    {
        if (_scene is null) return;
        var profile = _scene.Profile;
        string Lines(string value) => value.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Replace('\t', '\n');
        string Box(string? value, string empty) => value is null ? "정보 수신 중" : value.Length == 0 ? empty : Lines(value);
        if (_nativePage == 0)
        {
            // Native draw0x473a17..0x473ab5 right-aligns these at local175;
            // their baselines are62/79/96, inside the source's three boxes.
            ProfileLabel("ProfileClanName", profile?.ClanName ?? "", new(504, 59, 105, 15), true);
            ProfileLabel("ProfileClanTitle", profile?.ClanTitle ?? "", new(504, 76, 105, 15), true);
            ProfileLabel("ProfileTitle", profile?.Title ?? "", new(504, 93, 105, 15), true);
            ProfileLabel("ProfileClassName", KoreanText.Display(profile?.ClassName ?? ""), new(449, 114, 68, 15), true);
            ProfileLabel("ProfileCharacterName", _name, new(522, 114, 82, 15), true);
            ProfileTextBox("ProfileBuffText", KoreanText.Display(Box(profile?.BuffText, "적용 효과 없음")), new(453, 221, 142, 53));
        }
        else if (_nativePage == 1)
        {
            ProfileTextBox("ProfilePartyText", Box(profile?.GroupText, "파티 없음"), new(453, 84, 142, 80));
            ProfileLabel("ProfileMaxHp", _scene.Stats.MaxHp.ToString(), new(496, 180, 113, 16), true);
            ProfileLabel("ProfileMaxMp", _scene.Stats.MaxMp.ToString(), new(496, 197, 113, 16), true);
            ProfileLabel("ProfileAc", profile?.Ac.ToString() ?? "—", new(496, 217, 34, 16), true);
            ProfileLabel("ProfileDam", profile?.Dam.ToString() ?? "—", new(496, 234, 34, 16), true);
            ProfileLabel("ProfileHit", profile?.Hit.ToString() ?? "—", new(577, 234, 32, 16), true);
            ProfileLabel("ProfileTnl", profile?.Tnl.ToString() ?? "—", new(496, 254, 113, 16), true);
        }
        else
        {
            ProfileLegendBox(profile);
        }
    }

    private bool CanUseNativeRows => !_busy && !_hostFaulted && _scene?.EntryComplete == true && !ModalOpen && _scene.Dialog is null && _scene.Shop is null && _scene.WorldMap is null;
    private void SelectNativePanel(string panel)
    {
        if (_scene?.Dialog is not null || _scene?.Shop is not null || _scene?.WorldMap is not null) return;
        CloseLocalPanel(); CancelInputs(); _nativePanel = panel; _nativePage = 0;
        UpdateNativePanel(); NativeOverlay.QueueRedraw();
    }
    private Button NativeRow(string key, string text, Action pressed, float y, float width, float height)
    {
        var button = Button(key, text, pressed, 10);
        button.Name = key; button.CustomMinimumSize = Vector2.Zero; button.Position = new(0, y); button.Size = new(width, height);
        button.Alignment = HorizontalAlignment.Left; button.Disabled = !CanUseNativeRows;
        button.AddThemeColorOverride("font_color", new Color(_nativePanel == "inventory" ? "fff0c7" : "352717"));
        var normal = new StyleBoxFlat { BgColor = new Color(0, 0, 0, 0), ContentMarginLeft = 2, ContentMarginRight = 2, ContentMarginTop = 0, ContentMarginBottom = 0 };
        button.AddThemeStyleboxOverride("normal", normal);
        button.AddThemeStyleboxOverride("disabled", normal);
        var hover = (StyleBoxFlat)normal.Duplicate(); hover.BgColor = new Color(.8f, .65f, .3f, .2f); button.AddThemeStyleboxOverride("hover", hover);
        var down = (StyleBoxFlat)normal.Duplicate(); down.BgColor = new Color(.4f, .3f, .15f, .3f); button.AddThemeStyleboxOverride("pressed", down);
        _nativeRowKeys.Add(key); _nativeRows.AddChild(button); button.Size = new(width, height); return button;
    }

    private void NativePageButton(string key, int step, Vector2 position, bool enabled)
    {
        var button = NativeRow(key, "", () =>
        {
            if (!CanUseNativeRows || !enabled) return;
            _nativePage += step; _nativeRowsVersion = ""; UpdateNativePanel(); NativeOverlay.QueueRedraw();
        }, position.Y - _nativeRows.Position.Y, 12, 18);
        button.Position = position - _nativeRows.Position; button.Size = new(12, 18);
        button.TooltipText = step < 0 ? "이전 쪽" : "다음 쪽";
        button.Disabled = !enabled || !CanUseNativeRows;
    }

    private void Layout()
    {
        // Diagnostic status is available in the menu/export; it must not allocate
        // an extra strip below the game or paint across the original footer.
        _status.Visible = false;
        Vector2 modalSize = new(Mathf.Min(800, Size.X - 44), Mathf.Min(650, Size.Y - 56));
        _modal.Position = (Size - modalSize) / 2; _modal.Size = modalSize;
    }

    private void OpenLocal(string panel)
    {
        // A faulted transport cannot answer its pending authoritative prompt. Recovery must remain
        // reachable without acknowledging/hiding that prompt in ClientModel; Stop owns cancellation.
        if ((_scene?.Dialog is not null || _scene?.Shop is not null || _scene?.WorldMap is not null) && !(_hostFaulted && panel == "menu")) return;
        if (panel is "inventory" or "equipment" or "spells") { _nativePanel = panel; UpdateNativePanel(); NativeOverlay.QueueRedraw(); }
        CancelInputs(); _localPanel = panel; _modalKey = ""; RefreshModal();
    }
    public void OpenMenu() => OpenLocal("menu");
    public void CloseLocalPanel()
    { DismissKeyboard(); _localPanel = ""; _spellPrompt = null; RefreshModal(); }

    private void DismissKeyboard()
    {
        GetViewport().GuiReleaseFocus();
        if (DisplayServer.HasFeature(DisplayServer.Feature.VirtualKeyboard)) DisplayServer.VirtualKeyboardHide();
    }

    private LineEdit OriginalInput(VBoxContainer body, string name, int maxLength = 255, bool number = false)
    {
        var input = new LineEdit { Name = name, MaxLength = maxLength, CustomMinimumSize = new(0, 58), SizeFlagsHorizontal = SizeFlags.ExpandFill,
            VirtualKeyboardType = number ? LineEdit.VirtualKeyboardTypeEnum.Number : LineEdit.VirtualKeyboardTypeEnum.Default };
        body.AddChild(input);
        _inputError = Text("", 15); _inputError.AddThemeColorOverride("font_color", new Color("ffd5b5")); body.AddChild(_inputError);
        return input;
    }

    private void SubmitOriginalText(LineEdit input, Action<string> submit)
    {
        if (_busy) return;
        input.ApplyIme(); string text = input.Text;
        // PlaySession.OriginalAscii rejects the same range before producing any packet;
        // preserve typed text here instead of closing the panel and logging it as a crash.
        if (text.Any(c => c < 0x20 || c > 0x7e))
        {
            if (_inputError is not null) _inputError.Text = "원본 자유 입력은 영문·숫자·기호를 지원합니다. 입력 내용은 유지됩니다. 한글 표시명은 시작 화면에서 입력하세요.";
            input.GrabFocus(); return;
        }
        DismissKeyboard(); submit(text);
    }

    private void RefreshModal()
    {
        if (_scene is null) return;
        _inventoryKey = string.Join("|", _scene.Inventory.Select(i => $"{i.WireSlot}:{i.Name}:{i.Amount}")) + ";" +
            string.Join("|", _scene.Equipment.Select(i => $"{i.WireSlot}:{i.Name}")) + ";" +
            string.Join("|", _scene.Spells.Select(i => $"{i.WireSlot}:{i.Name}:{i.Type}"));
        string localVersion = _localPanel is "inventory" or "equipment" or "spells" ? _inventoryKey : "";
        bool recoveryMenu = _hostFaulted && _localPanel == "menu";
        string key = recoveryMenu ? "recovery:menu" : _scene.Dialog is not null ? "dialog:" + _scene.Dialog.Sequence : _scene.Shop is not null ? "shop:" + _scene.Shop.Sequence
            : _scene.WorldMap is not null ? "worldmap:" + _scene.WorldMap.Sequence
            : _localPanel.Length > 0 ? "local:" + _localPanel + ":" + localVersion : "";
        if (key == _modalKey) return;
        if (_modal.Visible) DismissKeyboard();
        _modalKey = key; _modal.Visible = key.Length > 0; CancelInputs();
        _inputError = _recoveryStatus = null;
        foreach (string dynamicKey in _dynamicKeys) Buttons.Remove(dynamicKey);
        _dynamicKeys.Clear();
        foreach (Node child in _modalContent.GetChildren()) { _modalContent.RemoveChild(child); child.QueueFree(); }
        if (!_modal.Visible) return;
        if (recoveryMenu) BuildLocal("menu");
        else if (_scene.Dialog is not null) BuildDialog(_scene.Dialog);
        else if (_scene.Shop is not null) BuildShop(_scene.Shop);
        else if (_scene.WorldMap is not null) BuildWorldMap(_scene.WorldMap);
        else BuildLocal(_localPanel);
        Layout();
    }

    private void Heading(string text)
    { var label = new Label { Text = KoreanText.Display(text) }; label.AddThemeFontSizeOverride("font_size", 24); label.AddThemeColorOverride("font_color", new Color("ffdfa1")); _modalContent.AddChild(label); }
    private VBoxContainer ScrollBody()
    {
        var scroll = new ScrollContainer { SizeFlagsVertical = SizeFlags.ExpandFill, SizeFlagsHorizontal = SizeFlags.ExpandFill,
            HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled };
        var rows = new VBoxContainer { SizeFlagsHorizontal = SizeFlags.ExpandFill }; rows.AddThemeConstantOverride("separation", 9);
        scroll.AddChild(rows); _modalContent.AddChild(scroll); return rows;
    }
    private static Label Text(string text, int size = 18, bool verbatim = false)
    { var label = new Label { Text = verbatim ? text : KoreanText.Display(text), AutowrapMode = TextServer.AutowrapMode.WordSmart, SizeFlagsHorizontal = SizeFlags.ExpandFill }; label.AddThemeFontSizeOverride("font_size", size); label.AddThemeColorOverride("font_color", new Color("fff0cf")); return label; }
    private void AddClose()
    { _modalContent.AddChild(Button("local-close", "닫기", CloseLocalPanel, dynamic: true)); }
    private Button ModalButton(string key, string text, Action action)
    { return Button(key, text, action, dynamic: true); }

    private void BuildLocal(string panel)
    {
        if (_scene is null) return;
        Heading(panel switch { "inventory" => "가방", "equipment" => "장착 장비", "spells" => "기술", "chat" => "채팅", "cast-input" => "기술 입력", _ => "메뉴" });
        var body = ScrollBody();
        if (panel == "inventory")
        {
            body.AddChild(Text("놓기: 바닥에 1개 또는 묶음을 놓습니다. 채집 도구는 자원 옆에서 놓아 사용합니다. 건네기: 바라보는 바로 앞 대상에게 전달합니다.", 15));
            if (_scene.Inventory.Length == 0) body.AddChild(Text("가방이 비어 있습니다."));
            foreach (var item in _scene.Inventory)
            {
                var row = ItemRow(item, body);
                var actions = new HBoxContainer(); row.AddChild(actions);
                actions.AddChild(ModalButton("use-" + item.WireSlot, "사용", () => { CloseLocalPanel(); Emit("use", item.WireSlot); }));
                actions.AddChild(ModalButton("eat-" + item.WireSlot, "먹기", () => { CloseLocalPanel(); Emit("eat", item.WireSlot); }));
                actions.AddChild(ModalButton("equip-" + item.WireSlot, "장착", () => { CloseLocalPanel(); Emit("equip", item.WireSlot); }));
                var gestures = new HBoxContainer(); row.AddChild(gestures);
                gestures.AddChild(ModalButton("drop-" + item.WireSlot, "놓기 1개", () => { CloseLocalPanel(); Emit("drop", item.WireSlot); }));
                gestures.AddChild(ModalButton("hand-" + item.WireSlot, "건네기 1개", () => { CloseLocalPanel(); Emit("hand", item.WireSlot); }));
                if (item.Amount > 1)
                {
                    gestures.AddChild(ModalButton("drop-all-" + item.WireSlot, "모두 놓기", () => { CloseLocalPanel(); Emit("drop-all", item.WireSlot); }));
                    gestures.AddChild(ModalButton("hand-all-" + item.WireSlot, "모두 건네기", () => { CloseLocalPanel(); Emit("hand-all", item.WireSlot); }));
                }
            }
        }
        else if (panel == "equipment")
        {
            if (_scene.Equipment.Length == 0) body.AddChild(Text("장착한 장비가 없습니다."));
            foreach (var item in _scene.Equipment)
            {
                var row = ItemRow(item, body);
                row.AddChild(ModalButton("unequip-" + item.WireSlot, "해제", () => { CloseLocalPanel(); Emit("unequip", item.WireSlot); }));
            }
        }
        else if (panel == "spells")
        {
            if (_scene.Spells.Length == 0) body.AddChild(Text("아직 배운 기술이 없습니다."));
            body.AddChild(Text("대상 기술: 화면에서 대상을 고른 뒤 시전하세요. 대상을 고르지 않으면 원본의 바라보는 칸을 사용합니다.", 15));
            foreach (var spell in _scene.Spells)
            {
                var row = new HBoxContainer(); body.AddChild(row); row.AddChild(Text($"{spell.WireSlot}. {KoreanText.Spell(spell.Name, _scene.Stats.Nation)}"));
                row.AddChild(ModalButton("cast-" + spell.WireSlot, "시전", () =>
                {
                    if (spell.Type == 1) OpenSpellInput(spell);
                    else { CloseLocalPanel(); Emit("cast", spell.WireSlot, spell.Type == 2 ? SelectedTarget : 0); }
                }));
                if (spell.Type == 2) row.AddChild(ModalButton("cast-self-" + spell.WireSlot, "자신", () =>
                { uint self = _scene.SelfId; CloseLocalPanel(); Emit("cast", spell.WireSlot, self); }));
            }
        }
        else if (panel == "chat")
        {
            body.AddChild(Text("원본 게임 채팅은 영문·숫자·기호를 지원합니다. 한글 표시명은 별도로 보존됩니다.", 16));
            var input = OriginalInput(body, "ChatInput"); input.PlaceholderText = "메시지 입력";
            void Send() => SubmitOriginalText(input, text => { CloseLocalPanel(); Emit("chat", text: text); });
            body.AddChild(ModalButton("chat-send", "보내기", Send)); input.TextSubmitted += _ => Send();
        }
        else if (panel == "cast-input" && _spellPrompt is not null)
        {
            var spell = _spellPrompt;
            body.AddChild(Text(spell.Name));
            body.AddChild(Text("원본 기술의 입력을 직접 입력하세요. 영문·숫자·기호를 사용합니다.", 16));
            var input = OriginalInput(body, "SpellInput");
            void Send() => SubmitOriginalText(input, text => { CloseLocalPanel(); Emit("cast", spell.WireSlot, text: text); });
            body.AddChild(ModalButton("cast-input-submit", "시전", Send)); input.TextSubmitted += _ => Send();
        }
        else
        {
            body.AddChild(Text(_name, verbatim: true));
            if (_hostFaulted)
            {
                body.AddChild(Text("진행이 중단되었습니다. 마지막 확정 저장만 유지됩니다. 결과를 내보낸 뒤 시작 화면으로 돌아가 이어하기를 선택하세요.", 18));
                _recoveryStatus = Text(_status.Text, 16); body.AddChild(_recoveryStatus);
            }
            var save = ModalButton("menu-save", "지금 저장", () => Emit("save")); save.Disabled = _hostFaulted; body.AddChild(save);
            var originalHelp = ModalButton("menu-original-help", "원본 게임 메뉴", () => { CloseLocalPanel(); Emit("original-help"); }); originalHelp.Disabled = _hostFaulted; body.AddChild(originalHelp);
            var ride = ModalButton("menu-ride", "말 타기 · 내리기", () => { CloseLocalPanel(); Emit("ride"); }); ride.Disabled = _hostFaulted; body.AddChild(ride);
            body.AddChild(ModalButton("menu-pad", _showPad ? "방향 패드 숨기기" : "화면 안 방향 패드 표시", () =>
            { _showPad = !_showPad; _pad.Visible = _showPad; CloseLocalPanel(); }));
            body.AddChild(ModalButton("menu-bgm", MusicEnabled ? "배경 음악: 켜짐 · 누르면 끄기" : "배경 음악: 꺼짐 · 누르면 켜기", () => Emit("bgm")));
            body.AddChild(Text("바닥을 한 번 누르면 목적지까지 이동합니다. 이동 중 다른 곳을 누르면 목적지를 바꿉니다. 손가락을 밀면 수동 이동하고, 손을 떼면 멈춥니다.", 16));
            body.AddChild(ModalButton("menu-export", "검사 결과 내보내기", () => Emit("export")));
            body.AddChild(ModalButton("menu-return", _hostFaulted ? "시작 화면으로 돌아가기" : "저장하고 시작 화면으로", () => Emit("menu")));
        }
        AddClose();
    }

    private VBoxContainer ItemRow(SceneItemSnapshot item, VBoxContainer body)
    {
        var row = new VBoxContainer(); body.AddChild(row); var heading = new HBoxContainer(); row.AddChild(heading);
        var icon = IconTexture?.Invoke(item.Icon);
        if (icon is not null) heading.AddChild(new TextureRect { Texture = icon, CustomMinimumSize = new(42, 42), ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize, StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered });
        heading.AddChild(Text($"{item.WireSlot}. {KoreanText.Display(item.Name)}  ×{item.Amount:N0}")); return row;
    }

    private void OpenSpellInput(SceneSpellSnapshot spell)
    {
        _spellPrompt = spell; _localPanel = "cast-input"; _modalKey = ""; ResetHeld(); RefreshModal();
    }

    private void BuildDialog(SceneDialogSnapshot dialog)
    {
        Heading("대화"); var body = ScrollBody(); body.AddChild(Text(dialog.Text, 20));
        if (dialog.Kind == 2)
        {
            for (int i = 0; i < dialog.Options.Length; i++)
            {
                int choice = i + 1;
                string option = KoreanText.Display(dialog.Options[i]);
                var button = ModalButton("dialog-menu-" + choice, option,
                    () => Emit("dialog-menu", choice, sequence: dialog.Sequence));
                // Theme/font inheritance is only authoritative after parenting.
                // Measuring an unattached button uses the engine fallback font
                // and can falsely accept a clipped Hangul choice on wide screens.
                body.AddChild(button);
                // Hangul can exceed the same row at far fewer characters than Latin text.
                // Preserve the full choice in the existing scroll body whenever its actual font width exceeds the button.
                float available = Mathf.Min(800, Size.X - 44) - _modal.GetThemeStylebox("panel").GetMinimumSize().X
                    - button.GetThemeStylebox("normal").GetMinimumSize().X - 20;
                bool fullCaption = option.Length > 45 || button.GetThemeFont("font").GetStringSize(option, fontSize: button.GetThemeFontSize("font_size")).X > available;
                if (fullCaption)
                {
                    var caption = Text($"{choice}. {option}"); body.AddChild(caption);
                    body.MoveChild(caption, button.GetIndex()); button.Text = $"선택 {choice}";
                }
            }
        }
        else if (dialog.Kind == 4)
        {
            body.AddChild(Text("답은 직접 입력하세요. 원본 자유 입력은 영문·숫자·기호를 사용합니다.", 15));
            var input = OriginalInput(body, "DialogInput");
            void Send() => SubmitOriginalText(input, text => Emit("dialog-input", text: text, sequence: dialog.Sequence));
            body.AddChild(ModalButton("dialog-input", "입력", Send)); input.TextSubmitted += _ => Send();
        }
        var bottom = new HBoxContainer(); _modalContent.AddChild(bottom);
        if (dialog.Previous) bottom.AddChild(ModalButton("dialog-previous", "이전", () => Emit("dialog-previous", 1, sequence: dialog.Sequence)));
        if (dialog.Kind == 1 && dialog.Next) bottom.AddChild(ModalButton("dialog-next", "다음", () => Emit("dialog-next", 2, sequence: dialog.Sequence)));
        bottom.AddChild(ModalButton("dialog-cancel", dialog.Kind == 1 && !dialog.Next ? "닫기" : "취소", () => Emit("dialog-cancel", 0, sequence: dialog.Sequence)));
    }

    private void BuildShop(SceneShopSnapshot shop)
    {
        // The original bank uses the same grids: kind4 numbers are stored counts,
        // kind5 is the bag deposit picker. Do not label every grid as a sale.
        Heading(shop.Kind switch { 4 => "항목 선택", 5 => "가방에서 선택", _ => "수량 입력" });
        var body = ScrollBody(); body.AddChild(Text(shop.Text, 20));
        if (shop.Kind == 3)
        {
            body.AddChild(Text($"{KoreanText.Display(shop.ItemName)}  ·  표시 최대 {shop.Maximum:N0}", 16));
            var input = OriginalInput(body, "ShopAmountInput", 10, number: true); input.PlaceholderText = "수량";
            void Send() => SubmitOriginalText(input, text => Emit("shop-amount", text: text, sequence: shop.Sequence));
            body.AddChild(ModalButton("shop-amount", "확인", Send)); input.TextSubmitted += _ => Send();
        }
        else foreach (var row in shop.Rows)
        {
            string caption = shop.Kind == 4 ? $"{KoreanText.Display(row.Name)}  ·  {row.Number:N0}" : KoreanText.Display(row.Name);
            body.AddChild(ModalButton("shop-select-" + (shop.Kind == 4 ? row.Name : row.WireSlot.ToString()), caption,
                () => Emit("shop-select", row.WireSlot, text: row.Name, sequence: shop.Sequence)));
            if (row.Blurb.Length > 0) body.AddChild(Text(row.Blurb, 16));
        }
        _modalContent.AddChild(ModalButton("shop-cancel", "취소", () => Emit("shop-cancel", sequence: shop.Sequence)));
    }

    private void BuildWorldMap(SceneWorldMapSnapshot map)
    {
        Heading("세계 지도 · 목적지 선택"); var body = ScrollBody();
        if (string.Equals(map.Background, "field10", StringComparison.OrdinalIgnoreCase))
        {
            var texture = ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/field10.png")
                ?? throw new System.IO.InvalidDataException("Original field10 map resource is missing.");
            var canvas = new Control { Name = "OriginalWorldMap", CustomMinimumSize = new(0, 360), SizeFlagsHorizontal = SizeFlags.ExpandFill, MouseFilter = MouseFilterEnum.Ignore };
            var background = new TextureRect { Name = "WorldMapBackground", Texture = texture,
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize, StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                TextureFilter = TextureFilterEnum.Nearest, MouseFilter = MouseFilterEnum.Ignore };
            canvas.AddChild(background); background.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect); body.AddChild(canvas);
            var dots = new List<(Button Button, SceneWorldMapDestination Destination)>();
            for (int i = 0; i < map.Destinations.Length; i++)
            {
                int destination = i; var row = map.Destinations[i];
                var button = ModalButton("worldmap-dot-" + i, row.Name,
                    () => Emit("worldmap-select", destination, sequence: map.Sequence));
                button.Name = "worldmap-dot-" + i; button.CustomMinimumSize = Vector2.Zero;
                foreach (string state in new[] { "normal", "hover", "pressed", "disabled" })
                {
                    var compact = (StyleBoxFlat)button.GetThemeStylebox(state).Duplicate();
                    compact.ContentMarginLeft = compact.ContentMarginRight = compact.ContentMarginTop = compact.ContentMarginBottom = 0;
                    button.AddThemeStyleboxOverride(state, compact);
                }
                canvas.AddChild(button); dots.Add((button, row));
            }
            void PlaceDots()
            {
                float scale = Math.Min(canvas.Size.X / 640, canvas.Size.Y / 480);
                if (scale <= 0) return;
                Vector2 origin = (canvas.Size - new Vector2(640, 480) * scale) / 2;
                foreach (var dot in dots)
                {
                    // Original 0x2e dot coordinates are button CENTRES in the
                    // 640x480 FIELD10 image (Protocol §11m, native 0x423600).
                    // Keep those centres; Noto's touch label metrics are not a
                    // claim of native bitmap-font or full visual parity.
                    int fontSize = Math.Max(8, Mathf.RoundToInt(10 * scale));
                    dot.Button.AddThemeFontSizeOverride("font_size", fontSize);
                    float width = dot.Button.GetThemeFont("font").GetStringSize(dot.Button.Text, fontSize: fontSize).X + 12 * scale;
                    dot.Button.Size = new(width, 20 * scale);
                    dot.Button.Position = origin + new Vector2(dot.Destination.DotX, dot.Destination.DotY) * scale - dot.Button.Size / 2;
                }
            }
            canvas.Resized += PlaceDots; PlaceDots();
        }
        // Keep the exact packet names as a larger touch alternative. Unsupported
        // background names retain this list instead of impersonating FIELD10.
        for (int i = 0; i < map.Destinations.Length; i++)
        {
            int destination = i; var row = map.Destinations[i];
            body.AddChild(ModalButton("worldmap-select-" + i, row.Name,
                () => Emit("worldmap-select", destination, sequence: map.Sequence)));
        }
        _modalContent.AddChild(ModalButton("worldmap-cancel", "취소 · 현재 위치", () => Emit("worldmap-cancel", sequence: map.Sequence)));
    }
}
