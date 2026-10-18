using System.IO.Compression;
using System.Text.Json;
using Godot;
using P1998.P4;
using Shared;
using Server;
using File = System.IO.File;
using Environment = System.Environment;

public partial class Bootstrap : Control
{
    public override void _Ready()
    {
        string root = ProjectSettings.GlobalizePath("user://p4");
        try
        {
            var custom = Environment.GetEnvironmentVariable("P1998_P4_OUTPUT");
            if (!string.IsNullOrWhiteSpace(custom)) root = custom;
            if (!Path.IsPathFullyQualified(root)) throw new InvalidDataException("P4 root must be absolute");
            root = Path.GetFullPath(root);
            if (OS.GetName() == "Linux" && OS.GetCmdlineUserArgs().Contains("--p4-test-empty-base")) AppContext.SetData("APP_CONTEXT_BASE_DIRECTORY", "");
            byte[] manifest = Godot.FileAccess.GetFileAsBytes("res://capsule.json");
            string hash = Checkpoint.Hash(manifest);
            Checkpoint.Guard(root, hash);
            string content = Path.Combine(root, "content", hash);
            Extract(content, manifest);
            Environment.SetEnvironmentVariable("P1998_P3_ROOT", root);
            Environment.SetEnvironmentVariable("P1998_GAME_DATA", content);
            Environment.SetEnvironmentVariable("P1998_STATE", Path.Combine(root, "cache-p5"));
            Environment.SetEnvironmentVariable("P1998_LOGS", Path.Combine(root, "logs"));
            Environment.SetEnvironmentVariable("P1998_RUN", Path.Combine(root, "run"));
            Content.Load();
            var scene = GD.Load<PackedScene>("res://p5/main.tscn").Instantiate<Control>();
            scene.Call("initialize", root); AddChild(scene);
        }
        catch (Exception e)
        {
            var label = new Label { Text = "P5 시작 실패\n" + e.GetBaseException().Message,
                AutowrapMode = TextServer.AutowrapMode.WordSmart };
            label.AddThemeFontOverride("font", GD.Load<Font>("res://fonts/NotoSansKR.ttf"));
            label.AddThemeFontSizeOverride("font_size", 25); label.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect); AddChild(label);
            GD.PushError(e.ToString());
            if (Path.IsPathFullyQualified(root)) { Directory.CreateDirectory(root); Checkpoint.AtomicText(Path.Combine(root, "failure.json"), JsonSerializer.Serialize(new { error = e.ToString() })); }
        }
    }

    private static void Extract(string output, byte[] bytes)
    {
        using var manifest = JsonDocument.Parse(bytes);
        using var buffer = new MemoryStream(Godot.FileAccess.GetFileAsBytes("res://capsule.zip"));
        using var archive = new ZipArchive(buffer, ZipArchiveMode.Read);
        foreach (var row in manifest.RootElement.GetProperty("files").EnumerateArray())
        {
            string name = row.GetProperty("path").GetString()!;
            if (Path.IsPathRooted(name) || name.Contains("..")) throw new InvalidDataException("Unsafe capsule member");
            using var source = archive.GetEntry(name)!.Open(); using var memory = new MemoryStream(); source.CopyTo(memory);
            byte[] data = memory.ToArray(); if (Checkpoint.Hash(data) != row.GetProperty("sha256").GetString()) throw new InvalidDataException("P4 content hash mismatch");
            string path = Path.Combine(output, name); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            if (!File.Exists(path) || Checkpoint.Hash(File.ReadAllBytes(path)) != Checkpoint.Hash(data))
            { File.WriteAllBytes(path + ".pending", data); File.Move(path + ".pending", path, true); }
        }
    }
}
