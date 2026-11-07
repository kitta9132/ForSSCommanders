# 自艦 ID と `torpedo.ownerId` の対応経路調査

**目的**: `torpedo.ownerId` が自艦を指すとき、それと対応させられる「自艦 ID」を公式 ModsAPI・既存ソース・過去記録から特定する。runtime 実装／設定変更／ゲーム操作／recorder 操作／導入／commit/push は行わず、調査・資料作成のみとする。生の player/vehicle/owner ID 値は出力せず、匿名集計に留める。

**調査日**: 2026-11-07

## 1. 結論（要約）

現時点の調査では **自艦 ID の取得候補はあるが、`torpedo.ownerId` との対応を公開契約として確定できていない**。取得経路が存在しないと証明したものではない。

- `battle.getSelfPlayerShip()` は `Ship` オブジェクトを返すが、公式文書に `id`/`vehicleId` 属性はない。`uiId` しか公開契約として使えない。
- `battle.getSelfPlayerInfo()` の `shipId` は `getPlayerByVehicleId()` の入力と対応する「vehicle ID 候補」だが、これは `PlayerInfo` 上の未文書化（あるいは文書化が不十分な）フィールドであり、公式 Ship 文書には存在しない。
- `_build_ships` で `Ship` オブジェクトから `'_Ship__id'` / `'id'` / `'vehicleId'` を読んでいるが、これは公開契約外の未文書属性。自艦 `Ship` オブジェクトでも同じ属性が同じ namespace で使えるかは保証されていない。
- 過去記録では `ownerId == ships[].vehicleId` が高頻度で一致するが、自艦は `ships` 一覧に含まれないため、**自艦魚雷の `ownerId` と自艦 `vehicleId` の直接一致は確認できていない**。
- したがって、`ownerId == selfVehicleId` による `isOwn=True` 推論は現状では実装しない。`isOwn` は引き続き `owner.isPlayer` の厳密 bool のみ、それ以外は unknown／safety HIGH とする。

## 2. 自艦 ID 取得の候補経路

### 2.1 候補一覧

| # | 取得関数 / オブジェクト | 返却型（公式文書） | 取得できる識別子 | 自艦 ID としての現状評価 |
|---|------------------------|-------------------|-----------------|------------------------|
| A | `battle.getSelfPlayerShip()` | `Ship` | `uiId`（公式）。`_Ship__id`/`id`/`vehicleId` は `_build_ships` で試行中だが非公開 | **最も有力だが未確定**。公開属性が `uiId` のみで、`ownerId` との対応は文書化されていない |
| B | `battle.getSelfPlayerInfo()` | `PlayerInfo` | `id`（playerId）、`teamId`、`shipId`、`shipGameData` | `shipId` は `getPlayerByVehicleId()` 入力＝vehicle ID 候補。ただし `PlayerInfo` のフィールド定義は公式文書に明記されておらず、gist 例に基づく |
| C | `battle.getSelfPlayer()` | `Player` | `teamId`, `isObserver`, `isAlive`, `isBot` | 識別子を持たない。自艦判定には使えない |
| D | `dataHub.getEntityCollections('selfVehicle')` の entity.id | GUI component | `entityIdCandidate` | `selfSubmarineProbe` で出力済みだが、vehicle ID や player ID との対応は未検証・未文書化 |
| E | `battle.getPlayerByVehicleId(shipId)` | `PlayerInfo` | 入力 `shipId` を vehicle ID と解釈 | `PlayerInfo.shipId` と同じ namespace 候補を示唆するが、自艦自身を指す取得経路ではない |

### 2.2 各候補の詳細

#### A. `battle.getSelfPlayerShip()`

- 公式 `battle.md` では「Returns: object [Ship]」と定義されている。
- 公式 `Ship.md` の公開属性は `uiId`, `teamId`, `isPlayer`, `subtype`, `isBot`, `name`, `playerName` のみ。`id`/`vehicleId` は**含まれていない**。
- 現行ソース `_build_ships`（`Main.py:3562-3565`）では `Ship` オブジェクトから次の順で未文書属性を読んでいる。

```python
for _name in ('_Ship__id', 'id', 'vehicleId'):
    vehId = _get(ship, _name)
    if vehId is not None:
        break
```

- このロジックは `getAllShips()` から得た他艦に対して使われている。`getSelfPlayerShip()` が返す自艦 `Ship` でも同じ属性が同じ意味で使えるかは、公式文書も過去記録も保証していない。
- 自艦の `Ship` オブジェクトは `getAllShips()` に含まれないため、`_build_ships` の識別子読み取りは自艦には適用されていない（`_build_self` は `getSelfPlayerShip()` から位置・HP・yaw 等を読むが `vehicleId` は出力しない）。

