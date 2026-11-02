# ID名前空間候補の再検証（B10/B12/B14/B27）

正本コピー先：[正本リポジトリ内の調査Doc](../WowsExtractor-torpedoes-client-test/docs/RESEARCH_ID_NAMESPACE_CANDIDATES.ja.md)。正本側はこのルート資料の複製で、内容は同一です（相互リンクのみ追加）。

## 0. 目的と変更範囲

- DSFF復帰レビューで提示された次の主張を、正本 `WowsExtractor-torpedoes-client-test/` の既存JSONLで再検証する。
  - B10/B12/B14の魚雷2014行で `ownerId == ships[].vehicleId`、そのshipの `playerId == self.playerId`。
  - B04の5,676行でも同じ一致（ただし複数versionの集約ファイル）。
  - B27のWaveHit 439行で `targetID == 敵ship.vehicleId`。
- 本書は**一致候補**の再検証であり、API契約・名前空間の確定ではない。
- ソース、tests、TASKS、既存docsは変更していない。実機起動・新規記録もない。追加したのは本ファイルのみ。
- ID実値、player名、battleId、vehicleId、targetID、uiId、shotIdの実値は記載しない。数値は件数・型・状態だけを扱う。
- ファイル名の再利用に注意する。`with-atm-b04.jsonl` は複数versionの集約で、`discarded/without-atm-b04.jsonl` は別内容の除外対象。どちらも主証拠にしない。

対象ファイル（すべて読み取りのみ）:

| 記録 | ファイル | mod version | 位置づけ |
|---|---|---|---|
| B10 | `recordings/without-atm-b10.jsonl` | `0.3.5-context-clock-diagnostics` | 主検証 |
| B12 | `recordings/without-atm-b12.jsonl` | `0.3.7-collection-observations` | 主検証 |
| B14 | `recordings/without-atm-b14.jsonl` | `0.3.8-gun-reload-diagnostics` | 主検証 |
| B27 | `recordings/without-atm-b27.jsonl` | `0.3.12-collection-compat` | 主検証（WaveHit） |
| B04 | `recordings/with-atm-b04.jsonl` | 0.2.3 / 0.3.0 / 0.3.1×2 / 0.3.2 | 参考。主証拠にしない |
| 旧B04 | `recordings/discarded/without-atm-b04.jsonl` | `0.2.0-torpedoes` | 既存docsで除外済み。使わない |

## 1. 検証方法

- Python標準 `json` でJSONLを1行ずつストリーム解析した。全ファイルでJSON parse errorは0。
- 「厳密一致」は次をすべて満たす場合だけ数えた。
  - 同じstate内の `torpedoes[]`（または `waveHitProbe.rows[]`）と `ships[]` を比較する。
  - `type(value) is int` を両側で要求する。`bool`、`float`、`str`、`None` は一致扱いしない。型変換もしない。
  - `ships[].vehicleId` が同じsnapshot内で一意に1行だけ一致する。
  - 魚雷側は、そのshipの `playerId` が `self.playerId` と厳密int一致するかも別に数える。
- 行の分母は「その配列に行があるstate」に限る。終端の `active:false` 軽量stateは、行がなければ不一致に数えない。
- 履歴・キャッシュ・前後frame・別battleのIDをまたぐjoinはしていない。
- 文字列化、大小比較、range推定、最寄り艦join、`position.y` のdepth流用はしていない。

## 2. 再検証結果

### 2.1 B10/B12/B14 魚雷 `ownerId`

