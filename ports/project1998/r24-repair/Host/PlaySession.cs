using System.Buffers.Binary;
using System.Text;
using Shared;
using Server;
using Microsoft.Data.Sqlite;

namespace P1998.Embedded;

/// <summary>The interactive boundary sends original protocol actions. It never routes a player through
/// HostProbe's automatic scenarios, reads a Character to invent a scene, or changes game facts.
/// A command admitted before an app pause cannot run after the subsequent resume.</summary>
public sealed class PlaySession
{
    private readonly SemaphoreSlim _commands = new(1, 1);
    private readonly CancellationTokenSource _stopping = new();
    // A large map stays fenced until every original terrain rectangle has arrived. A Home fence may
    // cancel the remaining requests; Resume retries only this read-only cache, never the action.
    private sealed record PendingMap(int Id, int Width, int Height, long Generation);
    private PendingMap? _pendingMap;
    internal const int MaximumMapCellsPerRequest = (ushort.MaxValue - 2 - 6) / 4;
    public EmbeddedHost Host { get; }
    public ClientModel Model => Host.Model;
    public bool Ready => Host.Ready && !Host.Paused && !Host.Faulted && Volatile.Read(ref _pendingMap) is null;
    public bool Paused => Host.Paused;
    public bool Faulted => Host.Faulted;
    public string InternalId { get; }
    public string DisplayName { get; private set; }

    private PlaySession(EmbeddedHost host, HostOptions options)
    { Host = host; InternalId = options.InternalId; DisplayName = options.DisplayName; }

