"""Losslessly extract original per-frame pixels; no new art, palette or content identity."""
from pathlib import Path
import hashlib,json,zlib
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];folder=ROOT/'android/assets/runtime';catalog=folder/'catalog.json';doc=json.loads(catalog.read_text());images={};rows={};body=bytearray();source_hashes={}
for key,frame in doc['frames'].items():
 if not key.startswith(('head:','body:')):continue
 name=frame.get('atlas_file','atlas.png')
 if name not in images:
  images[name]=Image.open(folder/name).convert('RGBA');source_hashes[name]=hashlib.sha256((folder/name).read_bytes()).hexdigest()
 x,y,w,h=frame['rect'];raw=images[name].crop((x,y,x+w,y+h)).tobytes();assert len(raw)==w*h*4
 packed=zlib.compress(raw,6);rows[key]=[len(body),len(packed),w,h];body.extend(packed)
target=folder/'character-pixels.bin';target.write_bytes(body)
index={'schema':'P1998_LOSSLESS_CHARACTER_PIXELS_1','source_catalog_sha256':hashlib.sha256(catalog.read_bytes()).hexdigest(),'source_atlases':source_hashes,'blob':'character-pixels.bin','blob_bytes':len(body),'blob_sha256':hashlib.sha256(body).hexdigest(),'frames':rows}
(folder/'character-pixels.json').write_text(json.dumps(index,separators=(',',':')))
print(json.dumps({'frames':len(rows),'source_atlases':len(images),'compressed_bytes':len(body),'new_art':0}))
