# 元仕様の各項目と取得状況

**現行の詳細対応表は [SPEC_COVERAGE_0.3.1.ja.md](SPEC_COVERAGE_0.3.1.ja.md)。**
以下は開発途中の記録を含む履歴であり、最新判定は上記の表を優先する。

2026-11-01時点。元の `OUTPUT_SPEC.ja.md` と `DESIGN.ja.md` の項目に対応。
実機根拠はbuild 13357625のb01～b03、b06、b07、およびwith-atm-b01～b03。
破棄対象b04・b05は根拠に含めない。
0.2.3のisSpotted追加は実装・オフライン確認段階で、実機未確認。

## 0.3.0で追加した範囲（実機未確認）

0.3.0の初回実機試験は初期22フレーム後に収集エラーで停止。
地図較正・魚雷motionは未判定。selfSystemsの消耗品状態とソナー情報は値を確認できた。
0.3.1で修正、詳細はMAP_MOTION.ja.mdを参照。

### 0.3.1実機確認

2026-11-01 01:04～01:07頃の対象戦闘、1576 activeフレーム、終了フレームあり。
起動ログは0.3.1、当該起動以降のWowsExtractorエラー0件。
約78.7秒で移動履歴較正が成立し、その後813フレーム継続、driftStreak=0。
8隻の他艦について計6504行のworld位置を地図座標から補助変換した。
これは独立した3D位置の取得ではない。地図マーカー鮮度・他地図の検証は残る。
係数採用時の検証誤差holdoutRmse約0.0656ゲーム座標単位。
通常魚雷1本374フレームで地図座標が出力され、373フレームで差分運動値あり。
ATM isSpotted=trueを80フレーム取得、残り294フレームはunknown（falseではない）。
同じ80フレームでisHoming=falseを取得。isSpotted=falseはこの試験では未観測。
消耗品状態とソナー状態も1576フレームで取得成功。

記録名の再利用に注意：この試験のファイルは作業ルートrecordings/with-atm-b04.jsonl。
過去のdiscardedにある同名記録とは別物で、mod.versionと対象戦闘・時刻で区別する。

- `torpedoes[].uiState`：UI診断からID一意一致でisHoming/isSpottedを各魚雷へ対応付け。
- `torpedoes[].motion`：差分速度・航向、連続観測区間の時間・移動距離。
  ゲーム座標単位の推定値で、ノットや残り射程ではない。
- 自艦等の移動履歴から地図較正し、他艦のworld位置と魚雷の地図座標を補助変換。
- `positionSource` / `lastPositionSource` / 地図座標の未検証鮮度ラベル。
- `diag.positionReads`：world取得経路の失敗分類。
- `selfSystems`：自艦消耗品のicon/num/currentState/endTimeと、
  レーダー・ソナー・潜水艦探知装置のdistShip/state/workTimeLeftを追加。
  実機未確認で、ping区画タイマーや魚雷再装填時間ではない。

以下の一覧は元仕様と実機確認済み状態を中心とする。新規項目の詳細は
[MAP_MOTION.ja.md](MAP_MOTION.ja.md)を参照。

## 魚雷

| 元仕様の項目 | 現状 | 注意・残作業 |
| --- | --- | --- |
| uiId / shotId | 実機取得済み、飛翔中安定 | 複数本の同時斉射でshotId共有は未検証 |
| ownerId / ownerTeamId / ownerType | 実機取得済み | ownerIdとplayerId/vehicleIdの一般的同一性は未確定 |
| type | 実機取得済み | normal/acoustic/magnetic、復帰・再変化を観測。誘導中とは独立 |
| position [x,y,z] | 実機取得済み | 有限値・移動を確認。メートル換算、yの深度換算は未検証 |
| relation | 実機取得済み | 敵魚雷・僚艦魚雷の試験は未実施 |
| owner.teamId / isObserver / isAlive / isBot | 実機で値あり | 発射元オブジェクトの種類に依存 |
| owner.uiId / isPlayer / subtype / name / playerName | フィールドはあるがnullを観測 | 推測で埋めない |
| isOwn | nullを観測、判定未成立 | owner.isPlayerだけを読む旧実装。名前空間・意味の検証が必要 |
| torpedoStatus | 実機取得済み | availableと正常な空配列、終了時unknownを区別 |
| UI側type / エンティティID | 0.2.2で実機取得済み | 試験した魚雷では全フレームAPI uiId/typeと一致。全ケース保証ではない |
| isHoming | ATMありで実機取得済み | 診断枠uiTorpedoProbe内。true/false/nullを区別。停止・再誘導を観測 |
| isSpotted | 0.2.3で抽出追加、実機未確認 | ATM dataにキーが存在することは実測済み。被発見表示用のATM判定で、サーバー確定検出ではない |
| 誘導先ID / ping対象・命中区画 | 未取得・未実装 | typeや距離から決めつけない |
| ping残時間・開始/命中/失効時刻 | 未取得・未実装 | 操作の申告と状態変化時刻だけでは厳密なタイマーにならない |
| 誘導停止距離・停止理由 | 未取得・未実装 | 距離制限と期限切れは観測上の候補。確定理由フィールドにしない |
| 魚雷の速度 / 航向 | 未算出 | 座標差分から推定可能だが単位・時刻の検証が先 |
| 最大射程 / 残存射程 / 寿命 | 未取得・未実装 | ammoParamsが空。未観測の発射位置から推測しない |
| 命中/消滅理由 | 直接判定未実装 | 一覧からの消滅は観測可能。命中・射程切れ等は同義ではない |

