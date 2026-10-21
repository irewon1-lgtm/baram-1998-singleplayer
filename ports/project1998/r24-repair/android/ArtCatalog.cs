using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.IO.Compression;
using System.Diagnostics;
using Godot;
using Shared;

/// <summary>Draws unchanged, unscaled source pixels from the selected 4.x atlas.
/// Frame rectangles and signed origins come from the audited asset catalog. Missing
/// source-version art uses separately declared, user-authorized playable substitutes.
/// Ordinary-human poses and equipment families follow the original 4.95 resolver;
/// native executable timing, blend and occlusion parity remain unverified.</summary>
public sealed class ArtCatalog
{
    public const string NativeParityStatus = "NOT_RUN";
    public const string ActorPoseBindingStatus = ActorPose.BindingStatus;

    internal readonly record struct ArtFrame(Rect2 Region, Vector2 Origin, int TerrainLayer = 0, string? AtlasFile = null);
    private readonly Dictionary<int, ArtFrame?> _groundFrames = new();
    private readonly Dictionary<int, IReadOnlyList<ArtFrame>> _objectFrames = new();
    private readonly JsonElement _root;
    private readonly Texture2D _atlas;
    private readonly Dictionary<string, Texture2D> _extraAtlases = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Vector2I> _extraAtlasSizes = new(StringComparer.Ordinal);
    private readonly string _assetFolder;
    private readonly Dictionary<string, ArtFrame> _frames = new(StringComparer.Ordinal);
    private readonly Dictionary<int, Texture2D> _icons = new();
    private readonly HashSet<string> _missing = new(StringComparer.Ordinal);
    private readonly HashSet<string> _substitutions = new(StringComparer.Ordinal);
    private readonly BudgetCache<Texture2D> _customFrames = new(512, 4 * 1024 * 1024);
    private readonly BudgetCache<byte[]> _characterPixels = new(256, 2 * 1024 * 1024);
    private readonly Dictionary<string, (long Offset, int Length, int Width, int Height)> _pixelRows = new(StringComparer.Ordinal);
    private long _customMisses, _smallFrameReads, _smallFrameBytes, _smallFrameTicks;
    private readonly object _missingGate = new();
    private readonly int _cellPixels;
    private Texture2D? _deathSign;

    public IReadOnlyCollection<string> Missing
    {
        get { lock (_missingGate) return _missing.OrderBy(x => x, StringComparer.Ordinal).ToArray(); }
    }
    public IReadOnlyCollection<string> Substitutions
    {
        get { lock (_missingGate) return _substitutions.OrderBy(x => x, StringComparer.Ordinal).ToArray(); }
    }

    public ArtCatalog(string catalogPath = "res://assets/runtime/catalog.json")
    {
        string text = Godot.FileAccess.GetFileAsString(catalogPath);
        if (string.IsNullOrEmpty(text)) throw new InvalidDataException($"Missing asset catalog: {catalogPath}");
        using var doc = JsonDocument.Parse(text);
        _root = doc.RootElement.Clone();
        if (_root.GetProperty("schema").GetString() != "P1998_G2_RUNTIME_ASSETS_1")
            throw new InvalidDataException("Unsupported original asset catalog schema.");
        _cellPixels = _root.GetProperty("cell_pixels").GetInt32();
        if (_cellPixels != 24) throw new InvalidDataException("Unexpected original tile size.");
        string folder = _assetFolder = catalogPath[..(catalogPath.LastIndexOf('/') + 1)];
        string atlasFile = _root.GetProperty("atlas").GetProperty("file").GetString()
            ?? throw new InvalidDataException("Atlas path is absent.");
        if (atlasFile.Contains("..", StringComparison.Ordinal) || atlasFile.StartsWith('/') || atlasFile.Contains(':'))
            throw new InvalidDataException("Atlas must be relative to its catalog.");
        _atlas = ResourceLoader.Load<Texture2D>(folder + atlasFile)
            ?? throw new InvalidDataException($"Missing original atlas texture: {folder + atlasFile}");
        if (_atlas.GetWidth() != _root.GetProperty("atlas").GetProperty("width").GetInt32()
            || _atlas.GetHeight() != _root.GetProperty("atlas").GetProperty("height").GetInt32())
            throw new InvalidDataException("Atlas dimensions do not match the catalog.");
        foreach (var row in _root.GetProperty("frames").EnumerateObject())
        {
            Texture2D texture = _atlas;
            if (row.Value.TryGetProperty("atlas_file", out var extraFile))
            {
                string file = extraFile.GetString() ?? throw new InvalidDataException("Additional atlas path is absent.");
                if (file.Contains("..", StringComparison.Ordinal) || file.Contains('/') || file.Contains('\\') || file.Contains(':'))
                    throw new InvalidDataException("Additional sprite atlas must be a sibling of its catalog.");
                if (!_extraAtlasSizes.TryGetValue(file, out var dimensions))
                {
                    var declared = _root.GetProperty("extra_atlases").GetProperty(file);
                    dimensions = new(declared.GetProperty("width").GetInt32(), declared.GetProperty("height").GetInt32());
                    if (dimensions.X <= 0 || dimensions.Y <= 0 || !ResourceLoader.Exists(folder + file, "Texture2D"))
                        throw new InvalidDataException("Missing original sprite atlas: " + folder + file);
                    _extraAtlasSizes.Add(file, dimensions);
                }
                // Validate every declared rectangle now, but keep unused original atlases
                // off the GPU. The actual texture dimensions are checked on first use.
            }
            JsonElement r = row.Value.GetProperty("rect"), o = row.Value.GetProperty("origin");
            var frame = new ArtFrame(new Rect2(r[0].GetInt32(), r[1].GetInt32(), r[2].GetInt32(), r[3].GetInt32()),
                new Vector2(o[0].GetInt32(), o[1].GetInt32()), AtlasFile: row.Value.TryGetProperty("atlas_file", out var atlasName) ? atlasName.GetString() : null);
            Vector2I size = frame.AtlasFile is { } fileName ? _extraAtlasSizes[fileName] : new(texture.GetWidth(), texture.GetHeight());
            if (frame.Region.Position.X < 0 || frame.Region.Position.Y < 0 || frame.Region.Size.X <= 0 || frame.Region.Size.Y <= 0
                || frame.Region.End.X > size.X || frame.Region.End.Y > size.Y)
                throw new InvalidDataException($"Asset frame exceeds its atlas: {row.Name}");
            _frames.Add(row.Name, frame);
        }
        string indexPath = folder + "character-pixels.json";
        if (Godot.FileAccess.FileExists(indexPath))
        {
            using var pixels = JsonDocument.Parse(Godot.FileAccess.GetFileAsString(indexPath));
            if (pixels.RootElement.GetProperty("schema").GetString() != "P1998_LOSSLESS_CHARACTER_PIXELS_1")
                throw new InvalidDataException("Unsupported character pixel index.");
            foreach (var row in pixels.RootElement.GetProperty("frames").EnumerateObject())
                _pixelRows.Add(row.Name, (row.Value[0].GetInt64(), row.Value[1].GetInt32(), row.Value[2].GetInt32(), row.Value[3].GetInt32()));
        }
    }

