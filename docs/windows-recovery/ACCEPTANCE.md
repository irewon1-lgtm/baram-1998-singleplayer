# Windows 복구 및 자동화 검증 기준

입력: 첨부 ZIP SHA256 `7fe9b59e90410ec6af915797ccbb8e7630855574274c419d00fea0a32895baf2`, 개발 HEAD `c483df8aba6fda0ae2c55340258cde44df18c572`.

1. 입력: ZIP CRC·파일 해시·내장 PCK와 최신 코드 대조.
2. 시작: Windows x64 실제 EXE에서 60초 이내 ready, 오류·충돌·무한 대기 없음. 초기화 구간·CPU·최대 메모리 기록. 로딩 중 메시지 펌프 진행.
3. 게임 자동시험: 실제 게임 코드로 캐릭터 생성·이동·맵전환·전투·획득·NPC·저장·별도 프로세스 재시작 모두 실행. 미실행 PASS 금지.
4. GUI: 실제 Windows 화면 조작과 렌더 표시를 별도 판정. headless·Linux·fixture를 GUI 플레이 통과로 바꾸지 않음.
5. 보존: 기존 private_assets/private_content 943개 바이트 그대로 유지, 저장 schema2·경로·백업 유지.
6. CI: 개발 브랜치 변경 시 Windows 빌드·시작·게임 회귀·ZIP 자동 실행. 실패 시 전달 차단, 원인 기록. 비공개 자산·화면·세이브는 공개 저장소 및 평문 Actions artifact 금지.
7. 전달: 기존 ZIP 보존, 새 ZIP을 클릭 가능한 파일로 제공.

구현·정적·fixture·Windows-native·GUI·전달 상태를 각각 기록한다.
