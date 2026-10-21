using Godot;
using P1998.Embedded;
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;
using IO = System.IO;

/// <summary>Presentation only. Consumes original server audio events once and never edits game state.
/// Call Present and playback controls on the Godot thread. SnapshotStatus reads only cached evidence.
/// Source WAV/MIDI payloads remain native archive bytes. Explicit catalog aliases for
/// missing IDs are user-authorized playable substitutes and reported separately.</summary>
public sealed partial class GameAudio : Node
{
    private const string AudioRoot = "res://assets/runtime/audio/";
    private readonly object _gate = new();
    private readonly Dictionary<int, AudioStreamPlayer> _players = new();
    private readonly Dictionary<int, WaveObservation> _waves = new();
    private readonly Dictionary<int, int> _unsupportedSounds = new();
    private readonly Dictionary<int, int> _compatibilitySounds = new();
    // The packaged catalog is immutable for this scene. Keep only its tiny MIDI
    // rows instead of reparsing all sprite/terrain metadata on every music cue.
    private readonly Dictionary<string, JsonElement> _midiSources = new(StringComparer.Ordinal);
    private readonly List<string> _errors = new();
    private GodotObject? _midi;
    private long _lastSequence;
    private int _requestedTrack, _musicType, _musicVolume = 100, _musicPosition;
    private int _soundRequests, _musicRequests, _pausedSoundSuppressed, _eventGaps;
    private bool _paused, _midiPlayingObserved;
    private string _musicStatus = "NOT_RUN", _driver = "NOT_OBSERVED", _midiHash = "";
    private double _pollRemaining;
    private bool _musicEnabled = true;
    private long _musicLoads, _musicPolls;
    public bool MusicEnabled => _musicEnabled;
    public void SetMusicEnabled(bool enabled)
    {
        lock (_gate)
        {
            if (_musicEnabled == enabled) return;
            _musicEnabled = enabled; ReleaseMidi(); _pollRemaining = 0;
            _musicStatus = enabled ? "ENABLED" : "DISABLED";
            if (enabled && !_paused && _requestedTrack != 0 && _musicType == 2)
            {
                try { StartMidi(); }
                catch (Exception error) { RecordError("MIDI enable: " + error.Message); ReleaseMidi(); _musicStatus = "FAIL"; }
            }
        }
    }

    private sealed record WaveObservation(int Id, int Requests, double Seconds, int MixRate,
        string SourceSha256, string LoadPath, bool PlayingObserved, float Position,
        string OriginalPcmSha256, int SourceSoundId = 0, bool CompatibilitySubstitute = false);

    public bool InitializationComplete { get; private set; }
    public override void _Ready()
    {
        ProcessMode = ProcessModeEnum.Always;
        lock (_gate) _driver = AudioServer.GetDriverName();
        using (var catalog = JsonDocument.Parse(Godot.FileAccess.GetFileAsString("res://assets/runtime/catalog.json")))
        {
            foreach (var row in catalog.RootElement.GetProperty("audio").EnumerateObject())
                if (int.TryParse(row.Name, out int requested) && row.Value.TryGetProperty("compatibility_substitute", out var substitute))
                    _compatibilitySounds[requested] = substitute.GetProperty("source_sound").GetInt32();
            if (catalog.RootElement.TryGetProperty("music", out var music) && music.ValueKind == JsonValueKind.Object)
                foreach (var row in music.EnumerateObject()) _midiSources[row.Name] = row.Value.Clone();
        }
        InitializationComplete = true;
    }

