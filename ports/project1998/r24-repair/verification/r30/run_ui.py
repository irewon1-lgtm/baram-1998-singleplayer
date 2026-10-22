from pathlib import Path
r=Path(__file__).resolve().parents[2]
s=(r/'verification/r28/run_ui.py').read_text().replace("r/'evidence/r28/ui'","r/'evidence/r30/ui'")
s=s.replace("shutil.copy2(r/'verification/r28/UsabilityUiSmoke.cs',project/'UsabilityUiSmoke.cs')","shutil.copy2(r/'verification/r30/RecoveryUiSmoke.cs',project/'RecoveryUiSmoke.cs')")
s=s.replace('BeginR28UsabilitySmoke','BeginR30RecoverySmoke').replace("'r28-usability-'","'r30-recovery-'")
exec(compile(s,str(r/'verification/r30/run_ui.py'),'exec'))
