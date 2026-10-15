# 개인 원본 정적 조사 근거 — P0/P1

기준: AGENTS.md, MASTER_PLAN v1.0, STATE.json, STEP01_WORK_INSTRUCTIONS.md를 읽었다. 새 게임/기준 클라이언트/서버/원본 EXE는 실행하지 않았다. 목록·바이트·메타데이터 검사만 수행했다. 원본·추출 자산 바이트와 매뉴얼 전문은 공개 결과에 포함하지 않는다.

## 범위와 실제 식별

- 개인 파일 42개, 원본 최상위 파일을 포함한 내부 바이트 레코드 2,204개, 고유 SHA-256 1,794개. 동일 해시는 같은 계보로 취급하며 발견 경로를 유지한다.
- LIB-001~038 최초 ID를 유지했고 추가 인계 4개는 LIB-039~042로 부여했다. 선택한 프로젝트 관련 파일만 조사했으며 전송 중간 파일은 목록화하지 않았다.
- 기존 PRIVATE_ASSET_INVENTORY의 원본 13개는 최종 정본의 크기·SHA가 모두 일치했다. NA_ALL 최초 materialization은 26,476,544바이트/916bbf6e5976b5288ac6390ff338be8af82f3da4caa456ab117006aa39baa5a4로 불완전했으나, 원본을 덮어쓰지 않고 별도 재확보한 218,174,017바이트/d41b644303581f7dfc05ef627d99820f8ccce3152637c9be533f0465dbbcb885 정본을 사용했다. 양쪽 경로·지문은 LIB-015에 기록했다.
- NA_ALL 명칭은 5.0 이전이라고 되어 있으나 내부에는 5.32/5.33도 존재한다. 파일명만으로 목표 시대 채택 금지.
- KR1.25: ZIP에서 실제 MAP 218개, winbaram.dat, 실행파일을 확인했다. 한국어 도움말은 이 묶음에서 발견되지 않았다. KR4.91: 외부 ZIP의 한글 매뉴얼 TXT 11개, 지도 이미지·중첩 ZIP과 CAB를 읽었다. ZIP의 구형 이름 바이트를 CP949로 복원했으며 TXT도 CP949로 해독했다.

## 해독·재사용 결과