    // Bounded by both entries and RGBA bytes. Eviction is incremental and recency is refreshed on hits.
    private sealed class BudgetCache<T>(int maximumItems, long maximumBytes) where T : class
    {
        private readonly Dictionary<string, (T Value, long Bytes, LinkedListNode<string> Node)> _entries = new(StringComparer.Ordinal);
        private readonly LinkedList<string> _recent = new();
        public int Count => _entries.Count;
        public long Bytes { get; private set; }
        public long Evictions { get; private set; }
        public bool TryGetValue(string key, out T value)
        {
            if (!_entries.TryGetValue(key, out var row)) { value = null!; return false; }
            _recent.Remove(row.Node); _recent.AddFirst(row.Node); value = row.Value; return true;
        }
        public void Add(string key, T value, long bytes)
        {
            _entries.Add(key, (value, bytes, _recent.AddFirst(key))); Bytes += bytes;
            while (Count > maximumItems || Bytes > maximumBytes)
            {
                string oldest = _recent.Last!.Value; var row = _entries[oldest];
                _entries.Remove(oldest); _recent.RemoveLast(); Bytes -= row.Bytes; Evictions++;
            }
        }
    }

    public object CustomizationDiagnostics() => new
    {
        atlas_reads = 0, atlas_read_bytes = 0L, custom_misses = _customMisses,
        small_frame_reads = _smallFrameReads, small_frame_compressed_bytes = _smallFrameBytes,
        small_frame_read_ms = _smallFrameTicks * 1000.0 / Stopwatch.Frequency,
        texture_entries = _customFrames.Count, texture_rgba_bytes = _customFrames.Bytes,
        texture_limit_entries = 512, texture_limit_rgba_bytes = 4 * 1024 * 1024,
        source_entries = _characterPixels.Count, source_rgba_bytes = _characterPixels.Bytes,
        source_limit_entries = 256, source_limit_rgba_bytes = 2 * 1024 * 1024,
        texture_evictions = _customFrames.Evictions, source_evictions = _characterPixels.Evictions,
    };

    private Image CharacterPixels(string key, ArtFrame frame)
    {
        if (!_characterPixels.TryGetValue(key, out var raw))
        {
            long started = Stopwatch.GetTimestamp();
            if (!_pixelRows.TryGetValue(key, out var row) || row.Width != (int)frame.Region.Size.X || row.Height != (int)frame.Region.Size.Y
                || row.Width <= 0 || row.Height <= 0 || row.Width > 1024 || row.Height > 1024 || row.Length <= 0)
                throw new InvalidDataException("Missing or inconsistent lossless character frame: " + key);
            using var file = Godot.FileAccess.Open(_assetFolder + "character-pixels.bin", Godot.FileAccess.ModeFlags.Read)
                ?? throw new InvalidDataException("Missing lossless character pixels.");
            file.Seek(checked((ulong)row.Offset)); byte[] packed = file.GetBuffer(row.Length);
            if (packed.Length != row.Length) throw new InvalidDataException("Truncated character frame.");
            using var input = new MemoryStream(packed, false); using var decoded = new ZLibStream(input, CompressionMode.Decompress);
            raw = new byte[checked(row.Width * row.Height * 4)]; decoded.ReadExactly(raw);
            if (decoded.ReadByte() != -1) throw new InvalidDataException("Character frame exceeds its declared size.");
            _characterPixels.Add(key, raw, raw.Length); _smallFrameReads++; _smallFrameBytes += packed.Length;
            _smallFrameTicks += Stopwatch.GetTimestamp() - started;
        }
        return Image.CreateFromData((int)frame.Region.Size.X, (int)frame.Region.Size.Y, false, Image.Format.Rgba8, raw);
    }