#### B. `battle.getSelfPlayerInfo()`

- 公式 `battle.md` では「Returns: PlayerInfo object」とのみ記載。`PlayerInfo` の構造は公式文書では定義されていない。
- gist `rapsealk/0e2948433f9f849966227bb4d076e1fa` の `PlayerInfo` クラスでは、`dict_["id"]` を `self.id`、`dict_["shipId"]` を `self.ship_id` として使っており、`battle.isVehicleBurning(self.ship_id)` に渡している。これは `shipId` が vehicle ID 候補であることを示唆する。
- 現行ソースでも `_remember_player_vehicle`（`Main.py:1467-1482`）では `player.shipId` を vehicle ID として `DamageTracker.remember()` に登録している。
- `_plain_player_row`（`Main.py:459-480`）では `shipId` を第一優先で vehicle ID とみなし、`vehicleId`/`vehicleID` をフォールバックとしている。
- これらは全て「vehicle ID 候補」であり、公式契約ではない。

#### C. `battle.getSelfPlayer()`

- 公式 `Player.md` の属性は `teamId`, `isObserver`, `isAlive`, `isBot` のみ。識別子を持たないため、自艦 ID 取得には使えない。

#### D. `dataHub.selfVehicle` entity ID

- `submarine_telemetry.py:self_submarine_probe()`（`submarine_telemetry.py:289-359`）では `dataHub.getEntityCollections('selfVehicle')` から自艦に相当する singleton entity を取得し、`entity.id` を `entityIdCandidate` として出力している。
- この `entity.id` が `Ship.vehicleId` や `PlayerInfo.shipId` と同じ namespace かどうかは未検証。`selfSubmarineProbe` では「candidate」と明記している。

#### E. `battle.getPlayerByVehicleId(shipId)`

- 公式 `battle.md` では入力を `shipId`、戻り値を `PlayerInfo` と定義。これは「shipId = vehicle ID」という namespace 候補の強い証拠になる。
- ただしこれは「指定 vehicle ID のプレイヤー情報を取得する関数」であり、自艦の vehicle ID を取得する経路ではない。

## 3. 公式文書・外部例の確認

### 3.1 公式 ModsAPI 文書

| 文書 | URL | 該当箇所 | 確認内容 |
|------|-----|---------|---------|
| `battle.md` | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/battle.md` | `getSelfPlayerShip()` | Returns `object [Ship]`。自艦 Ship 取得の公式経路 |
| `battle.md` | 同上 | `getSelfPlayerInfo()` | Returns `PlayerInfo object`。構造は文書化されていない |
| `battle.md` | 同上 | `getPlayerByVehicleId(shipID)` | 入力 `shipID`、Returns `PlayerInfo object`。vehicle ID 入力の存在を示唆 |
| `battle.md` | 同上 | `getTorpedoOwnerById(ownerId)` | Returns `object [Player]` と記載。`Ship.md` では Ship 取得元として列挙 |
| `Classes/Ship.md` | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Ship.md` | Athributes | `uiId`, `teamId`, `isPlayer`, `subtype`, `isBot`, `name`, `playerName`。**`id`/`vehicleId` はない** |
| `Classes/Ship.md` | 同上 | 「You can get object of this type by following functions」 | `battle.getTorpedoOwnerById(ownerId)` を Ship 取得元として列挙。`battle.md` と矛盾 |
| `Classes/Player.md` | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Player.md` | Athributes | `teamId`, `isObserver`, `isAlive`, `isBot` のみ。`isPlayer` なし |

### 3.2 外部 gist 例

- `https://gist.github.com/rapsealk/0e2948433f9f849966227bb4d076e1fa`
- `PlayerInfo` クラスで `dict_["id"]`, `dict_["teamId"]`, `dict_["shipId"]` を読み、`ship_id` を `battle.isVehicleBurning(...)` に渡している。
- これは `shipId` が vehicle ID 候補であることを示唆するが、公式契約ではない。

## 4. ソースコード上の根拠

