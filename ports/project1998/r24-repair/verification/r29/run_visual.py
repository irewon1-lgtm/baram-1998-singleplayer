"""Reuse the actual r28 renderer harness, adding only dev-only r29 assertions."""
from pathlib import Path
import sys
r=Path(__file__).resolve().parents[2]
source=(r/'verification/r28/run_visual.py').read_text()
source=source.replace("'GameHud.Map.cs'","'GameHud.Map.cs'")
source=source.replace("for n in names:shutil.copy2(root/'android'/n,project/n)","names += [p.name for p in (root/'android').glob('GameHud.*.cs') if p.name not in names]\nfor n in names:shutil.copy2(root/'android'/n,project/n)")
anchor="pv=project/'VisualProbe.cs';"
source=source.replace(anchor,"shutil.copy2(root/'verification/r29/HudVisualProbe.cs',project/'HudVisualProbe.cs')\n"+anchor)
source=source.replace("if(_mode==\"layout\")','if(_mode==\"r25appearance\")", "if(_mode==\"layout\")','if(_mode==\"r29hud\") { await R29Hud(scene); }\\n            else if(_mode==\"r25appearance\")")
exec(compile(source,str(r/'verification/r29/run_visual.py'),'exec'))
