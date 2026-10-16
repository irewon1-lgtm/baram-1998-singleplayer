# P2-01 KR1.25 map consumption

The actual `LIB-009` ZIP bytes were read, checked against SHA256
`62642ca3ef492f58947abb2c17cbae5b5a60d5f96fd146704b7d99d1aad3bcef`,
and the bounded legacy DAT/PAL reader was reused. The converter is
`tools/rebuild/p2/kr125_map.py`. It adds the KR1.25-specific raw bitmap and
SOBJECT.OTB consumer; it does not alter the archived parser or use the
undated 4.x editor atlases as Korean1.25 graphics.

Native maps 1, 99, 100 were rendered using only their original DAT's
TileA/B/C, WINDLAND.PAL, SOBJECT.OTB and SOTP.DAT. The output contains 777
object placements, with height/offset and per-cell depth ordering preserved.
Map1 renders a wooden/stone interior; map99 renders cave terrain; map100
renders water/rock terrain. These are visual descriptions, not verified
Korean map names. All three full storage-chunk composite PNGs were viewed.

The source inventory retains all218 MAP members. 196 exact single64x64
storage chunks parse and their tile/object references fit the original DAT.
22 remain BLOCKED: 21 have nonexact/large multi-chunk lengths (no server
active width/height imported), and map4 has out-of-range ground/object
words. Extra bytes are not trimmed and missing objects are not replaced.
This is format/reference validation, not196 historically verified maps.

The source client executable was not executed. Its own static x86
instructions independently establish24px tiles,64x64 disk chunk copying,
A/C's prepended blank tile, B's1024base, extended A2048..2175, upward
object stacking, index0 transparency, and directional movement edge rules.
A/C words are1-based; B is zero-based after subtracting1024. SOTP has one
prepended zero entry for the null object. The SOBJECT.OTB stores u16count,
u32offsets and variable height/u16tile words. All2000 objects and all6422
constituent tile words pass full-file bounds validation. Actual selected
map object IDs are much fewer and only their referenced output is emitted.

|Independent executable fact|Start VA|End VA exclusive|Span SHA256|
|---|---|---|---|
|64x64 disk chunks copied into a 128x128 sliding memory window|0x40dfcc|0x40dfe9|4b0f12ebf384d82fd8e1196a093930eaa2a485e6890c2d08794cf0b8d1dc9bd6|
|ground graphics: 24px, B base1024, A extension2048..2175|0x40f0c9|0x40f13c|f0a8c72dffb6f78ff6208de942ecbbece00399c6918d72c0cfd91ba74295cc73|
|A prepends one zero tile; B uses no prefix; C prepends one zero tile|0x428401|0x428476|8bbf1ad95f5fe32ccb035fa7b008a1ddfe26925f6c7697316e5648e0cce99555|
|object stack draws native tile words upward from base row|0x40f738|0x40f7a6|118807abc29037fb2bb3cf84cea51f6a54db7008a93141905de2be2697c2eb56|
|SOTP raw bytes have one zero byte prepended for null object|0x40de04|0x40de1d|e5a24cfd98403609197e420fc240232630643aec612466f73e6e1e08f4c004c3|
|movement target and source edge checks; B terrain blocked|0x412d73|0x412e4a|d0df24dd0ff10fe5596ac5b6b84155692a1efd5c728c2c5db4240b280a31ac13|
|index0 is transparent for object blit|0x429cd3|0x429ce1|3cbe23e706093d006bb133f761ffb0a78cf27557502abfbfafc3479d94e72f45|
|N/E/S/W dx then dy table|0x4342f0|8 bytes|c4665c798bf416fe2c7df405e6cb8ac5d094762380a5f27ebf09f74f8789da62|

The declared movement rules use N/E/S/W dx/dy from the executable data
table. A source edge uses1/2/4/8 and target reverse edge4/8/1/2; target
ground in1024..2047 blocks movement. `collisions.status` is
STATIC_EXE_DERIVED, not original-client runtime verification. Active map
width/height came from a server packet in the source client, so the64x64
storage extent is explicitly not promoted to the exact playable rectangle.
Blank external cells are not known original walkable terrain.

No Korean city name, exit, return point, server spawn, historical tile
geometry match or original-client movement/occlusion pass was invented.
Those stay UNKNOWN/UNVERIFIED. Godot consumption, actor/object occlusion
and actual movement observations are separate integration evidence.

## Private output and reproducibility

Current private output: `/workspace/scratch/97ae6f841c63/private_runtime/maps`.
This is a local generation location, not a user download or durable source.
The parent integration's private delivery receipt owns persistent input IDs
and restore commands. Its required input is LIB-009; the reference ZIP's
`legacy_parser_tools/legacy_assets.py` restores the reused bounded reader.
The converter records all original member lengths/SHA, decoder/converter
fingerprints and an ARTIFACTS.json hash list. Objects are regenerated once
per run; existing PNGs do not validate an old parser/palette generation.

```sh
python tools/rebuild/p2/kr125_map.py \
  --client-zip PRIVATE_INPUTS/KR_1.25_winbaram.zip \
  --parser-dir PRIVATE_RESTORED_PARSERS \
  --output PRIVATE_RUNTIME/maps --maps 1,99,100
```

Actual command exit0 generated3 maps/777placements. The accompanying
`evidence/map-converter-validation.json` records7 executed checks with
0failures: original invalidmap4 retained/rejected; original map3 extra byte
rejected; copied map truncation/unknown object/OTB truncation rejected;
original executable direction deltas independently compared;54 generated
runtime artifact hashes checked. Expected-rejection PASS does not make
map3/map4 valid. No full G0 or P2 completion is implied.
