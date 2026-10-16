# Codex 실제 바이트 전달 안내

P0 CODEX-P2-REQ-001에 대한 Work 응답이다. 현재 Codex는 Library 연결/공유 마운트가 없어 B001을 메타데이터만 확인하고 DEFERRED로 기록했다. 아래 링크는 사용자 계정에서 내려받는 경로이며, Codex가 이미 받은 파일이라는 뜻이 아니다.

먼저 기존4파일과 새배치2파일을 Codex 대화의 파일 첨부 또는 명시적 공유 마운트로 제공한다. 압축을 합치거나 기존ZIP을 다시 만들 필요가 없다. Codex는 원래 verify_delivery_set으로 수신 바이트를 검사한다. 전체 G0에 필요한 원본42개의 정확한 목록은 뒤 표와 INPUT_MANIFEST에 있다. 기기별 기술시험의 부분 해제 여부는 Codex가 결정한다.

| 파일 | 지속 다운로드 | 길이 | SHA256 |
|---|---|---:|---|
| BARAM_P1_5_handoff_20261016.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_5625c3d22e548191bb3c06296c42bf6c/download) | 28665916 | f9fa57ea09f2755d5038cb7208258e3c5b44f6dddea77ebf66dfd6129ef8233c |
| BARAM_P1_5_reference_sources.zip.part001 | [다운로드](https://chatgpt.com/api/library/files/libfile_036902e5f5d88191b4d9080d1646855c/download) | 41943040 | b7bb487c336c185ef2256539a490d85b77519a78cfb19cd08ae536c8eba655cb |
| BARAM_P1_5_reference_sources.zip.part002 | [다운로드](https://chatgpt.com/api/library/files/libfile_9dde919394388191a9c1943fb5908035/download) | 41943040 | 79ad49d06b62f8d40c0141a34346c8f8d2502a691cdd5cf58bb42fb18611e941 |
| BARAM_P1_5_reference_sources.zip.part003 | [다운로드](https://chatgpt.com/api/library/files/libfile_6a18240b68c88191bf3df12b49e58025/download) | 40576768 | 67c0a3a9469bd2bf905e8cd6d83f595c1f2bd8dee36e2545d8279959bacae2c9 |
| BARAM_WORK_SOURCE_DELTA_B001_20261016.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_9f81524ef6708191b09b4150a8ac908e/download) | 19352 | b61c169c899853c0a90849f81174d76c8503e6827ef3244ca489aff2b721e6af |
| BARAM_WORK_SOURCE_DELTA_B002_20261016.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_b231096282808191bd9f316beec877a2/download) | 613492 | dc87687e7260ee4f0c3777bbb46559a67be64f7050195baf6650a29d1c068aee |

| 원본 ID | 파일 | 지속 다운로드 | 길이 | SHA256 |
|---|---|---|---:|---|
| LIB-001 | 7476.jpg | [다운로드](https://chatgpt.com/api/library/files/libfile_ffcf125d9e208191861c69d9171cc108/download) | 341517 | 1b268f01a95883fef923d8b0dcfc0d0d3bdba22a3706da14953213a96c2adca7 |
| LIB-002 | 7478.jpg | [다운로드](https://chatgpt.com/api/library/files/libfile_fcc7a55c4fd8819182cd4dd9badea24f/download) | 385438 | 9d7df72b4ada338fc6233e85c15647549f9fe14b657d6d3e0a0035cbb395d170 |
| LIB-003 | 7480.jpg | [다운로드](https://chatgpt.com/api/library/files/libfile_d7369f0eaba08191aebce13d6d658af1/download) | 298660 | a6b92fcdcc5a3a1b91641dd09bc2ee6b86875f48e730645931ad9db475b948d6 |
| LIB-004 | BARAM.PAL | [다운로드](https://chatgpt.com/api/library/files/libfile_e5e13eb7a9648191aac3e9a307883bae/download) | 768 | 34bee372e754fc423099193587ae265b731d7f7ff0f083a87cb564179aeb266a |
| LIB-005 | Baram_Map_Editor.7z | [다운로드](https://chatgpt.com/api/library/files/libfile_8a6db54007508191b9f51717a0de566e/download) | 1817308 | 4b63aaff6aea18c7b038db715e753468f9a0202e0d3e692dfd7f0c3f341c6e5a |
| LIB-006 | CODEX_ASSET_INTAKE_20261014.md | [다운로드](https://chatgpt.com/api/library/files/libfile_6266ebd0a8d8819182b17729f14c8f8a/download) | 6059 | 338f0b1e6519901141925be2b92c3423ad72e741a0aed3ea91ec889c04e855ea |
| LIB-007 | EPFTool.exe | [다운로드](https://chatgpt.com/api/library/files/libfile_f4a4ccbb5eec81919f96ecd4a2dac2a8/download) | 385024 | d58303a3129547505daf7006e7dc58cc27bcfdad33ee5137c1350ef172a02221 |
| LIB-008 | Judge_Map_Editor.7z | [다운로드](https://chatgpt.com/api/library/files/libfile_5d426fbc78688191a0e20caafef79f36/download) | 2577176 | 7df59393d9aa077c79e0d6f0b40b89d7b56f0ca7edf9f86f9823dc94aa630646 |
| LIB-009 | KR_1.25_winbaram.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_135f7d90220c81919353822363ea2395/download) | 2207781 | 62642ca3ef492f58947abb2c17cbae5b5a60d5f96fd146704b7d99d1aad3bcef |
| LIB-010 | KR_4.91_491v.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_8c9b5125c46c8191b3e21428f6b2b1a4/download) | 26556803 | f11e448db6478b1aca3a7dd47403bdef00cf873b203b14629b0215632190532f |
| LIB-011 | NA_4.03_NexusTK.7z | [다운로드](https://chatgpt.com/api/library/files/libfile_8927e0894a5c8191aa95e91b57fed064/download) | 8517463 | db89e2b1ac3dfd3f5668fd7746478507b370ee627b4321d7dec441620ce96b53 |
| LIB-012 | NA_4.03_french.exe | [다운로드](https://chatgpt.com/api/library/files/libfile_2574d6feb3b08191bd621361ed9d79d1/download) | 6617137 | c8820ac5af784fa6aadcdc86198c84f07ac4e73af1c74ece1152a1c9bd52cd4b |
| LIB-013 | NA_4.66_NexusTK.7z | [다운로드](https://chatgpt.com/api/library/files/libfile_9c0497c882988191b9e9bc4a6c9f0840/download) | 11850016 | 54ca6b8892a2b44ddfaadebc92e1886a770ac07a82b60ceacbfd3e2e44e5774a |
| LIB-014 | NA_4.95_Nexus495.exe | [다운로드](https://chatgpt.com/api/library/files/libfile_0ef3b7e0828c8191a637c4061889b72d/download) | 24658356 | 486f4684b76658d92eaf84aab77fe9be9489ea01de8264fe90d0040466620aaa |
| LIB-015 | NA_5.0_or_older_clients_ALL.7z | [다운로드](https://chatgpt.com/api/library/files/libfile_763dcd5bf7bc8191b8a7bf555403a1b4/download) | 218174017 | d41b644303581f7dfc05ef627d99820f8ccce3152637c9be533f0465dbbcb885 |
| LIB-016 | PRIVATE_ASSET_INVENTORY_20261014.json | [다운로드](https://chatgpt.com/api/library/files/libfile_0b1736e534948191b5cee32ceffb5b5c/download) | 5258 | 4bc4119feee541d60a6d46f1930d3e6dafa0ba7b104264c5aa5db83fc5d725b5 |
| LIB-017 | baram_Codex_tile_handoff_PRIVATE.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_03062c0c1d808191bd8e03d73a9df68e/download) | 7017376 | f36929c43d775058678a708a1da7a140ea13e0e9243d5f4fc2b5e304fa54500b |
| LIB-018 | baram_tile_atlases_PRIVATE.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_60297b3e1ec081918c1dd21d413fc316/download) | 7008649 | 18581f104aa725eb615a205d428a10b46bd670b956876b99fa92ce32ebdc1514 |
| LIB-019 | godot_private_tile_atlas.gd | [다운로드](https://chatgpt.com/api/library/files/libfile_de62e418824481919c06e57812591af7/download) | 2889 | 95d55d99f2267b19bd39df637f231461678b33714520aaa7dca51fc982daa16e |
| LIB-020 | import_private_tile_atlases.py | [다운로드](https://chatgpt.com/api/library/files/libfile_de86cb44b3508191b2e8df4db946613b/download) | 5452 | 114c9d3716262cc0df3437e414b206643413ab35fcb6da0dc52bc20ca66e272d |
| LIB-021 | mithiamapeditor-master.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_fb88347ce2708191ab828bf3690ce11e/download) | 119648 | d49ca6f1ee839d8bf3146b1455bbb07f9642fcc945c914d08106beea40bd54b1 |
| LIB-022 | baram-1998-github-ready.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_4b9d859bc728819194cd995746777fbf/download) | 37216 | c1b682354f15f4c85010f42e2dde8e776076b751aa3bf9ac888d22f15bec0b44 |
| LIB-023 | baram-PC-Android-progress-20261015.md | [다운로드](https://chatgpt.com/api/library/files/libfile_07228e0f7f8881918558230226058887/download) | 15439 | edced326043017a5aca29e7bc6d5555262b6fe37fe08289dade42caafee7ad2f |
| LIB-024 | baram-checksums-05bde481.json | [다운로드](https://chatgpt.com/api/library/files/libfile_2f151520f2188191bee6c27168a647c9/download) | 1487 | 04fefccedeb686563b91b951a3b74b547ca5da3cf11b7fe1834ba34956de243f |
| LIB-025 | baram-evidence-05bde481.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_28226864442881919a7252aef418cfdb/download) | 10584410 | c95648025c435a36636f1d4666021a2e35a8d992c81bb1348fe51aebc2ed623d |
| LIB-026 | baram-work-fix-package-20261015.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_878b995aaef88191a87647cea02e04a8/download) | 1017612 | 1d11618f7cd7c38ab7165721c4c1305d094fffb2c9b92496c3ee55e78cda61de |
| LIB-027 | baram_1998_4_0_research_v1.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_e5d5799da018819188f03aa471d30b44/download) | 8616 | f35a21cb9132bc88b857040fe18b4d8c90e284012d143ca2c1d070114bfe17ba |
| LIB-028 | baram_windows_recovery_results_20261015.md | [다운로드](https://chatgpt.com/api/library/files/libfile_3943ff5574a88191ae019c710189fbed/download) | 10341 | 1ad24e63801e8f69d97c4a17bc5bd377529b2e884c56dfe9ad061327dc01aba5 |
| LIB-029 | baram-ui-map-audit-20261015.json | [다운로드](https://chatgpt.com/api/library/files/libfile_e7fde4f317dc81918d248e9fc8ca1d83/download) | 49869 | 34dc80b1b9550b53046e498e7bae5e879172f4f05eb860f1231175f4025a85a8 |
| LIB-030 | baram-ui-map-audit-20261015.md | [다운로드](https://chatgpt.com/api/library/files/libfile_87168d390ba88191bb248670c350123b/download) | 13221 | f63aa67ac468c898eb647790f0653fe88ad60a7fbeaecd6201918412d82c9608 |
| LIB-031 | baram-work-fix-instructions-20261015.md | [다운로드](https://chatgpt.com/api/library/files/libfile_bb18c9ffce64819197dddb3ed015f9f6/download) | 14532 | 04e78ea5784eef0d63b6d2a7a7d569483644af5ddff0b0063db836e611e67658 |
| LIB-032 | baram_1997_resources_PRIVATE.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_59dedc86ce30819182c9f9b1a4c1a4c3/download) | 1933116 | 8d68178fd64c451d910ace0b702abeb9a19998113f88489c169c1176bd3703ea |
| LIB-033 | baram_1997_sprite_atlases_PRIVATE.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_9afa4d2c562c8191ad95a481b9ef7e87/download) | 2407678 | 1e3bd29712d4ad7e4dd5f2554d80757b65692e31b1846820e26cd7156110c3dd |
| LIB-034 | baram_restoration_ASSET_HANDOFF_PRIVATE.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_322759c82b4c81919a11a960f427a30c/download) | 11687627 | a13dac2a107feefeec256c620ff003cc22b0f40fefb8a619c0276c316dd62dde |
| LIB-035 | baram_source_intake_20261014.md | [다운로드](https://chatgpt.com/api/library/files/libfile_67f86e2645788191901c3e04258e1f51/download) | 5156 | 36faf7c7aec5a647af29f815fac4c5a81a42703f226443744104346a56cbfd0c |
| LIB-036 | work_assets_shared_PRIVATE_final_20261014.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_e8323a0756908191a6b0862fab1291c7/download) | 45747991 | 3bbcd5d69565bbe0d3bbe34149c59061dc3d1c5f3d27533e50a336cefd3e207c |
| LIB-037 | work_regions_PRIVATE_expansion_002_20261014.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_355d5fc3bc70819183e497df9f3e9f9b/download) | 474654 | 0759c95a578c5e25cab3de55b31e254bd1387514de5ce2a191db69699d00956f |
| LIB-038 | work_regions_PRIVATE_final_20261014.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_12659d1a1ab08191bb34bb78ffe68a0d/download) | 219203 | 77bb4290061d5c41b3552623d32c4c795de438d4dcd895cf59cb2c7cefb06b41 |
| LIB-039 | 03_치명결함_필수수정과_회귀시험.md | [다운로드](https://chatgpt.com/api/library/files/libfile_17b5ba8d2a408191b8db6e6cf91450fe/download) | 16619 | c5589eda69919f79ef331000531bef9b61eb9aaaa7596957f164f79dc69356db |
| LIB-040 | work_ui_recovered_PRIVATE_002_20261014.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_bd12aecbf084819182d18b3e717239da/download) | 3686257 | 81ed6c992edbb18ef95f0673aeeec2932cf7c53883127546820af6529ec25c20 |
| LIB-041 | 바람의나라_통합복원_분석과실행지시서_20261015.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_2b06e1dac1bc8191abe60295622901ff/download) | 44261 | c98071d95024c36e037dda48ab96539d4a1b0052ba0fc62600cbb55e7baf727d |
| LIB-042 | 바람의나라_통합복원_치명결함반영_v2_20261015.zip | [다운로드](https://chatgpt.com/api/library/files/libfile_b86d9a5a913c8191b11b4b51ad2af702/download) | 53115 | 5376bdcf1024b4e6b49531ef13dd681db2e2fc62baff174a9e3a4fa02534c52d |

민감 RTK2파일은 Codex가 별도 확보했다고 요청에 기록했으므로 다시 전달하지 않는다. 서명키/실제세이브/폰트/인증토큰을 요청 대응에 넣지 않는다. 원본을 공개 Git에 올리지 않는다.