    private Texture2D TextureFor(ArtFrame frame)
    {
        if (frame.AtlasFile is not { } file) return _atlas;
        if (_extraAtlases.TryGetValue(file, out var texture)) return texture;
        texture = ResourceLoader.Load<Texture2D>(_assetFolder + file)
            ?? throw new InvalidDataException("Missing original sprite atlas: " + _assetFolder + file);
        Vector2I expected = _extraAtlasSizes[file];
        if (texture.GetWidth() != expected.X || texture.GetHeight() != expected.Y)
            throw new InvalidDataException("Additional atlas dimensions differ from the catalog.");
        _extraAtlases.Add(file, texture);
        return texture;
    }

    public bool DrawFrame(CanvasItem target, string key, Vector2 position, float opacity = 1f)
    {
        ArgumentNullException.ThrowIfNull(target);
        if (!_frames.TryGetValue(key, out ArtFrame frame)) { Absent("frame:" + key); return false; }
        Texture2D texture = TextureFor(frame);
        target.DrawTextureRectRegion(texture, new Rect2(position + frame.Origin, frame.Region.Size), frame.Region,
            new Color(1f, 1f, 1f, opacity), false, true);
        return true;
    }

    // Terrain is resolved once per immutable terrain snapshot. Its signed source origins and
    // every multipart SOBJ offset travel with the atlas region, so viewport rejection uses the
    // actual pixel rectangle rather than the owner tile (a tall object can enter from below).
    internal ArtFrame? GroundFrame(int rawGround)
    {
        if (rawGround == 0) return null;
        if (_groundFrames.TryGetValue(rawGround, out var cached)) return cached;
        ArtFrame? resolved = null;
        if (!Row("grounds", rawGround, out JsonElement key)) Absent($"ground:{rawGround}");
        else if (!_frames.TryGetValue(key.GetString()!, out ArtFrame frame)) Absent("frame:" + key.GetString());
        else resolved = frame;
        _groundFrames.Add(rawGround, resolved);
        return resolved;
    }

    internal IReadOnlyList<ArtFrame> ObjectFrames(int objectId)
    {
        if (objectId == 0) return Array.Empty<ArtFrame>();
        if (_objectFrames.TryGetValue(objectId, out var cached)) return cached;
        var resolved = new List<ArtFrame>();
        if (!Row("objects", objectId, out JsonElement row)) Absent($"object:{objectId}");
        else
        {
            int layer = 0;
            foreach (JsonElement key in row.GetProperty("frames").EnumerateArray())
            {
                if (key.ValueKind != JsonValueKind.Null)
                {
                    if (!_frames.TryGetValue(key.GetString()!, out ArtFrame frame)) Absent("frame:" + key.GetString());
                    else resolved.Add(frame with { TerrainLayer = layer });
                }
                layer++;
            }
        }
        IReadOnlyList<ArtFrame> result = resolved.AsReadOnly();
        _objectFrames.Add(objectId, result);
        return result;
    }

    internal void DrawTerrainFrame(CanvasItem target, ArtFrame frame, Vector2 position)
        => target.DrawTextureRectRegion(TextureFor(frame), new Rect2(position - new Vector2(0, frame.TerrainLayer * _cellPixels) + frame.Origin, frame.Region.Size), frame.Region,
            Colors.White, false, true);

    /// <summary>Input is the codec's decoded client Item.epf frame, not the raw 0xC000 wire icon.</summary>
    public Texture2D? IconTexture(int icon)
    {
        if (_icons.TryGetValue(icon, out Texture2D? cached)) return cached;
        if (ReconstructedGraphics.Icon(icon) is { } rebuilt)
        {
            Substitute("r24-reconstructed-role-icon:"+icon);
            _icons.Add(icon,rebuilt);
            return rebuilt;
        }
        if (!Row("items", icon, out JsonElement item)) { Absent($"item:{icon}"); return null; }
        string? key = item.GetProperty("frame").GetString();
        if (key is null || !_frames.TryGetValue(key, out ArtFrame frame)) { Absent($"item-frame:{icon}"); return null; }
        NoteSubstitution("item", icon, item);
        var texture = new AtlasTexture { Atlas = TextureFor(frame), Region = frame.Region, FilterClip = true };
        _icons.Add(icon, texture);
        return texture;
    }

    /// <summary>rawGround retains the original high-bit sheet selector; zero is authored void.</summary>
    public void Ground(CanvasItem target, int rawGround, Vector2 position)
    {
        if (rawGround == 0) return;
        if (!Row("grounds", rawGround, out JsonElement key)) { Absent($"ground:{rawGround}"); return; }
        DrawFrame(target, key.GetString()!, position);
    }

