#!/usr/bin/env python3
"""Split a verified evidence archive into ordinary ZIPs and verify every member."""
import argparse,copy,hashlib,json,zipfile
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output-directory',type=Path,required=True);a=p.parse_args()
 a.output_directory.mkdir(parents=True,exist_ok=True);limit=400*1024*1024
 with zipfile.ZipFile(a.source)as src:
  index=src.read('EVIDENCE_INDEX.json');old=json.loads(index);expected={r['path']:r for r in old['files']}
  groups=[[]];size=0
  for info in src.infolist():
   if info.filename not in expected:continue
   cost=info.compress_size+len(info.filename.encode('utf-8'))*2+100
   if groups[-1]and size+cost>limit:groups.append([]);size=0
   groups[-1].append(info);size+=cost
  outputs=[];seen=set()
  for i,group in enumerate(groups,1):
   out=a.output_directory/f'baram-G2-r16-evidence-{i}.zip'
   if out.exists():raise ValueError('Fresh output required')
   with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True)as dst:
    for info in group:
     data=src.read(info);r=expected[info.filename]
     assert hashlib.sha256(data).hexdigest()==r['sha256'];dst.writestr(copy.copy(info),data)
    dst.writestr('EVIDENCE_INDEX.json',index)
    dst.writestr('PART_INDEX.json',json.dumps({'schema':'baram.r16.evidence-part/1','part':i,'parts':len(groups),'members':[x.filename for x in group],'original_archive_sha256':hashlib.file_digest(a.source.open('rb'),'sha256').hexdigest(),'scope':'Lossless member-content repartition; not a new test or visual verdict.'},ensure_ascii=False,indent=2)+'\n')
    dst.writestr('OPEN_FIRST.txt',f'검증 근거 {i}/{len(groups)}\n\n증거 ZIP {len(groups)}개를 같은 폴더에 풀어 폴더 내용을 병합하세요.\n그 다음 evidence/world-qa-joint-final/world-qa-gallery.html을 열면111지도·276출입구 근거를 볼 수 있습니다.\n건물은 evidence/city-building-gallery/architecture-gallery.html, 기준·전후는 final_comparison/final/reference-before-after.html입니다.\n별도 제공하는 baram-G2-r16-results.html은 압축 해제 없이 전체 요약과111개 실제 지도 미리보기를 보여줍니다.\n각 파일의 실제 시험·재사용·FAIL·NOT_RUN 범위는 원래 보고서를 그대로 보존했습니다. 분할은 검사 PASS를 추가하지 않습니다.\n')
   assert out.stat().st_size<=512*1024*1024
   with zipfile.ZipFile(out)as check:
    for info in group:
     assert info.filename not in seen;seen.add(info.filename)
     assert hashlib.sha256(check.read(info.filename)).hexdigest()==expected[info.filename]['sha256']
   outputs.append({'filename':out.name,'local_path':str(out.resolve()),'bytes':out.stat().st_size,'sha256':hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),'verified_original_members':len(group)})
  assert seen==expected.keys()
 receipt={'schema':'baram.r16.evidence-parts/1','original_archive':str(a.source.resolve()),'original_archive_sha256':hashlib.file_digest(a.source.open('rb'),'sha256').hexdigest(),'all_original_members_verified':len(seen),'all_original_content_hashes_preserved':True,'parts':outputs,'instruction':'Extract all3 ordinary ZIPs into the same folder and merge their directories; open the standalone results HTML for a no-extraction summary.'}
 (a.output_directory/'EVIDENCE_PARTS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
