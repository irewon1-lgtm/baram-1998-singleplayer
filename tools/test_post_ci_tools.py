"""Synthetic policy/transport tests; none certify a native build."""
import base64
import hashlib
import http.client
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import fetch_recovery_artifact as fetch
import package_recovery_delivery as delivery

class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def archive(self,name,entries):
  p=self.root/name
  with zipfile.ZipFile(p,'w') as z:
   for key,value in entries:z.writestr(key,value)
  return p
 def test_zip_escape_duplicate_and_symlink_are_rejected(self):
  for index,entries in enumerate([[('../escape',b'x')],[('A',b'x'),('a',b'y')],[('x/y',b'x'),('x',b'file')]]):
   with self.assertRaises(fetch.ArtifactError):fetch.safe_extract_zip(self.archive(str(index)+'.zip',entries),self.root/('out'+str(index)))
  link=zipfile.ZipInfo('link');link.external_attr=(stat.S_IFLNK|0o777)<<16
  p=self.root/'link.zip'
  with zipfile.ZipFile(p,'w') as z:z.writestr(link,'/etc/passwd')
  with self.assertRaises(fetch.ArtifactError):fetch.safe_extract_zip(p,self.root/'links')
  self.assertFalse((self.root/'escape').exists())
 def test_declared_expansion_limit_is_enforced_before_extract(self):
  p=self.archive('large.zip',[('large',b'x'*200)])
  with self.assertRaises(fetch.ArtifactError):fetch.safe_extract_zip(p,self.root/'large',max_expanded=100)
  self.assertFalse((self.root/'large').exists())
 def test_AES_compatible_with_original_sealer_and_wrong_tag_never_publishes(self):
  config=self.root/'key.json';private=b'synthetic-private-fixture-only'
  config.write_text(json.dumps({'pkcs12_base64':base64.b64encode(private).decode()}))
  plain=self.archive('plain.zip',[('proof.json',b'{"status":"FAIL"}')]).read_bytes();nonce=b'0'*12
  sealed=self.root/'sealed';sealed.write_bytes(b'BARAMQ01'+nonce+AESGCM(hashlib.sha256(private).digest()).encrypt(nonce,plain,b'baram-quality-private'))
  result=fetch.decrypt_sealed(sealed,self.root/'decrypted.zip',config)
  self.assertEqual(result['sha256'],hashlib.sha256(plain).hexdigest())
  damaged=bytearray(sealed.read_bytes());damaged[-1]^=1;sealed.write_bytes(damaged)
  with self.assertRaises(fetch.ArtifactError):fetch.decrypt_sealed(sealed,self.root/'bad.zip',config)
  self.assertFalse((self.root/'bad.zip').exists())
 def test_range_resume_keeps_verified_prefix_and_bounds(self):
  class Response:
   def __init__(self,status,headers,data,interrupt=False):self.status=status;self.headers=headers;self.data=data;self.interrupt=interrupt;self.sent=False
   def geturl(self):return 'https://signed.invalid/artifact?secret=never-log'
   def __enter__(self):return self
   def __exit__(self,*a):return False
   def read(self,n):
    if self.sent:
     if self.interrupt:raise http.client.IncompleteRead(b'')
     return b''
    self.sent=True;return self.data
  class Opener:
   def __init__(self):self.requests=[]
   def open(self,request,timeout):
    self.requests.append(request)
    if len(self.requests)==1:return Response(200,{'Content-Length':'6','ETag':'same'},b'abc',True)
    return Response(206,{'Content-Range':'bytes 3-5/6','ETag':'same'},b'def')
  opener=Opener()
  with mock.patch.object(fetch.time,'sleep'):
   result=fetch.download('https://signed.invalid/file',self.root/'download',hashlib.sha256(b'abcdef').hexdigest(),opener=opener)
  self.assertEqual((self.root/'download').read_bytes(),b'abcdef');self.assertEqual(result['attempts'],2)
  self.assertEqual(opener.requests[1].get_header('Range'),'bytes=3-')
 def test_complete_fetch_atomically_publishes_only_authenticated_files(self):
  private=b'synthetic transport key';signing=self.root/'synthetic-signing.json'
  signing.write_text(json.dumps({'pkcs12_base64':base64.b64encode(private).decode()}))
  plain=self.archive('proofs.zip',[('native.json',b'{"status":"FAIL"}')]).read_bytes()
  nonce=b'1'*12;sealed=b'BARAMQ01'+nonce+AESGCM(hashlib.sha256(private).digest()).encrypt(nonce,plain,b'baram-quality-private')
  wrapper=self.archive('artifact.zip',[('windows-quality.sealed',sealed)])
  url_file=self.root/'signed-url.txt';url_file.write_text('https://signed.invalid/artifact?private=token')
  args=SimpleNamespace(output=str(self.root/'received'),url_file=str(url_file),signing=str(signing),sealed_name='windows-quality.sealed',expected_sha256=None)
  def local_transfer(url,target,expected):
   target.write_bytes(wrapper.read_bytes());return {'bytes':target.stat().st_size,'sha256':fetch.digest(target),'attempts':1}
  with mock.patch.object(fetch,'download',side_effect=local_transfer):result=fetch.fetch(args)
  self.assertEqual(result['status'],'PASS');self.assertEqual((self.root/'received/native.json').read_bytes(),b'{"status":"FAIL"}')
  self.assertIn('NOT_PLATFORM',result['scope'])
  self.assertNotIn('private=token',(self.root/'received/artifact-fetch-report.json').read_text())
  before=(self.root/'received/native.json').read_bytes()
  with self.assertRaises(fetch.ArtifactError):fetch.fetch(args)
  self.assertEqual((self.root/'received/native.json').read_bytes(),before)
 def test_missing_native_CI_is_BLOCKED_before_signing_or_copy(self):
  ci=self.root/'ci.json';ci.write_text(json.dumps({'conclusion':'failure','head_sha':'a'*40,'jobs':[]}))
  args=SimpleNamespace(output=str(self.root/'deliver'),report=str(self.root/'report.json'),android_dir=str(self.root/'android'),windows_dir=str(self.root/'windows'),ci_run=str(ci),source_sha='a'*40,signing=str(self.root/'DO_NOT_READ_SECRET'),expected_content=None)
  result=delivery.package(args)
  self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['reason'],'NATIVE_CI_NOT_SUCCESSFUL');self.assertFalse((self.root/'deliver').exists())
 def test_report_path_cannot_overwrite_secret_or_original_metadata(self):
  secret=self.root/'signing.json';secret.write_bytes(b'never overwritten')
  args=SimpleNamespace(output=str(self.root/'delivery'),report=str(secret),android_dir=str(self.root/'android'),windows_dir=str(self.root/'windows'),ci_run=str(self.root/'ci.json'),source_sha='a'*40,signing=str(secret),expected_content=None)
  result=delivery.package(args)
  self.assertEqual(result['status'],'BLOCKED');self.assertEqual(secret.read_bytes(),b'never overwritten')
  self.assertFalse((self.root/'delivery').exists())
 def test_metadata_PASS_without_level6_attack_is_rejected(self):
  gate=delivery.Gate()
  report={'status':'PASS','checks':[{'name':'new_character_is_level1_commoner','status':'PASS'}]}
  with self.assertRaises(delivery.GateError):gate.all_pass(report,delivery.CORE_CHECKS,'core')
 def test_any_NOT_RUN_or_wrong_platform_cannot_pass(self):
  gate=delivery.Gate()
  with self.assertRaises(delivery.GateError):gate.all_pass({'status':'PASS','checks':[{'name':'x','status':'NOT_RUN'}]},(), 'notrun')
  path=self.root/'wrong.json';path.write_text(json.dumps({'status':'PASS','checks':[{'name':'x','status':'PASS'}],'platform':'Linux','game_build':'a'*40,'content_version':'b'*64,'time_scale':1}))
  with self.assertRaises(delivery.GateError):delivery.game_report(delivery.Gate(),path,'Windows','a'*40,'b'*64,{'x'},'native')
 def test_frozen_input_digest_rejects_changed_source_and_cert_constant_complete(self):
  rows=[{'path':'game/main.gd','sha256':'a'*64}]
  value={'files':rows,'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
  self.assertEqual(delivery.frozen_inputs(value),value['sha256'])
  value['files'][0]['sha256']='b'*64
  with self.assertRaises(delivery.GateError):delivery.frozen_inputs(value)
  self.assertEqual(len(delivery.CERTIFICATE),64)

if __name__=='__main__':unittest.main()
