#!/usr/bin/env python3
"""Optional workaround for /proc PID-namespace restrictions in a build host.

The .NET 8 CLI unconditionally reads Process.StartTime in Program.Main.
This forwards build/publish to the same SDK's MSBuild.dll entry point, so no
game, compiler, SDK assembly or export template is patched. Normal hosts do
not need this wrapper. Set P3_REAL_DOTNET and P3_MSBUILD_DLL; place a copy named
dotnet at the front of PATH for Godot's export process.
"""
import os
import sys

real = os.environ['P3_REAL_DOTNET']
args = sys.argv[1:]
if not args or args[0] not in {'build', 'publish', 'clean'}:
    os.execv(real, [real, *args])
mode, *args = args
translated = [os.environ['P3_MSBUILD_DLL'], '-m:1', '-nr:false',
              '-p:BuildInParallel=false', '-p:UseSharedCompilation=false', '-t:' + mode.capitalize()]
restore = mode != 'clean'
i = 0
options = {'-c': 'Configuration', '--configuration': 'Configuration', '-r': 'RuntimeIdentifier',
           '--runtime': 'RuntimeIdentifier', '-o': 'PublishDir', '--output': 'PublishDir', '--self-contained': 'SelfContained'}
while i < len(args):
    value = args[i]
    if value in {'-v', '--verbosity'}:
        i += 1; translated.append('-v:' + args[i])
    elif value in options:
        i += 1; translated.append('-p:' + options[value] + '=' + args[i])
    elif value == '--no-restore': restore = False
    elif value == '--nologo': translated.append('-nologo')
    elif value == '--no-incremental': translated.append('-p:NoIncremental=true')
    else: translated.append(value)
    i += 1
if restore: translated.append('-restore')
os.execv(real, [real, *translated])
