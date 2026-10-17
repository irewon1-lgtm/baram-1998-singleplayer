#!/usr/bin/env python3
"""Render an evidence-authored r16 manifest; never infer a test or art verdict."""
import argparse
import base64
from html import escape
from io import BytesIO
import json
from pathlib import Path
from PIL import Image


def picture(path, caption, width=1100):
    path = Path(path)
    with Image.open(path) as source:
        source.load()
        preview = source.convert('RGB')
        if preview.width > width:
            preview.thumbnail((width, 10000), Image.Resampling.NEAREST)
        stream = BytesIO()
        preview.save(stream, format='JPEG', quality=92, subsampling=0)
    uri = 'data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode()
    return '<figure><img loading="lazy" src="' + uri + '"><figcaption>' + escape(caption) + '</figcaption></figure>'


def table(headers, rows):
    return '<div class="overflow"><table><thead><tr>' + ''.join('<th>' + escape(str(x)) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(str(x)) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    root = Path(manifest['workspace']).resolve()
    required = ['source_commit', 'overall', 'verdicts', 'changes', 'comparisons', 'world_qa', 'artifacts']
    if any(key not in manifest for key in required):
        raise ValueError('The integration owner must author all verdicts and evidence paths')
    body = ['<p class="eyebrow">BARAM · G2 · r16 설치 후보</p><h1>기준 장면과 실제 게임을 비교하며 수정했습니다.</h1>',
            '<p class="notice">' + escape(manifest['overall']) + '</p>',
            '<p>정본 계획 BARAM_REBUILD_V2_RESOURCE_FIRST_20261016 / v2.1 · B5→B6 순서 유지</p>',
            '<p>앱 소스 <code>' + escape(manifest['source_commit']) + '</code><br>원격 정본 브랜치의 최신 HEAD에서 이어갔으며 과거 SHA로 초기화하지 않았습니다.</p>',
            '<h2>실제 판정</h2>',
            table(['범위', '판정', '관측·제한'], [(r['name'], r['status'], r['detail']) for r in manifest['verdicts']]),
            '<p>30분 연속 플레이·무편집 영상 필수 조건은 사용자의 후속 지시로 해제했습니다. 장시간 안정성은 수행한 시험과 분리하며, 미실행 결과를 PASS로 처리하지 않았습니다.</p>',
            '<h2>바뀐 코드와 이미지</h2>',
            table(['문제와 수정', '실제 소스·근거'], [(r['description'], r['evidence']) for r in manifest['changes']]),
            '<h2>단일 기준 원본 · 수정 전 · 수정 후</h2><p>기준 사진의 실제 게임 영역만 비교합니다. 아래 미리보기는 실제 캡처의 축소본이며, 원본 PNG와 좌표·카메라·소스 지문은 비교 HTML과 증거 ZIP에 보존했습니다.</p><div class="comparison">']
    for row in manifest['comparisons']:
        body.append(picture(root / row['image'], row['caption'], 900))
    body.append('</div><h2>111개 지도·전체 출입구</h2>')
    world = json.loads((root / manifest['world_qa']).read_text())
    body.append(table(['항목', '관측 결과'], [(key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value) for key, value in world['summary'].items()]))
    body.append('<p>' + escape(manifest.get('world_scope', world['scope'])) + '</p>')
    body.append('<p>지도별 실제 화면과 개요의 전체 크기 PNG, 문 접근·도착·귀환 캡처, OS 입력 로그 및 개별 시각 판정은 증거 ZIP의 world-qa-gallery.html에서 확인할 수 있습니다. 아래는 실제 화면의 미리보기입니다.</p><div class="maps">')
    for row in world['maps']:
        image_path = (root / manifest['world_qa']).parent / row['runtime_frame']
        caption = row['name'] + ' · ' + row['map_id'] + ' · ' + str(row['coordinate'])
        body.append(picture(image_path, caption, 440))
    body.append('</div><h2>짧은 실행·저장 검사</h2>')
    body.append(table(['검사', '실제 결과', '범위'], [(row['name'], row['result'], row['scope']) for row in manifest.get('short_tests', [])]))
    body.append('<h2>설치 후보와 증거</h2>')
    body.append(table(['파일', 'bytes', 'SHA-256'], [(row['filename'], row['bytes'], row['sha256']) for row in manifest['artifacts']]))
    body.append('<p>' + escape(manifest.get('installation', '')) + '</p>')
    body.append('<h2>남은 조건</h2><ul>')
    for item in manifest.get('remaining', []):
        body.append('<li>' + escape(item) + '</li>')
    body.append('</ul><footer><p>검사 스코프·실패·미실행을 분리했습니다. 원본 자료·서명키·기존 저장·안정 ID를 보존했으며, 새 유료 자원이나 계정 서버를 만들지 않았습니다.</p></footer>')
    style = 'body{margin:0;background:#201810;color:#eadfc9;font:16px/1.65 system-ui,sans-serif}main{max-width:1250px;margin:auto;padding:40px 22px}h1,h2{color:#f1cd91;line-height:1.3}h1{font-size:clamp(30px,4vw,50px)}h2{margin-top:48px}.eyebrow{color:#bdad93}.notice{padding:18px;border-left:4px solid #d7ac63;background:#3c2c1b}.overflow{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #685039;overflow-wrap:anywhere}th{color:#f6d9a8;background:#342619}.comparison{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.maps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:12px 0}img{width:100%;height:auto;display:block;image-rendering:pixelated}figcaption{padding:8px 0;font-size:12px;color:#c6b69e}code{overflow-wrap:anywhere}footer{margin:48px 0 12px;color:#bba98f;font-size:13px}@media(max-width:800px){.comparison,.maps{grid-template-columns:1fr}main{padding:24px 14px}}'
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>바람의나라 r16 실제 수정·검수 결과</title><style>' + style + '</style><main>' + '\n'.join(body) + '</main></html>'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page)
    print(json.dumps({'output': str(args.output.resolve()), 'bytes': args.output.stat().st_size, 'actual_map_previews': len(world['maps']), 'verdict_policy': 'Integration-owner-authored; rendering a report establishes no PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
