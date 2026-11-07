# B49 味方判別・self.position 欠測 根因調査（0.3.42）

**調査範囲**：`recordings/without-atm-b49.jsonl`（0.3.42-launch-restricted-builtins、1,058 state）および `recordings/without-atm-b48.jsonl`（0.3.40-radius-l5、897 active state）のオフライン解析。

**禁止事項の遵守**：runtime ソース変更、導入、ゲーム／recorder 操作、commit/push は行わない。生の battle ID・player ID・vehicle ID・owner ID・座標は公開しない。本資料に掲載する数値は匿名集計値のみである。

## 1. 調査対象

- **原因 1**：`owner.isPlayer` が全行 `None` のため、自艦魚雷の `isOwn=True` 検出が成立せず、結果として「味方無条件 2Hz（`allyLow`）」が機能しない。
- **原因 2**：分類 tick で `self.position` が欠測し、`unknownDistanceHigh` が最大 82 本発生。B48 では `self.position` 欠測が 0 だった。

## 2. 使用ツール

- 新規：`tools/research_b49_classification_gaps.py`（匿名集計専用）。
- 既存：`tools/analyze_b49_team_budget.py`、`docs/PERFORMANCE_B49_TEAM_BUDGET_0.3.42.ja.md`。

再現コマンド（プライベート録画が存在する環境）：

```bash
python tools/research_b49_classification_gaps.py --recording recordings/without-atm-b49.jsonl
python tools/research_b49_classification_gaps.py --recording recordings/without-atm-b48.jsonl
```

## 3. 確認済み事実

### 3.1 `owner.isPlayer` が常に `None`（確認済み）

#### 3.1.1 実記録の事実

B49 の detail 行 89,546 行すべてで以下が成立した（`tools/research_b49_classification_gaps.py` 集計）。

| 項目 | 値 |
| --- | ---:|
| `owner` オブジェクト取得行 | 89,546 / 89,546 |
| `owner.isPlayer == True` | 0 |
| `owner.isPlayer == False` | 0 |
| `owner.isPlayer == None` | 89,546 |
| `owner.subtype` が非 None | 0 |
| 非 Null だった owner フィールド | `isAlive`, `isObserver`, `isBot`, `teamId` のみ |

`_fields` は `OWNER_FIELDS` に含まれるキーを常に出力する（取得失敗時も `None`）。したがって値が `None` なのは、API オブジェクトに属性が存在しないか、存在しても値が `None` であるか、読み出しに失敗したかのいずれかであり、**この記録だけでは区別できない**。

#### 3.1.2 公開 API 文書の確認

公式 Mods API 文書を 2026-11-07 に確認した。

- `battle.md` の `getTorpedoOwnerById(ownerId)` は「Returns: object Player」と記載されている。
  - URL: `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/battle.md`
  - 該当箇所：「### getTorpedoOwnerById(ownerId) … Returns … object [Player]」
- `Player.md` に列挙される属性は `teamId`, `isObserver`, `isAlive`, `isBot` のみで **`isPlayer` は含まれない**。
  - URL: `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Player.md`
  - 該当箇所：「### Athributes: - teamId - isObserver - isAlive - isBot」
- 一方、`Ship.md` は `getTorpedoOwnerById(ownerId)` を Ship オブジェクトの取得元として列挙し、属性に `isPlayer`（bool）を含む。
  - URL: `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Ship.md`
  - 該当箇所：「You can get object of this type by following functions: … `battle.getTorpedoOwnerById(ownerId)` … Athributes: … `isPlayer - bool`」

実記録の返却オブジェクトは `isObserver`/`isAlive`/`isBot`/`teamId` が非 Null であり、`isPlayer`/`subtype`/`uiId`/`name`/`playerName` は Null である。このため、**Player クラスの定義に含まれるフィールド形状とは整合するが、Ship クラスに特有の `isPlayer` フラグは取得不能**である。対象が Player オブジェクトなのか Ship オブジェクトなのか、また `isPlayer` 属性が存在しないのか値が None なのかは、本資料作成時点では未確定である。

したがって `owner.isPlayer is True` による自艦検出が一切成立しないことは確認できたが、それが「Player クラスに `isPlayer` が存在しないため」なのか「Ship クラスの `isPlayer` が `None` であるため」なのかは確定しない。

#### 3.1.3 テスト stub との整合性

既存テスト（`tests/test_team_torpedo_budget.py`, `tests/test_own_torpedo_sampling.py` 等）では stub の `getTorpedoOwnerById` が `isPlayer=True/False` を返すように実装されている。これは「取得できれば判別できる」という仮定のもとで動作確認するものであり、実ゲーム API が `isPlayer` を返さないこととの不整合を示している。

### 3.2 `self.position` 欠測は自艦沈没後に集中（確認済み）

#### 3.2.1 分類 tick 単位の集計

| 指標 | B49 S1 | B48 S2 |
| --- | ---: | ---:|
| active state 数 | 1,057 | 897 |
| 分類 tick 数 | 43 | 37 |
| context 欠測 tick 数 | 13 | 2 |
| うち較正 degenerate | 1（魚雷 0 本） | 2（魚雷 0 本） |
| うち `self.position` 欠測 | 12 | 0 |