| 項目 | B10 | B12 | B14 | 合計 |
|---|---:|---:|---:|---:|
| state（active / inactive） | 2,356 / 1 | 1,643 / 1 | 1,472 / 1 | 5,471 / 3 |
| 魚雷行 | 1,157 | 428 | 429 | **2,014** |
| 魚雷行があるstate | 588 | 428 | 429 | 1,445 |
| `ownerId` が厳密int | 1,157 | 428 | 429 | **2,014** |
| `ships[].vehicleId` と一意exact一致 | 1,157 | 428 | 429 | **2,014** |
| 一致0件 | 0 | 0 | 0 | **0** |
| 一致複数件 | 0 | 0 | 0 | **0** |
| 一致shipの `playerId` が `self.playerId` と厳密int一致 | 1,157 | 428 | 429 | **2,014** |
| 一致shipの `playerId` 欠測 | 0 | 0 | 0 | **0** |
| 一致shipが非self（`playerId != self.playerId`） | 0 | 0 | 0 | **0** |
| 一致shipの `relation=1` / `teamId == self.teamId` | 1,157 | 428 | 429 | **2,014** |
| snapshot内の `vehicleId` 重複 | 0 | 0 | 0 | **0** |
| `ships[].playerId` 欠測 | 0 | 0 | 0 | **0** |
| `diag` ありのstateで `diag.totalShips != len(ships)` | 0 | 0 | 0 | **0** |
| 魚雷行がinactive state | 0 | 0 | 0 | **0** |
| `isOwn` が `null` | 1,157 | 428 | 429 | **2,014** |
| `owner.isPlayer` が `null` | 1,157 | 428 | 429 | **2,014** |
| `ownerId == self.playerId` | 0 | 0 | 0 | **0** |
| `ownerId == いずれかの ships[].vehicleId` | 1,157 | 428 | 429 | **2,014** |

補足:

- 3記録は別battleで、selfの `playerId` も `vehicleId` も別。合計で3個のself vehicleId、3個の `ownerId` 候補があり、各記録内では1個ずつ。battleをまたぐ同一性は主張しない。
- 魚雷行2,014は独立発射2,014本ではない。トラック数はB10が2、B12が1、B14が1、合計4。同一魚雷の連続snapshotを延べ行として数えている。
- 全2,014行が「`ships` が1行だけのactive snapshot」に属する。つまり**self-only snapshot**での一致であり、多艦snapshotでの `ownerId` 一致ではない。
- `ownerId` は `self.playerId` とは2014/2014で一致しない。`ships[].vehicleId` とは2014/2014で一致する。この記録範囲では「playerIdではなくvehicleId側」に見える、という候補止まりである。
- `isOwn` と `owner.isPlayer` は全行 `null`。したがって、この一致から `isOwn=true` を作る根拠はない。現行のlegacy `isOwn` を上書きしてはいけない。

### 2.2 B27 WaveHit `targetID`

| 項目 | 値 |
|---|---:|
| meta / state（active / inactive） | 2 / 2,233 / 2 |
| WaveHit row | **439** |
| rowがあるsnapshot | 439 |
| WaveHitが正常空のactive snapshot | 1,794 |
| `targetID` が厳密int | 439 |
| `targetID` の `fieldStatus=available` | 439 |
| `targetID` の `fieldType=int` | 439 |
| `targetID` の `fieldReason=null` | 439 |
| distinct `targetID` | **1** |
| `ships[].vehicleId` と一意exact一致 | **439** |
| 一致0件 / 複数件 | 0 / 0 |
| 一致shipが敵（`relation=2`） | **439** |
| 一致shipの `teamId` がselfと異なる | 439 |
| 一致shipの `playerId != self.playerId` | **439** |
| 一致shipの `playerId` 欠測 | 0 |
| 一致したtarget shipのdistinct数 | 1 |
| snapshot内の `vehicleId` 重複 | 0 |
| WaveHit probe `available` / `partial=false`、collection `complete=true` / `truncated=false` | 2,233 / 2,233 / 2,233 / 2,233 |
| rowがinactive state | 0 |

補足:

