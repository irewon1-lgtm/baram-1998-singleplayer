#!/usr/bin/env python3
"""Write a compact review page for actual production-render fixture captures."""
import argparse,html,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--captures',type=Path,required=True);p.add_argument('--review',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();data=json.loads(a.captures.read_text());review=json.loads(a.review.read_text()) if a.review else {'status':'NOT_REVIEWED'}
 rel=a.captures.parent.relative_to(a.output.parent);cards=[]
 for c in data['captures']:
  details=html.escape(json.dumps(c.get('detail',{}),ensure_ascii=False,indent=2))
  cards.append(f'<article><h3>{html.escape(c["file"])}</h3><img loading="lazy" src="{rel}/{c["file"]}"><details><summary>Fixture and event evidence</summary><pre>{details}</pre></details></article>')
 table=''.join(f'<tr><td>{html.escape(c["id"])}</td><td>{c["status"]}</td></tr>' for c in data['checks'])
 page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>캐릭터·원본 효과 실제 실행 검수</title><style>body{{background:#21170f;color:#ead5ad;font:16px system-ui;margin:24px}}h1{{font-size:24px}}.scope{{background:#3c2a19;padding:18px;max-width:1000px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(580px,1fr));gap:18px}}article{{border:1px solid #80613d;padding:12px}}img{{width:100%;image-rendering:pixelated}}pre{{white-space:pre-wrap;font-size:12px}}table{{border-collapse:collapse}}td{{padding:5px 10px;border-bottom:1px solid #5b432c}}</style><h1>캐릭터·착용 외형·효과: 실제 게임 실행 화면</h1><div class="scope"><b>{html.escape(data['status'])}</b><p>실제 production gameplay.tscn과 원본 자산을 실행했다. 캐릭터 레벨·장비·위치·대상·시간을 명시적으로 설정한 fixture이다. 일반 입력 플레이·자연 육성·네이티브 Android/Windows·전체 미술 PASS가 아니다.</p><p>4직업×4방향, 방패 착탈과 전신 미리보기, 공격/시전/실제 명중/효과 종료를 별도로 확인한다. 원본 그림을 재사용한 효과의 기술별 역사적 타이밍·사운드 일치는 확정하지 않았다.</p><pre>content {data['content_sha256']}\nactors {data['actor_index_sha256']}\nUI {data['ui_sha256']}</pre><p>육안 검수: {html.escape(review.get('status','NOT_REVIEWED'))}</p><pre>{html.escape(json.dumps(review,ensure_ascii=False,indent=2))}</pre></div><div class="grid">{''.join(cards)}</div><h2>실제 수행 검사</h2><table>{table}</table></html>'''
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(page)
 print(a.output)
if __name__=='__main__':main()
