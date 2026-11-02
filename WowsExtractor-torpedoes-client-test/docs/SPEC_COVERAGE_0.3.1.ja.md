# 元仕様との詳細対応表 — 0.3.1実機確認版

本書は0.3.1の実機実績。0.3.2で最終目撃キャッシュ／TTL／ghostを撤去し、
可視状態と座標を分離した。現行契約は [OBSERVATIONS.ja.md](OBSERVATIONS.ja.md) を優先。

更新日：2026-11-01。元仕様は同梱の `OUTPUT_SPEC.ja.md`、`DESIGN.ja.md`。
「出力するコードがある」「実際に値を取得した」「値の意味まで検証した」を分離する。
この表は取得側modの状態。簡易2Dビューアの表示可否は別文書で扱う。

簡易ビューアは追加済み。2026-11-01、グリッド上の位置が概ねゲームと一致すると
テスターが目視確認。これは定量較正や全条件の検証完了ではない。

## 判定と根拠

- **取得確認**：実機で値を観測。全艦種・全条件の保証ではない。
- **条件付き**：欠損・供給者依存・推定変換などがある。
- **実装のみ**：コードはあるが対象ケースの実機確認がない。
- **未取得**：必要な値がnull/空、または取得経路を実装していない。

主な根拠：0.2.0の通常/音響魚雷、0.2.1の連続2戦、0.2.2のUI比較、
ATMありの一重/二重ping・期限切れ・再誘導、および0.3.1の移動較正試験。
破棄された旧b04/b05は根拠から除外する。同名ファイルが再利用されているため、
ファイル名だけでなくversion・戦闘・記録時刻で区別する。

**0.3.1対象戦闘の集計**：active 1576フレーム、約162.8秒、終了フレームあり。
艦船延べ13906行、通常魚雷1本374行、当該起動のWowsExtractorエラー0件。
個人名・IDの実値はこの表へ転載しない。

## 1. 魚雷の公開7属性と識別

| 元仕様の項目 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| UI識別子 | `torpedoes[].uiId` | 取得確認 | 374/374行。UI entity IDとの一致も試験範囲で確認 |
| 発射元識別子 | `ownerId` | 取得確認 | 374/374。playerId/vehicleIdと同じ名前空間とは確定していない |
| 発射元チーム | `ownerTeamId` | 取得確認 | 374/374。敵・僚艦魚雷の専用比較は未実施 |
| 発射元種別 | `ownerType` | 取得確認 | 374/374。Cruiser/Submarine等の生値 |
| 射撃/斉射識別子 | `shotId` | 取得確認 | 飛翔中安定。複数本で共有され得るため単体キーにしない |
| 魚雷type | `type` | 取得確認 | normal/acoustic/magneticの変化・復帰を観測。deepwater/not_dangerous等は未試験 |
| ワールド位置 | `position:[x,y,z]` | 取得確認 | 374/374。ゲーム座標の生値。実m・潜航深度とは未検証 |
| 味方/敵の分類 | `relation` | 条件付き | チーム比較の1/2/null。自艦と僚艦は区別しない |
| 発射元オブジェクト | `owner` | 条件付き | オブジェクトは得られるが属性の一部は常にnull |
| 発射元のチーム/生存等 | `owner.teamId/isObserver/isAlive/isBot` | 取得確認 | 各374/374行に値あり |
| 発射元のUI ID/名称/艦種等 | `owner.uiId/isPlayer/subtype/name/playerName` | 未取得 | 最新試験は各0/374行に非null。キーは存在する |
| 自艦魚雷判定 | `isOwn` | 未取得 | 最新374行すべてnull。owner.isPlayerへの依存では未成立 |
| API一覧取得状態 | `torpedoStatus.available/status/source` | 取得確認 | availableと空配列、unknown、unsupportedを区別。実機飛翔中は取得成功 |

現在は自艦の単発魚雷中心の訓練戦試験。12対12での敵/味方/画面外魚雷、
複数本斉射、ID再利用は実機検証が必要。消えた魚雷は正常な次フレームから削除し、
見失った魚雷の位置を外挿して現在値として残さない。

## 2. UI/ATM由来の状態

