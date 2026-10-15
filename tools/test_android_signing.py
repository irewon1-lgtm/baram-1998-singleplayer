"""Ephemeral CI fixture signing only. Never use for a player release."""
import argparse,base64,json,os
from pathlib import Path
import subprocess
p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
key=out/'fixture.p12'
subprocess.run(['keytool','-genkeypair','-storetype','PKCS12','-keystore',str(key),'-alias','fixture','-keyalg','RSA','-validity','30','-dname','CN=CI fixture only','-storepass','fixture-test-only'],check=True,capture_output=True)
(out/'fixture.json').write_text(json.dumps({'alias':'fixture','password':'fixture-test-only','pkcs12_base64':base64.b64encode(key.read_bytes()).decode()}))