    public int ObjectLayerCount(int objectId)
    {
        if (objectId == 0) return 0;
        if (!Row("objects", objectId, out JsonElement row)) { Absent($"object:{objectId}"); return 0; }
        return row.GetProperty("frames").GetArrayLength();
    }

    /// <summary>position is the original owner tile origin. Layer0 is at that tile;
    /// each later source SOBJ piece is placed one24px tile north internally.</summary>
    public void ObjectLayer(CanvasItem target, int objectId, int layer, Vector2 position)
    {
        if (objectId == 0) return;
        if (!Row("objects", objectId, out JsonElement row)) { Absent($"object:{objectId}"); return; }
        JsonElement frames = row.GetProperty("frames");
        if (layer < 0 || layer >= frames.GetArrayLength()) { Absent($"object-layer:{objectId}:{layer}"); return; }
        JsonElement key = frames[layer];
        if (key.ValueKind == JsonValueKind.Null) return; // An authored empty piece, not missing art.
        DrawFrame(target, key.GetString()!, position - new Vector2(0, layer * _cellPixels));
    }

    public void Actor(CanvasItem target, byte[] appearance, int direction, int walkFrame, bool attacking, Vector2 position, int hairTone = 0, int skinTone = 0)
        => Actor(target, appearance, direction, walkFrame, attacking ? 1 : 0, position, hairTone, skinTone);

    /// <summary>Signed original EPF bounds for the same selected layers that Actor draws.
    /// The native profile centres BODY+HEAD (0x432d00), then lets weapon pixels extend
    /// from that anchor (0x4329b0); includeWeapon=false selects that centring rectangle.
    /// Source-native layers and declared compatibility layers use the same bounds.</summary>
    public Rect2? ActorBounds(byte[] appearance, int direction = 2, int walkFrame = 0, int action = 0, bool includeWeapon = true)
    {
        if (appearance is null || appearance.Length != 7 || !Facing(direction) || walkFrame < 0
            || !ActorPose.TryResolveAction(direction, walkFrame, action, appearance[5], out var pose)) return null;
        if (appearance[1] == 2) return null; // Native resolver's deliberately hidden form.
        int body = appearance[3]; if (appearance[0] != 0 && body == 0) body = 1;
        Rect2? bounds = null;
        void Add(string family, int art, int ramp, int frame)
        {
            if (!ResolveSprite(family, art, ramp, frame, out string key) || !_frames.TryGetValue(key, out var piece)) return;
            var rect = new Rect2(piece.Origin, piece.Region.Size);
            bounds = bounds is { } previous ? previous.Merge(rect) : rect;
        }
        if (appearance[1] == 1) { Add("ghost", 0, 0, appearance[2]); return bounds; }
        int bodyPose = MountedPose(appearance, direction, walkFrame, action, pose.Body);
        Add("body", body, appearance[4], bodyPose); Add("head", appearance[2], 0, bodyPose);
        if (includeWeapon && (appearance[1] != 3 || action != 0) && pose.Weapon >= 0 && WeaponFamily(appearance[5]) is { } weapon)
            Add(weapon.Family, weapon.Art, 0, pose.Weapon);
        return bounds;
    }

    // New independent hair/skin choices are an explicitly authorized local visual
    // customization. Tone0 preserves original pixels; no 4.95 wire field is invented.
    public void Actor(CanvasItem target, byte[] appearance, int direction, int walkFrame, int action, Vector2 position, int hairTone = 0, int skinTone = 0, RecoveredAppearance cosmetics = default)
    {
        if (appearance is null || appearance.Length != 7) { Absent("actor:appearance-length"); return; }
        if (!Facing(direction) || walkFrame < 0) { Absent($"actor:phase:{direction}:{walkFrame}"); return; }
        if (appearance[1] == 2) return;
        if (!ActorPose.TryResolveAction(direction, walkFrame, action, appearance[5], out var pose))
        { Absent($"actor:pose:{direction}:{walkFrame}:{action}:{appearance[5]}"); return; }
        if (appearance[1] == 1) { Sprite(target, "ghost", 0, 0, appearance[2], position); return; }
        int body = appearance[3]; if (body == 0 && appearance[0] != 0) body = 1;
        int bodyPose = MountedPose(appearance, direction, walkFrame, action, pose.Body);
        JsonElement orders = _root.GetProperty("draw_order");
        if (bodyPose >= orders.GetArrayLength()) { Absent($"actor:draw-order:{bodyPose}"); return; }
        float opacity = appearance[1] is 4 or 5 ? .55f : 1f;
        foreach (char layer in orders[bodyPose].GetString()!)
        {
            switch (layer)
            {
                case 'b': CharacterSprite(target,"body",body,appearance[4],bodyPose,position,0,skinTone,opacity); break;
                case 'h':
                    CharacterSprite(target,"head",appearance[2],0,bodyPose,position,hairTone,skinTone,opacity,
                        cosmetics.Enabled ? cosmetics.HairRgb : -1);
                    if (cosmetics.Enabled && cosmetics.BeardStyle != 0)
                        DrawRecoveredBeard(target, appearance[2], bodyPose, direction, position, cosmetics.BeardStyle, cosmetics.BeardRgb, opacity);
                    break;
                case 'w':
                    if ((appearance[1] != 3 || action != 0) && pose.Weapon >= 0 && WeaponFamily(appearance[5]) is { } weapon)
                    {
                        if (cosmetics.Enabled && cosmetics.WeaponIcon >= 0)
                            DrawRecoveredWeapon(target, cosmetics.WeaponIcon, direction, action, position, opacity);
                        else Sprite(target,weapon.Family,weapon.Art,0,pose.Weapon,position);
                    }
                    break;
                case 's':
                    if ((appearance[1] != 3 || action != 0) && appearance[6] != 255 && action is 0 or 1)
                    {
                        int shieldFrame = action == 1 ? 12 + direction * 2 + walkFrame % 2
                            : direction * 3 + ((walkFrame % 4) switch { 1 => 1, 3 => 2, _ => 0 });
                        Sprite(target,"shield",appearance[6],0,shieldFrame,position);
                    }
                    break;
                case '0': break;
            }
        }
    }