| 元仕様の候補 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| UI魚雷type | `uiState.uiType` / `uiTorpedoProbe.rows[].uiType` | 取得確認 | API側typeとの一致を確認。ゲーム内の意味はtype単独で確定しない |
| UIとAPIの対応 | `uiState.matchStatus` | 条件付き | IDが一意に一致した場合のみexactUiId。重複/未一致はunknown |
| 現在の誘導判定 | `uiState.isHoming/homingStatus` | 条件付き | ATMありでtrue/false、停止→再誘導を実測。取得前はnull |
| 被発見表示用判定 | `uiState.isSpotted/spottedStatus` | 条件付き | 0.3.1でtrueを80行取得、294行はunknown。falseの実機変化は未検証 |
| 取得元/供給者 | `uiState.source/producer` | 出力あり | ui.mods_DataComponent / unknown。フィールドだけでATM供給を証明しない |
| 生値・型・コンポーネントキー | `uiTorpedoProbe` | 取得確認 | bool/null・型・キーを診断。正式な判定にはuiStateを優先 |

ATMなしではisHomingが未供給だった。取得不可はfalseと異なる。
isSpottedはATMの被発見表示用の計算値で、敵がサーバー上で確実に検出したという意味ではない。

観測された傾向（原因確定ではない）：
- 接近時の誘導停止候補ではtypeを維持したままisHoming=false。
- ping期限切れ候補ではtypeがnormalに戻り、isHoming=false。
- 再pingで同じ魚雷が再びisHoming=trueになった。
- typeとATM状態には約1フレームの更新差が出る場合がある。

## 3. 魚雷の追加推定情報

| 項目 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| 水平速度 | `motion.horizontalSpeed` | 推定・取得確認 | 373/374行で計算。0～約6.04ゲーム座標単位/秒。ノットではない |
| 3軸速度 | `motion.velocity` | 推定・取得確認 | 連続する位置差/ゲーム時刻差。ゲームの公式速度属性ではない |
| 航向 | `motion.headingRadians` | 推定・取得確認 | atan2(vx,vz)、+Z基準、+X方向が正。停止時null。ship.yawとは規約が別 |
| 差分間隔 | `motion.dt` | 出力あり | 初回・非増加時刻・1秒超の欠測では速度を出さない |
| 連続観測時間 | `motion.observedAge` | 推定・取得確認 | 最初の連続取得から。真の発射時刻/寿命ではない |
| 連続観測移動距離 | `motion.observedDistance` | 推定・取得確認 | 水平移動の和。真の走行距離/最大射程とは限らない |
| 推定の明示 | `motion.source/inferred/speedUnit/available` | 出力あり | positionDifference / true / game_world_units_per_second |
| 地図座標 | `mapPosition:[nx,ny]` | 推定・取得確認 | 較正後の全374行で取得。地図外・未較正はnull |
| 地図座標の状態/由来 | `mapPositionStatus/mapPositionSource` | 出力あり | available/unknown、calibratedWorldPosition |

位置が動かなくなっても命中とは断定しない。APIの消滅と命中/射程切れは同義ではない。

## 4. 自艦魚雷兵装・未取得の魚雷戦情報

| 元仕様の項目/要求 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| 発射管一覧・取得状態 | `torpedoArmament.modules/modulesStatus/available` | 取得確認 | 最新は4基×1576フレーム=6304行 |
| 発射管の種別/HP/状態/位置 | `modules[].type/currentHP/maxHP/state/position` | 取得確認 | 各6304/6304行に値あり。故障・破壊時の変化は未試験 |
| 故障関連タイマー | `modules[].critTimer` | 未取得 | 最新6304行すべてnull。再装填タイマーではない |
| 選択中の魚雷弾ID | `selectedAmmoId/selectedAmmoStatus` | 取得確認 | 選択弾IDあり。複数魚雷種への切替は未試験 |
| 魚雷弾詳細 | `ammoParams/ammoParamsStatus` | 未取得 | availableでも実値は{}。速度/射程が取得できたことにはならない |
| 管別装填残数/残り装填時間 | なし | 未実装・経路未確認 | 発射管HP/stateや消耗品numから補完しない |
| 最大射程/残り射程/確定寿命 | なし | 未実装・経路未確認 | 観測距離・時間を代入しない |
| 誘導先ID/ping目標/命中区画 | なし | 未実装・経路未確認 | 最寄りの艦を確定目標として扱わない |
| ping効果残時間/命中・失効時刻 | なし | 未実装・経路未確認 | isHoming変化と操作申告のみでは厳密な効果タイマーにならない |
| 誘導停止距離/停止理由 | なし | 未実装・経路未確認 | 距離制限・期限切れを確定理由として出していない |
| 命中/射程切れ等の消滅理由 | なし | 未実装 | 現在は魚雷一覧からの消滅だけを観測 |

外部の艦艇百科APIには標準構成の魚雷速度・射程・再装填時間があるが、
戦闘中の装備・選択弾や各種補正を保証しない。動的取得値として組み込んでいない。