| 根拠 | ファイル:行 | 内容 |
|------|------------|------|
| 自艦情報取得 | `Main.py:3161-3195` | `_build_self` で `battle.getSelfPlayerInfo()` から `id`/`teamId`/`shipGameData` を読み、`battle.getSelfPlayerShip()` から位置・HP・yaw を取得。`vehicleId`/`shipId` は出力しない |
| 自艦 Ship 取得 | `Main.py:3177-3191` | `getSelfPlayerShip()` → `None` 時は `getObserverShip()` fallback。位置取得失敗時の挙動を示す |
| 他艦 vehicle ID 読み取り | `Main.py:3560-3565` | `_build_ships` で `Ship` オブジェクトの `'_Ship__id'`/`'id'`/`'vehicleId'` を非公開属性として試行 |
| PlayerInfo から vehicle ID 取得 | `Main.py:1467-1482` | `_remember_player_vehicle` で `player.shipId` を vehicle ID として扱う |
| roster 行の vehicle ID 解決 | `Main.py:459-480` | `_plain_player_row` で `shipId` → `vehicleId` → `vehicleID` の順で vehicle key を解決 |
| battle 開始時の自艦 player ID | `Main.py:1316-1317` | `_selfPlayerId = battle.getSelfPlayerInfo().id`、`_remember_player_vehicle(getSelfPlayerInfo())` |
| 魚雷 owner 取得 | `torpedo_telemetry.py:4087-4096` | `getTorpedoOwnerById(ownerId)` を呼び、`_fields(owner, OWNER_FIELDS)`。`isOwn` は `owner.isPlayer` の厳密 bool のみ |
| 自艦判定の厳密 bool 化 | `torpedo_telemetry.py:2919-2922` | `_owner_is_own` で `type(value) is bool` のみ採用。整数 1 や文字列は自艦扱いしない |
| selfVehicle entity ID 取得 | `submarine_telemetry.py:324-327` | `self_submarine_probe` で `entity.id` を `entityIdCandidate` として出力 |
| identityCandidates 出力 | `Main.py:2783` | `_build_state` で `identityCandidates` を state に含める |

## 5. 過去記録による匿名検証

### 5.1 B49（0.3.42、自艦未発射・自艦不在）

`recordings/without-atm-b49.jsonl` における集計（[tools/research_b49_classification_gaps.py](../tools/research_b49_classification_gaps.py)）。

| 比較 | 一致数 / 対象行数 | 備考 |
|------|------------------|------|
| `ownerId == self.playerId` | 0 / 89,546 | この記録では一致なし。一般的な namespace 契約は未確定 |
| `ownerId == ship.playerId` | 0 / 89,546 | 同上 |
| `ownerId == ship.vehicleId`（同一 state の ships 一覧） | 76,188 / 89,546 | 高頻度で一致するが、**自艦は ships 一覧に含まれないため自艦魚雷の検証にはならない** |
| `owner.isPlayer == True` | 0 / 89,546 | 自艦検出不可 |
| `owner.isPlayer == None` | 89,546 / 89,546 | `isPlayer` 属性が取得不能または None |

### 5.2 B10/B12/B14（self-only snapshot）

`recordings/without-atm-b10.jsonl` / `b12.jsonl` / `b14.jsonl` における集計（[RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md](RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md)）。

| 項目 | 合計 |
|------|---:|
| 魚雷行 | 2,014 |
| `ownerId` が厳密 int | 2,014 |
| `ships[].vehicleId` と一意 exact 一致 | 2,014 |
| 一致 ship の `playerId == self.playerId` | 2,014 |
| `isOwn == null` / `owner.isPlayer == null` | 2,014 / 2,014 |

ただし全行が **self-only・1 艦 snapshot** であり、多艦環境や敵／僚艦魚雷は含まれない。`isOwn` は上書きしない。

### 5.3 B27（WaveHit targetID）

`recordings/without-atm-b27.jsonl` における WaveHit 集計。

| 項目 | 値 |
|------|---:|
| WaveHit row | 439 |
| `targetID` が厳密 int | 439 |
| `ships[].vehicleId` と一意 exact 一致 | 439 |
| 一致 ship が敵（`relation=2`） | 439 |

`targetID` も vehicle ID 候補と整合するが、これは WaveHit の対象 ID であり魚雷 owner ID ではない。

### 5.4 B04（参考・集約ファイル）

`recordings/with-atm-b04.jsonl` は 5 meta・4 mod version・23 track の集約ファイル。

| 項目 | 値 |
|------|---:|
| 魚雷行 | 5,676 |
| `ownerId == ships[].vehicleId` | 5,676 |
| 一致 ship の `playerId == self.playerId` | 5,676 |

算術的には一致するが、単一 battle・単一 version の再現ではないため**主証拠にはしない**。

## 6. 未確定事項・残件