    private static int MountedPose(byte[] appearance, int direction, int phase, int action, int normal)
        => appearance[1] == 3 && action == 0 ? 80 + direction * 3 + ((phase % 4) switch { 1 => 1, 3 => 2, _ => 0 }) : normal;

    private static Color Rgb(int rgb) => Color.Color8((byte)(rgb>>16),(byte)(rgb>>8),(byte)rgb);

    // These vector pixel masks are local compatibility drawings, not recovered beard sheets.
    // Their four styles and 26 colour names come from the unchanged item rows.
    private void DrawRecoveredBeard(CanvasItem target,int face,int pose,int direction,Vector2 anchor,int style,int rgb,float opacity)
    {
        if(direction==0||!ResolveSprite("head",face,0,pose,out string key)||!_frames.TryGetValue(key,out var frame))return;
        string[] mask=style switch
        {
            3=>new[]{"110111011","111111111","011111110","001111100","000111000"},
            1=>new[]{"001111100","000111000","000111000","000010000"},
            7=>new[]{"111101111","110000011","100000001","100000001"},
            _=>new[]{"011101110","111111111","110000011"}
        };
        var origin=(anchor+frame.Origin+new Vector2(frame.Region.Size.X/2-4,frame.Region.Size.Y-5)).Round();
        Color colour=Rgb(rgb<0?0x33281f:rgb);colour.A=opacity;
        Color shade=colour*.65f;shade.A=opacity;
        for(int y=0;y<mask.Length;y++)for(int x=0;x<mask[y].Length;x++)
        {
            if(mask[y][x]!='1')continue;
            if(direction==1&&x<5||direction==3&&x>3)continue;
            target.DrawRect(new Rect2(origin+new Vector2(x,y),Vector2.One),y==mask.Length-1?shade:colour);
        }
        Substitute("reconstructed-vector-beard:"+style);
    }

    // A held inventory drawing makes later skins visible without inventing unsupported weapon
    // pose IDs. The existing weapon still controls the original pose, damage and attack timing.
    private void DrawRecoveredWeapon(CanvasItem target,int icon,int direction,int action,Vector2 anchor,float opacity)
    {
        var texture=IconTexture(icon);if(texture is null)return;
        float ratio=Math.Min(1f,24f/Math.Max(texture.GetWidth(),texture.GetHeight()));
        var size=new Vector2(texture.GetWidth(),texture.GetHeight())*ratio;
        float side=direction==3?-10:direction==1?8:direction==0?-6:8;
        var position=(anchor+new Vector2(side,-24+(action==1?2:0))-size/2).Round();
        target.DrawTextureRect(texture,new Rect2(position,size),false,new Color(1,1,1,opacity));
        Substitute("reconstructed-held-item-skin:"+icon);
    }
    private static (string Family, int Art)? WeaponFamily(byte wire) => wire switch
    {
        255 => null, < 128 => ("sword",wire), < 192 => ("spear",wire-128),
        < 224 => ("bow",wire-192), _ => ("fan",wire-224)
    };

    /// <summary>Playable helmet overlay when native4.95 lacks the later worn-head art.
    /// The actual equipped ground icon is shown; this is not a fabricated original helm pose.</summary>
    public void DrawHeadEquipment(CanvasItem target, int icon, Vector2 anchor, Rect2 bounds)
    {
        var texture = IconTexture(icon); if (texture is null) return;
        float width = Math.Min(20, texture.GetWidth());
        float height = Math.Min(16, texture.GetHeight());
        target.DrawTextureRect(texture, new Rect2(anchor + new Vector2(-width/2, bounds.Position.Y-3), new Vector2(width,height)), false);
        Substitute("wearable-ground-icon-overlay:"+icon);
    }

