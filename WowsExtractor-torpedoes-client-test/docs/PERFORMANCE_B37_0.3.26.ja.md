# B37：avatar観測と魚雷6本のまとめ確認

2026-11-03。ユーザー報告：装填は最初45秒・全体90秒、ゲーム内表示8:28に装填完了・発射、7:30に終了。FPS・カクつきは今回未報告。ゲーム表示残り時刻とstate tsは直接変換しない。試験後クライアント停止を確認し、mod13ファイルをhash照合してロード対象外へ保全退避。

## 記録概要

私有JSONLを逐次解析。meta2件はいずれも0.3.26-avatar-observations、roster12。active738、inactive2。重複metaを独立した2試験と断定しない。active ts3284.2865～3434.8668（約150.58秒）、平均更新間隔0.20432秒、最小0.20000、最大0.22011秒。

shipsは12艦725 state、6艦10、10艦2、9艦1。全8,789艦行でmap nx/ny・playerIdあり、indexHits8,789、ships内vehicleLookups0。

## avatarObservations：位置・HPは取得、対応は未解決

全738 activeでcomplete、sampledEntityCount12、healthRawAvailableCount12。mapPositionAvailableCount12が731 state、6が7 state。**distinctPlayerIdCount0、unmatchableIdCount12、apiPresenceUnknownCount12が全state**。apiMatched/missingInApiはともに0。

これによりraw地図座標・HPの別出力は実機で動作した一方、avatar.playerIdを使う厳密対応は成立しなかった。既存map経路のavatar.id fallbackが関係する可能性はあるが、この記録では候補の生値・playerId欠測理由を出していないため、None／属性欠落等の詳細や名前空間は確定できない。avatar.idを確認なしでplayerIdへ代入しない。24対20問題に使える識別付き観測としては未完成。

## 魚雷負荷

魚雷なし504 state、6本202 state、残りは1～5本の遷移。uiId/shotId/ownerId複合候補は6種類、ownerIdは1種類。初出ts3380.0558、最終有観測3427.7056（約47.65秒）。この区間は観測期間であり、直接取得した魚雷寿命ではない。

全魚雷行1,306のmotion availableは1,300、初回等のunavailable6。魚雷mapPositionStatusは全行unknownで、今回の較正から地図座標は取得できていない。world positionと地図座標の取得可否を混同しない。

profilerはtime.clock / basis assumed、syncEncodeWrite、29窓。記録時計上の値でCPU使用率・FPSへ換算しない。各summary間のstateがすべて0本の18窓、すべて6本の7窓を比較し、発射・消失の遷移を含む4窓は別群とした。summaryは直前submit/cycleの完了境界とずれ得るため、厳密なper-state attributionではない。

| 区間 | 0本・450 sample平均ms | 6本・175 sample平均ms |
|---|---:|---:|
| torpedoes | 0.020 | 0.260 |
| submit | 0.975 | 1.083 |
| ships（avatar観測生成込み） | 0.813 | 0.852 |
| avatar | 2.134 | 2.190 |
| state_cycle_total | 5.146 | 5.633 |

6本群のtorpedoes最大0.465ms、全29窓のtorpedoes最大0.846ms。全窓cycle平均5.321ms・最大7.834ms。inclusive区間を加算しない。同一試験の魚雷6本出現後は小さな増分を観測したが、cycle差全てを魚雷起因と断定しない。

## 判断と次工程

0.3.25のフィールド共有は0.3.26の追加出力とまとめて試験したため、単独の性能効果は切り分けられない。FPS情報も未報告なので体感改善は主張しない。6本・所有者1つの負荷を多数魚雷／多数所有者へ直線外挿しない。

優先はavatar識別子の取得経路とテストfixtureの実機差の調査。まず既存record/sourceで確認し、候補IDを明示的に別namespaceとして出す最小修正を検討する。無根拠joinやrosterからのalive/位置補完は行わない。開始直後FPS低下はユーザー指示どおり追わない。