isHoming/isSpottedの取得経路は `ui.mods_DataComponent`。
ATM無効ではisHoming未供給を観測した。isSpottedも欠損時はnullとする。
共通UIデータ領域なのでフィールドだけから供給者を証明できるわけではなく、
試験構成上ATM由来として区別する。ゲーム生フラグと表記しない。

## 自艦魚雷兵装

| 元仕様の項目 | 現状 | 注意・残作業 |
| --- | --- | --- |
| modules / modulesStatus | 実機取得済み | MinotaurおよびUndineの発射管情報あり |
| 各管type / currentHP / maxHP / state / position | 実機取得済み | 故障・破壊時の変化は未試験 |
| critTimer | nullを観測 | 故障関連。再装填時間ではない |
| selectedAmmoId / selectedAmmoStatus | 実機取得済み | 異なる魚雷弾種への切替試験は未実施 |
| ammoParams / ammoParamsStatus | availableだが{} | 取得成功フラグは速度・射程の取得成功を意味しない |
| 装填残数 / 管別再装填残時間 | 未取得・未実装 | modulesのHP等からは補完不可 |

## 自艦・他艦・地図・共通情報

| 元仕様の項目 | 現状 | 注意・残作業 |
| --- | --- | --- |
| self playerId/teamId/position/yaw/speed/health/maxHealth | 最新実機記録に値あり | speed/yawの単位・座標規約は外部マップ用に検証が必要 |
| self isObserver/isVisible/isShipVisible | 最新実機記録に値あり | 観戦状態への切替は未試験 |
| ships識別・艦種・HP・yaw・可視状態 | 最新実機記録に値あり | 状態の意味・敵艦HP変化の厳密検証は別途必要 |
| ships.position | 自艦は取得、他艦はnullを観測 | 最新試験の代表フレームでは9隻中1隻のみ。全艦のワールド位置取得済みとはいえない |
| ships.nx / ny | 最新実機記録に値あり | 他艦の2D地図座標候補。画面上位置との一致・軸・スケールは未検証 |
| 最終目撃lastPosition等 | 実装あり、今回の試験では未検証 | 発見→未発見・撃沈での専用テストが必要 |
| mapの名前/パス/ID | 実機取得済み | 試験した地図に限定 |
| mapのwidth/height/worldSize/bounds等 | 最新記録では未取得 | 地図情報の全候補が埋まるわけではない |
| diag.mapCalib / mapSamples | null / 1を観測 | ワールド→地図の較正未成立。外部マップの重要な残課題 |
| diag艦数/可視数/uiHealth | 出力あり | 診断値。座標の正確性を保証しない |
| meta.roster艦名/艦種/tier/team等 | 実機取得済み | 個人名・IDが含まれるため記録共有に注意 |
| roster.consumables title/abilityId/params | 実機で値あり | 動的残回数/クールダウンを取得したという意味ではない |
| damage inflicted/received/teamTotal | 出力・変化あり | 魚雷専用の戦果ではない。命中イベントの確定判定に流用しない |
| ballistics砲弾各値 | 実装あり、潜水艦試験ではavailable:false | 魚雷パラメーターではない。今回の取得成功には含めない |
| schema/apiVersion/battleId/active/ts/mod.version | 実機取得済み | tsはゲーム由来時刻。battleIdの途中昇格は許容 |
| 約10Hz収集・終了フレーム | 実機確認済み | 全tick保存の保証なし。0.2.1以降の開始時保存修正は2戦確認済み |

## 次の優先事項

1. isSpottedの実機読取りと意味の検証、UI診断枠から正式な魚雷出力への整理。
2. 他艦/敵魚雷の取得と所有者対応、画面外・未発見での欠損の確認。
3. 地図較正と他艦2D座標の検証（外部マップの土台）。
4. 魚雷兵装・pingタイマー・停止距離等の取得経路調査。