- 439行は独立した439 targetではない。1個の `WaveHit` rowが439 snapshot連続で観測されたもので、`targetID` は全行同一。`hitCount` は1→2に変化するが、target自体の切替はない。
- 439行はすべて7艦snapshot内にあり、その内訳はself 1 + 敵Battleship 6。`targetID` はその6敵のうち1隻の `vehicleId` と厳密一致する。
- 1,794の正常空snapshotは「対象なし」ではなく、その時点でWaveHit rowがない正常状態。失敗や不一致に数えない。
- `targetID` は `ships[].playerId` とは439/439で一致しない。`vehicleId` とは439/439で一致する。ただしこれは値の一致であり、API上のtarget契約ではない。
- WaveHit collectionの `complete=true` はWaveHit列挙の完全性であり、**ships列挙の完全性ではない**。混同しない。

### 2.3 B04（参考。主証拠にしない）

`recordings/with-atm-b04.jsonl` は5個のmeta、4種類のmod version（0.2.3 / 0.3.0 / 0.3.1×2 / 0.3.2）を含む集約ファイルだった。

| 項目 | 値 |
|---|---:|
| meta / state（active / inactive） | 5 / 10,051 / 8 |
| 魚雷行 | **5,676** |
| 魚雷行があるstate | 2,724 |
| distinctトラック（uiId/shotId組） | 23 |
| distinct `ownerId` | 4 |
| `ownerId` が厳密int | 5,676 |
| `ships[].vehicleId` と一意exact一致 | **5,676** |
| 一致shipの `playerId == self.playerId` | 5,676 |
| 非self / 一致0 / 複数 / `vehicleId` 重複 / ship欠測 | 0 / 0 / 0 / 0 / 0 |
| `isOwn=null` / `owner.isPlayer=null` | 5,676 / 5,676 |
| 魚雷行が属するsnapshotの艦数 | 全行9艦 |
| 0.3.1区間だけの魚雷行 | 374 |

判断:

- 5,676/5,676の算術的な一致は確認できた。ただし、これは単一battle・単一versionの記録ではない。5 meta、4 version、4つの魚雷行区間（346 / 374 / 4,721 / 235行）の集約で、トラックは23。
- 既存0.3.1資料の374行と一致する区間を含む。つまり「B04の5,676」は0.3.1単独の再現ではなく、複数記録の合算。
- `recordings/discarded/without-atm-b04.jsonl` は811行・`0.2.0-torpedoes`で、既存docsのとおり根拠から除外する。
- したがってB04は `validationScope=ambiguousReusedFilename` の参考値にとどめ、**B10/B12/B14の2014行の主結論には含めない**。

### 2.4 snapshot完全性と「不一致をfalseにしない」根拠

現行collectorのships列挙は、`WowsExtractor-torpedoes-client-test/res_mods/PnFMods/WowsExtractor/Main.py` の `_build_ships` で次の形になっている。

- `ships = _try(lambda: battle.getAllShips(), []) or []`
- `diag.totalShips = len(ships)`
- ships用の `status` / `complete` / `reason` / 期待件数は出力されない。

`_try` は例外を握りつぶして `[]` を返す。したがって、列挙例外・部分列挙・正常空を、現行diagだけでは区別できない。`diag.totalShips` は「観測できた行数」であって「戦闘に存在する艦数」ではない。

B27では、roster 7に対して7艦未満のactive snapshotが実在した。

| B27 active snapshotの観測艦数 | snapshot数 |
|---|---:|
| 1艦 | 183 |
| 3艦 | 1 |
| 5艦 | 2 |
| 7艦 | 2,047 |
| 合計 | 2,233 |

- rosterは7。それでもactive 186 snapshotが7艦未満で、うち166 snapshotは記録途中の連続した1艦区間。ただし、これが「列挙漏れ」なのか「その時点で本当に7艦未満だった」のかは、現行データだけでは決められない。
- diagを持つactive stateでは `diag.totalShips == len(ships)`。つまりdiagは「7艦いるはず」と警告せず、列挙漏れと実際の艦不在を区別しない。
- 439 WaveHit rowはすべて7艦のsnapshotに属するため、今回のrow-level一致は成立している。しかし、もし同じrowが1艦区間に出ていれば、target shipがship一覧にないだけで「一致0」になり得る。これは真の不一致ではない。
- したがって、`matchStatus=uniqueExact` と `completeness=unknown` を必ず分ける。`completeness=unknown` のときの一致0は `false` / `notSameNamespace` ではなく `indeterminate` とする。

