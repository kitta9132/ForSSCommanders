# B50：自艦ID候補の実機照合

2026-11-07、`0.3.43-self-id-observation`、build13533378。既存ATM・他mod・設定を保持。Minotaurの小規模訓練戦で自己発射を依頼し、ユーザーから終了報告を受領。取得周期・isOwn判定は変更していない。

## 記録

- 私有記録 `recordings/without-atm-b50.jsonl`：33,305,665 bytes、645 records（meta 1、active state 643、inactive state 1）。ファイル名はATM不在を意味しない。
- SHA256：`8e9185e92f865839f1d4656ce669edbd751a6853027fb4449726a48c10a6056f`。
- JSON破損0行、最終stateは`active=false`。ゲーム・レコーダー停止後に保全。

## 同一stateでの厳密な型・値照合

| 自艦候補 | active stateの取得 | 魚雷のある157 stateでownerId一致 |
| --- | ---: | ---: |
| `battle.getSelfPlayerInfo().shipId` | 643/643 | 157/157 |
| `battle.getSelfPlayerShip()._Ship__id`（非公開） | 643/643 | 157/157 |
| `battle.getSelfPlayerInfo().id` | 643/643 | 0/157 |
| `battle.getSelfPlayerShip().uiId` | 643/643 | 0/157 |
| Shipの`id` / `vehicleId` | missing 643/643 | 照合不可 |

魚雷の複合識別候補は4個。延べ622 detail行すべてで`ownerId`が自艦`PlayerInfo.shipId`と厳密一致し、不一致0行。`shipId`と非公開`_Ship__id`は全643 active stateで厳密一致した。既存`isOwn`は622行すべてunknownのまま。

## 結論と範囲

このbuild・今回の自己発射試験では、`getSelfPlayerInfo().shipId`を取得でき、自艦発射魚雷の`ownerId`と直接一致することを確認した。距離heuristicや非公開属性の使用を必要としない取得候補が実測で裏付けられた。

異なるbuild・味方魚雷混在・死亡後・再入場での一般契約まで証明する結果ではない。観測版から判定版への変更は未実施であり、本試験をもって味方2Hzが修正済みとはしない。

## 解析上の注意

`tools/analyze_self_id_candidates.py`のCLI出力にはbattleIdが含まれるため、そのまま公開しない。metaをstate対象から除外した件数を`typeMismatches=1`と表示するが、これはデータ破損ではない。playerId・shipId・uiIdは別namespaceなので、全候補間の不一致集計は異常判定に使わない。上記はmetaの版と全行を別途確認した匿名集計である。
