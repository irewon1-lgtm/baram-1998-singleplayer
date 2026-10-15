#!/usr/bin/env python3
"""Compare Godot tokenizer101 semantics, excluding source line/column metadata.

Godot4.6.3 primary specification:
modules/gdscript/gdscript_tokenizer_buffer.{h,cpp}, official4.6.3-stable.
Accepts only all8byte token streams (nonzero token type); fails closed otherwise.
Pool encodings retain identifier/constant indexes and exact Variant bytes.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import zstandard

def sha(b):return hashlib.sha256(b).hexdigest()
def signature(path):
 raw=path.read_bytes();magic,version,size=struct.unpack_from('<3I',raw)
 assert magic==1129530439 and version==101,(path,'unsupported GDC')
 b=zstandard.ZstdDecompressor().decompress(raw[12:],max_output_size=size) if size else raw[12:]
 if size:assert len(b)==size
 ni,nc,nl,nt=struct.unpack_from('<4I',b)
 start=len(b)-nt*8;pool_end=start-nl*16
 assert 16<=pool_end<=start
 tokens=[]
 for i in range(nt):
  code,line=struct.unpack_from('<2I',b,start+i*8)
  assert code&128 and 0<(code&127)<127,(path,'unsupported variable token')
  tokens.append(code&~128)
 pool=b[16:pool_end]
 normalized=struct.pack('<3I',ni,nc,nt)+pool+struct.pack('<'+'I'*nt,*tokens)
 return {'identifiers':ni,'constants':nc,'tokens':nt,'pool_sha256':sha(pool),'semantic_sha256':sha(normalized),'gdc_sha256':sha(raw)},(pool,tokens)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('original');ap.add_argument('recompiled');ap.add_argument('--report',required=True);a=ap.parse_args()
 rows=[]
 for p in sorted(Path(a.original).glob('*.gdc')):
  q=Path(a.recompiled)/p.name;o,os=signature(p);r,rs=signature(q)
  equal=os==rs
  mismatch=next((i for i,(v,w) in enumerate(zip(os[1],rs[1])) if v!=w),None)
  rows.append({'file':p.name,'status':'PASS' if equal else 'FAIL','original':o,'recompiled':r,'first_token_mismatch':mismatch})
 report={'status':'PASS' if rows and all(r['status']=='PASS' for r in rows) else 'FAIL','scope':'same tokenizer101 identifier and constant pool bytes plus token type and value index, excludes only line/column positions','rows':rows}
 Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'files':len(rows),'failed':[r['file'] for r in rows if r['status']!='PASS']},ensure_ascii=False))
if __name__=='__main__':main()
