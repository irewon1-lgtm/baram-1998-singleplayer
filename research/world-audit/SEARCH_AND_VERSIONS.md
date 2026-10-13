# 조사 범위·출처·버전 구분

전수 인터넷 검색을 완료했다는 뜻이 아니다. 아래 공개 자료를 실제 검색/수집했고 접근 제한과 다운로드 실패를 구분한다. 로그인/유료 구독/실행 운영 서버는 사용하지 않았다.

| 조사면 | 실제 결과 |
|---|---|
| GitHub 이름·코드·브랜치·과거 커밋·릴리스·포크 | 기존19소스 외 Java RTK 확보. P1998 전체1260커밋, 태그/릴리스 없음, master 외8브랜치는 모두 master에 이미 포함. 포크2개 실제 clone; Essorcal601커밋 뒤/unkmc968커밋 뒤, master보다 앞선 커밋0. 포크 개선판 확보라고 주장하지 않는다 |
| GitLab/Codeberg 공개API | nexustk 이름검색 결과0. Baram 추가검색은 CFD/IT 관리/동명이인 등 목표 무관 자료. 실제 내부 코드 전수 검색 권한 없음 |
| Internet Archive | 4.03/4.66/4.95 포함 클라이언트 모음, 한국4.91, 지도 편집기2종, EPFTool, CoM2014, RuneGard 런처/위키, 지도 편집기 소스 보존본 실제 다운로드 |
| Wayback | 공식4.95 파일 실제 다운로드. Nemu/KamiKaze 홈페이지·다운로드·VB페이지/공개 스크린샷 페이지 확보. 정확한 Nemu RAR경로 다운로드404 |
| NexusAtlas | 3.0/4.0 경로로 공개 보존 페이지356개 요청,319개 확보. 발견한 이미지URL908개 모두 요청:870개 다운로드·PIL검증,38개 실패. 해시 중복 제거851개. 3.0지도 이미지186/4.0지도 이미지93; 동굴 썸네일133/10; 몬스터3.0 이미지127. 서버 맵 데이터로 집계하지 않는다 |
| Reddit | Old client links 문서의4.03/4.95/5.32 자료 경로를 원본 링크까지 따라가 실제 확보. 댓글의1999/2001 날짜만으로 한국판 연도 확정하지 않는다 |
| RaGEZONE | 2006 Nemu 싱글플레이 원글·Downloads! 확인. 첨부 로그인 장벽/과거 실패 댓글. 역사적 기능 주장과 오늘 실행검증을 분리 |
| 구 팬사이트/한국커뮤니티/공략집 | Baraminside4.91보존 자료 실제 확보; 구바람 블로그/옛사이트 스크린샷/가이드북 기록 검색. 한국1998 미수정 클라이언트와 옛 공략집 전체 합법적 디지털 원문 미확보 |

검색어는 바람의나라/구바람/바람의나라4.0/Baram/Old Baram/NexusTK/Kingdom of the Winds/3.0/4.0/4.03/4.95/server emulator/old client/map data/sprites/offline server/NemuTK/Runegard/Mithia 및 이름/파일경로 조합을 사용했다. 이름 일치만으로 PASS를 주지 않았다.

## 핵심 원본 URL

- 공식4.95 보존 EXE: https://web.archive.org/web/20010811181949id_/http://file.nexustk.com:80/NexusTK/Client/Single/Nexus495.exe
- 옛 클라이언트 모음: https://archive.org/details/NexusTKKruSetups
- 영문4.03 별도 보존: https://archive.org/details/nexus-tk-v-4.0.3.7z
- 4.66: https://archive.org/details/nexus-tk-v-4.66.7z
- 한국4.91: https://archive.org/details/baram_491
- 한국판 보존 게시물: https://web.archive.org/web/20230704153844/https://www.baraminside.com/bbs/board.php?bo_table=utility&wr_id=13
- Nemu원글: https://forum.ragezone.com/threads/offline-server-using-nemutk-vb-version.165687/
- Nemu다운로드 게시물: https://forum.ragezone.com/threads/downloads.165684/
- Nemu보존 VB페이지: https://web.archive.org/web/20070107092016id_/http://www.kamikazeserver.com/nemu_tk_visual_basic.html
- NexusAtlas3.0/4.0: https://nexusatlas.com/30atlas/ · https://nexusatlas.com/40atlas/
- Java서버: https://github.com/bosbabi168-cpu/RTK-java-version

그 외 정확한 파일URL/리디렉션/크기/해시는 download-attempts.json 및 atlas-results.json. 보존 캡처 날짜와 원본 출시 날짜는 구분한다. 사이트 현재 PHP406은 Wayback의 공개 HTML로 보완했으며 이미지 요청도 최초406 후 올바른 User-Agent로 다시 다운로드했다. 실패 기록 자체를 자료 없음으로 확정하지 않는다.

## 버전 증거의 한계

- 1998: 공식 당대 한국 클라이언트 미확보. EXE의1998 copyright는 출시일과 데이터 연도 증거가 아니다. 커뮤니티의1998 지명/스크린샷을 독립 검증 전 확정 원본으로 쓰지 않는다.
- 1999: 영문4.03의 실제 EXE4,0,3,0과613개 .map 확인. early1999 유통 주장은 자료 경로를 제공한 커뮤니티 기록이며 당대 서명된 배포 원장까지 확보한 것은 아니다.
- 2000:4.66은 보존 메타데이터의2000-05-06/옛 CD 기록, 설치 EXE까지만 추출. 한국4.91은2000-12-14 보존 게시물 날짜 및 실제4,9,1,0 버전 문자열. 동시대 서버 데이터 미확보.
- 2001:4.95는 공식 배포 호스트를 캡처한2001-08-11 보존 파일이며 실제4.95 문자열. PE stub의2000-04-25 timestamp는 설치 도구 빌드일일 수 있어 게임 출시일로 사용하지 않는다.
- 후대: CoM2014, RTK, P1998(2026 시작), Nemu2006, RuneGard2008,5.32/5.33은 독립 계층.4.95와 호환되는 규칙이라도 한국2001과 동일하다고 보지 않는다.
- 클라이언트 모음의 French4.03은 파일명/폴더 라벨과PE2001 날짜가 공존한다.5.32라벨 설치파일에5.31 버전 문자열이 있어 라벨만 신뢰하지 않는다.1996복원판의2013빌드는1996미수정원본이 아니다.

지역/연도 프로필과 각 데이터의 확정·추정·후대 등급을 유지한다. 북미Kugnae/Buya 지도와 한국부여/국내성을 동일 파일로 섞지 않는다.
