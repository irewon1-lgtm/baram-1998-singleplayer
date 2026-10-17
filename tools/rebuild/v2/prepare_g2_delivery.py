#!/usr/bin/env python3
"""Package immutable G2 candidates and private runtime. No execution PASS inferred."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path

def digest(path):
 with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);a=p.parse_args();root=a.workspace.resolve();repo=root/'baram';out=root/'deliverables';out.mkdir(exist_ok=True)
 w=json.loads((root/'builds/g2-delivery-Windows/EXPORT_RECEIPT.json').read_text());android=json.loads((root/'builds/g2-delivery-Android/EXPORT_RECEIPT.json').read_text())
 assert w['result']==android['result']=='PASS_EXPORT_ONLY'
 assert w['source_snapshot']==android['source_snapshot']and w['runtime_snapshot']==android['runtime_snapshot']
 assert android['final_apk_signer_matches_retained']and android['final_apk_manifest']['version_code']==7
 freeze=json.loads((root/'evidence/G2_DELIVERY_FREEZE.json').read_text());assert freeze['source_commit']==w['source_commit']
 assert w['source_snapshot']==freeze['source_snapshot']
 for name,sha in freeze['source_snapshot'].items():assert digest(repo/'rebuild/p2'/name)==sha
 guide=(repo/'docs/rebuild/v2/G2_INSTALL_KO.md').read_text()
 apk=out/'baram-G2-r15-Android.apk';shutil.copy2(Path(android['artifact']['path']),apk)
 exe=Path(w['artifact']['path']);archive=out/'baram-G2-r15-Windows64.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  z.write(exe,'baram-p3-playable.exe');z.writestr('START.txt',guide);z.writestr('EXE-SHA256.txt',digest(exe)+'  baram-p3-playable.exe\n')
 with zipfile.ZipFile(archive)as z:assert hashlib.sha256(z.read('baram-p3-playable.exe')).hexdigest()==digest(exe)
 runtime=root/'private/g2-delivery';pack=out/'baram-G2-r15-private-runtime.zip'
 with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for name,sha in w['runtime_snapshot'].items():
   file=runtime/name;assert digest(file)==sha;assert file.suffix.lower()not in('.keystore','.jks','.pem');z.write(file,name)
 items=[{'filename':f.name,'local_path':str(f),'bytes':f.stat().st_size,'sha256':digest(f),'status':'BUILT_NOT_NATIVE_EXECUTION_VERIFIED'}for f in(apk,archive,pack)]
 receipt={'schema':'baram.g2.packaged-artifacts/1','source_commit':w['source_commit'],'source_content_fingerprint':w['source_content_fingerprint'],'runtime_manifest_sha256':w['runtime_manifest_sha256'],'content_sha256':w['gameplay_content_sha256'],'windows_exe_sha256':digest(exe),'original_export_zip_sha256':w['windows_zip']['sha256'],'repacked_windows_zip_policy':'Same byte-identical EXE plus Korean installation/control/save guide and checksum; no executable changes.','artifacts':items,'installed_package':android['installed_package'],'user_directory':android['preserved_user_dir'],'version_code':7,'signer_sha256':android['retained_signer_sha256'],'native_update':'NOT_RUN','native_execution':'NOT_RUN','private_keys_or_user_saves_in_artifacts':False}
 (root/'evidence/G2_PACKAGED_ARTIFACTS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'artifacts':[{'file':i['filename'],'bytes':i['bytes'],'sha256':i['sha256']}for i in items]},ensure_ascii=False))
if __name__=='__main__':main()