## 5. 自艦・他艦と座標

| 元仕様の項目 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| 自艦ID/チーム | `self.playerId/teamId` | 取得確認 | 各1576/1576フレーム |
| 自艦位置/向き/速度 | `self.position/yaw/speed` | 取得確認 | 各1576/1576。yaw/speedの単位・軸規約の検証は残る |
| 自艦HP | `self.health/maxHealth` | 取得確認 | 各1576/1576。UI由来補完を含む |
| 自艦可視/観戦状態 | `self.isVisible/isShipVisible/isObserver` | 条件付き | 値はある。観戦切替の専用試験は未実施 |
| 他艦を含む識別 | `ships[].uiId/vehicleId/playerId/teamId/relation` | 取得確認 | 最新延べ13906行に値あり。ID名前空間は別々に扱う |
| 艦名・艦種 | `ships[].name/shipType` | 取得確認 | 同13906行。個人名を外部表示する必要はない |
| 生存・可視判定 | `alive/visible` | 条件付き | visibleは現在の実装による位置存在判定。現在3D可視を保証しない |
| HP/向き | `health/maxHealth/yaw` | 取得確認 | 同13906行に値あり。敵艦HP・yawの正確性の専用比較は未実施 |
| 直接ワールド位置 | `positionSource=shipOrPlayerApi` | 条件付き | 最新1576行、自艦のみ。他艦getPositionはNoneを観測 |
| 他艦の推定ワールド位置 | `positionSource=calibratedMapPosition` | 推定・取得確認 | 較正後8隻×813フレーム=6504行。較正前は欠損。y=0で深度ではない |
| 地図座標 | `ships[].nx/ny` | 取得確認 | 最新13906行。UI mapPosition由来。画面との独立照合は次段階 |
| 地図座標の由来/鮮度 | `mapPositionSource/mapPositionFreshness` | 出力あり | dataHub.mapPosition / unverified。現在値と断言しない |
| 最終目撃位置/向き/HP | `lastPosition/lastNx/lastNy/lastYaw/lastHealth` | 実装のみ | 最新試験では0行。発見→失探→再発見/撃沈の専用試験が必要 |
| 最終目撃時刻/経過 | `lastSeenTs/staleSeconds` | 実装のみ | 最新試験では0行。取得元はlastPositionSourceで区別する |

**重要な残課題**：mapPositionが失探後も残る可能性があり、現modはその鮮度を
完全には判定していない。外部表示は「現在可視の確定位置」と誤称しない。
将来の深度表示もy=0補完位置からは作れない。

## 6. 地図・較正・診断

| 元仕様の項目 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| 地図ID/名前/画像参照 | `meta.map.id/mapId/mapName/mapPath` | 取得確認 | Oceanで取得。ゲーム内画像パスは外部HTTP URLではない |
| その他の地図名候補 | `geometryName/geometry/spaceName/spaceId/name/arenaName`等 | 条件付き・最新未取得 | 存在する公開属性のみ出力。全候補が常にあるわけではない |
| 地図サイズ/境界 | `width/height/size/worldSize/bounds/spaceBounds/min*/max*`等 | 最新未取得 | mapメタデータに実値なし。係数を実mの地図サイズと呼ばない |
| 履歴式較正状態 | `diag.mapCalibration.status/reason` | 実機確認 | 開始約78.7秒でavailable。その後813フレーム安定、driftStreak=0 |
| 係数・軸対応 | `mapCalibration.coefficients` | 推定・実機確認 | OceanでX←nx、Z←ny反転。他地図は未検証、定数はハードコードしない |
| 較正誤差 | `rmse/holdoutRmse` | 実機確認 | 採用時約0.0649/0.0656ゲーム座標単位。独立した他艦正解位置との誤差ではない |
| 蓄積/採用/保留サンプル数 | `sampleCount/fitSampleCount/holdoutCount` | 出力あり | 最新168/72/15。後から蓄積された全点で再fitするわけではない |
| サンプルの広がり/不整合 | `span/driftStreak/holdoutOutlierCount` | 出力あり | 停船・直線・微小移動・異常値では安全側に保留 |
| そのフレームの対応点数 | `diag.mapSamples` | 実機確認 | 依然1。履歴式では1隻でも移動によって較正できる |
| 互換診断名 | `diag.mapCalib` | 出力あり | 0.3.0以降はA/B/nullではなく較正status。詳細はmapCalibration |
| 直接位置の取得失敗分類 | `diag.positionReads` | 実機確認 | getPosition:none等を記録。複数経路の再試行を含み艦数とは一致しない |
| 艦数・可視数・HP件数 | `totalShips/allies/alliesVisible/enemies/enemiesVisible/ghosts/uiHealth` | 条件付き | 出力あり。可視数は現実装の判定であり視認保証ではない |