B10/B12/B14も、active snapshotはすべて1艦（selfのみ）で、rosterも1。このため2014行の一致は「self-only snapshot」という限定条件付きであり、多艦での完全性を証明しない。終端inactiveはshipsが空でselfもないが、魚雷行がないため分母に入れていない。

## 3. 一致候補とAPI契約の分離

### 3.1 今回確認できたこと

- B10/B12/B14: 2,014/2,014行で `ownerId` は同一snapshotの `ships[].vehicleId` と厳密int一致し、そのshipの `playerId` は `self.playerId` と厳密int一致した。
- B27: 439/439行で `targetID` は同一snapshotの敵ship `vehicleId` と厳密int一致した。
- いずれも重複 `vehicleId`、ship欠測、非self魚雷owner、複数一致は0。ただし対象条件が限定的。
- B04: 5,676/5,676行で同じ自己一致。ただし `with-atm-b04.jsonl` は複数versionの集約で、同名の別ファイル（`discarded/without-atm-b04.jsonl`）も存在するため主証拠にしない。

### 3.2 まだ確定していないこと

- `ownerId` がAPI契約上 `vehicleId` であること。`ownerId` が全艦・敵魚雷・僚艦魚雷・別buildでも `vehicleId` と一致する保証はない。
- `targetID` がAPI契約上 `ship.vehicleId` であること。静的定義のコメントは有力なヒントだが、join契約ではない。
- 非self魚雷の `ownerId`。B10/B12/B14は全行self-onlyで、敵/僚艦魚雷のownerは0行。
- 多艦snapshotでの魚雷owner。B10/B12/B14は全行1艦snapshot。
- battleをまたぐIDの安定性。3 battleで3個のself vehicleId/ownerId候補があり、同一IDの再利用・不変性は主張しない。
- `targetID` の複数target・target切替・失効・区画。B27は1 targetのみ。
- `isOwn`。全2,014行で `isOwn=null`、`owner.isPlayer=null`。一致候補から `isOwn` を補完しない。

### 3.3 静的定義と現行契約の扱い

- 以下は正本リポジトリ外の抽出物 `../mino-smoke/research/extracted/gui/` にある静的定義であり、`WowsExtractor-torpedoes-client-test/` には含まれない。
- `gui/data/Components.xml` の `Torpedo` は `ownerID:Integer sync=false`、`shotID:Integer sync=false`、`depth:Number sync=false`、`type:String`。`ownerID` に名前空間の説明はない。
- 同 `Components.xml` の `WaveHit.targetID` は `Integer pk=true` で、コメントは `Waved vehicle ID`。これはvehicle ID候補の静的ヒントだが、Python APIのjoin契約ではない。
- `WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md` は `ownerId` を「プレイヤーIDや艦船IDと同一とは扱わない」と明記している。
- `torpedo_telemetry.py` の `torpedoes()` は `ownerId` を `getTorpedoOwnerById` に渡すだけで、`ownerId` と `vehicleId`/`playerId` を同一視しない。`isOwn` は `owner.isPlayer` の厳密boolだけを使い、それ以外は `null` にしている。
- よって、今回の一致は**値の一致候補**であり、`OUTPUT_SPEC` の契約を変更する根拠ではない。

## 4. namespace candidate の最小将来設計

### 4.1 原則

