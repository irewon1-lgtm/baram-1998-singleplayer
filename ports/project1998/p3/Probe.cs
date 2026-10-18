using System.Text.Json;
using System.IO.Compression;
using Godot;
using Server;
using Shared;
using P1998.P3;
using File = System.IO.File;
using Environment = System.Environment;

public partial class Probe : Control
{
    private Label _text = null!;
    private string _root = "";
    private string _stage = "paths";
    private bool _passed;
    private int _exit;

    public override void _Ready()
    {
        var font = GD.Load<Font>("res://fonts/NotoSansKR.ttf");
        var background = new ColorRect { Color = new Color("172319"), MouseFilter = MouseFilterEnum.Ignore };
        background.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect); AddChild(background);
        var margin = new MarginContainer(); margin.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect);
        foreach (var side in new[] { "left", "right", "top", "bottom" }) margin.AddThemeConstantOverride("margin_" + side, 36);
        AddChild(margin);
        var column = new VBoxContainer(); column.AddThemeConstantOverride("separation", 16); margin.AddChild(column);
        var title = new Label { Text = "PROJECT1998  /  P3 · 수정 1\n오프라인 C# 코어 연동 실험" };
        title.AddThemeFontOverride("font", font); title.AddThemeFontSizeOverride("font_size", 34); column.AddChild(title);
        _text = new Label { Text = "원본 규칙 실행 중…", AutowrapMode = TextServer.AutowrapMode.WordSmart,
            SizeFlagsVertical = SizeFlags.ExpandFill };
        _text.AddThemeFontOverride("font", font); _text.AddThemeFontSizeOverride("font_size", 25); column.AddChild(_text);
        var button = new Button { Text = "저장 상태 확인", CustomMinimumSize = new Vector2(260, 70) };
        button.AddThemeFontOverride("font", font); button.AddThemeFontSizeOverride("font_size", 25); column.AddChild(button);
        button.Pressed += () =>
        {
            string name = _passed ? "verification.json" : "failure.json";
            button.Text = File.Exists(Path.Combine(_root, name))
                ? (_passed ? "검증·저장 기록 확인됨" : "오류 기록 저장됨 · 단계: " + _stage)
                : "기록 저장 여부 확인 불가";
        };
        CallDeferred(MethodName.RunProbe);
    }

    private void RunProbe()
    {
        try
        {
            // Resolve the Godot sandbox first so even a rejected host override
            // has a valid place for failure diagnostics. Never use the CWD.
            _root = AbsoluteRoot(ProjectSettings.GlobalizePath("user://p3"));
            string? outputOverride = Environment.GetEnvironmentVariable("P1998_P3_OUTPUT");
            if (!string.IsNullOrWhiteSpace(outputOverride)) _root = AbsoluteRoot(outputOverride);
            // Linux regression fixture for an embedded Android runtime with no
            // managed assembly base directory. It does not emulate Android.
            if (OS.GetName() == "Linux" && OS.GetCmdlineUserArgs().Contains("--p3-test-empty-base"))
            {
                AppContext.SetData("APP_CONTEXT_BASE_DIRECTORY", "");
                if (AppContext.BaseDirectory != "") throw new InvalidOperationException("Empty-base fixture was not applied");
            }
            Environment.SetEnvironmentVariable("P1998_P3_ROOT", _root);
            _stage = "save-identity";
            byte[] capsuleBytes = Godot.FileAccess.GetFileAsBytes("res://capsule.json");
            string capsuleHash = ProbeStore.Hash(capsuleBytes);
            string state = Path.Combine(_root, "v1");
            ProbeStore.Guard(state, capsuleHash); // BEFORE original Db/ServerConfig can initialize.
            _stage = "content-extraction";
            string content = Path.Combine(_root, "content", capsuleHash);
            ExtractAndVerify(content, capsuleBytes);
            Environment.SetEnvironmentVariable("P1998_GAME_DATA", content);
            Environment.SetEnvironmentVariable("P1998_STATE", state);
            Environment.SetEnvironmentVariable("P1998_LOGS", Path.Combine(_root, "logs"));
            Environment.SetEnvironmentVariable("P1998_RUN", Path.Combine(_root, "run"));
            _stage = "content-load";
            Content.Load();
            if (Content.Maps.Count != 1 || Content.Items.Count != 4 || Content.Mobs.Count != 1 || Content.Spawns.Count != 0 || Content.Npcs.Count != 0)
                throw new InvalidDataException("P3 capsule exceeded bounded scope or failed to load");
            if (!ItemScript.HasVerb("heal") || !ItemScript.HasVerb("drink")) throw new InvalidDataException("Original MoonSharp verbs missing");
            var store = new ProbeStore(state);
            var cold = store.Store.Load("p3probe");
            if (cold.Status is not (CharacterLoadStatus.Ok or CharacterLoadStatus.NotFound))
                throw new InvalidDataException("EXISTING_SAVE_PROTECTED: " + cold.Status);
            _stage = "original-rules";
            using var fixture = JsonDocument.Parse(Godot.FileAccess.GetFileAsString("res://fixtures.json"));
            var scenario = new Scenario(store.Store, fixture.RootElement);
            scenario.Run(fixture.RootElement);
            ProbeStore.AtomicText(Path.Combine(_root, "trace.json"), JsonSerializer.Serialize(scenario.Result(fixture.RootElement), Scenario.Json));
            string expectedTrace = Godot.FileAccess.GetFileAsString("res://oracle.expected.json");
            bool parity = JsonSerializer.Serialize(JsonDocument.Parse(expectedTrace).RootElement) ==
                JsonSerializer.Serialize(JsonSerializer.SerializeToElement(scenario.Result(fixture.RootElement), Scenario.Json));
            if (!parity) throw new InvalidDataException("ORIGINAL_PARITY_MISMATCH");
            _stage = "sqlite-save-backup";
            uint wantedHp = scenario.Character.Hp;
            if (!store.Save(scenario.Character)) throw new IOException("Original SQLite save failed");
            scenario.Character.Hp = wantedHp - 1;
            if (!store.Save(scenario.Character)) throw new IOException("Second SQLite save failed");
            var current = store.Store.Load("p3probe");
            var backup = store.ReadBackup("p3probe");
            bool roundTrip = current.Status == CharacterLoadStatus.Ok && current.Character!.Hp == wantedHp - 1;
            bool rollback = backup is not null && backup.Hp == wantedHp;
            if (!roundTrip || !rollback) throw new IOException("SQLite round-trip or backup mismatch");
            var receipt = new { status = "PASS_OBSERVED_PLATFORM", platform = OS.GetName(), process_id = OS.GetProcessId(),
                schema = ProbeStore.SchemaId, version = ProbeStore.Version, capsule_sha256 = capsuleHash,
                steps = scenario.Trace.Count, original_parity = parity, moonsharp_heal_and_drink = true,
                sqlite_round_trip = roundTrip, sqlite_online_backup = rollback,
                cold_existing_save = cold.Status.ToString(), cold_hp = cold.Character?.Hp,
                world_started = scenario.World.IsStarted, network_transport = "none; in-process sink",
                random_draws = 0, galaxy = "NOT_RUN_DEVICE", build = "0.0.2-p3-fix1",
                empty_base_directory = string.IsNullOrEmpty(AppContext.BaseDirectory), deployment_root_explicit = true };
            _stage = "verification-record";
            ProbeStore.AtomicText(Path.Combine(_root, "verification.json"), JsonSerializer.Serialize(receipt, Scenario.Json));
            _passed = true;
            _stage = "complete";
            _text.Text = $"원본 C# 규칙 {scenario.Trace.Count}단계 일치\n\n캐릭터 생성 · 이동 및 점유 충돌\n아이템 수량 제한 · Lua 회복/음료\n토끼 상태 만료 · 위협 수치\nSQLite 저장 · 이전 저장 백업 읽기\n\n플랫폼: {OS.GetName()} / 단일 앱 프로세스\n게임 서버·로그인 서버·인터넷 연결 없음\nP3 실험 전용 · 전체 플레이는 P4 범위";
            GD.Print("P3_CORE_PASS " + JsonSerializer.Serialize(receipt));
        }
        catch (Exception e)
        {
            _exit = 1;
            var cause = e.GetBaseException();
            _text.Text = "P3 검증 실패 · 수정 1\n단계: " + _stage + "\n" + cause.GetType().Name + ": " + cause.Message;
            GD.PushError(e.ToString());
            try
            {
                Directory.CreateDirectory(AbsoluteRoot(_root));
                ProbeStore.AtomicText(Path.Combine(_root, "failure.json"), JsonSerializer.Serialize(new {
                    status = "FAIL", build = "0.0.2-p3-fix1", stage = _stage, error = e.ToString(),
                    empty_base_directory = string.IsNullOrEmpty(AppContext.BaseDirectory) }, Scenario.Json));
            }
            catch (Exception logError)
            {
                _text.Text += "\n오류 기록 저장 실패: " + logError.GetType().Name;
                GD.PushError("P3 failure record: " + logError);
            }
        }
        if (OS.GetCmdlineUserArgs().Contains("--p3-quit")) GetTree().Quit(_exit);
    }

    private static string AbsoluteRoot(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !Path.IsPathFullyQualified(path))
            throw new InvalidDataException("P3 storage root must be an absolute, non-empty sandbox path");
        return Path.GetFullPath(path);
    }

    private static void ExtractAndVerify(string output, byte[] manifestBytes)
    {
        using var manifest = JsonDocument.Parse(manifestBytes);
        using var packed = new MemoryStream(Godot.FileAccess.GetFileAsBytes("res://capsule.zip"));
        using var archive = new ZipArchive(packed, ZipArchiveMode.Read);
        foreach (var row in manifest.RootElement.GetProperty("content_files").EnumerateArray())
        {
            string relative = row.GetProperty("path").GetString()!;
            if (relative.Contains("..") || Path.IsPathRooted(relative)) throw new InvalidDataException("Unsafe capsule path");
            using var source = (archive.GetEntry(relative) ?? throw new InvalidDataException("Capsule entry missing")).Open();
            using var buffer = new MemoryStream(); source.CopyTo(buffer); byte[] bytes = buffer.ToArray();
            if (ProbeStore.Hash(bytes) != row.GetProperty("capsule_sha256").GetString()) throw new InvalidDataException("Content hash mismatch: " + relative);
            string target = Path.Combine(output, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            if (!File.Exists(target) || ProbeStore.Hash(File.ReadAllBytes(target)) != ProbeStore.Hash(bytes))
            {
                string pending = target + ".pending"; File.WriteAllBytes(pending, bytes); File.Move(pending, target, true);
            }
        }
    }
}