    public void Present(ClientSceneSnapshot scene)
    {
        lock (_gate)
        {
            if (scene.LastEventSequence < _lastSequence)
            {
                // A new ClientModel starts its journal at zero. The host owns
                // restart/restore; audio must not reuse the previous journal.
                StopCore();
                _lastSequence = 0;
            }
            foreach (var entry in scene.Events)
            {
                if (entry.Sequence <= _lastSequence) continue;
                if (entry.Sequence > _lastSequence + 1)
                    _eventGaps += checked((int)Math.Min(int.MaxValue - _eventGaps, entry.Sequence - _lastSequence - 1));
                _lastSequence = entry.Sequence;
                int volume = entry.Body.Length >= 5 ? Math.Clamp((int)entry.Body[4], 0, 100) : 100;
                try
                {
                    if (entry.Kind == "sound") PlayWave(entry.Value, volume);
                    else if (entry.Kind == "music") PlayMusic(entry.Value, entry.Auxiliary, volume);
                }
                catch (Exception error)
                {
                    RecordError($"audio event {entry.Sequence} {entry.Kind} {entry.Value}: {error.Message}");
                    if (entry.Kind == "music") { _musicStatus = "FAIL"; ReleaseMidi(); }
                }
            }
            _lastSequence = Math.Max(_lastSequence, scene.LastEventSequence);
            ObservePlayback();
        }
    }

    private void PlayWave(int id, int volume)
    {
        _soundRequests++;
        if (_paused) { _pausedSoundSuppressed++; return; }
        if (!_players.TryGetValue(id, out var player))
        {
            int sourceId = _compatibilitySounds.GetValueOrDefault(id, id);
            string path = AudioRoot + sourceId + ".wav";
            // Godot exports .wav through an imported/remapped resource. Keep an
            // exact native-byte .bin twin so APK execution takes the same
            // bounded PCM decoder path verified on PC, independent of WAV import.
            string rawPath = path + ".bin";
            AudioStreamWav? wav;
            string sourceHash = "NOT_OBSERVED", pcmHash = "NOT_OBSERVED", route;
            if (Godot.FileAccess.FileExists(rawPath) || Godot.FileAccess.FileExists(path))
            {
                bool rawTwin = Godot.FileAccess.FileExists(rawPath);
                byte[] bytes = Godot.FileAccess.GetFileAsBytes(rawTwin ? rawPath : path);
                sourceHash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
                wav = AudioStreamWav.LoadFromBuffer(PcmDecoderBuffer(bytes, out pcmHash));
                route = rawTwin ? "original_wav_bin_exact_pcm_chunks_buffer" : "original_wav_exact_pcm_chunks_buffer";
            }
            else if (ResourceLoader.Exists(path))
            {
                // Export may remap the original WAV into Godot's imported
                // AudioStreamWAV resource. This preserves the selected source
                // payload; a declared requested-ID alias remains a substitute.
                wav = ResourceLoader.Load<AudioStreamWav>(path);
                route = "godot_imported_original_wav";
            }
            else
            {
                _unsupportedSounds[id] = _unsupportedSounds.GetValueOrDefault(id) + 1;
                return;
            }
            if (wav is null || wav.GetLength() <= 0) throw new IO.InvalidDataException("Original WAV could not be decoded: " + path);
            player = new AudioStreamPlayer { Name = "OriginalSound" + id, Stream = wav, MaxPolyphony = 4,
                ProcessMode = ProcessModeEnum.Always };
            AddChild(player);
            _players.Add(id, player);
            if (sourceId != id) route = "USER_AUTHORIZED_SUBSTITUTE:" + route;
            _waves.Add(id, new(id, 0, wav.GetLength(), wav.MixRate, sourceHash, route, false, 0, pcmHash, sourceId, sourceId != id));
        }
        // The original protocol's 100 means full volume. Its logarithmic
        // gain maps to the same normalized amplitude here; no distance fade.
        player.VolumeLinear = volume * 0.01f;
        player.Play();
        _waves[id] = _waves[id] with { Requests = _waves[id].Requests + 1 };
    }