1. 既存raw fieldは一切変更しない。`ownerId`、`targetID`、`ships[].vehicleId`、`ships[].playerId`、`self.playerId`、`isOwn` はそのまま。
2. 一致候補は別objectに分離する。`source` / `inferred` / `validationScope` を必ず持たせる。
3. `matchStatus` と `completeness` を別fieldにする。`uniqueExact` でも `completeness=unknown` はあり得る。
4. `completeness=unknown` の一致0は `false` にしない。`resolution=indeterminate` とする。
5. `candidateMatches` は配列にする。1件でも配列。複数一致は `ambiguousMultiple` とし、先頭を選ばない。
6. `targetID` から特定shipを確定する単一field（例: `targetShipId`）は出さない。候補配列だけにする。
7. `isOwn` は上書きしない。必要なら別名の `isOwnCandidate` を `status=candidate` で出すが、legacy `isOwn` へ昇格しない。
8. 同一snapshot内だけを見る。履歴・cross-battle・最寄り艦・距離joinはしない。

### 4.2 出力形（案）

将来の診断versionで、該当rowに追加する最小形。値は実IDではなく、raw fieldを参照する。

```json
{
  "identityCandidates": [
    {
      "candidateRef": "NC1",
      "source": {
        "field": "torpedoes[].ownerId",
        "rawType": "int",
        "snapshot": "sameState",
        "contractStatus": "unverified",
        "staticHint": "Components.Torpedo.ownerID:Integer(sync=false); namespace comment absent"
      },
      "match": {
        "status": "uniqueExact",
        "completeness": "unknown",
        "resolution": "candidate",
        "candidateMatches": [
          {
            "collection": "ships",
            "field": "vehicleId",
            "rawType": "int",
            "match": "exact",
            "index": "unique"
          }
        ],
        "unknownReason": "shipsCollectionCompletenessNotReported"
      },
      "inferred": {
        "namespaceCandidate": "ships.vehicleId",
        "status": "candidate",
        "basis": "sameSnapshotStrictValueEqualityOnly",
        "contractStatus": "unverified",
        "isOwnOverride": false
      },
      "validationScope": {
        "records": ["B10", "B12", "B14"],
        "rowCount": 2014,
        "trackCount": 4,
        "conditions": ["activeOnly", "selfOnly", "singleShipSnapshot"],
        "notCovered": [
          "enemyTorpedo",
          "allyTorpedo",
          "multiShipSnapshot",
          "crossBattle",
          "apiContract"
        ]
      }
    }
  ]
}
```

B27のWaveHit rowでは `source.field` を `waveHitProbe.rows[].fields.targetID`、`validationScope` を `records:["B27"]`、`rowCount:439`、`targetCount:1`、`conditions:["activeOnly","enemyTarget","sevenShipSnapshot"]`、`notCovered:["selfTarget","multipleTargets","targetSwitch","ownerId"]` とする。`inferred.namespaceCandidate` は `ships.vehicleId` のままだが、`candidateMatches` は敵shipの候補配列として出す。

### 4.3 `matchStatus` / `completeness` / `resolution`

| 観測 | `completeness` | `matchStatus` | `resolution` | 意味 |
|---|---|---|---|---|
| 厳密一致が1件 | `complete` | `uniqueExact` | `candidate` | 完全なsnapshot内の一致候補 |
| 厳密一致が1件 | `unknown` | `uniqueExact` | `candidate` | 観測範囲の一致候補。契約確定ではない |
| 厳密一致が0件 | `complete` | `noExactMatch` | `noValueMatch` | 完全なsnapshot内で値一致なし。名前空間のfalseではない |
| 厳密一致が0件 | `unknown` | `noExactMatch` | `indeterminate` | 欠測・部分列挙の可能性。falseにしない |
| 厳密一致が2件以上 | 任意 | `ambiguousMultiple` | `ambiguous` | 先頭を選ばない |
| 型不一致・欠測・inactive | 任意 | `notEvaluated` / `unknown` | `notEvaluated` | 不一致ではない |
| ships列挙自体が不明 | `unknown` | `unknown` | `indeterminate` | 比較不能 |