    private void CharacterSprite(CanvasItem target,string family,int art,int ramp,int frame,Vector2 position,int hairTone,int skinTone,float opacity,int hairRgb=-1)
    {
        if (!ResolveSprite(family,art,ramp,frame,out string key)) return;
        hairTone = Math.Clamp(hairTone,0,7);skinTone = Math.Clamp(skinTone,0,3);
        if ((hairTone == 0 && skinTone == 0 && hairRgb < 0) || !_root.TryGetProperty("character_customization_palette",out var palette))
        { DrawFrame(target,key,position,opacity);return; }
        Substitute($"local-character-colours:{hairTone}:{skinTone}");
        string customKey=key+":"+hairTone+":"+skinTone+":"+hairRgb;
        if (!_customFrames.TryGetValue(customKey,out var texture))
        {
            _customMisses++;
            var f=_frames[key];
            using var image=CharacterPixels(key,f);
            image.Convert(Image.Format.Rgba8);
            var sourceSkin=palette.GetProperty("skin");var sourceHair=palette.GetProperty("hair");
            Color ColorOf(JsonElement a)=>Color.Color8((byte)a[0].GetInt32(),(byte)a[1].GetInt32(),(byte)a[2].GetInt32());
            int firstSkinY=image.GetHeight();
            for(int sy=0;sy<image.GetHeight();sy++)for(int sx=0;sx<image.GetWidth();sx++)
            {
                var sample=image.GetPixel(sx,sy);
                if(sample.A==0)continue;
                for(int shade=0;shade<8;shade++)if(sample==ColorOf(sourceSkin[shade]))firstSkinY=Math.Min(firstSkinY,sy);
            }
            var hairTargets=new[]{Colors.White,new Color(.14f,.13f,.13f),new Color(.42f,.27f,.13f),new Color(.92f,.70f,.22f),new Color(.20f,.35f,.72f),new Color(.50f,.25f,.66f),new Color(.24f,.50f,.28f),new Color(.78f,.80f,.84f)};
            Color hairTarget=hairRgb>=0 ? Rgb(hairRgb) : hairTargets[hairTone];
            var skinTargets=new[]{Colors.White,new Color(.98f,.85f,.69f),new Color(.77f,.55f,.35f),new Color(.47f,.29f,.17f)};
            for(int y=0;y<image.GetHeight();y++)for(int x=0;x<image.GetWidth();x++)
            {
                var pixel=image.GetPixel(x,y);if(pixel.A==0)continue;
                // Black hairstyles share palette16 with the eye/outline. Restrict
                // the authorized colour adaptation to the upper hair silhouette,
                // above the first skin row, so eye and lower-face pixels stay intact.
                if((hairTone!=0||hairRgb>=0) && family=="head" && y<firstSkinY+2 && pixel==Color.Color8(23,23,23))
                {
                    Color altered=hairTarget*.72f;altered.A=pixel.A;image.SetPixel(x,y,altered);continue;
                }
                for(int shade=0;shade<8;shade++)
                {
                    Color? change=null;float weight=.62f+shade*.054f;
                    if(skinTone!=0 && pixel==ColorOf(sourceSkin[shade]))change=skinTargets[skinTone]*weight;
                    if((hairTone!=0||hairRgb>=0) && family=="head" && pixel==ColorOf(sourceHair[shade]))change=hairTarget*weight;
                    if(change is { } altered){altered.A=pixel.A;image.SetPixel(x,y,altered);break;}
                }
            }
            texture=ImageTexture.CreateFromImage(image);_customFrames.Add(customKey,texture,(long)image.GetWidth()*image.GetHeight()*4);
        }
        target.DrawTexture(texture,position+_frames[key].Origin,new Color(1,1,1,opacity));
    }

    public void Creature(CanvasItem target, int look, int color, int direction, int walkFrame, Vector2 position)
    {
        if (!Facing(direction) || walkFrame < 0) { Absent($"creature:phase:{direction}:{walkFrame}"); return; }
        int art = look is >= 0x8000 and < 0xc000 ? look - 0x8000 : look;
        if (!SpriteRow("monster", art, out JsonElement row)) return;
        int walkCount = row.GetProperty("walk_count").GetInt32();
        if (walkCount <= 0) { Absent($"creature:walk-count:{art}"); return; }
        Sprite(target, "monster", art, color, direction * walkCount + walkFrame % walkCount, position);
    }

    public Rect2? CreatureBounds(int look, int color, int direction, int walkFrame)
    {
        if (!Facing(direction) || walkFrame < 0) return null;
        int art = look is >= 0x8000 and < 0xc000 ? look - 0x8000 : look;
        if (art is 681 or 778 or 1302) return new Rect2(-20,-48,40,48);
        if (!SpriteRow("monster", art, out var row)) return null;
        int walkCount = row.GetProperty("walk_count").GetInt32();
        if (walkCount <= 0 || !row.GetProperty("ramps").TryGetProperty(color.ToString(System.Globalization.CultureInfo.InvariantCulture), out var frames)) return null;
        int index = direction * walkCount + walkFrame % walkCount;
        return index < frames.GetArrayLength() && _frames.TryGetValue(frames[index].GetString()!, out var frame)
            ? new Rect2(frame.Origin, frame.Region.Size) : null;
    }