    private static byte[] PcmDecoderBuffer(byte[] original, out string pcmHash)
    {
        // Native source WAVs contain non-UTF8 LIST labels; 719.WAV also omits
        // an odd data chunk's pad before its LIST. Godot's metadata reader emits
        // errors for these while decoding the PCM. Keep the original files/hash
        // and copy only the bounded fmt/data chunks into a decoder-only RIFF.
        // Every sample byte, rate, bit depth and channel count stays unchanged.
        var source = original.AsSpan();
        if (source.Length < 12 || !source[..4].SequenceEqual("RIFF"u8) ||
            !source.Slice(8, 4).SequenceEqual("WAVE"u8))
            throw new IO.InvalidDataException("Original sound is not a RIFF WAVE.");
        long extent = 8L + BinaryPrimitives.ReadUInt32LittleEndian(source.Slice(4, 4));
        if (extent > source.Length || extent < 12)
            throw new IO.InvalidDataException("Original WAVE RIFF size exceeds its payload.");
        ReadOnlySpan<byte> format = default, pcm = default;
        int offset = 12;
        while (offset <= extent - 8)
        {
            var tag = source.Slice(offset, 4);
            uint length = BinaryPrimitives.ReadUInt32LittleEndian(source.Slice(offset + 4, 4));
            long end = (long)offset + 8 + length;
            if (end > extent || length > int.MaxValue)
                throw new IO.InvalidDataException("Original WAVE chunk exceeds its RIFF extent.");
            if (tag.SequenceEqual("fmt "u8)) format = source.Slice(offset + 8, (int)length);
            else if (tag.SequenceEqual("data"u8)) pcm = source.Slice(offset + 8, (int)length);
            if (!format.IsEmpty && !pcm.IsEmpty) break;
            offset = checked((int)(end + (length & 1)));
        }
        if (format.Length < 16 || pcm.IsEmpty || BinaryPrimitives.ReadUInt16LittleEndian(format[..2]) != 1)
            throw new IO.InvalidDataException("Original sound has no supported PCM fmt/data chunks.");
        int channels = BinaryPrimitives.ReadUInt16LittleEndian(format.Slice(2, 2));
        uint rate = BinaryPrimitives.ReadUInt32LittleEndian(format.Slice(4, 4));
        uint byteRate = BinaryPrimitives.ReadUInt32LittleEndian(format.Slice(8, 4));
        int alignment = BinaryPrimitives.ReadUInt16LittleEndian(format.Slice(12, 2));
        int bits = BinaryPrimitives.ReadUInt16LittleEndian(format.Slice(14, 2));
        if (channels is < 1 or > 2 || rate == 0 || bits is not (8 or 16) ||
            alignment != channels * (bits / 8) || byteRate != (ulong)rate * (uint)alignment ||
            pcm.Length % alignment != 0)
            throw new IO.InvalidDataException("Original PCM format or sample alignment is invalid.");
        pcmHash = Convert.ToHexString(SHA256.HashData(pcm)).ToLowerInvariant();
        var result = new byte[checked(44 + pcm.Length + (pcm.Length & 1))];
        "RIFF"u8.CopyTo(result);
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(4, 4), (uint)result.Length - 8);
        "WAVEfmt "u8.CopyTo(result.AsSpan(8));
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(16, 4), 16);
        format[..16].CopyTo(result.AsSpan(20));
        "data"u8.CopyTo(result.AsSpan(36));
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(40, 4), (uint)pcm.Length);
        pcm.CopyTo(result.AsSpan(44));
        return result;
    }

    private void PlayMusic(int track, int type, int volume)
    {
        _musicRequests++;
        if (!_musicEnabled)
        {
            _requestedTrack = track; _musicType = type; _musicVolume = volume;
            _musicStatus = "DISABLED"; return;
        }
        if (track == 0)
        {
            ReleaseMidi(); _requestedTrack = 0; _musicType = type; _musicStatus = "STOPPED_BY_ORIGINAL_EVENT";
            return;
        }
        if (track == _requestedTrack && type == _musicType && _midi is not null)
        {
            _musicVolume = volume;
            JavaCall(_midi, "setVolume", volume * 0.01f, volume * 0.01f);
            return;
        }
        ReleaseMidi();
        _requestedTrack = track; _musicType = type; _musicVolume = volume;
        _midiHash = ""; _midiPlayingObserved = false; _musicPosition = 0;
        if (type != 2) { _musicStatus = "NOT_RUN_UNSUPPORTED_ORIGINAL_MUSIC_TYPE"; return; }
        if (!IsPackagedMidi(track)) { _musicStatus = "NOT_RUN_UNPACKAGED_MIDI_TRACK"; return; }
        if (_paused) { _musicStatus = "DEFERRED_WHILE_PAUSED"; return; }
        StartMidi();
    }

    private void StartMidi()
    {
        if (!_musicEnabled || _paused || !IsPackagedMidi(_requestedTrack)) return;
        _musicLoads++;
        string relative = $"audio/{_requestedTrack}.mid";
        byte[] bytes = Godot.FileAccess.GetFileAsBytes("res://assets/runtime/" + relative);
        if (bytes.Length < 14 || !bytes.AsSpan(0, 4).SequenceEqual("MThd"u8))
            throw new IO.InvalidDataException($"Original MIDI{_requestedTrack} payload is unavailable.");
        _midiHash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        if (!_midiSources.TryGetValue(_requestedTrack.ToString(System.Globalization.CultureInfo.InvariantCulture), out var row)
            || row.GetProperty("file").GetString() != relative
            || !string.Equals(row.GetProperty("sha256").GetString(), _midiHash, StringComparison.OrdinalIgnoreCase))
            throw new IO.InvalidDataException($"Original MIDI{_requestedTrack} differs from its source catalog.");
        if (!OS.HasFeature("android")) { _musicStatus = "NOT_RUN_PC_MIDI"; return; }
        if (!Engine.HasSingleton("AndroidRuntime") || !Engine.HasSingleton("JavaClassWrapper"))
            throw new InvalidOperationException("Godot Android Java runtime bridge is unavailable.");
        string directory = ProjectSettings.GlobalizePath("user://original-audio");
        IO.Directory.CreateDirectory(directory);
        string path = IO.Path.Combine(directory, _requestedTrack + "-" + _midiHash + ".mid");
        if (!IO.File.Exists(path) || !IO.File.ReadAllBytes(path).AsSpan().SequenceEqual(bytes))
            IO.File.WriteAllBytes(path, bytes);
        var activity = Engine.GetSingleton("AndroidRuntime").Call("getActivity").AsGodotObject()
            ?? throw new InvalidOperationException("Android Activity is unavailable.");
        var uriClass = JavaClassWrapper.Wrap("android.net.Uri")
            ?? throw new InvalidOperationException("android.net.Uri could not be wrapped.");
        CheckJava("wrap Uri");
        var uri = JavaCall(uriClass, "parse", new System.Uri(path).AbsoluteUri).AsGodotObject()
            ?? throw new InvalidOperationException("Local MIDI URI is unavailable.");
        var mediaClass = JavaClassWrapper.Wrap("android.media.MediaPlayer")
            ?? throw new InvalidOperationException("android.media.MediaPlayer could not be wrapped.");
        CheckJava("wrap MediaPlayer");
        _midi = JavaCall(mediaClass, "create", activity, uri).AsGodotObject()
            ?? throw new InvalidOperationException($"MediaPlayer.create returned null for original MIDI{_requestedTrack}.");
        JavaCall(_midi, "setLooping", true);
        JavaCall(_midi, "setVolume", _musicVolume * 0.01f, _musicVolume * 0.01f);
        JavaCall(_midi, "start");
        _musicStatus = "ANDROID_START_REQUESTED";
        ObserveMidi();
    }

    // The native 4.95 type-2 channel accepts the twelve stock MIDI IDs
    // (candidate/re/extract_mus.py, client guard at 0x4588b4). Read actual
    // packaged availability; restricting this to the first tutorial/city tracks
    // silently suppressed other original MapBgm.csv zones after expansion.
    // StartMidi still validates both the exact catalog path and source hash.
    private static bool IsPackagedMidi(int track) => track is >= 1 and <= 12 &&
        Godot.FileAccess.FileExists(AudioRoot +
            track.ToString(System.Globalization.CultureInfo.InvariantCulture) + ".mid");

    public void PausePlayback()
    {
        lock (_gate)
        {
            if (_paused) return;
            _paused = true;
            foreach (var player in _players.Values) player.StreamPaused = true;
            if (_midi is not null)
            {
                try { JavaCall(_midi, "pause"); _musicStatus = "PAUSED"; ObserveMidi(); }
                catch (Exception error) { RecordError("MIDI pause: " + error.Message); ReleaseMidi(); _musicStatus = "FAIL"; }
            }
            ObservePlayback();
        }
    }

    public void ResumePlayback()
    {
        lock (_gate)
        {
            if (!_paused) return;
            _paused = false;
            foreach (var player in _players.Values) player.StreamPaused = false;
            try
            {
                if (_midi is not null) { JavaCall(_midi, "start"); _musicStatus = "ANDROID_RESUME_REQUESTED"; ObserveMidi(); }
                else if (_musicEnabled && IsPackagedMidi(_requestedTrack) && _musicType == 2) StartMidi();
            }
            catch (Exception error) { RecordError("MIDI resume: " + error.Message); ReleaseMidi(); _musicStatus = "FAIL"; }
            ObservePlayback();
        }
    }

    public void StopPlayback()
    {
        lock (_gate) { StopCore(); _lastSequence = 0; }
    }

    private void StopCore()
    {
        foreach (var player in _players.Values) { player.Stop(); player.StreamPaused = false; }
        ReleaseMidi();
        _requestedTrack = 0; _musicType = 0; _paused = false; _musicStatus = "STOPPED";
        ObservePlayback();
    }

    private void ReleaseMidi()
    {
        if (_midi is null) return;
        try { JavaCall(_midi, "release"); }
        catch (Exception error) { RecordError("MIDI release: " + error.Message); }
        _midi.Dispose(); _midi = null; _midiPlayingObserved = false; _musicPosition = 0;
    }

    private static Variant JavaCall(GodotObject target, string method, params Variant[] arguments)
    {
        Variant value = target.Call(method, arguments);
        CheckJava(method);
        return value;
    }

    private static void CheckJava(string operation)
    {
        var error = JavaClassWrapper.GetException();
        if (error is not null) throw new InvalidOperationException($"Java {operation}: {error.Call("toString").AsString()}");
    }

    private void RecordError(string error)
    {
        if (_errors.Count == 32) _errors.RemoveAt(0);
        _errors.Add(error);
    }

    private void ObserveMidi()
    {
        if (!_musicEnabled || _midi is null) return;
        _musicPolls++;
        _midiPlayingObserved = JavaCall(_midi, "isPlaying").AsBool();
        _musicPosition = JavaCall(_midi, "getCurrentPosition").AsInt32();
        if (_midiPlayingObserved) _musicStatus = "ANDROID_PLAYING_OBSERVED";
    }

    private void ObservePlayback()
    {
        foreach (var (id, player) in _players)
            _waves[id] = _waves[id] with { PlayingObserved = player.Playing, Position = player.GetPlaybackPosition() };
    }

    public override void _Process(double delta)
    {
        _pollRemaining -= delta;
        if (_pollRemaining > 0) return;
        _pollRemaining = 0.25;
        lock (_gate)
        {
            ObservePlayback();
            try { ObserveMidi(); }
            catch (Exception error) { RecordError("MIDI observation: " + error.Message); ReleaseMidi(); _musicStatus = "FAIL"; }
        }
    }

    public object SnapshotStatus()
    {
        lock (_gate) return new
        {
            schema = "P1998_G2_ORIGINAL_AUDIO_1", driver = _driver, paused = _paused,
            last_event_sequence = _lastSequence, event_gaps = _eventGaps,
            sound_event_requests = _soundRequests, music_event_requests = _musicRequests,
            paused_sound_events_suppressed = _pausedSoundSuppressed,
            waves = _waves.Values.OrderBy(x => x.Id).ToArray(),
            unsupported_sound_ids = new Dictionary<int, int>(_unsupportedSounds),
            music = new { enabled = _musicEnabled, loads = _musicLoads, polls = _musicPolls, track = _requestedTrack, type = _musicType, volume = _musicVolume,
                status = _musicStatus, native_playing_observed = _midiPlayingObserved,
                position_ms = _musicPosition, original_midi_sha256 = _midiHash },
            errors = _errors.ToArray(), audible_confirmation = "NOT_RUN",
            limits = new[] { "Playback request/native state does not prove audible output.",
                "Headless/Dummy audio cannot receive audible PASS.", "PC MIDI playback is NOT_RUN.",
                "Original MIDI is synthesized by Android; exact legacy Windows instrument parity is NOT_RUN." }
        };
    }

    public override void _ExitTree() => StopPlayback();
}