`completeness=complete` にできるのは、将来collectorがships列挙の `status=available`、`complete=true`、件数・重複検査を出した場合だけ。現行の `diag.totalShips` は `len(ships)` であり、completeの根拠にしない。`roster` 件数も、bot/observer/欠測を含み得るため、それだけでcompleteにしない。

### 4.4 実装時の安全条件

- `ships[].vehicleId` のindexは、全行が厳密intで、同一snapshot内に重複がない場合だけ「unique index」とする。欠測・非int・重複があれば `index=incomplete/duplicate` とし、`uniqueExact` を出さない。
- `ownerId` / `targetID` が `bool` / `float` / `str` / `null` の場合は比較しない。`int(value)` や文字列正規化をしない。
- `ships` がlistでない、欠測、空、inactive軽量stateの場合は `notEvaluated`。0件一致にしない。
- `completeness=unknown` の `noExactMatch` を `isOwn=false`、`notSameNamespace`、`noTarget` に変換しない。
- `candidateMatches` は最大件数を制限し、元rowのID実値を別fieldへ複製しない。参照は `candidateRef` とcollection/field名だけにする。
- B04のような複数meta・複数versionの集約ファイル（`with-atm-b04.jsonl`）や同名の別ファイルは `validationScope.recordIdentity="ambiguousReusedFilename"` とし、`primary=false` にする。候補の集計に混ぜない。
- 既存 `isOwn` は `owner.isPlayer` の厳密boolのみ。`identityCandidates` から `isOwn` を上書きしない。

## 5. offline fixture計画（実機なし）

次コード実装は別指示。ここでは、実機を起動せず既存JSONLの小切片または手作りJSONで検証する計画だけを示す。fixtureのIDは実値ではなく、小さな不透明整数に置換する。個人名・battleId・実IDを入れない。

| # | fixture | 期待 |
|---|---|---|
| 1 | self-onlyの魚雷row。`ownerId` が唯一のship `vehicleId` と一致し、ship `playerId == self.playerId` | `uniqueExact` / `completeness=unknown` / `candidate` / `isOwn` は元の `null` のまま |
| 2 | 7艦snapshotのWaveHit row。`targetID` が敵1艦の `vehicleId` と一致 | `uniqueExact` / `candidate` / `candidateMatches` 1件 / 単一 `targetShipId` を出さない |
| 3 | 1艦・3艦・5艦の部分snapshotにtarget rowを置く（対象shipをship一覧から除く） | `noExactMatch` / `completeness=unknown` / `indeterminate`。`false` にしない |
| 4 | 同一snapshotに同じ `vehicleId` のshipが2行 | `ambiguousMultiple` / `candidateMatches` 2件 / 先頭を選ばない |
| 5 | 一致shipの `playerId` が欠測 | `uniqueExact` だが `selfLinkStatus=unknown`。`isOwn` を補完しない |
| 6 | 一致shipの `playerId != self.playerId` | `uniqueExact` だが `scope=nonSelf`。self扱いしない |
| 7 | `ownerId` / `targetID` / `vehicleId` が `bool` / `float` / `str` / `null` | `notEvaluated` / `strictTypeRejected`。型変換しない |
| 8 | `active:false` の軽量state（ships/self/probeなし） | `notEvaluated` / `inactive`。不一致に数えない |
| 9 | 同じownerの魚雷2本、`shotId` は別（B10型） | rowごとに候補。`ownerId` でdedupeしない |
| 10 | B04集約切片（任意） | 一致しても `recordIdentity=ambiguousReusedFilename` / `primary=false`。主集計に混ぜない |

受け入れ条件:

- 上記1〜9がofflineで通り、`isOwn` の既存値が変わらない。
- `completeness=unknown` のケースで `false` が出力されない。
- `candidateMatches` が配列で、重複時に単一選択しない。
- 実機・ゲーム・新規記録を必要としない。
- 実装・テスト追加は別指示。今回はdocのみ。

## 6. 魚雷depth（別次診断候補。今回は原典と現在UI pathの確認だけ）

