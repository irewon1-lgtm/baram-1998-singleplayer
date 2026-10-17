#!/usr/bin/env python3
"""Package explicit review evidence, excluding original assets, keys and userdata."""
import argparse,hashlib,json,zipfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--selection',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 root=a.workspace.resolve();selection=json.loads(a.selection.read_text());out=a.output.resolve()
 if out.exists():raise ValueError('Fresh archive path required')
 files={}
 bannedparts={'data','config','userdata','.godot','__pycache__','characters','private-resume','new-private-test-signing','initial-save-fixtures'}
 allowed={'.json','.jsonl','.csv','.log','.png','.jpg','.jpeg','.html','.md','.txt','.py','.gd','.diff','.mp4','.mkv'}
 def add(path):
  path=path.resolve();rel=path.relative_to(root)
  if path.is_symlink()or not path.is_file():return
  if any(s in bannedparts or 'userdata' in s or s.endswith('-xdg') for s in rel.parts):return
  if path.suffix.lower()not in allowed:return
  if path.name.endswith('-save.json') or path.name in {'fixture-seed-save.json','seed-save.json'}:return
  if path.suffix.lower()=='.json':
   try:document=json.loads(path.read_text())
   except (ValueError,UnicodeError):document=None
   if isinstance(document,dict) and ({'owner','payload','profile','manifest_sha256'}<=document.keys() or {'character','inventory','monsters'}<=document.keys()):return
  if any(s in path.name.lower()for s in ['keystore','private-key','password','android-signing']):raise ValueError('Sensitive file in evidence selection')
  files[rel.as_posix()]=path
 for row in selection['paths']:
  item=root/row
  if not item.exists():raise ValueError('Missing selected evidence: '+row)
  if item.is_dir():
   for file in sorted(item.rglob('*')):add(file)
  else:add(item)
 records=[];out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True)as z:
  for rel,path in sorted(files.items()):
   digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest();records.append({'path':rel,'bytes':path.stat().st_size,'sha256':digest});z.write(path,rel)
  index={'schema':'baram.r16.evidence-archive/1','scope':selection['scope'],'files':records,'raw_DAT_original_archives_keys_user_saves_included':False,'skipped_userdata_directories_and_schema_recognized_save_files':True,'note':'Verdicts are authored in individual reports. Archive creation does not establish PASS.'}
  z.writestr('EVIDENCE_INDEX.json',json.dumps(index,ensure_ascii=False,indent=2)+'\n')
  z.writestr('OPEN_FIRST.txt','baram-G2-r16-results.html is the separately delivered summary.\nOpen evidence/world-qa-joint-final/world-qa-gallery.html for actual maps and doors; evidence/city-building-gallery/architecture-gallery.html for buildings; final_comparison/final/reference-before-after.html for the sole reference and actual before/after scenes.\nAll prior failures and conditional evidence reuse remain attributed to their original source versions.\nNative platforms/account/long stability are not inferred from this archive.\n')
 with zipfile.ZipFile(out)as z:
  for row in records:
   if hashlib.sha256(z.read(row['path'])).hexdigest()!=row['sha256']:raise ValueError('Archive member differs: '+row['path'])
 receipt={'path':str(out),'bytes':out.stat().st_size,'sha256':hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),'verified_members':len(records),'selection_sha256':hashlib.sha256(a.selection.read_bytes()).hexdigest()}
 out.with_suffix('.receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
