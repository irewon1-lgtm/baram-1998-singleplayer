# 정규화 입력의 공개·비공개 경계

실제 값이 들어 있는 KR/NA JSONL은 비공개 인계 ZIP의 같은 상대 경로에 둔다. 이 폴더의 catalog에는 파일명·해시·행수·스키마·용도만 공개한다. catalog를 실제 데이터나 역사적 완성도로 집계하지 않는다. `INPUT_MANIFEST.json`과 전달 영수증의 지속 파일 ID를 사용한다.

한국 공식 문서의 `selected_original_value`는 해당 출처·시대에서 명시된 필드만 담는다. 클라이언트 자산의 `ORIGINAL_VERIFIED`는 해당 한국491 원본 바이트의 해독값 범위이며, 목표1998~2001의 서버 동작·수치 전체 확인이 아니다. `selected_for_p2_technical_input`과 `selected_for_build`는 새 게임 BOUND/EXERCISED가 아니다.

북미 데이터는 별도 namespace의 참고값이며 한국판 기본값이 아니다. 미확정 확률·수량·시점·네이티브 ID는 null/UNKNOWN으로 유지한다. 같은 이름·다른 시기의 숫자는 합치거나 평균 내지 않는다. 재구성 대사는 `reconstructed_value`로 분리한다.

실제 읽기 검사는 `tools/rebuild/p1_5/import_dry_run.py`를 사용한다. 필수 데이터가 없으면 공개 catalog만으로 성공 판정하지 않는다. 미지원 명령·끊어진 원소스 참조·원문 이상값·실제 실행 미시도는 각자의 결과로 남긴다.