### 6.1 原典

- 正本リポジトリ外の `../mino-smoke/research/extracted/gui/data/Components.xml` の `Torpedo` は `id:String`、`ownerID:Integer sync=false`、`shotID:Integer sync=false`、`depth:Number sync=false`、`type:String` を定義する。
- `depth` は `Number` だが `sync=false`。Python/dataHubから取得できるか、単位・基準面・意味は、この定義だけでは確定しない。
- `ownerID` / `shotID` も `sync=false` で、API側の `ownerId` / `shotId` と綴り・対応が異なる。XML定義だけでAPI契約を確定しない。

### 6.2 現在のUI path

- 同抽出物の `gui/unbound2/pc/battle/markers/torpedo_marker.unbound` と `gui/unbound2/pc/battle/minimap/markers/torpedo_marker.unbound` は、`torpedoComponent.type` とrelationからアイコンを選ぶだけで、`depth` を読んでいない。
- 現行collectorの `torpedo_telemetry.py::ui_torpedo_probe` は `dataHub.getEntityCollections('torpedo')` のentityから `CC.torpedo.depth` を読み、`rows[].depth` として `source/status/type/raw/unit=unknown/semantics=unverified` を出す。
- `attach_ui_state` は `uiId` の一意exact一致があるときだけ `torpedoes[].uiState.depth` へコピーする。欠測・readError・重複・非一致では `unknown` を維持し、前frameの値や `position.y` で補完しない。
- testsにはdepthのfinite/nonbool、missing/readError、duplicate uiId、frame再利用なしのunit testがある。ただし実機のdepth値・単位を確認した記録ではない。

### 6.3 今回の記録での扱い

- B10/B12/B14の魚雷行2,014行には `uiState.depth` キーがない（0/2,014）。これらはdepth probe追加前のversion。
- B27は魚雷rowがない。したがって、この再検証資料に実機の魚雷depth値は存在しない。
- `position.y` をdepthとして扱わない。今回のID namespace検証にもdepthを混ぜない。魚雷depthは別次診断候補として、原典と現在UI pathの確認だけを維持する。ソース編集はしない。

## 7. 結論

- B10/B12/B14の主張は**行数・厳密型・自己一致**の範囲で再現した。
  - 魚雷2014行、`ownerId` は全行厳密int、`ships[].vehicleId` と2014/2014で一意exact、一致shipの `playerId` は `self.playerId` と2014/2014で厳密int一致。
  - 一致0、複数一致、`vehicleId` 重複、ship欠測、非self魚雷ownerはすべて0。
  - ただし全行がself-only・1艦snapshot。`isOwn` は全行 `null` のままで、上書き禁止。
- B27の主張は**439/439の値一致**として再現した。
  - `targetID` は全行厳密int、1個の敵ship `vehicleId` と439/439で一意exact、敵relation・非self playerId。
  - ただし1 targetの連続snapshotであり、targetIDのAPI join契約ではない。
- B04の5,676一致は算術的には確認したが、`recordings/with-atm-b04.jsonl` は5 meta・4 version・23 trackの集約で、単一battleの再現ではない。同名の別ファイル `recordings/discarded/without-atm-b04.jsonl`（811行、`0.2.0-torpedoes`）は既存docsどおり除外する。いずれも主証拠にしない。
- 現行ships列挙は `getAllShips()` の例外を `[]` に畳み、`diag.totalShips=len(ships)` しか出さない。B27ではroster 7に対して7艦未満のactive snapshotが186（うち166連続1艦）実在したが、現行diagは列挙漏れと実際の艦不在を区別できない。したがって `matchStatus=uniqueExact` と `completeness=unknown` を分離し、unknown時の一致0を `false` にしない設計が必要。
- 将来実装は、既存raw fieldとlegacy `isOwn` を変えず、`source` / `inferred` / `validationScope` 付きの `identityCandidates` を追加する最小案に留める。実装・テスト・TASKS更新は別指示。