    /// <summary>Original 4.95 health-widget feedback, not an invented monster death body pose.
    /// Native 0x4611e0: percent0 draws DEADSIGN.EPF; positive percent draws a 24x6 bar,
    /// inset1 with 22*percent/100 fill and original BARAM palette indices128/12/14/2.</summary>
    public void CombatHealth(CanvasItem target, int percent, Vector2 actorAnchor, float actorTop)
    {
        if (percent is < 0 or > 100) return;
        if (percent == 0)
        {
            _deathSign ??= ResourceLoader.Load<Texture2D>("res://assets/runtime/ui-extra/deadsign-original.png");
            if (_deathSign is null) { Absent("ui:DEADSIGN"); return; }
            // Native monster bounds resolver0x4344dd translates EPF bounds by(+12,+12).
            // This renderer's established anchor already denotes the EPF centre. Convert
            // native tile-leftX back by12; the signed top below already comes from the body.
            target.DrawTexture(_deathSign, actorAnchor + new Vector2(-8, actorTop + 7));
            return;
        }
        int fill = Math.Min(22, 22 * percent / 100);
        Vector2 origin = actorAnchor + new Vector2(-12, actorTop - 11);
        target.DrawRect(new Rect2(origin, new Vector2(24, 6)), Colors.Black);
        var color = fill < 7 ? new Color(1f, 87 / 255f, 87 / 255f)
            : fill < 12 ? new Color(1f, 1f, 87 / 255f) : new Color(0, 171 / 255f, 0);
        if (fill > 0) target.DrawRect(new Rect2(origin + Vector2.One, new Vector2(fill, 4)), color);
    }

    /// <summary>User-authorized playable impact feedback where the precise historical
    /// critical flash binding is unavailable. It changes no damage or combat rules.</summary>
    public void CombatHitFeedback(CanvasItem target, bool critical, long elapsed, Vector2 anchor, Rect2 bounds)
    {
        if (elapsed < 0 || elapsed >= 120) return;
        float strength = 1f - elapsed / 120f;
        Vector2 centre = anchor + bounds.GetCenter();
        Color color = critical ? new Color(1,1,1,strength) : new Color(1,.85f,.35f,strength);
        float radius = critical ? 9 : 5;
        target.DrawLine(centre-new Vector2(radius,0),centre+new Vector2(radius,0),color,1);
        target.DrawLine(centre-new Vector2(0,radius),centre+new Vector2(0,radius),color,1);
        if (critical)
        {
            target.DrawLine(centre-new Vector2(6,6),centre+new Vector2(6,6),color,1);
            target.DrawLine(centre-new Vector2(6,-6),centre+new Vector2(6,-6),color,1);
            target.DrawRect(new Rect2(anchor+bounds.Position,bounds.Size),new Color(1,1,1,.16f*strength));
        }
        Substitute("playable-hit-feedback:"+(critical?"critical":"normal"));
    }

    /// <summary>frame is the selected original table's front/back sequence index.
    /// Alpha is native transparency, quantized to 32 weights. Godot receives the
    /// complementary source opacity; RGB555/565 rounding and native light-map
    /// pixel parity remain NOT_RUN. Light is retained without invented brightness.</summary>
    public int EffectDuration(int wireId)
    {
        if (!Row("effects", wireId, out JsonElement row)) return 0;
        var frames=row.GetProperty("frames").EnumerateArray();
        int front=0,back=0;
        foreach(var frame in frames)
        {
            int delay=frame.GetProperty("delay_ms").GetInt32();
            if(frame.GetProperty("layer").GetString()=="back")back+=delay;else front+=delay;
        }
        return Math.Max(front,back);
    }
    public int EffectFrame(int wireId, long elapsed, bool back = false)
    {
        if (!Row("effects", wireId, out JsonElement row)) return -1;
        int i = 0; foreach (var frame in row.GetProperty("frames").EnumerateArray())
        {
            bool isBack=frame.GetProperty("layer").GetString()=="back";
            if(isBack==back)
            {elapsed-=frame.GetProperty("delay_ms").GetInt32();if(elapsed<0)return i;}
            i++;
        }
        return -1;
    }
    public void Effect(CanvasItem target, int wireId, int frame, Vector2 position)
    {
        if (!Row("effects", wireId, out JsonElement row)) { Absent($"effect:{wireId}"); return; }
        JsonElement sequence = row.GetProperty("frames");
        if (sequence.GetArrayLength() == 0) return; // Authored empty native effect73.
        if (frame < 0 || frame >= sequence.GetArrayLength()) { Absent($"effect-frame:{wireId}:{frame}"); return; }
        JsonElement selected = sequence[frame];
        DrawFrame(target, selected.GetProperty("frame").GetString()!, position,
            EffectSourceOpacity(selected.GetProperty("alpha").GetSingle()));
    }

    /// <summary>Native 0x434F10 selects the opaque path for Alpha &lt;= 0;
    /// 0x429A7A quantizes positive transparency with int(Alpha*32+0.5).
    /// 0x429BEB..0x429C52 weights source by 32-q and destination by q.
    /// This preserves that weight contract, not its 16-bit channel rounding.</summary>
    public static float EffectSourceOpacity(float nativeTransparency)
    {
        if (!float.IsFinite(nativeTransparency) || nativeTransparency < 0 || nativeTransparency > 1)
            throw new InvalidDataException("Effect transparency is outside its supported original range.");
        if (nativeTransparency <= 0) return 1f;
        int q = (int)(nativeTransparency * 32f + .5f);
        return (32 - q) / 32f;
    }