B48 では `self.position` 欠測は発生していない。B49 で 12 tick 発生したのは、その区間で自艦位置が取得できなくなったためである。

#### 3.2.2 欠測 tick の self 状態

`tools/research_b49_classification_gaps.py` による 12 tick の内訳（匿名）：

- `isObserver` は**すべて `false`**。
- `calibrationStatus` は `available`（較正は有効）。
- `classificationReason` は `contextMissing`。
- Torpedo 本数は 140–238 本。
- `health` をサンプリングしていた tick では `health = 0.0`、すなわち**自艦が沈没済み**。
- `self` 行に `position` キーが存在しない（`self.position` 欠測）。

最初の欠測 tick（ts ≈ 403.8 s）は `health` サンプリングが非 due で `health` 不在。その後の tick で `health=0` が確認できた。これは **自艦が ts ≈ 403 s 付近に沈没し、それ以降 `getSelfPlayerShip().getPosition()` が位置を返さなくなった**ことを示唆するが、最初の欠測時刻を「死亡確定境界」とは区別する。つまり、その時刻が沈没直前か直後かは `health` サンプル間隔から直接確定しない。

#### 3.2.3 ソース経路

`Main.py` の経路は以下の通り。

1. `_build_self`（`Main.py:3161-3195`）
   - `battle.getSelfPlayerInfo()` から `id`, `teamId`, `shipGameData` を読む。
   - `battle.getSelfPlayerShip()` から `ship.getPosition()` で位置を取得。失敗時は `battle.getObserverShip()` に fallback。
   - 自艦が沈没すると `getSelfPlayerShip()` が `None`／位置を返さない可能性がある。
2. `_torpedo_sampling_context`（`Main.py:2802-2836`）
   - `self_state.get('isObserver') is not False` なら `None` を返す。
   - `self_state.get('position')` が無効／`None` なら `None` を返す。
   - 較正が `available` でなければ `None` を返す。
3. `_sampling_context` → `_sampling_distance`（`torpedo_telemetry.py:2935-2999`）
   - context が無効なら距離を `unknown` とし、`unknownDistanceHigh` が増える。

B49 では較正は有効（1 tick を除く）であり、`isObserver` も `false` だった。欠測原因は **`self.position` 取得経路の失敗、すなわち自艦沈没後の位置非供給**が最も有力である。生ワイヤで getter 失敗とオブジェクト不在を区別できないため、これは仮説に留まる。

#### 3.2.4 B48 との差分解釈

B48 では 897 active state すべてで `self.position` が取得できた。B49 で `self.position` 欠測が health=0 の期間と一致することから、**B49 の欠測は沈没後の位置非供給と整合する**。ただし、B48 は ts ≈ 4511 s から記録を開始しており、戦闘中盤以降のみを捉えている点は条件が異なる。B48 の self.position availability だけで「B48 で自艦が沈没しなかった」と確定させたり、0.3.42 の regression ではないと否定することはできない。

## 4. 未確定事項

### 4.1 `ownerId` と `vehicleId` の同一性（候補一致、未昇格）

`tools/research_b49_classification_gaps.py` の比較結果：

| 比較 | 一致数 / 対象行数 |
| --- | ---:|
| `ownerId == self.playerId` | 0 / 89,546 |
| `ownerId == ship.playerId` | 0 / 89,546 |
| `ownerId == ship.vehicleId`（同一 state の ships 一覧と比較） | 76,188 / 89,546 |

`ownerId` が `ship.vehicleId` と高頻度で一致することは、B49 1 記録における**候補一致**に過ぎない。`getTorpedoOwnerById` の doc が `battle.md` では Player、Ship.md では Ship と矛盾しているため、**namespace 契約として `ownerId == vehicleId` に昇格する根拠はない**。

特に以下は未確定である：

- `ownerId` が `vehicleId` と同一の namespace であること。
- `ownerId` が `playerId` やその他の ID と同一でないこと。
- 自艦の `vehicleId` は `ships` 一覧に出現しないため、上記比較だけでは「自艦魚雷の `ownerId` は自艦 `vehicleId` である」を直接確認できていない。

したがって `ownerId == selfVehicleId` を `isOwn=True` に使用する提案は**撤回する**。正式に文書化された API 契約、または `owner` オブジェクトと `selfPlayerInfo`/`selfPlayerShip` の文書化された識別フィールドが確認できない限り、確定判別経路は存在しない。

### 4.2 自艦死亡後の安全 HIGH 方針

B49 の `unknownDistanceHigh`（最大 82 本）は自艦沈没後の context 欠測によるものである。現行方針では context 欠測時に全 identity を safety HIGH とする（`torpedo_telemetry.py:3218-3265`, `3806-`）。これは mod の目的（魚雷警告）から安全側だが、死亡後は自艦が関与しないため負荷を増やす。lower-risk な代案（例：死亡／観戦検出時は全魚雷を LOW 扱い）については、runtime 変更を伴う方針決定が必要である。

## 5. 推奨最小修正

### 5.1 自艦魚雷識別：現状維持（unknown / safety-HIGH）

