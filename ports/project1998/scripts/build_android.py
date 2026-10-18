#!/usr/bin/env python3
"""Build the isolated, offline P2 APK with a task-owned signing identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess


def main():
    p=argparse.ArgumentParser()
    for name in ['godot','templates','sdk','runtime','private','output']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key,value in vars(a).items():setattr(a,key,value.resolve())
    a.private.mkdir(parents=True,exist_ok=True);a.output.parent.mkdir(parents=True,exist_ok=True)
    signing=a.private/'signing';signing.mkdir(exist_ok=True);signing.chmod(0o700)
    password_file=signing/'password'
    if not password_file.exists():password_file.write_text(secrets.token_hex(24));password_file.chmod(0o600)
    keystore=signing/'p1998-dev.keystore'
    env=os.environ.copy()
    env.update(GODOT_SILENCE_ROOT_WARNING='1',XDG_DATA_HOME=str(a.private/'editor-data'),
               XDG_CONFIG_HOME=str(a.private/'editor-config'),JAVA_HOME='/usr/lib/jvm/java-17-openjdk-amd64',
               P1998_KEYSTORE_PASSWORD=password_file.read_text(),
               GODOT_ANDROID_KEYSTORE_DEBUG_PATH=str(keystore),GODOT_ANDROID_KEYSTORE_DEBUG_USER='p1998dev',
               GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD=password_file.read_text())
    if not keystore.exists():
        subprocess.run(['keytool','-genkeypair','-keystore',str(keystore),'-storepass:env','P1998_KEYSTORE_PASSWORD',
                        '-keypass:env','P1998_KEYSTORE_PASSWORD','-alias','p1998dev','-keyalg','RSA','-keysize','2048',
                        '-validity','10000','-dname','CN=Project1998 Private P2'],env=env,check=True)
        keystore.chmod(0o600)
    config=a.private/'editor-config/godot';config.mkdir(parents=True,exist_ok=True)
    settings='[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
    settings+='export/android/android_sdk_path='+json.dumps(str(a.sdk))+'\n'
    settings+='export/android/java_sdk_path="/usr/lib/jvm/java-17-openjdk-amd64"\n'
    (config/'editor_settings-4.6.tres').write_text(settings)
    preset='''[preset.0]
name="P1998 Android"
platform="Android"
runnable=true
export_filter="all_resources"
include_filter="assets/*.json,assets/maps/*.map,fonts/OFL.txt"
exclude_filter="ASSEMBLY.json,assets/BUILD_ASSETS_MANIFEST.json"
export_path=""
script_export_mode=2

[preset.0.options]
custom_template/debug="%s"
custom_template/release="%s"
gradle_build/use_gradle_build=false
architectures/armeabi-v7a=false
architectures/arm64-v8a=true
architectures/x86=false
architectures/x86_64=true
package/unique_name="com.irewon.baram.project1998.dev"
package/name="Project1998 P2"
package/signed=true
version/code=1
version/name="0.0.1-p2"
screen/immersive_mode=true
screen/orientation=0
user_data_backup/allow=false
permissions/internet=false
permissions/access_network_state=false
permissions/read_external_storage=false
permissions/write_external_storage=false
'''%(str(a.templates/'android_debug.apk'),str(a.templates/'android_release.apk'))
    (a.runtime/'export_presets.cfg').write_text(preset)
    command=[str(a.godot),'--headless','--path',str(a.runtime),'--export-debug','P1998 Android',str(a.output)]
    result=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (a.private/'android-export.log').write_text(result.stdout)
    print(result.stdout[-4500:])
    if result.returncode or not a.output.exists():raise SystemExit(result.returncode or 1)
    tools=a.sdk/'build-tools/35.0.1'
    verified=subprocess.run([str(tools/'apksigner'),'verify','--verbose','--print-certs',str(a.output)],check=True,capture_output=True,text=True)
    (a.private/'apk-signature.txt').write_text(verified.stdout)
    manifest=subprocess.run([str(tools/'aapt2'),'dump','badging',str(a.output)],check=True,capture_output=True,text=True)
    (a.private/'apk-badging.txt').write_text(manifest.stdout)
    permissions=subprocess.run([str(tools/'aapt2'),'dump','permissions',str(a.output)],check=True,capture_output=True,text=True)
    (a.private/'apk-permissions.txt').write_text(permissions.stdout)
    assert 'android.permission.INTERNET' not in permissions.stdout
    assert "package: name='com.irewon.baram.project1998.dev'" in manifest.stdout
    receipt={'status':'BUILD_PASS','apk':a.output.name,'bytes':a.output.stat().st_size,
             'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),
             'package':'com.irewon.baram.project1998.dev','versionCode':1,'abis':['arm64-v8a','x86_64'],
             'network_permission':False,'galaxy_device':'NOT_RUN_DEVICE',
             'signing_public_certificate':verified.stdout,'signing_key':'Private; excluded from public source and report'}
    (a.private/'BUILD_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='signing_public_certificate'},indent=2))


if __name__=='__main__':main()
