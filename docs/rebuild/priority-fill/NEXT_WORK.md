# 멈춘 곳에서 재개

현재 새 작업은 P2자료선정·검수 PARTIAL이다. P3/P4승인으로 해석하지 않는다. 최신 원격HEAD→STATE_PRIORITY_FILL→RESULTS→PRIVATE_DELIVERY 순서로 읽는다. 실제최신HEAD를 보존하고 GEN003으로 reset하지 않는다.

1. 비공개 BARAM_PRIORITY_PRIVATE_RUNTIME_GEN002.zip을 PRIVATE_DELIVERY의 동일ID로 복원한다. ZIP SHA256 6d9ea0d67116b40287eb4b02e61aac8e1fe86afb48603261450175938d0fb173, runtime.json SHA256 812e4bd6397cf540af203ca6644aea99b898532e071f0637cfdcbba8d144e286.
2. `python3 tools/rebuild/p2/priority_restore.py --zip <ZIP> --sha256 6d9ea0d67116b40287eb4b02e61aac8e1fe86afb48603261450175938d0fb173 --manifest-sha256 812e4bd6397cf540af203ca6644aea99b898532e071f0637cfdcbba8d144e286 --destination <새 private경로> --receipt <새 receipt.json>`를 실행한다. GEN003restorer의100MiB범위는 변경하지 않았다. 새 명시generation만192MiB상한·4237파일·두SHA pin·전후파일검사로 처리한다.
3. 실제검수는 Godot4.6.3에서 `BARAM_P2_RUNTIME=<복원경로> BARAM_P2_REPORT=<새결과.json> <Godot> --path rebuild/p2 -- --p2-priority-smoke`로 가능하다. 화면/오디오서버가 필요하면 priority_run.py의 --system-root/--output을 새 경로로 주고 실행한다. 같은해시·소스·범위의554GUI/47기존회귀/386효과/17규칙을 단순재실행하지 않는다.
4. TOP20_REMAINING.json 순서대로 한국도시정체성→출구/귀환→개별NPC외형·좌표→음향/타격/마스크→실기기/인증 장애를 해결한다. 정확한 새자료가 없으면 이미명시된재구성만 별도프로필로 확장한다. 필드마다 selection→binding→output단계를 구분한다.
5. Android의 다음진단은 tools/rebuild/p2/work_platform.py android-run과 PLATFORM_DIAGNOSIS.json을 사용한다. 전체로그·launch-W·PID·Activity·graphics·보고서후보경로를 먼저확인하고 SDK/에뮬레이터를 허용된무료환경에서 확보한 뒤 영향좁힌시험만한다. Windows는 규칙우회없이허용된native환경이 필요하다.
6. 신규값을 선택했으면 별도GEN003이후 세대로작성하고 원본/현재GEN002/GEN003역사는 보존한다. 충돌15·더넓은82·진마반지충돌·Work비선정89의행방을지우지않는다. 남은자료CSV883행의분모·중첩범위를유지한다.

사용자 실제세이브·기존앱·서명키·인증DB·운영브랜치는 이 작업에서 열거나변경하지 않았다. 설치/실행본 요청은별도범위로받고 현재Linux성공을Android/Windows완료로승격하지않는다.