    public void Ui(CanvasItem target, string name, int frame, Vector2 position)
    {
        string normalized = name.ToUpperInvariant();
        if (!_root.GetProperty("ui").TryGetProperty(normalized, out JsonElement ui)) { Absent("ui:" + normalized); return; }
        JsonElement sequence = ui.GetProperty("frames");
        if (frame < 0 || frame >= sequence.GetArrayLength()) { Absent($"ui-frame:{normalized}:{frame}"); return; }
        DrawFrame(target, sequence[frame].GetString()!, position);
    }

    /// <summary>Responsive framing stretches only selected original UI pixels. Actors, terrain,
    /// and the right-hand scroll retain their native aspect and 24px coordinate system.</summary>
    public void DrawUiSlice(CanvasItem target, string name, int frame, Rect2 source, Rect2 destination)
    {
        string normalized = name.ToUpperInvariant();
        if (!_root.GetProperty("ui").TryGetProperty(normalized, out JsonElement ui)) { Absent("ui:" + normalized); return; }
        JsonElement sequence = ui.GetProperty("frames");
        if (frame < 0 || frame >= sequence.GetArrayLength()) { Absent($"ui-frame:{normalized}:{frame}"); return; }
        if (!_frames.TryGetValue(sequence[frame].GetString()!, out var art)) { Absent("frame:" + sequence[frame].GetString()); return; }
        if (source.Position.X < 0 || source.Position.Y < 0 || source.End.X > art.Region.Size.X || source.End.Y > art.Region.Size.Y
            || source.Size.X <= 0 || source.Size.Y <= 0 || destination.Size.X <= 0 || destination.Size.Y <= 0)
            throw new ArgumentOutOfRangeException(nameof(source), "UI slice exceeds its original frame.");
        target.DrawTextureRectRegion(_atlas, destination, new Rect2(art.Region.Position + source.Position, source.Size), Colors.White, false, true);
    }

    private void Sprite(CanvasItem target,string family,int art,int ramp,int frame,Vector2 position)
    {
        if (family=="monster"&&ReconstructedGraphics.DrawCreature(target,art,position))
        { Substitute("r24-reconstructed-prop:"+art); return; }
        if (ResolveSprite(family,art,ramp,frame,out string key)) DrawFrame(target,key,position);
    }
    private bool ResolveSprite(string family,int art,int ramp,int frame,out string key)
    {
        key=""; if (!SpriteRow(family,art,out var row)) return false;
        if (!row.GetProperty("ramps").TryGetProperty(ramp.ToString(System.Globalization.CultureInfo.InvariantCulture),out var sequence))
        {
            if (!row.GetProperty("ramps").TryGetProperty("0",out sequence)) { Absent($"sprite-ramp:{family}:{art}:{ramp}");return false; }
            Substitute($"palette-fallback:{family}:{art}:{ramp}:0");
        }
        if(frame<0||frame>=sequence.GetArrayLength()){Absent($"sprite-frame:{family}:{art}:{ramp}:{frame}");return false;}
        key=sequence[frame].GetString()!;return true;
    }
    private bool SpriteRow(string family,int art,out JsonElement row)
    {
        if(_root.GetProperty("sprites").TryGetProperty(family,out var rows))
        {
            if(rows.TryGetProperty(art.ToString(System.Globalization.CultureInfo.InvariantCulture),out row)) {NoteSubstitution(family,art,row);return true;}
            int replacement=family=="head"?41:family=="monster"?38:0;
            if(rows.TryGetProperty(replacement.ToString(System.Globalization.CultureInfo.InvariantCulture),out row))
            {Substitute($"sprite-fallback:{family}:{art}:{replacement}");return true;}
        }
        row=default;Absent($"sprite:{family}:{art}");return false;
    }
    private void NoteSubstitution(string family,int art,JsonElement row)
    {if(row.ValueKind==JsonValueKind.Object && row.TryGetProperty("compatibility_substitute",out _))Substitute($"declared:{family}:{art}");}
    private void Substitute(string key){lock(_missingGate)_substitutions.Add(key);}

    private bool Row(string table, int key, out JsonElement row)
    {
        var rows = _root.GetProperty(table);
        if (rows.TryGetProperty(key.ToString(System.Globalization.CultureInfo.InvariantCulture),out row))
        { NoteSubstitution(table,key,row);return true; }
        int replacement=table switch { "effects"=>5,"items"=>232,"objects"=>1,_=>-1 };
        if(replacement>=0 && rows.TryGetProperty(replacement.ToString(System.Globalization.CultureInfo.InvariantCulture),out row))
        {Substitute($"row-fallback:{table}:{key}:{replacement}");return true;}
        return false;
    }
    private static bool Facing(int direction) => direction is >= 0 and <= 3;
    private void Absent(string key) { lock (_missingGate) _missing.Add(key); }
}
