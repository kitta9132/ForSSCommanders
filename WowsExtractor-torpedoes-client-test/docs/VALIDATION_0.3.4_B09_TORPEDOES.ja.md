# 0.3.4 実機記録：without-atm-b09 魚雷

対象：`recordings/without-atm-b09.jsonl`。Python標準ライブラリでJSONLを逐次解析し、個人名・戦闘ID・実IDは文書へ転記していない。IDの個体数は本記録内の非null値のdistinct数のみを記載する。全2,383行（state 2,381、meta 2）、JSON解析失敗0。stateの `observedAt` は2026-10-31 23:45:28〜23:53:20 UTC。以下はログ記録上の観測で、画面操作の独立証明ではない。

## 魚雷取得の開始・終了と件数

| 観測 | 結果 |
|---|---|
| state中の取得状態 | `available=true/status=available` 2,379件。各フレームでAPI一覧取得成功。unsupportedは0件 |
| inactive state | 2件とも `available=false/status=unknown`。記録冒頭の非戦闘stateと末尾の終了state。取得失敗を正常な空一覧とは数えない |
| 魚雷行／正常空 | 580行、580フレーム。各フレーム1行で複数行の同時出現なし。残り1,799 active framesは取得成功の空配列 |
| 最初の出現 | state index 1357、`observedAt` 23:51:35.246 UTC |
| 最後の出現 | state index 1936、`observedAt` 23:52:34.960 UTC |
| 最初から最後まで | 約59.7秒。次フレームで正常取得された空配列となり、その後の記録でも魚雷行なし |

冒頭・終了の `unknown` は仕様どおりの終了/非active形で、成功した空取得とは区別する。魚雷行が一覧から消えたことは観測できるが、命中・消滅・寿命満了などの理由はこのログから判定できない。

## 取得できた魚雷属性

- `uiId`、`ownerId`、`shotId` は全580行で非null、各フィールドのdistinct数は本記録内で1。実値は掲載しない。これらは別名前空間の値であり、相互joinやプレイヤーID／艦船IDへの読み替えはしない。
- 全行 `ownerType=Cruiser`、`ownerTeamId=0`、`relation=1`、`type=normal`。relationは実装仕様上の自艦チームとの比較で味方を表す。この値だけで発射操作の主体や対象艦を特定しない。
- owner lookupの返却は全580行でobject。`owner.teamId` は全行取得、`owner.isAlive=true`、`owner.isBot=false`、`owner.isObserver=false`。一方 `owner.isPlayer` と `owner.uiId` は全行nullで、`isOwn` も全行null（unknown）。`ownerId`の一致だけからプレイヤー／自艦の識別を一般化しない。
- `type=normal` はAPI値の記録にすぎず、誘導不能という意味には解釈しない。

## 位置・運動・地図較正

- `position` は580行すべてでXYZ取得。記録値の軸別範囲はX −293.30〜−272.36、Y −0.14（一定）、Z 9.64〜340.19。APIのワールド座標をそのまま集計し、単位の確定やメートル換算はしていない。Yを深度と断定しない。
- motionは初回1行が未算出、残る579行で差分値あり。`horizontalSpeed` は約5.07〜6.04 `game_world_units_per_second`。追跡区間の最大 `observedAge` は約59.69、最大 `observedDistance` は約331.21ゲーム座標単位。推定差分値であって、実m/s・ノット・最大射程・全航続距離ではない。
- `mapPosition` は全580行null、`mapPositionStatus=unknown`、sourceなし。diagの較正はactive中2,379件すべて `collecting`、reasonは `insufficient_samples`、`sampleCount=1`。較正係数の成立・地図座標変換は確認できず、変換エラー発生とも判定しない。

## UI状態とユーザー操作との照合

- active中の `uiTorpedoProbe` は2,379件で `status=available`。580行すべて `uiState.matchStatus=exactUiId`、`uiType=normal`。ただし `homingStatus`／`spottedStatus` は全行unknown、各bool値はnull。UIのcollection/key候補を読めたことと誘導・発見状態を読めたことは別である。sourceは診断用UI経路、producerはunknownで、ゲーム生値やATMの有無を証明しない。
- 報告された操作順は「8:00で魚雷選択 → 7:40で発射 → 6:00で装填完了」。選択から発射まで20秒という申告と、後に魚雷行が現れたことは大枠では矛盾しない。しかしstateの `ts` は残り時間との変換根拠がなく、操作時刻を対応付ける画面録画やイベント記録もない。したがって、選択の成功、出現行が申告した発射そのものか、装填完了との因果はJSONLだけでは確認できない。`weaponHubProbe`／兵装と再装填の詳しい突合は別検証記録の担当範囲とする。
- 一覧の580行は観測フレーム数であって、総発射本数ではない。ひとつの `shotId`/`uiId` が1本の射出を独立に証明するとの一般化や、他namespaceとのjoinはしない。

## 結論・次に必要な試験

**確認できた範囲：** 戦闘中のAPI一覧取得、単一魚雷行の連続取得と正常空一覧への遷移、公開属性・owner lookupの一部、positionおよび推定motion、UIの同一 `uiId` 候補一致。**未確認：** ownerが自艦か、誘導／被発見状態、地図較正、一覧消失理由、ユーザー操作と各値の厳密な時刻対応、選択・発射・再装填の因果。

次回は残時間表示を含む画面録画を同時に残し、選択・単発発射・装填完了の各時点を記録する。発射前後から魚雷が一覧に現れて消えるまでを収集し、画面の残時間とJSONLを同じ映像で照合する。地図変換も確認する場合は、停船／一方向直進だけにせず、独立した2D移動を加えて較正成立を確認する。現ログからenum・namespace・単位・欠落理由を推定して埋める実装変更は行わない。