- LIB-010 DATA1.CAB는 InstallShield v4 ISc( 형식이다. host libarchive는 이 포맷을 해독하지 못했다. MIT unshield 소스(tree 0d1e7cbac7986fbd5aa050da8249a27428fee057)를 정적 도구로 빌드해 목록 4개는 확인했으나 추출 0개였다. 기존 저장소의 hash-pinned legacy_installers.py(c919cf1bdffe0e318d4058dc3fc17be4a2844203)를 재사용해 CAB 4파일을 정적 추출함으로써 필요한 데이터는 해결했다. 게임·설치 EXE 실행은 없었다.
- NWind.dat 70,116,637바이트 / f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7: 203개 내부 항목(EPF133/PAL36/TBL20/FRM1 등). NWind.snd 4,558,322바이트 / 003534e57b426971900f7ec39f5e65d3662fa5f32672cd0564d04680e31e300c: WAV163개. CAB와 DAT에는 KR4.91 MAP가 없다. 이것은 이 설치 묶음 내부의 관측이며 전체 한국 지도 부재의 증명이 아니다.
- KR491 캐릭터·이펙트·아이템·UI 아틀라스의 원본 EPF/PAL 연결 131세트(공유84+회수UI47)는 원본 DAT의 실제 각 SHA와 일치했다. PNG를 재해독하지 않고 기존 변환 결과를 재사용할 입력 동일성을 확인했다. 원작 렌더링 정확성/방향/시간 검증은 NOT_RUN이다.
- 공유 WAV163개는 NWind.snd 원본 파일과 각각 바이트 SHA가 일치했다. 레코드에 원본 숫자 ID·채널·샘플레이트·길이를 기록했다. 기술/사건의 소리 선택·재생 시점·음량·반복 조건은 아직 미확인이다.
- KR1.25 기존 추출 manifest의 45개 파일은 winbaram.dat의 원본 offset/end 슬라이스와 SHA가 모두 일치했다. 프레임을 다시 전수 해독하지 않았다. 동작 의미와 목표 시대 대응은 별도 검증 대상이다.
- 공유·지역·회수UI private manifest 986개 선언 파일의 SHA/크기를 전수 대조했다. 정상 바이트 보존 검사이며 게임 동작이나 역사적 정확성 PASS가 아니다.
- 지역 묶음 LIB-038 manifest는 source를 Pinned NA495 layouts라고 명시한다. LIB-037 확장도 같은 성격의 레이아웃을 포함한다. 한국 이름 부착만으로 한국 지형으로 채택하지 않는다.
- 회수UI dlglogin/dlgnew01 등은 원본 EPF/PAL SHA와 일치하지만 metadata에 clipped_pixels/clipped_runs와 native_raster_comparison NOT_RUN이 있다. 이미지 회수와 실제 원본 렌더러 일치 판정은 구분한다.

## 실제로 읽은 한국어 문서의 기능 근거

모두 LIB-010 동봉 문서다. 문서 바이트/내용 관측과 1998~2001 게임 규칙의 채택은 구분한다. 문서 자체 작성연도는 UNKNOWN이며 서로 다른 시대 설명이 섞여 있다. 아래는 전문 인용이 아닌 요약이다.

|근거 ID|원본 member ID|라인|해결하는 칸과 제한|SHA-256|
|---|---|---|---|---|
|DOC-KR491-001|LIB-010-M-f8611076fb4d<br>VERSION.TXT|21|4.91 풀버전과 12월14일 표기는 확인되나 연도는 기재되지 않았다. 동봉 문서 전체를 같은 연도 자료로 취급하지 않는다.|2275a60d75d2a5a555310db9cb785b7df88e1dff02276b133fa3bbe539bffd08|
|DOC-KR491-002|LIB-010-M-71bda654cf90<br>지도매뉴얼/초보자용메뉴얼-1.txt|69–72|신규 평민·Lv5 직업 선택을 설명한다. 같은 문단의 도사 추가 예정 문구 때문에 4.91 동봉 문서 안에 과거 시점 자료가 섞였음이 드러난다.|6ad554b9414077d9c39c84ed332cac10b8a76c473aefdfddabd397c7e191a6ba|
|DOC-KR491-003|LIB-010-M-83ce2f6ad1db<br>지도매뉴얼/주술사 가이드.txt|23–34;160–167|Lv1 주막 시작, 서문 부근 토끼·다람쥐, 주술사 Lv6 파이어볼·Lv10 무장이라는 후보 근거다. 좌표·밀도·현행 정확한 수치를 확정하지 않는다.|76782bb3abef9b21609dced97dd90bcd4baf51cfb2b3953afc0cdd9cadce53e4|
|DOC-KR491-004|LIB-010-M-a40d21297ae5<br>지도매뉴얼/도사레벨별마법안내서.txt|25–33;45–53|도사 Lv5 초기 기술과 Lv6 회복·Lv12 파이어볼을 구분한다. 주술사 문서와 같은 공격기술의 학습레벨이 달라 공통 기술표를 강제할 수 없다.|ad65f2b30410c44478d1f9a2d59a1d759d9ed597f2882f6e9b554eeff2e44211|
|DOC-KR491-005|LIB-010-M-e298b8f39a26<br>지도매뉴얼/국내성위치가이드.txt|56–74;90–97|전사·주술사·도적·도사 길드 위치와 국내성 사대문 위치가 각각 적혀 있다. 비영사천문은 직업 취득 후 배워 사대문으로 이동한다고 설명한다. 서문 좌표 원문의 구두점은 불명확하다.|b355475351dfd0639212b887dcdc39a2f9e768f68b9d6722fecc05f60f85fd91|
|DOC-KR491-006|LIB-010-M-71bda654cf90<br>지도매뉴얼/초보자용메뉴얼-1.txt|214–230|길드별 위치와 레벨에 맞는 기술 목록·재료 확인·학습 절차를 설명한다. 여기의 길드 좌표는 국내성위치가이드와 달라 별도 시대/맵 후보로 보존해야 한다.|6ad554b9414077d9c39c84ed332cac10b8a76c473aefdfddabd397c7e191a6ba|
|DOC-KR491-007|LIB-010-M-83ce2f6ad1db<br>지도매뉴얼/주술사 가이드.txt|128–131;153–158|비영사천문에서 서 방향을 고르면 서문에 도착한다는 동작과, 사망 후 성황령·성황당 부활 절차를 설명한다. village 하나로 이동시키는 규칙의 근거가 아니다.|76782bb3abef9b21609dced97dd90bcd4baf51cfb2b3953afc0cdd9cadce53e4|
|DOC-KR491-008|LIB-010-M-a40d21297ae5<br>지도매뉴얼/도사레벨별마법안내서.txt|133–139|도사 Lv35 귀환의 주막 이동·마력 소모가 적혀 있다. 비영사천문과 귀환을 별도 기술 규칙으로 관리할 근거이며 연도 채택은 잠정이다.|ad65f2b30410c44478d1f9a2d59a1d759d9ed597f2882f6e9b554eeff2e44211|
|DOC-KR491-009|LIB-010-M-e298b8f39a26<br>지도매뉴얼/국내성위치가이드.txt|2–8|주막은 물품/돈 보관과 특정 재고, 푸줏간은 고기/가죽 거래로 설명한다. 모든 NPC에 같은 재고와 서비스를 붙일 근거가 없다.|b355475351dfd0639212b887dcdc39a2f9e768f68b9d6722fecc05f60f85fd91|
|DOC-KR491-010|LIB-010-M-b829514db09c<br>README.TXT|148–159|아이템 I·마법 + 목록의 오른쪽 표시와 소지량 초과 시 줍기 거절을 설명한다. 사용자 사진의 네 탭 모양/촬영연도는 별도 근거다.|b10f5a4f33a3e17f2352867f7d13c4598bfb4e86f6828fca6bec447389976777|

## P2용 대표 원본 연결

|파일|member ID|SHA-256|준비한 정보 / 남은 확인|
|---|---|---|---|
|Body.epf|LIB-010-M-2dee5af66267|9b100ef5f68adbc5691d8a34d76e9db82191d230c894015b6af779407fbd5f9b|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Body.pal|LIB-010-M-6dd2acb9a388|18e54785ce2c60905b43993fbf05694cd5c1ab0a524f4268200a82a46726b4a6|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Body.tbl|LIB-010-M-6ace34fcf47c|3f00ffd5fb9373da07ac4528c952e11441652ca05475a7a2d637813ca8494c46|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Head.epf|LIB-010-M-004fedd92b84|f8967f4b7f041de5f5601dc056621074ac436a2e235170fb31bc30b5f91dd4b0|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Head.tbl|LIB-010-M-8b2bb245878b|b789d7f2b10e47c91df32d47be682604bce6905eb59228f72e6f6fe9e80502d6|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Sword.epf|LIB-010-M-14b30d5faccb|6dc71d8b21b5ffe1083d771598cbaaa2d21d42f7467b50e404a325bc19f2bd3c|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Sword.tbl|LIB-010-M-fe92684d8663|844c866d22ebd2cf02de01058c4b19cd3510e0ad3dcfb4298143d62e27cdfff7|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Item.epf|LIB-010-M-baef0ec0ba27|7969bf7ae9a1998ebd6ff75fa8816473aa6bf1ac47e70c65fb223f8164cb6946|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Item.tbl|LIB-010-M-1bf6950b4c1c|b14d1429255a4c223d82d0d357d8572dbd1405dbebe7c0396916f6ae85bf25bc|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Effect.epf|LIB-010-M-971031de049e|2eff8473033b68a11c203c33b6818b80d46b69d7a13984d71f4e63e42dec6c9b|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Effect.tbl|LIB-010-M-295b87f08885|ef56308d711d52ce154950d542724def164870645aea1dd72d2685005fc1b1a8|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Effect.frm|LIB-010-M-16ef881cf3c8|2a166f05a9c231f545c3b57df69b0c765c9149121b8ef251401a52d035c734e5|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|EffLayer.tbl|LIB-010-M-d61152c67002|7c92fff628c59fe3374c0dfcf7524f61373ad48e2f3e90e761e217371313238a|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|EffRange.tbl|LIB-010-M-29ce0f41f465|7f0d12abe41a623f42daa5432dc070ae77e3c8d1315e4eb5d7d6b90cb349cc39|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|DrwOrder.tbl|LIB-010-M-b89c932190dc|c61a39740a467b001a4cd0d4455b1dadff1f9229d8cb08c91aaa01d72bbe74ca|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|MonsFrm.tbl|LIB-010-M-dd4a60742966|6df861860930d3b4564df862925519fe0e25380a5c4defdbe296b2425c8eede6|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|DlgLogin.epf|LIB-010-M-701e21fab54a|acd6464c430b5a1ac9208d59bd4f76b29e5d706dbd74cf5e5814361c48e1c783|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|DlgNew01.epf|LIB-010-M-f8b763f3e99a|6d6decd6a93fe0e2fa17e7b76197d7e6c3a456718be51b34f18d8441e4975414|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|
|Str_Kor.res|LIB-010-M-c59f784d166b|22e4085c4c556a725b9ba1f650bc286eed56ec73906899c3aa92f60a0f2fa27c|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|

## 미활용·미조사와 다음 행동

- 해독 실패: KR/NA 설치 보조 _SYS1.CAB/_USER1.CAB는 host libarchive 미지원이며 주 데이터와 별도 기록한다. 필요한 런타임 파일이 P2 기준 조합에서 확인될 때만 기존 reader를 확장한다.
- 정적 내부 미조사: NA 단독 EXE, NA4.66 nxuswind.exe, NA_ALL 8개 EXE의 payload는 이번 목록화에서 실행/추출하지 않았다. 이름·크기·SHA와 일부 installer marker만 기록했다. 같은 SHA의 4.95/프랑스 실행파일은 별도 독립 자료로 중복 계산하지 않는다.
- ID 미식별: 프레임 원본 ID와 팔레트는 연결되지만 기술명→효과ID→소리ID→시점 연결은 후속 표/관찰로 채워야 한다. 자료 있음과 완성 기술을 구분한다.
- 버전 불일치: KR1.25 지도, KR4.91 그래픽·문서, NA495 지형과 후대 지형은 각각 보존한다. 다른 도시좌표/도사 추가 예정 문구의 충돌을 평균내지 않는다.
- 지원 코드 없음: 새 게임은 미구현이므로 모든 자산의 새 런타임 BOUND/EXERCISED는 NOT_RUN이다.
- 의도적 미사용: 목표시기 밖 클라이언트와 개인정보 포함 가능 기존 save/build evidence를 새로운 게임 데이터로 넣지 않는다. 원본은 개인 보관한다.
- 패키징·캐시 원인: 같은 원본 지문만으로 기존 변환 코드가 올바르다고 확정하지 않는다. 입력+파서+설정+팔레트/ID mapping 지문을 P2 산출에 포함하고 캐시 변조·누락 시험을 설계한다.
- 다음 재개: 한국 원본 후보 MAP를 별도 포맷으로 읽어 독립 참고 지도/도구와 구조 대조 → 한국491 텍스트 효과/레이어/캐릭터표의 frame ID 연결 → 로그인·생성 UI 후보의 clipping 영향을 독립 비교. 이 문서는 P2를 실행한 결과가 아니다.

## 수행한 정적 검사의 결과

```json
[
  {
    "check": "v125_original_manifest_slices",
    "checked": 45,
    "failures": 0,
    "scope": "BYTES_ONLY_NO_ANIMATION_SEMANTICS"
  },
  {
    "check": "private_manifest_files",
    "source_id": "LIB-036",
    "manifest_member": "PRIVATE_MANIFEST.json",
    "checked": 506,
    "failures": 0
  },
  {
    "check": "private_manifest_files",
    "source_id": "LIB-037",
    "manifest_member": "PRIVATE_MANIFEST.json",
    "checked": 322,
    "failures": 0
  },
  {
    "check": "private_manifest_files",
    "source_id": "LIB-038",
    "manifest_member": "PRIVATE_MANIFEST.json",
    "checked": 64,
    "failures": 0
  },
  {
    "check": "private_manifest_files",
    "source_id": "LIB-040",
    "manifest_member": "PRIVATE_MANIFEST.json",
    "checked": 94,
    "failures": 0
  },
  {
    "check": "kr491_shared_epf_pal_source_links",
    "checked": 131,
    "failures": 0
  },
  {
    "check": "kr491_shared_sound_original_hashes",
    "checked": 163,
    "failures": 0,
    "meaning": "file IDs and PCM metadata only; skill/event mapping and playback timing unknown"
  }
]
```

재현: 먼저 inventory_archives.py로 ZIP/7z를 목록화하고 link_archive_metadata.py를 실행한다. --tools는 기존 커밋의 두 파서로 hash gate를 통과해야 하며, --private-work는 공개 checkout 밖으로 지정한다. 새 게임 시험 결과는 전부 NOT_RUN이다.
