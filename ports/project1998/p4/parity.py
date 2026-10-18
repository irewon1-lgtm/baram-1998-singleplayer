#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tooling import environment


def main():
    p = argparse.ArgumentParser()
    for name in ['workspace', 'experiment', 'source', 'output']: p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); w = a.workspace.resolve(); exp = a.experiment.resolve(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    env = environment(w, exp)
    for kind, reference in [('original', a.source.resolve() / 'Server/Server.csproj'), ('adapter', exp / 'source/Server/Server.csproj')]:
        project = out / kind; project.mkdir(); shutil.copyfile(Path(__file__).with_name('Parity.cs'), project / 'Program.cs')
        (project / 'Parity.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors><DefineConstants>%s</DefineConstants></PropertyGroup><ItemGroup><ProjectReference Include="%s" /></ItemGroup></Project>''' % ('ADAPTER' if kind == 'adapter' else '', reference))
        for name, command in [('build', [str(exp / 'dotnet-wrapper/dotnet'), 'build', str(project / 'Parity.csproj'), '-m:1', '-nr:false', '-p:UseSharedCompilation=false', '-p:NuGetAudit=false', '-v', 'minimal']),
                              ('run', [str(w / 'toolchain/dotnet/dotnet'), str(project / 'bin/Debug/net8.0/Parity.dll'), str(exp / 'content'), str(project / 'state'), str(project / 'result.json')])]:
            with (project / (name + '.log')).open('w') as log: r = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            if r.returncode: print((project / (name + '.log')).read_text()[-4000:]); raise RuntimeError(kind + '-' + name)
    original = json.loads((out / 'original/result.json').read_text()); adapter = json.loads((out / 'adapter/result.json').read_text())
    result = {'status': 'PASS' if original == adapter else 'FAIL', 'compared_steps': len(original['trace']), 'original_head': '65cb3ef28f289ee35d19abfb6829d6120b9ec0cd', 'scope': original['scope']}
    (out / 'PARITY.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result)); assert original == adapter


if __name__ == '__main__': main()