    public static async Task<PlaySession> OpenAsync(HostOptions options, CancellationToken cancellationToken = default,
        Action<PlaySession>? preparedCallback = null)
    {
        cancellationToken.ThrowIfCancellationRequested();
        EmbeddedHost? prepared = null;
        PlaySession? play = null;
        try
        {
            var host = await EmbeddedHost.OpenAsync(options with { RetainedWireCapacity = 512 },
                h => { prepared = h; h.Model.EnableInteractivePresentation(); play = new(h, options); preparedCallback?.Invoke(play); },
                async () =>
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    while (prepared is not null && prepared.Paused && !cancellationToken.IsCancellationRequested && play?._stopping.IsCancellationRequested != true)
                        await Task.Delay(20, cancellationToken);
                    cancellationToken.ThrowIfCancellationRequested();
                    if (play?._stopping.IsCancellationRequested == true) throw new OperationCanceledException("Stopped during interactive startup.");
                });
            cancellationToken.ThrowIfCancellationRequested();
            play ??= new(host, options);
            // Korean metadata is separate from the original ASCII identity and survives reopening.
            // Query only the committed metadata row after normal host initialization; never rewrite it.
            using (var connection = new SqliteConnection(new SqliteConnectionStringBuilder
            { DataSource = Path.Combine(options.StateDirectory, "project1998.db"), Mode = SqliteOpenMode.ReadOnly }.ToString()))
            {
                connection.Open(); using var command = connection.CreateCommand();
                command.CommandText = "SELECT display_name FROM offline_display_names WHERE username=$u;";
                command.Parameters.AddWithValue("$u", options.InternalId.ToLowerInvariant());
                if (command.ExecuteScalar() is string display) play.DisplayName = display;
            }
            await play.RequestProfileAsync();
            return play;
        }
        catch
        {
            if (prepared is not null) await prepared.StopAsync();
            throw;
        }
    }

    public ClientSceneSnapshot Capture() => Model.CaptureScene() with { Cosmetics = Host.RecoveredAppearance };
    public Task<OfflineActionResult> RequestProfileAsync() => Queue(ClientOp.ProfileRequest, () => new byte[] { 0 });
    public Task<OfflineActionResult> StepAsync(int direction)
    {
        CheckDirection(direction);
        return Queue(ClientOp.Walk, () =>
        {
            var state = Model.CaptureScene();
            // The original protocol carries the current/source tile, never the desired destination.
            var body = new byte[6]; body[0] = (byte)direction;
            BinaryPrimitives.WriteUInt16BigEndian(body.AsSpan(2), checked((ushort)state.X));
            BinaryPrimitives.WriteUInt16BigEndian(body.AsSpan(4), checked((ushort)state.Y));
            return body;
        });
    }
    public Task<OfflineActionResult> TurnAsync(int direction)
    { CheckDirection(direction); return Queue(ClientOp.Turn, () => new[] { (byte)direction }); }
    public Task<OfflineActionResult> ClickAsync(uint entityId) => Queue(ClientOp.ClickInfo, () =>
    { var body = new byte[5]; BinaryPrimitives.WriteUInt32BigEndian(body.AsSpan(1), entityId); return body; });
    public Task<OfflineActionResult> AttackAsync() => Queue(ClientOp.Attack, () => Array.Empty<byte>());
    public Task<OfflineActionResult> UseAsync(byte wireSlot) => Slot(ClientOp.UseItem, wireSlot);
    public Task<OfflineActionResult> EatAsync(byte wireSlot) => Slot(ClientOp.Eat, wireSlot);
    public Task<OfflineActionResult> EquipAsync(byte wireSlot) => Slot(ClientOp.Wield, wireSlot);
    public Task<OfflineActionResult> UnequipAsync(byte wireSlot) => Slot(ClientOp.Unequip, wireSlot);
    // Original one-based slot and whole-stack flag. Dropping a tool is also the
    // 4.95 gathering gesture; the authoritative handler decides whether to harvest.
    public Task<OfflineActionResult> DropAsync(byte wireSlot, bool all = false)
        => ItemGesture(ClientOp.DropItem, wireSlot, all);
    public Task<OfflineActionResult> HandItemAsync(byte wireSlot, bool all = false)
        => ItemGesture(ClientOp.HandItem, wireSlot, all);
    // Session.HandleSetting distinguishes Ride 00 01 00 from Options 00 00.
    // The original handler finds a real horse; this never toggles Character state.
    public Task<OfflineActionResult> RideAsync() => Queue(ClientOp.Setting, () => new byte[] { 0, 1, 0 });
    public Task<OfflineActionResult> PickupAsync(bool all = false) => Queue(ClientOp.Pickup, () => new[] { all ? (byte)1 : (byte)0 });
    public Task<OfflineActionResult> OpenDoorAsync() => Queue(ClientOp.Open, () => Array.Empty<byte>());
    public Task<OfflineActionResult> CastAsync(byte wireSlot, uint? target = null, string? prompt = null)
    {
        if (wireSlot == 0) throw new ArgumentOutOfRangeException(nameof(wireSlot));
        if (prompt is not null)
        {
            byte[] text = OriginalAscii(prompt);
            return Queue(ClientOp.Cast, () => new[] { wireSlot }.Concat(text).Append((byte)0).ToArray());
        }
        return Queue(ClientOp.Cast, () =>
        {
            if (target is null) return new[] { wireSlot };
            byte[] body = new byte[5]; body[0] = wireSlot;
            BinaryPrimitives.WriteUInt32BigEndian(body.AsSpan(1), target.Value); return body;
        });
    }
    public Task<OfflineActionResult> ChatAsync(string text)
    {
        byte[] bytes = OriginalAscii(text);
        return Queue(ClientOp.Chat, () => new byte[] { 0, checked((byte)bytes.Length) }.Concat(bytes).ToArray());
    }
    public Task<OfflineActionResult> ReplyAsync(int kind, int step = 2, int menu = 0, string? text = null, long? expectedDialogSequence = null)
    {
        if (kind is not (1 or 2 or 4)) throw new ArgumentOutOfRangeException(nameof(kind));
        if (step < 0 || step > 255 || menu < 0 || menu > 255) throw new ArgumentOutOfRangeException(nameof(step));
        byte[] input = text is null ? Array.Empty<byte>() : OriginalAscii(text);
        long sequence = expectedDialogSequence ?? Model.CaptureScene().Dialog?.Sequence
            ?? throw new InvalidOperationException("답할 대화창이 없습니다.");
        return Queue(ClientOp.NpcDialog, () =>
        {
            if (Model.CaptureScene().Dialog?.Sequence != sequence) throw new InvalidOperationException("지난 대화창의 입력은 취소되었습니다.");
            byte[] body = new byte[11 + input.Length]; body[0] = (byte)kind; body[8] = (byte)step;
            body[10] = kind == 4 ? checked((byte)input.Length) : (byte)menu;
            input.CopyTo(body, 11); return body;
        }, sequence);
    }
    public Task<OfflineActionResult> CancelDialogAsync()
    {
        var scene = Model.CaptureScene();
        if (scene.Shop is not null) return ShopReplyAsync(scene.Shop.Tag, expectedDialogSequence: scene.Shop.Sequence);
        return scene.Dialog?.Kind == 2
            ? ReplyAsync(2, menu: 0, expectedDialogSequence: scene.Dialog.Sequence)
            : ReplyAsync(1, step: 0, expectedDialogSequence: scene.Dialog?.Sequence);
    }
    public Task<OfflineActionResult> ShopReplyAsync(byte tag, string name = "", byte wireSlot = 0,
        string second = "", long? expectedDialogSequence = null)
    {
        byte[] first = OriginalAscii(name), other = OriginalAscii(second);
        long sequence = expectedDialogSequence ?? Model.CaptureScene().Shop?.Sequence
            ?? throw new InvalidOperationException("답할 상점창이 없습니다.");
        return Queue(ClientOp.ShopReply, () =>
        {
            if (Model.CaptureScene().Shop?.Sequence != sequence) throw new InvalidOperationException("지난 상점창의 입력은 취소되었습니다.");
            byte[] body;
            if (tag == 4) { body = new byte[8]; body[7] = wireSlot; }
            else
            {
                body = new byte[9 + first.Length + other.Length]; body[7] = (byte)first.Length;
                first.CopyTo(body, 8); body[8 + first.Length] = (byte)other.Length; other.CopyTo(body, 9 + first.Length);
            }
            body[0] = tag; return body;
        }, sequence);
    }
    public Task<OfflineActionResult> WorldMapSelectAsync(int destinationIndex, long? expectedSequence = null)
    {
        long sequence = expectedSequence ?? Model.CaptureScene().WorldMap?.Sequence
            ?? throw new InvalidOperationException("답할 세계 지도창이 없습니다.");
        return Queue(ClientOp.WorldMapSelect, () =>
        {
            var map = Model.CaptureScene().WorldMap;
            if (map?.Sequence != sequence) throw new InvalidOperationException("지난 세계 지도의 입력은 취소되었습니다.");
            if (destinationIndex < 0 || destinationIndex >= map.Destinations.Length)
                throw new ArgumentOutOfRangeException(nameof(destinationIndex));
            var destination = map.Destinations[destinationIndex];
            // 4.95 selection and ESC share this exact nine-byte body. The server
            // puts the captured origin tile first; cancellation therefore selects 0.
            byte[] body = new byte[9]; BinaryPrimitives.WriteUInt32BigEndian(body, destination.Map);
            BinaryPrimitives.WriteUInt16BigEndian(body.AsSpan(4), destination.X);
            BinaryPrimitives.WriteUInt16BigEndian(body.AsSpan(6), destination.Y); return body;
        }, sequence);
    }
    public Task<OfflineActionResult> CancelWorldMapAsync(long? expectedSequence = null)
        => WorldMapSelectAsync(0, expectedSequence);
    private Task<OfflineActionResult> ItemGesture(byte opcode, byte slot, bool all)
    { if (slot == 0) throw new ArgumentOutOfRangeException(nameof(slot)); return Queue(opcode, () => new[] { slot, all ? (byte)1 : (byte)0 }); }
    private Task<OfflineActionResult> Slot(byte opcode, byte slot)
    { if (slot == 0) throw new ArgumentOutOfRangeException(nameof(slot)); return Queue(opcode, () => new[] { slot }); }
    private static void CheckDirection(int direction)
    { if (direction is < 0 or > 3) throw new ArgumentOutOfRangeException(nameof(direction)); }
    private static byte[] OriginalAscii(string text)
    {
        if (text.Length > 255 || text.Any(c => c < 0x20 || c > 0x7e))
            throw new ArgumentException("원본 게임의 자유 입력은 영문·숫자·기호 255자까지 지원합니다. 한글 표시명은 별도로 보존합니다.", nameof(text));
        return Encoding.ASCII.GetBytes(text);
    }
    private Task<OfflineActionResult> Queue(byte opcode, Func<byte[]> body, long? acknowledge = null)
    {
        long generation = Host.Generation, lifecycle = Host.LifecycleVersion;
        return RunCommandAsync(opcode, body, generation, lifecycle, Model.MapEpoch, acknowledge);
    }
    private async Task<OfflineActionResult> RunCommandAsync(byte opcode, Func<byte[]> body, long generation, long lifecycle, long mapEpoch, long? acknowledge)
    {
        await _commands.WaitAsync(_stopping.Token);
        try
        {
            if (!Ready) throw new InvalidOperationException("게임이 준비되지 않았거나 일시 중지되었습니다.");
            if (Model.MapEpoch != mapEpoch) throw new InvalidOperationException("지도 전환 전의 입력을 취소했습니다. 새로 터치하세요.");
            var before = Model.CaptureScene();
            var result = await Host.ReceiveAsync(opcode, body(), expectedGeneration: generation, expectedLifecycleVersion: lifecycle, expectedMapEpoch: mapEpoch);
            if (result.Committed)
            {
                if (acknowledge is not null) Model.AcknowledgeDialog(acknowledge.Value);
                var after = Model.CaptureScene();
                // Original EnterMap also resets terrain for a same-map warp (e.g. Gateway).
                // Its visible rectangle alone is insufficient for rendering and touch routing.
                if (after.Map != before.Map || after.Cells.Length < (long)after.Width * after.Height || opcode == ClientOp.WorldMapSelect)
                {
                    bool largeMap = (long)after.Width * after.Height > MaximumMapCellsPerRequest;
                    if (largeMap) Volatile.Write(ref _pendingMap, new(after.Map, after.Width, after.Height, generation));
                    byte[] map = new byte[6]; map[4] = checked((byte)after.Width); map[5] = checked((byte)after.Height);
                    try
                    {
                        if (largeMap) await CompletePendingMapAsync(generation, lifecycle);
                        else await Host.ReceiveAsync(ClientOp.MapRequest, map, expectedGeneration: generation, expectedLifecycleVersion: lifecycle);
                    }
                    catch (InvalidOperationException) when (!Host.Faulted && (Host.Paused || Host.LifecycleVersion != lifecycle))
                    {
                        // The user's action already committed. A later application pause cancels only this
                        // read-only map follow-up; never report the committed action as rolled back or retry it.
                        // Original EnterMap has already primed the visible rectangle.
                    }
                }
                if (opcode is ClientOp.Wield or ClientOp.Unequip or ClientOp.Cast or ClientOp.NpcDialog or ClientOp.ShopReply
                    && !Host.Paused && !Host.Faulted && Host.LifecycleVersion == lifecycle)
                {
                    try { await Host.ReceiveAsync(ClientOp.ProfileRequest, new byte[] { 0 }, expectedGeneration: generation, expectedLifecycleVersion: lifecycle); }
                    catch (InvalidOperationException) when (!Host.Faulted && (Host.Paused || Host.LifecycleVersion != lifecycle))
                    { /* A later lifecycle fence cancels only this read-only refresh, never the committed action. */ }
                }
            }
            return result;
        }
        finally { _commands.Release(); }
    }

    /// <summary>Original 0x05 requests, split only when the 4.95 0x06 reply would overflow its u16
    /// length: opcode + increment + 6-byte rectangle + 4 bytes/cell. The cipher does not compress it.
    /// Small-map requests keep their exact bytes, including the startup checksum tail.</summary>
    internal static IEnumerable<byte[]> MapRequests(int width, int height, int requestBytes = 6)
    {
        byte w = checked((byte)width), h = checked((byte)height);
        if ((long)width * height <= MaximumMapCellsPerRequest)
        {
            byte[] request = new byte[requestBytes]; request[4] = w; request[5] = h;
            yield return request; yield break;
        }
        int rows = Math.Min(byte.MaxValue, MaximumMapCellsPerRequest / width);
        for (int y = 0; y < height; y += rows)
        {
            byte[] request = new byte[requestBytes];
            BinaryPrimitives.WriteUInt16BigEndian(request.AsSpan(2), checked((ushort)y));
            request[4] = w; request[5] = (byte)Math.Min(rows, h - y);
            yield return request;
        }
    }

    // Caller holds _commands. Readiness and retry concern only the current large-map cache.
    private async Task CompletePendingMapAsync(long generation, long lifecycle)
    {
        var pending = Volatile.Read(ref _pendingMap);
        if (pending is null) return;
        foreach (byte[] request in MapRequests(pending.Width, pending.Height))
        {
            if (_stopping.IsCancellationRequested || Host.Generation != pending.Generation || Model.Map != pending.Id)
            { Interlocked.CompareExchange(ref _pendingMap, null, pending); return; }
            var result = await Host.ReceiveAsync(ClientOp.MapRequest, request,
                expectedGeneration: generation, expectedLifecycleVersion: lifecycle);
            if (!result.Committed) return; // retain the fence; a partial cache is not ready
        }
        var scene = Model.CaptureScene();
        if (scene.Map != pending.Id || scene.Width != pending.Width || scene.Height != pending.Height)
        { Interlocked.CompareExchange(ref _pendingMap, null, pending); return; }
        if (scene.Cells.Length != pending.Width * pending.Height || scene.Cells.Any(c =>
            c.X < 0 || c.Y < 0 || c.X >= pending.Width || c.Y >= pending.Height))
            throw new InvalidDataException("Large-map terrain cache is incomplete.");
        Interlocked.CompareExchange(ref _pendingMap, null, pending);
    }

    public void RequestPause() => Host.RequestPause();
    public void RequestStop() { _stopping.Cancel(); Volatile.Write(ref _pendingMap, null); Host.RequestStop(); }
    public Task<OfflineSaveReceipt> SaveAsync() => Host.SaveAsync();
    public Task<OfflineSaveReceipt> PauseAsync() => Host.PauseAsync();
    public async Task ResumeAsync(long? expectedControlVersion = null)
    {
        await Host.ResumeAsync(expectedControlVersion);
        if (Volatile.Read(ref _pendingMap) is null || Host.Paused || Host.Faulted || _stopping.IsCancellationRequested) return;
        await _commands.WaitAsync(_stopping.Token);
        try
        {
            if (Host.Paused || Host.Faulted || _stopping.IsCancellationRequested) return;
            long generation = Host.Generation, lifecycle = Host.LifecycleVersion;
            try { await CompletePendingMapAsync(generation, lifecycle); }
            catch (InvalidOperationException) when (!Host.Faulted && (Host.Paused || Host.LifecycleVersion != lifecycle))
            { /* a later Home fence leaves the cache pending for a fresh Resume */ }
        }
        finally { _commands.Release(); }
    }
    public Task StopAsync() { RequestStop(); return Host.StopAsync(); }
}
