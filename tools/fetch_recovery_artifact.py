#!/usr/bin/env python3
"""Reconstructed post-CI transport; original Python source was not recovered.

Use a signed URL file produced from the GitHub artifact download response.
URLs and private signing material are never printed or written to reports.
"""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MAX_DOWNLOAD=1024**3
MAX_EXPANDED=2*1024**3
MAX_MEMBERS=12000
MAGIC=b'BARAMQ01'
AAD=b'baram-quality-private'

class ArtifactError(Exception):
    def __init__(self,code,message):super().__init__(message);self.code=code

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def safe_relative(name):
    if not isinstance(name,str) or not name or len(name)>2048 or '\\' in name or ':' in name or '\0' in name:
        raise ArtifactError('UNSAFE_ZIP_PATH','Nonportable archive member')
    value=name.rstrip('/')
    p=PurePosixPath(value)
    if not value or p.is_absolute() or len(p.parts)>50 or any(s in ('','.','..') for s in value.split('/')):
        raise ArtifactError('UNSAFE_ZIP_PATH','Archive path escape rejected')
    reserved={'con','prn','aux','nul'}|{f'{p}{i}' for p in ('com','lpt') for i in range(1,10)}
    if any(s.endswith((' ','.')) or s.split('.')[0].casefold() in reserved for s in p.parts):
        raise ArtifactError('UNSAFE_ZIP_PATH','Windows-incompatible archive member')
    return p

def checked_members(archive,max_expanded=MAX_EXPANDED):
    infos=archive.infolist()
    if len(infos)>MAX_MEMBERS:raise ArtifactError('ZIP_MEMBER_LIMIT','Too many archive members')
    seen={};total=0
    for info in infos:
        p=safe_relative(info.filename);key=str(p).casefold()
        if key in seen:raise ArtifactError('ZIP_DUPLICATE','Duplicate or case-colliding archive member')
        seen[key]=info.is_dir();mode=(info.external_attr>>16)&0o170000
        if mode not in (0,stat.S_IFREG,stat.S_IFDIR):raise ArtifactError('ZIP_LINK','Link or special archive member rejected')
        if info.flag_bits&1:raise ArtifactError('ZIP_ENCRYPTED','Nested ZIP encryption is unsupported')
        total+=info.file_size
        if info.file_size<0 or total>max_expanded:raise ArtifactError('ZIP_EXPANSION_LIMIT','Archive exceeds expansion budget')
        if info.file_size>max(1024,info.compress_size)*1000:raise ArtifactError('ZIP_RATIO_LIMIT','Archive exceeds compression ratio budget')
    for key,isdir in seen.items():
        for parent in PurePosixPath(key).parents:
            if str(parent)!='.' and str(parent) in seen and not seen[str(parent)]:
                raise ArtifactError('ZIP_PATH_COLLISION','A file is used as an archive directory')
    return infos

def safe_extract_zip(source,destination,max_expanded=MAX_EXPANDED):
    destination=Path(destination)
    if destination.exists():raise ArtifactError('OUTPUT_EXISTS','Archive destination must be fresh')
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(source) as archive:
            infos=checked_members(archive,max_expanded)
            for info in infos:
                target=destination/Path(*safe_relative(info.filename).parts)
                if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                count=0
                with archive.open(info) as stream,target.open('xb') as out:
                    for block in iter(lambda:stream.read(1024**2),b''):
                        count+=len(block)
                        if count>info.file_size:raise ArtifactError('ZIP_SIZE_MISMATCH','Archive member exceeded its declared size')
                        out.write(block)
                if count!=info.file_size:raise ArtifactError('ZIP_SIZE_MISMATCH','Archive member is incomplete')
    except BaseException:
        shutil.rmtree(destination,ignore_errors=True);raise
    return [p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()]

class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urllib.parse.urlsplit(newurl).scheme!='https':raise ArtifactError('HTTPS_REQUIRED','Non-HTTPS redirect rejected')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def load_url(path):
    raw=Path(path).read_text(encoding='utf-8').strip()
    if raw.startswith('https://'):url=raw
    else:
        document=json.loads(raw)
        values=[document[k] for k in ('download_url','url','location') if isinstance(document.get(k),str)]
        if len(values)!=1:raise ArtifactError('URL_INPUT','URL file must contain one unambiguous signed HTTPS URL')
        url=values[0]
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ArtifactError('HTTPS_REQUIRED','An HTTPS artifact URL is required')
    return url

