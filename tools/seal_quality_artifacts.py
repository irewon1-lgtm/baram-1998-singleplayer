"""Encrypt private runtime artifacts for public CI transfer. Never upload plaintext."""
import argparse,base64,hashlib,json,os,zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
p=argparse.ArgumentParser();p.add_argument('--signing',required=True);p.add_argument('--source');p.add_argument('--output',required=True);p.add_argument('--decrypt');a=p.parse_args()
key=hashlib.sha256(base64.b64decode(json.loads(Path(a.signing).read_text())['pkcs12_base64'])).digest()
if a.decrypt:
 data=Path(a.decrypt).read_bytes();assert data[:8]==b'BARAMQ01';Path(a.output).write_bytes(AESGCM(key).decrypt(data[8:20],data[20:],b'baram-quality-private'))
else:
 root=Path(a.source);archive=Path(a.output).with_suffix('.private.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in root.rglob('*'):
   if f.is_file():z.write(f,f.relative_to(root))
 nonce=os.urandom(12);Path(a.output).write_bytes(b'BARAMQ01'+nonce+AESGCM(key).encrypt(nonce,archive.read_bytes(),b'baram-quality-private'));archive.unlink()
