"""Explicit local toolchain paths for the repeatable private build/QA host."""
import os
from pathlib import Path
import shutil


def environment(workspace, experiment):
    w = Path(workspace).resolve(); exp = Path(experiment).resolve()
    sdk = w / 'toolchain/dotnet'; msbuild = sdk / 'sdk/9.0.319/MSBuild.dll'
    wrapper = exp / 'dotnet-wrapper'; wrapper.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parent.parent / 'p3/dotnet_msbuild.py', wrapper / 'dotnet')
    (wrapper / 'dotnet').chmod(0o755)
    return os.environ | {
        'LD_PRELOAD': str(w / 'p1998-private/p3/proc_self.so'),
        'DOTNET_ROOT': str(sdk), 'DOTNET_CLI_HOME': str(w / 'p1998-private/p3/dotnet-home'),
        'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'MSBUILDDISABLENODEREUSE': '1',
        'P3_REAL_DOTNET': str(sdk / 'dotnet'), 'P3_MSBUILD_DLL': str(msbuild),
        'MSBUILD_EXE_PATH': str(msbuild), 'MSBuildSDKsPath': str(msbuild.parent / 'Sdks'),
        'DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR': str(sdk),
        'PATH': str(wrapper) + ':' + str(sdk) + ':' + os.environ['PATH'],
        'GODOT_SILENCE_ROOT_WARNING': '1',
        'XDG_DATA_HOME': str(exp / 'editor-data'), 'XDG_CONFIG_HOME': str(exp / 'editor-config'),
        'JAVA_HOME': '/usr/lib/jvm/java-17-openjdk-amd64',
    }


def godot(workspace):
    return Path(workspace).resolve() / 'toolchain/godot-mono/Godot_v4.6-stable_mono_linux_x86_64/Godot_v4.6-stable_mono_linux.x86_64'