def download(url,path,expected_sha256=None,max_bytes=MAX_DOWNLOAD,retries=5,opener=None):
    opener=opener or urllib.request.build_opener(HTTPSRedirect())
    path=Path(path);etag=None;total=None;last_code='DOWNLOAD_FAILED'
    for attempt in range(retries):
        offset=path.stat().st_size if path.exists() else 0
        headers={'User-Agent':'baram-private-recovery/1'}
        if offset:
            headers['Range']=f'bytes={offset}-'
            if etag:headers['If-Range']=etag
        try:
            with opener.open(urllib.request.Request(url,headers=headers),timeout=45) as response:
                status=getattr(response,'status',200)
                if status not in (200,206):raise ArtifactError('HTTP_STATUS','Artifact server returned a non-success status')
                if response.geturl() and urllib.parse.urlsplit(response.geturl()).scheme!='https':
                    raise ArtifactError('HTTPS_REQUIRED','Non-HTTPS final artifact URL rejected')
                if status==206:
                    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                    if not match or int(match[1])!=offset or int(match[2])<offset:
                        raise ArtifactError('RANGE_MISMATCH','Artifact server returned an inconsistent range')
                    total=int(match[3])
                    if int(match[2])>=total:raise ArtifactError('RANGE_MISMATCH','Artifact range exceeds total size')
                else:
                    offset=0
                    length=response.headers.get('Content-Length')
                    total=int(length) if length is not None else None
                if total is not None and (total<0 or total>max_bytes):
                    raise ArtifactError('DOWNLOAD_SIZE_LIMIT','Artifact exceeds download budget')
                new_etag=response.headers.get('ETag')
                if etag and status==206 and new_etag and new_etag!=etag:
                    raise ArtifactError('ETAG_CHANGED','Artifact changed while resuming')
                etag=new_etag or etag
                with path.open('ab' if status==206 and offset else 'wb') as out:
                    for block in iter(lambda:response.read(1024**2),b''):
                        if out.tell()+len(block)>max_bytes:raise ArtifactError('DOWNLOAD_SIZE_LIMIT','Artifact exceeds download budget')
                        out.write(block)
                if total is not None and path.stat().st_size!=total:
                    raise http.client.IncompleteRead(b'')
            observed=digest(path)
            if expected_sha256 and observed!=expected_sha256.lower():
                raise ArtifactError('DOWNLOAD_HASH','Downloaded artifact differs from expected digest')
            return {'bytes':path.stat().st_size,'sha256':observed,'attempts':attempt+1}
        except urllib.error.HTTPError as error:
            last_code='HTTP_'+str(error.code)
            if error.code not in (408,429,500,502,503,504):raise ArtifactError(last_code,'Artifact download failed') from None
        except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.IncompleteRead,OSError):
            last_code='DOWNLOAD_INTERRUPTED'
        if attempt+1<retries:time.sleep(min(2**attempt,8))
    raise ArtifactError(last_code,'Artifact download did not complete within the retry budget')

def decrypt_sealed(source,destination,signing):
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
    config=json.loads(Path(signing).read_text(encoding='utf-8'))
    private_bytes=base64.b64decode(config['pkcs12_base64'],validate=True)
    key=hashlib.sha256(private_bytes).digest()
    size=Path(source).stat().st_size
    if size<36 or size>MAX_DOWNLOAD:raise ArtifactError('SEALED_SIZE','Invalid encrypted artifact size')
    with Path(source).open('rb') as stream:
        if stream.read(8)!=MAGIC:raise ArtifactError('SEALED_FORMAT','Unknown private artifact format')
        nonce=stream.read(12);stream.seek(-16,os.SEEK_END);tag=stream.read(16);stream.seek(20)
        decryptor=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor();decryptor.authenticate_additional_data(AAD)
        remaining=size-36
        try:
            with Path(destination).open('xb') as out:
                os.chmod(destination,0o600)
                while remaining:
                    block=stream.read(min(1024**2,remaining))
                    if not block:raise ArtifactError('SEALED_TRUNCATED','Encrypted artifact is incomplete')
                    remaining-=len(block);out.write(decryptor.update(block))
                out.write(decryptor.finalize())
        except BaseException:
            Path(destination).unlink(missing_ok=True)
            raise ArtifactError('SEALED_AUTHENTICATION','Private artifact authentication failed') from None
    return {'bytes':Path(destination).stat().st_size,'sha256':digest(destination)}

def fetch(args):
    output=Path(args.output).resolve()
    if output.exists():raise ArtifactError('OUTPUT_EXISTS','Existing artifacts are preserved; choose a fresh output')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.sealed',args.sealed_name):raise ArtifactError('SEALED_NAME','Expected a fixed safe sealed basename')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='artifact-transport-',dir=output.parent) as temporary:
        root=Path(temporary);outer=root/'artifact.zip'
        transfer=download(load_url(args.url_file),outer,args.expected_sha256)
        safe_extract_zip(outer,root/'wrapper')
        candidates=list((root/'wrapper').rglob(args.sealed_name))
        if len(candidates)!=1 or not candidates[0].is_file():raise ArtifactError('SEALED_MEMBER','Expected exactly one encrypted artifact member')
        plaintext=root/'private.zip';plain=decrypt_sealed(candidates[0],plaintext,args.signing)
        files=safe_extract_zip(plaintext,root/'ready')
        report={'status':'PASS','scope':'AUTHENTICATED_TRANSPORT_NOT_PLATFORM_OR_GAMEPLAY_VALIDATION',
                'implementation_origin':'RECONSTRUCTED_PYTHON_ORIGINAL_SOURCE_NOT_RECOVERED',
                'download':transfer,'sealed_sha256':digest(candidates[0]),'plaintext_zip':plain,
                'sealed_member':args.sealed_name,'extracted_files':len(files)}
        if (root/'ready'/'artifact-fetch-report.json').exists():raise ArtifactError('REPORT_COLLISION','Transport report would overwrite an original member')
        write_json(root/'ready'/'artifact-fetch-report.json',report)
        os.replace(root/'ready',output)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('url-file','signing','sealed-name','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--expected-sha256');p.add_argument('--report')
    args=p.parse_args()
    report_is_safe=not args.report or Path(args.report).resolve() not in {Path(args.signing).resolve(),Path(args.url_file).resolve()}
    try:
        if not report_is_safe:raise ArtifactError('READ_ONLY_INPUT','Report may not replace signing or URL input')
        report=fetch(args)
        if args.report and report_is_safe:write_json(args.report,report)
        print(json.dumps({'status':'PASS','scope':report['scope'],'files':report['extracted_files']}));return 0
    except Exception as error:
        code=error.code if isinstance(error,ArtifactError) else type(error).__name__
        report={'status':'FAIL','code':code,'scope':'ARTIFACT_TRANSPORT_ONLY','platform_validation':'NOT_RUN'}
        if args.report and report_is_safe:write_json(args.report,report)
        print(json.dumps(report));return 2

if __name__=='__main__':raise SystemExit(main())
