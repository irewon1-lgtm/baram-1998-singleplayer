# 신규 캐릭터 전체 경로 회귀 — dc36b5c

수정된 검증 입력으로 신규 캐릭터부터 전체 핵심 경로를 다시 실행했다. **core 45/45 PASS**, 직후 새 프로세스 재시작 **4/4 PASS**다. FAIL / NOT_RUN / BLOCKED 검사는 각 실행에 없었다.

평민 1 생성 → 마을과 실제 지도 → 사냥터 이동 → 정상 공격·경험치·랜덤 드롭 → 사냥 의뢰 → 평민 5 → NPC에게 주술사 전직 선택 → 재료 비용을 지불한 비영사천문 학습·시전·맵 전환 → 정상 사냥으로 주술사 6 → 배운 비영사천문으로 동굴에서 귀환 → 도토리 10개를 지불한 화염주 학습 → 실제 피해 44·처치·경험치 증가·MP 소비 → 저장 → 새 프로세스에서 전체 캐릭터·몬스터·드롭·RNG 복구를 확인했다.

최종 캐릭터는 주술사 6, 66킬이다. core 실행은 504.924초, 새 프로세스의 재시작 검사는 394ms였다. 실행 전체 벽시계 시간은 518.903초다. 캐릭터 수치·경험치·아이템·좌표·시간 배율을 주입하지 않았다. 생성 전에 해당 고유 저장 경로에 캐릭터 파일이 없음을 확인했다.

| 범위 | 결과 | 근거 |
| --- | --- | --- |
| 신규 캐릭터 핵심 경로 전체 | PASS | 45 checks, 0 FAIL / NOT_RUN / BLOCKED |
| 새 프로세스 저장 복원 | PASS | player / world / loot / RNG, 4 checks |
| 실행 EXE 불변 | PASS | 실행 전후 SHA-256 동일 |
| Windows 네이티브 실행 | NOT_RUN | 이 실행은 Linux에서 Windows EXE의 내장 PCK를 실행함 |
| Android 네이티브 실행 | NOT_RUN | 별도 검증 결과 필요 |
| 이 실행에서 나머지 전체 콘텐츠 플레이 | NOT_RUN | 이 경로의 성공을 전체 콘텐츠 완료로 확대하지 않음 |

## 소스 계보

- 요청 소스: `dc36b5c7f3283fd10739947238b0c6b1b56dbccc`
- 실제 EXE 내장 빌드 표기: `a0ccaa4b0e7bfc724d0d2fbf2ded91eb8c683a2d`
- 두 소스의 57개 게임 입력 중 차이는 검증 전용 `recovery_play_probe.gd` 1개뿐이다. 나머지 56개는 파일별 바이트 동일이며, 기존 EXE의 생산 스크립트 21개 의미 동일 검증도 별도로 보존했다.
- 이번 검증 helper SHA-256: `69655d19636834a6c87d37d01409da65976843f4a4031946ee7c6514e8e04bcc`
- 검증 PCK SHA-256: `e01033dee9c6cda02d919d5558fc9af5702b969cfeb4295daf81c131b463d2d7`
- 실행 전후 EXE SHA-256: `d4b31da9aa1dbadb1e280e087af78fde93cd649cdcfdc501100b4196551f6813`

이전 첫 실행의 39 PASS / 3 FAIL 기록은 변경하지 않았다. 동굴의 살아 있는 쥐를 통과하지 못한 시험 입력 경로 때문에 실패했고, 검증 helper가 이미 배운 비영사천문을 실제 단축키와 방위 선택으로 사용하도록 보강했다. 생산 게임 코드와 기존 저장 수치는 수정하지 않았다. 이번 결과는 그 보강 뒤 **처음부터 새 캐릭터로 실행한** 결과다.

이전 FAIL 보고서 SHA-256: `2069595c9b517f1d58ecca789669d78dfe73c030bc1b5655f833a8acf9a146b4`

## 증거

- [전체 실행 요약](sandbox:/workspace/scratch/3c696736f844/fresh-core-dc36b5c-20261015/fresh-loop-verification.json)
- [소스·입력 계보](sandbox:/workspace/scratch/3c696736f844/fresh-core-dc36b5c-20261015/source-lineage.json)
- [core 개별 검사](sandbox:/workspace/scratch/3c696736f844/fresh-core-dc36b5c-20261015/evidence/recovery-core-report.json)
- [새 프로세스 재시작 개별 검사](sandbox:/workspace/scratch/3c696736f844/fresh-core-dc36b5c-20261015/evidence/recovery-restart-report.json)
- [보존된 첫 FAIL 보고서](sandbox:/workspace/scratch/3c696736f844/pilot-windows-a0cc-20261015/evidence/core/recovery-core-report.json)

이 결과로 전체 게임 개선 완료나 Windows·Android 네이티브 검증 완료를 판정하지 않는다.