## 7. 消耗品・索敵装置・名簿

| 元仕様/追加項目 | 現在の出力 | 状態 | 実測・制約 |
| --- | --- | --- | --- |
| 名簿識別/チーム/艦種/艦名/tier | `meta.roster[].playerId/teamId/relation/name/shipType/shipName/shipTier` | 取得確認 | metaに値あり。個人情報の共有に注意 |
| 消耗品の静的情報 | `roster[].consumables[].title/abilityId/params` | 条件付き | 値あり。動的残数・残時間を意味しない |
| 自艦消耗品一覧 | `selfSystems.consumables.status/items` | 取得確認 | 全1576フレームavailable |
| アイコン/残数/状態/終了時刻 | `items[].icon/num/currentState/endTime` | 条件付き | 残数4等を観測、一部numはnull。endTimeの時刻基準は未検証、残秒に換算しない |
| ソナー距離/状態/作動残時間 | `search.hydroAcoustic.items[].distShip/state/workTimeLeft` | 条件付き | 実値あり。距離166.6666等は生値で実mと断定しない。作動中の変化は未試験 |
| レーダー状態 | `search.radar` | 実装のみ・最新unknown | 非搭載と取得不可を区別できず、falseや非搭載と決めつけない |
| 潜水艦探知装置状態 | `search.submarineLocator` | 実装のみ・最新unknown | 同上。pingの効果残時間とは別 |

## 8. 既存戦果・砲弾情報・共通契約

| 元仕様の項目 | 出力 | 状態・注意 |
| --- | --- | --- |
| 与ダメージ・対象別 | `damage.inflicted` | 出力・変化を観測。魚雷専用戦果ではない |
| 被ダメージ・攻撃者別 | `damage.received` | 最新57フレームで非空。今回の魚雷試験では被弾条件を網羅していない |
| チーム与ダメージ | `damage.teamTotal` | 出力あり。元コードの推定・重複抑制に依存 |
| 砲弾諸元/着弾情報 | `ballistics.available/squadronMode/ammoType/ammoId/penetration/impactSpeed/impactAngle` | 最新MinotaurでAP情報1464フレーム、penetration/impactSpeedは1463行に値あり。値の正確性の専用比較は未実施。魚雷には流用しない |
| AP/CS諸元 | `startRicochet/alwaysRicochet/overmatch` | 最新APで各1464行に値あり。CS専用試験は未実施 |
| AP信管諸元 | `detonatorDelay/detonatorThreshold` | 最新APで各1464行に値あり。信管挙動の実証は別問題 |
| 形式・契約バージョン | `schema/apiVersion` | 実機確認。1 / 1.0 |
| mod識別・版 | `meta.mod.name/version` | 実機確認。最新0.3.1-map-motion |
| 戦闘識別 | `battleId` | state/meta照合が必要。実ID到着時の昇格を許容 |
| 戦闘中/時刻 | `active/ts` | 実機確認。tsはゲーム開始由来、Unix時刻ではない |
| 戦闘種別/モード | `meta.battleType/gameMode` | 実機で値あり |
| 自プレイヤー識別 | `meta.selfPlayerId` | 実機取得済み。self.playerIdと照合可能 |
| 約10Hz収集 | `state.json`上書き | 実機継続更新。全tick保存や一定間隔を保証しない |
| 終了フレーム | `active:false`等の軽量形 | 実機確認。ただしUI退出成功とは別の判定 |
| 欠損/半書き/更新停止 | null・status・読取再試行 | 記録ツールは正常なJSONだけ保存し、更新停止を警告する |

`serviceId/instanceId/seq/availability/capabilities/objects/bounds`等の
元プロジェクト外部サーバー用の包みは、現modのstate契約には追加していない。
metaとstateは別ファイルなので、異なるbattleIdが一時的に見える場合は合成しない。

## 直近の優先順位

1. 簡易2D表示で船・魚雷・向き・座標軸の目視照合。
2. 失探/再発見/撃沈、画面外、敵・僚艦魚雷、複数本、12対12での欠損と鮮度確認。
3. 他地図での較正と、停止/旋回など異なる移動条件の確認。
4. 装填・ping対象/残時間・残り射程等の取得経路調査。推測値で欠損を隠さない。
