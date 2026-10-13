#!/usr/bin/env python3
"""Unprivileged reproducible stage-4/5 tooling, with signed/checksummed artifacts."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request
from legacy_assets import private_path

SDK_VERSION = '8.0.425'
SDK_URL = 'https://builds.dotnet.microsoft.com/dotnet/Sdk/8.0.425/dotnet-sdk-8.0.425-linux-x64.tar.gz'
# Official 8.0 release metadata, fetched and matched during this onboarding run.
SDK_SHA512 = '934b8060a7190e5909ad1fd0785db542f487b3bbf6cdd14826b02095fdd0d0394298b1634085eff302928fccc33f7c1a7253e9b87df555fc36fce819bcd2e798'


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True)
    args = parser.parse_args()
    setup = private_path(args.private_dir) / 'setup'
    setup.mkdir(parents=True, exist_ok=True)
    report = dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), checks=[], status='NOT_RUN')
    environment = dict(os.environ, DOTNET_CLI_HOME=str(setup / 'dotnet-home'), DOTNET_ROOT=str(setup / 'dotnet'),
                       NUGET_PACKAGES=str(setup / 'nuget'), DOTNET_CLI_TELEMETRY_OPTOUT='1',
                       XDG_CACHE_HOME=str(setup / 'cache'), XDG_CONFIG_HOME=str(setup / 'config'), XDG_DATA_HOME=str(setup / 'data'))
    try:
        sdk_archive = setup / 'dotnet-sdk.tar.gz'
        if not sdk_archive.exists():
            partial = sdk_archive.with_suffix('.partial')
            with urllib.request.urlopen(SDK_URL, timeout=45) as response, partial.open('xb') as target:
                while chunk := response.read(1024 * 1024): target.write(chunk)
            if digest(partial, 'sha512') != SDK_SHA512:
                raise ValueError('SDK SHA512 mismatch; partial preserved and not extracted')
            partial.rename(sdk_archive)
        if digest(sdk_archive, 'sha512') != SDK_SHA512:
            raise ValueError('Cached SDK SHA512 mismatch; existing files preserved')
        sdk = setup / 'dotnet/dotnet'
        if not sdk.exists():
            with tarfile.open(sdk_archive) as archive:
                archive.extractall(setup / 'dotnet', filter='data')
        version = subprocess.check_output([str(sdk), '--version'], env=environment, text=True, timeout=20).strip()
        if version != SDK_VERSION:
            raise ValueError('Existing SDK version differs; not overwritten')
        report['checks'].append(dict(name='Dotnet SDK', status='PASS_SHA512_AND_VERSION', version=version, sha512=SDK_SHA512))
        print('Verified .NET SDK', version, flush=True)
        apt = setup / 'apt'
        for folder in ['conf.d', 'lists/partial', 'cache/archives/partial']:
            (apt / folder).mkdir(parents=True, exist_ok=True)
        (apt / 'status').touch()
        (apt / 'sources.list').write_text('deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main\n')
        config = apt / 'bootstrap.conf'
        config.write_text('\n'.join([
            f'Dir::Etc::Parts "{apt / "conf.d"}";', 'Dir::Etc::main "-";',
            f'Dir::Etc::sourcelist "{apt / "sources.list"}";', 'Dir::Etc::sourceparts "-";',
            f'Dir::State::lists "{apt / "lists"}";', f'Dir::State::status "{apt / "status"}";',
            f'Dir::Cache "{apt / "cache"}";', 'APT::Get::List-Cleanup "0";', '']) )
        apt_environment = dict(environment, APT_CONFIG=str(config))
        subprocess.run(['apt-get', 'update'], env=apt_environment, cwd=setup, check=True, timeout=90)
        packages = ['xvfb', 'libxfont2', 'xserver-common']
        # apt omits print-uris rows for packages already present in the cwd.
        # Plan in a separate empty directory, then validate the real cache below.
        planning = apt / 'uri-plan'
        planning.mkdir(exist_ok=True)
        if any(planning.glob('*.deb')):
            raise ValueError('Package planning directory is not empty; existing files preserved')
        uris = subprocess.check_output(['apt-get', '--print-uris', 'download', *packages], env=apt_environment, cwd=planning, text=True, timeout=30)
        subprocess.run(['apt-get', 'download', *packages], env=apt_environment, cwd=setup, check=True, timeout=90)
        hashes = []
        for line in uris.splitlines():
            fields = shlex.split(line)
            if len(fields) != 4 or not fields[0].startswith('https://') or not fields[3].startswith('SHA256:'):
                raise ValueError('Expected signed-index HTTPS URI and SHA256 for Debian package')
            filename = fields[1]
            if Path(filename).name != filename:
                raise ValueError('Unexpected package filename path')
            package = setup / filename
            expected = fields[3].split(':', 1)[1]
            if digest(package) != expected:
                raise ValueError('Debian package SHA256 mismatch; not extracted')
            subprocess.run(['dpkg-deb', '-x', str(package), str(setup / 'x11')], check=True, timeout=20)
            hashes.append(dict(filename=filename, sha256=expected))
        if len(hashes) != 3:
            raise ValueError('Expected exactly three Debian packages')
        report['checks'].append(dict(name='Xvfb', status='PASS_SIGNED_APT_INDEX_AND_PACKAGE_HASHES', packages=hashes,
                                     executable_sha256=digest(setup / 'x11/usr/bin/Xvfb')))
        version = subprocess.check_output(['godot', '--version'], env=environment, text=True, timeout=20).strip()
        report['checks'].append(dict(name='Godot preinstalled', status='PASS_VERSION_ONLY', version=version))
        report['status'] = 'PASS_TOOL_INSTALLATION_ONLY'
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report.update(status='FAIL', error=type(exc).__name__ + ': ' + str(exc))
    report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (setup / 'setup-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'error': report.get('error')}))
    return int(report['status'] != 'PASS_TOOL_INSTALLATION_ONLY')


if __name__ == '__main__':
    raise SystemExit(main())