`owner.isPlayer` に依存した自艦検出は、本調査で信頼できる根拠が得られなかった。`ownerId == selfVehicleId` による推論も、namespace 契約未確認のため `isOwn` への昇格は行わない。

基本案：

- `isOwn` は**明示的に unknown** とする。
- `owner.isPlayer is True` の読み取りは後方互換のため残してもよいが、自艦判定の主要根拠にはしない。
- 同一チームかつ `isPlayer` が確認できない魚雷は、現行通り safety HIGH の対象とする。

今後の調査（runtime 変更禁止の範囲外）で、公式 API の `ownerId` 契約、`Player`/`Ship` オブジェクトの識別フィールド、または `getSelfPlayerShip()`/`getSelfPlayerInfo()` から取得できる自艦 ID と `ownerId` の比較が明確になった場合にのみ、`isOwn` 判定の再検討が可能である。

### 5.2 `self.position` 欠測時（推奨：現状維持）

- 自艦沈没・観戦により位置が取得できない場合、**履歴位置や推定位置を現在値として使う修正は禁止**されている（`DEVELOPMENT.md`）。
- 現行の safety HIGH（context 欠測時は全 identity HIGH）は、鮮度情報を `classification.selfPositionStatus` / `classification.reason` で明示している。安全側を維持するなら現状が最も安全。
- 負荷削減を優先する場合のみ、死亡／観戦検出時に全魚雷を LOW とする方針変更が考えられるが、これは mod 目的と tradeoff があり、runtime 変更を伴う方針決定が必要である。

## 6. strict `ownerTeamId`/`self.teamId` 集計

`tools/research_b49_classification_gaps.py` で追加した strict チーム比較の結果：

### B49

| チーム分類 | detail 行数 / 89,546 |
| --- | ---:|
| `sameTeam`（ownerTeamId == self.teamId） | 62,020 |
| `enemyTeam`（ownerTeamId != self.teamId） | 27,526 |
| `unknownTeam`（いずれかが None） | 0 |

### B48

| チーム分類 | detail 行数 / 47,135 |
| --- | ---:|
| `sameTeam`（ownerTeamId == self.teamId） | 27,902 |
| `enemyTeam`（ownerTeamId != self.teamId） | 19,233 |
| `unknownTeam`（いずれかが None） | 0 |

この集計は `isOwn` 確定には使えない（sameTeam 中に自艦魚雷と味方魚雷が混在する）。ただし、safety HIGH 内訳の理解の足しになる。再現コマンドは 2 節を参照。

## 7. 根拠：ファイル・行番号・匿名件数

| 根拠 | ファイル:行 | 内容 |
| --- | --- | --- |
| owner 読み取りフィールド | `torpedo_telemetry.py:21` | `OWNER_FIELDS` に `isPlayer` を含む |
| owner 取得 | `torpedo_telemetry.py:4087-4094` | `getTorpedoOwnerById` 呼び出し、`_fields(owner, OWNER_FIELDS)` |
| isOwn 判定 | `torpedo_telemetry.py:2919-2922`, `4094-4096` | `owner.isPlayer` の厳密 bool 値のみ `isOwn` に使用 |
| safety HIGH 政策 | `torpedo_telemetry.py:3422-3438`, `3218-3265` | context loss / unknown team / unknown isPlayer 時の safety HIGH |
| Player 文書（isPlayer なし） | `wgmods/Mods-API-Documentation/Classes/Player.md`（2026-11-07） | 属性は `teamId`, `isObserver`, `isAlive`, `isBot` のみ |
| Ship 文書（isPlayer あり） | `wgmods/Mods-API-Documentation/Classes/Ship.md`（2026-11-07） | `getTorpedoOwnerById` を Ship 取得元として列挙、`isPlayer` 属性あり |
| battle.md | `wgmods/Mods-API-Documentation/battle.md`（2026-11-07） | `getTorpedoOwnerById` の Returns を Player と記載 |
| self 構築 | `Main.py:3161-3195` | `getSelfPlayerShip().getPosition()` → observer fallback |
| context 構築 | `Main.py:2802-2836` | `isObserver`/`position`/`calibration` 検証 |
| B49 件数 | `tools/research_b49_classification_gaps.py` | detail 行 89,546、`isPlayer=None` 89,546、`ownerId==ship.vehicleId` 76,188 |
| B49 self.position | 同上 | active state 1,057 中 287 で `self.position` 欠測、うち分類 tick 12 で context 欠測 |
| B48 self.position | 同上 | active state 897 すべてで `self.position` 取得可、分類 tick context 欠測 2（degenerate、魚雷 0） |
| strict team class | `tools/research_b49_classification_gaps.py` | `ownerTeamId` と `self.teamId` の厳密比較による `sameTeam`/`enemyTeam`/`unknownTeam` |

## 8. テスト

- 新規 `tools/research_b49_classification_gaps.py` を B49/B48 両記録で実行し、上記集計が再現できた。
- テスト `tests/test_research_b49_classification_gaps.py` により、匿名化・self.position 欠測検出・owner フィールド集計・strict team class の基本動作を synthetic fixture で確認する。
