# B50：自艦 shipId による `isOwn` 分類の適用（0.3.44）

2026-11-07、`0.3.44-self-owner-id`、build13533378。本記録は **offline 検証と設計決定の記録**であり、新たな実機試験は行っていない。0.3.43 の B50 観測（`recordings/without-atm-b50.jsonl`）で `battle.getSelfPlayerInfo().shipId` と自艦発射魚雷の `ownerId` が全行厳密一致したことを根拠に、0.3.44 で分類に使用する。

## 根拠：0.3.43 B50 観測

- 私有記録 `recordings/without-atm-b50.jsonl`：33,305,665 bytes、645 records（meta 1、active state 643、inactive state 1）。
- SHA256：`8e9185e92f865839f1d4656ce669edbd751a6853027fb4449726a48c10a6056f`（0.3.43 観測版のまま）。
- 魚雷のある 157 active state、延べ 622 detail 行すべてで `ownerId` が `battle.getSelfPlayerInfo().shipId` と厳密一致。不一致 0 行。
- `battle.getSelfPlayerShip()._Ship__id` も同一 snapshot で `shipId` と厳密一致したが、0.3.44 では公式 ModsAPI 文書に記載のない非公開属性を分類に使わず、`battle.getSelfPlayerInfo().shipId` のみを使用する。

## 0.3.44 での変更

- `self.shipId` を毎 sample `battle.getSelfPlayerInfo().shipId` から取得し、`torpedo.ownerId` と厳密に比較。
- `isOwn` は型と値が一致するときだけ `true`、不一致なら `false`、比較不能なら `null`（unknown）。
- `owner.isPlayer` は `owner` 行に生の観測値として残すが、分類には使わない。
- sample 済み魚雷行に `isOwn`・`isOwnSource`・`isOwnReason` を追加。
- 自艦（`isOwn is True`）は全距離 HIGH、同一チームかつ `isOwn is False` の味方は全距離 LOW、敵は最近 `enemy_high_budget` 本 HIGH。不明は安全側 HIGH。

## 検証

- offline：`tests/test_self_owner_id.py`（厳密一致・型不一致・self ID 欠測）、`tests/test_own_torpedo_sampling.py`、`tests/test_team_torpedo_budget.py`、`tests/test_torpedo_high_budget_25_research.py`、`tests/test_far_torpedo_1hz_research.py`、既存 replay・cadence テストを更新して全 green。
- `tools/check_collector_offline.py` 11 module checker 成功。
- 新規実機試験は行っていない。B50 記録は 0.3.43 観測版のものであり、0.3.44 の分類版での再取得は未実施。

## 範囲と制約

- 本変更は B50 の自己発射条件での一致を根拠とする。味方魚雷混在・死亡後・再入場・異なる build での一般契約は未確認。
- `battle.getSelfPlayerInfo().shipId` が取得不能・非 scalar・型不一致の場合は `isOwn: null` とし、安全側 HIGH に留まる。
- `tools/analyze_self_id_candidates.py` の CLI 出力には battleId が含まれるため、そのまま公開しない。

## 関連

- [B50 0.3.43 観測記録](VALIDATION_B50_SELF_ID_0.3.43.ja.md)
- [出力仕様](OUTPUT_SPEC.ja.md)
- [チーム別魚雷サンプリング](TEAM_TORPEDO_BUDGET.ja.md)
