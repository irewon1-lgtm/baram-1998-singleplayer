from pathlib import Path
r=Path(__file__).resolve().parents[2]
s=(r/'verification/r28/run_ui.py').read_text().replace("r/'evidence/r28/ui'","r/'evidence/r29/ui'")
s=s.replace("shutil.copy2(r/'verification/r28/UsabilityUiSmoke.cs',project/'UsabilityUiSmoke.cs')","shutil.copy2(r/'verification/r29/GameplayUiSmoke.cs',project/'GameplayUiSmoke.cs')")
s=s.replace('BeginR28UsabilitySmoke','BeginR29GameplaySmoke').replace("'r28-usability-'","'r29-hud-'")
exec(compile(s,str(r/'verification/r29/run_ui.py'),'exec'))