| # | 未確定事項 | 影響 |
|---|-----------|------|
| 1 | `ownerId` と `vehicleId` が同一 namespace であること | 仮に一致しても、API 契約としての同一性は未確定。`isOwn` 確定の根拠にならない |
| 2 | 自艦 `Ship` オブジェクトの非公開 `id`/`vehicleId` 属性 | `_build_ships` と同じ属性が自艦でも読めるか、読めても同じ namespace か不明 |
| 3 | `PlayerInfo.shipId` が自艦 vehicle ID であること | gist・ソースから候補だが、公式文書未記載。build 間で不変かも不明 |
| 4 | `dataHub.selfVehicle.entity.id` と `vehicleId` の対応 | 潜水艦 probe での候補。対応は未検証 |
| 5 | `getTorpedoOwnerById` の返却型 | `battle.md` は Player、`Ship.md` は Ship。実記録では `isPlayer` が常に None。どちらが正しいか不明 |
| 6 | 自艦取得専用経路と `ownerId` の直接対応 | B10/B12/B14には自艦と対応するships行との一致があるが、getSelfPlayerShip/getSelfPlayerInfoから直接取得したIDとの照合は未確認 |
| 7 | 敵／僚艦魚雷の `ownerId` と `vehicleId` の契約 | B49/B48の多艦記録にも候補一致はある。既存記録の一致と一般API契約の確認を区別する |

## 7. 推奨方針

1. **`isOwn` は現状維持**: `owner.isPlayer is True`（厳密 bool）のみを自艦判定に使用し、それ以外は `null`/unknown とする。
2. **`ownerId` と vehicle/player ID の namespace 推測 join はしない**: 距離 heuristics や `ownerId == vehicleId` の候補一致を `isOwn` 確定に昇格しない。
3. **同一チームかつ `isPlayer` が確認できない魚雷は safety HIGH**: 自艦と味方を区別できないため、誤って LOW に落とさない。
4. **候補一致は `identityCandidates` として記録する**: 将来の検証用に、`source`/`inferred`/`validationScope` を付けて出力する（[RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md](RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md) の設計に従う）。
5. **新たな実機試験は依頼しない**: 現状の記録と文書調査だけで判断する。新記録が得られた場合に再検討する。

## 8. ファイル・行番号・資料一覧

| 資料 | パス / URL | 用途 |
|------|-----------|------|
| 直前研究 | [RESEARCH_B49_CLASSIFICATION_GAPS.ja.md](RESEARCH_B49_CLASSIFICATION_GAPS.ja.md) | `owner.isPlayer==None`、`ownerId==ship.vehicleId` 候補、自艦未発射の集計根拠 |
| ID namespace 候補研究 | [RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md](RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md) | B10/B12/B14/B27 の `ownerId`/`targetID` と `ships[].vehicleId` の一致候補 |
| Avatar ID 研究 | [RESEARCH_AVATAR_ID_NAMESPACE.ja.md](RESEARCH_AVATAR_ID_NAMESPACE.ja.md) | GUI `avatar.id` と API `playerId` の対応限界 |
| 出力仕様 | [OUTPUT_SPEC.ja.md](OUTPUT_SPEC.ja.md) | `self` / `ships` / `identityCandidates` / `selfSubmarineProbe` の出力契約 |
| Main.py | `../res_mods/PnFMods/WowsExtractor/Main.py:3161-3195` | `_build_self` |
| Main.py | `../res_mods/PnFMods/WowsExtractor/Main.py:3560-3621` | `_build_ships` の vehicle ID 読み取り |
| Main.py | `../res_mods/PnFMods/WowsExtractor/Main.py:1467-1482` | `_remember_player_vehicle`（`shipId` を vehicle ID として扱う） |
| Main.py | `../res_mods/PnFMods/WowsExtractor/Main.py:459-480` | `_plain_player_row`（`shipId`→`vehicleId`→`vehicleID`） |
| torpedo_telemetry.py | `../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py:4087-4096` | `getTorpedoOwnerById` 呼出しと `isOwn` 判定 |
| torpedo_telemetry.py | `../res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py:2919-2922` | `_owner_is_own`（厳密 bool のみ） |
| submarine_telemetry.py | `../res_mods/PnFMods/WowsExtractor/submarine_telemetry.py:289-359` | `self_submarine_probe`（`entityIdCandidate`） |
| 公式 battle.md | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/battle.md` | `getSelfPlayerShip`/`getSelfPlayerInfo`/`getTorpedoOwnerById` 定義 |
| 公式 Ship.md | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Ship.md` | Ship 属性（`uiId`/`isPlayer` 等） |
| 公式 Player.md | `https://github.com/wgmods/Mods-API-Documentation/blob/main/docs/PythonAPI/Classes/Player.md` | Player 属性（`isPlayer` なし） |
| gist 例 | `https://gist.github.com/rapsealk/0e2948433f9f849966227bb4d076e1fa` | `PlayerInfo.id`/`teamId`/`shipId` の使用例 |
| 集計ツール | [../tools/research_b49_classification_gaps.py](../tools/research_b49_classification_gaps.py) | B49/B48 の匿名集計 |

## 9. 変更履歴

- 2026-11-07: 初版作成。公式文書・ソース行番号・過去記録を整理し、自艦 ID 取得経路の未確定性を結論とした。
