#!/usr/bin/env python3
"""Regenerate only corrupted PNG pages of an unpublished draft package."""
import io
import sys
import zipfile
from pathlib import Path
from PIL import Image
sys.dont_write_bytecode=True
from common import ROOT, WORK, load, write, file_sha, sha, lines, canonical
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import Epf, dat_entries, read_palettes

def repair():
    p=WORK/'packages/WK-ASSETS-001';out=WORK/'drafts/private-assets/shared'
    if (p/'manifest.json').exists():raise ValueError('Cannot repair frozen package')
    d=dat_entries(next((WORK/'drafts/private-inputs').rglob('NWind.dat')).read_bytes());changed=[]
    for mp in sorted((out/'kr491').glob('*.json')):
        meta=load(mp);epf=Epf(d[meta['source_file']][2]);pals=read_palettes(d[meta['palette_file']][2]);dirty=False
        for page in meta['pages']:
            dest=out/page['path']
            try:
                with Image.open(dest) as im:im.verify()
                continue
            except (OSError,SyntaxError,ValueError):pass
            atlas=Image.new('RGBA',(page['width'],page['height']))
            for fm in meta['frames']:
                if fm['path']!=page['path']:continue
                f=epf.frame(fm['frame']);x,y,cw,ch=fm['region'];ox,oy=fm['pivot']
                if f.width and f.height:
                    im=Image.frombytes('P',(f.width,f.height),f.indices);im.putpalette([c for rgb in pals[fm['palette']].colors for c in rgb]);im=im.convert('RGBA');im.putalpha(Image.frombytes('L',(f.width,f.height),f.alpha))
                    if sha(im.tobytes())!=fm['rgba_sha256']:raise ValueError('Source RGBA changed')
                    atlas.paste(im,(x+ox+f.left,y+oy+f.top))
            buf=io.BytesIO();atlas.save(buf,format='PNG',compress_level=6);dest.write_bytes(buf.getvalue())
            with Image.open(dest) as im:im.verify()
            page.update(size_bytes=dest.stat().st_size,sha256=file_sha(dest));changed.append(page['path']);dirty=True
        if dirty:write(mp,meta)
    for f in sorted(p.glob('content-*.jsonl')):
        rs=lines(f)
        for r in rs:
            a=r['data']['acquisition'];mp=out/a['member']
            if a['member'].startswith('kr491/'):
                a['sha256']=file_sha(mp)
                if r['data']['asset_type'] in ('frame_sheet','tile_sheet'):
                    m=load(mp);r['data']['metadata'].update(pages=m['pages'],frame_metadata_sha256=file_sha(mp))
        f.write_text(''.join(canonical(r)+'\n' for r in rs))
    write(out/'PRIVATE_MANIFEST.json',{'protocol_id':'BARAM_PARALLEL_V1','bundle_id':'wk.bundle.assets.001',
      'source_dat_sha256':'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7','public_pixels':False,
      'files':[{'path':str(f.relative_to(out)),'size_bytes':f.stat().st_size,'sha256':file_sha(f)} for f in sorted(out.rglob('*')) if f.is_file() and f.name!='PRIVATE_MANIFEST.json']})
    bundle=WORK/'drafts/work_assets_shared_PRIVATE_20261014.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                zi=zipfile.ZipInfo(str(f.relative_to(out)),(2026,10,14,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16;z.writestr(zi,f.read_bytes())
    acquire=load(p/'acquisition.json');acquire.update(size_bytes=bundle.stat().st_size,sha256=file_sha(bundle));write(p/'acquisition.json',acquire)
    write(WORK/'catalog/asset-page-repair.json',{'batch_id':p.name,'changed_pages':changed,'source_rgba_hashes':'UNCHANGED','scope':'Unpublished draft only','initial_fail_log':'drafts/assets-validation-first.log'})
    print('Repaired',len(changed),'pages',bundle.stat().st_size)
if __name__=='__main__':repair()
