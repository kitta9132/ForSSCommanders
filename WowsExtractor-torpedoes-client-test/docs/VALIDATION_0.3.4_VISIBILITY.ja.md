# 0.3.4 実機可視性記録の突合

記録: `recordings/without-atm-b08.jsonl`（28,285,904 bytes）。旧日付フォルダー側の記録ではなく、現行 `WowsExtractor-torpedoes-client-test/` のファイルをPython標準ライブラリのJSONパーサーで全行集計した。個人名、player/vehicle/ui ID、戦闘IDはこの文書に記載しない。個体は同一記録内で一貫する仮ラベルで表す。

## 記録同定

- meta: mod `0.3.4-weapon-diagnostics`、schema 1、API 1.0、ATMなし。build番号はJSONL metaに見当たらず、この記録からは確認できない。
- battle type: TrainingBattle。metaとstateで同一battleIdが一貫している（値は非掲載）。roster 7隻。rosterにはKremlinに相当するvehicle params (`PRSB110_Sovetskaya_Rossiya`) が6枠あり、実行時の `ships[].name` は `KREMLIN`。そのうち4個体がこの記録のstate一覧に現れた。したがってユーザー報告の単数形だけでは対象の一個体を特定できない。
- 全2,305レコード（meta 1、state 2,304）。active=trueのstateは2,303、最後のstateはactive=falseかつships空。state `ts` は148.143〜386.262、observedAtは2026-10-31 18:08:29.050〜18:12:27.290 UTC。最後のactive=true stateは記録末尾の直前。
- `ts` はbattle内の記録値で、ゲーム画面の残り時間との換算根拠はmetaにない。したがって報告された「残時間7:30の確認」を特定のts/frameへ対応付けない。

## 対象ラベル別集計

ラベルはKREMLIN行の初出順。別個体の同定に実IDは使わず、この文書内でのみ有効。以下のframe番号はmetaを除いたstate配列の0始まりindex。

|対象|収録行 / frame範囲|mapVisible=true / false|false中の座標|false後の観測|
|---|---:|---:|---|---|
|対象A|534 / 1363–2302|518 / 16|全16行で `positionAvailable=true`、`position` と `mapPositionRaw` あり|false区間3回。各々、対象が一覧から外れた後にtrueで再出現|
|対象B|357 / 1758–2302|351 / 6|全6行で座標あり|false区間は対象Aの3回目と同一frame群。188 frame不在後、trueで再出現|
|対象C|26 / 2151–2176|21 / 5|全5行で座標あり|false後の再取得行はこの記録にない。以後の未掲載はfalseを意味しない|
|対象D|140 / 2163–2302|140 / 0|該当なし|false遷移なし|

`mapVisible=false`の遷移（tsは記録値、残り時間ではない）:

|対象|直前true|false行の範囲|trueで再出現|一覧欠落|
|---|---:|---:|---:|---|
|A|1390 / 291.400|1391–1395 / 291.504–291.915|1403 / 292.736|frame 1396–1402（7 frames）|
|A|1429 / 295.434|1430–1434 / 295.536–295.947|1646 / 317.801|frame 1435–1645（211 frames）|
|A・B|1836 / 337.638|1837–1842 / 337.745–338.277|2031 / 357.758|frame 1843–2030（188 frames）|
|C|2171 / 372.563|2172–2176 / 372.664–373.072|なし|falseの後、以降のstateでは対象Cは未掲載|

false行は一覧に掲載されている間の値である。対象が一覧から外れた区間は「未取得／未掲載」であってfalseではない。対象A/B/Cについて上記以外にも一覧から外れている時間があるが、そこから可視状態は判定していない。

## 候補statusと現行出力フィールド

KREMLIN全1,057行を合算:

- `visibility.dataHubCandidates.mapVisible`: available 1,057（true 1,030、false 27）。この実機ログで候補の値と遷移が実際に取得された。
- `dataHubCandidates.visible`: 全1,057行が `nonBoolean`, type `int`, raw `1`, reason `expectedBoolean`。bool候補としては利用できず、true/falseへ読み替えない。
- `dataHubCandidates.isVisible` / `isShipVisible`: 各1,057行すべて `missing` / `attributeMissing`。
- `shipApiCandidates.isVisible` / `isShipVisible`: 各1,057行すべて `missing` / `attributeMissing`。
- 表に出る互換 `ships[].visible` はmapVisibleの投影で、false 27行。raw `visibility.raw.visible`（整数1）とは別物。`worldVisibleSource`は `dataHub.visibility.visible` を指すが、候補statusがnonBooleanなのでworldVisibleのbool値としては解釈できない。
- 各KREMLIN行で `visibility.semantics=unverified`。`position` と `mapPositionRaw` はmapVisible=false時も保持されていた。対象が一覧にないことをfalse値や座標消失に置き換えていない。

現行 `res_mods/PnFMods/WowsExtractor/Main.py` との照合: `_build_ships` は `dataHub.visibility` の4候補を別々に診断し、候補diagnosticのbool取得と互換raw値を分ける（L1414–1435）。L1594–1613で `visible` をmapVisibleから投影し、`worldVisibleSource`はraw `visible` の取得時に設定、semanticsはunverified。L1536–1539はmapVisible=falseでもworld positionを破棄せず、較正サンプルからのみ除外する。観測されたJSONのフィールド形・値はこの実装と整合する。

## 報告との突合・判定

- 報告された煙幕使用、残時間7:30時点の確認、直接視認→盲目→直接視認の完遂、および最終目撃表示の目視確認は、操作記録・画面録画がないためJSONLだけでは独立検証できない。
- JSONLには複数個体でmapVisible true→falseがあり、一部は一覧からの欠落を挟んでtrueで再出現している。これは報告の大枠と矛盾しないが、ラベルA/B/Cのどれが報告対象かは特定できず、特定の操作との因果対応も確認できない。
- 最終目撃アイコンを表す独立フィールド／標準UI画像はこのJSONLにはない。mapVisible=false、位置保持、後の再出現だけから「最終目撃表示になった」またはサーバー発見状態が確定したとは判定しない。
- `ts`・`observedAt`はログ内時刻であり、残り時間7:30との対応はunknown。残時間表示をbattle開始時刻・tsへ換算する仮定は置かない。

## 結論と次試験

0.3.4実機でKREMLIN行のmapVisible候補取得、true/false遷移、false時の座標保持、および複数の一覧欠落後の再出現を確認した。一方、対象一個体への割当て、操作時刻との対応、UI最終目撃表示、サーバー発見状態との意味同一性は未確定。TASKSの意味検証は `[△]` のまま。

次試験は要。記録と同時に、対象を一隻に識別できる画面録画（標準ミニマップと残時間表示を含む）、操作時刻、対象ラベル対応を保存する。残時間とJSONLの対応は両方が同じ録画に写る形で取得する。最終目撃表示の確認と、味方視界のみの区間は別々に記録し、再現できない条件は未実施とする。画面証拠なしの既存JSONLを後から該当時刻へ推定対応させない。
