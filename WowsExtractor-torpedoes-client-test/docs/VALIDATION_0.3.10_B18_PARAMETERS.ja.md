# B18：tooltip parameter probe 実機確認

## 結果

2026-11-02、ユーザー報告の実機試験。Undineで戦闘開始直後に魚雷を選び、tooltipを約10秒表示した。画面表示は前回と同一（75kts / 9km）との独立目視報告。個人・戦闘・entity・parameterの実IDはこの記録に転記しない。

正本は [`recordings/without-atm-b18.jsonl`](../recordings/without-atm-b18.jsonl)。逐次JSON解析で143レコード（meta 2、state 141）、parse errorなし。解析前後でファイルサイズは19,764,236 bytesのまま。meta両方のmod versionは`0.3.10-tooltip-parameter-diagnostics`、schema 1、apiVersion 1.0。stateは139 active、2 inactive。戦闘識別の遷移が1回あり、末尾は`active=false`の軽量終了stateでprobe項目なし。解析対象state全141件の`schema`/`apiVersion`は1/1.0。

## 選択TTX（別経路）

tooltip区間の139 active stateすべてでselectionはavailable、descriptorは`torpedo`。選択variant親とleaf、およびspeed/maxDistのvalue/deltaはavailableで、TTX rawはspeed 75.0、maxDist 9.0、deltaはいずれも0。これは`selfVehicle.shipTTX`由来の静的TTX候補であり、画面値との数値整合はユーザーの独立目視報告とも一致する。

全variantを含む`ttxStatus=partial`はdeepwater/alternative variantがnoneであるため。選択`torpedo` variant/leafの失敗ではない。TTX candidateの数値一致はparameter probeの成功、補正後live値、または補正overrideが存在しないことを意味しない。

## `torpedoTooltipParameterProbe`

139 active stateすべて同じ経路結果：

| 段階 | 観測 |
| --- | --- |
| top-level | `unknown` |
| owner (`playerAvatar` singleton → `entity.id`) | `available`。owner key candidateも生成 |
| parameter component key / getter / call / collection | すべて`available` |
| parameter rows | 54行。上限64未満、`partial=false`、`truncated=false` |
| 記録時の選択結果 | `selectedParameter=unknown`, `reason=noExactMatch`（旧selector） |
| match stage | `unknown`。probe errorはなし |

各rowでcomponentと`ownerID`, `id`, `baseValue`, `currentValue`はavailable。`source`, `status`, `type`はunknown。全139 snapshotを通した7,506 row観測で、rowの`ownerID`と`playerAvatar.entity.id`は型も含むstrict scalar一致が6,394回、非一致が1,112回だった。旧selectorはGUI形式の合成keyと`parameter.id`を比較していたためmatch 0件だった。修正版selectorではB18実raw候補を再生し、139件すべてで複合PK候補を一意選択した。これは診断候補の選択であり、tooltipへの適用や画面値の因果関係を証明しない。

collectionはcompleteで上限にも到達していない。旧selectorのnoExactMatchはcollection欠落ではなくselectorの誤りだった。記録時のunknownも「補正なし」の証拠ではない。selected parameter候補のraw取得と補正overrideの適用は区別する。

## 次の作業判断

同条件の実機再試験は追加要求しない。Components.xmlの複合PK定義とB18 raw shapeに沿ってselectorを修正し、実JSONLをoffline再生した。GUI `getPrimaryEntity`内部encoding、適用時系列、namespace一般性は依然未確定であり、それらを確認する場合は別途GUIソース調査を続ける。

このP1項目では、静的TTX routeとtooltip-owner/parameter collection routeが実機で通り、記録rawのoffline再生でparameter候補を139/139件選択できた。これは実機GUI lookupやtooltipへの適用確認ではない。回帰テストはproducer→parameter probe統合で「complete singleton owner + unique strict composite PKでavailable」「no exact matchはunknown」「duplicate/partial/truncated/incompleteは選択しない」を確認する。

## 再現・解釈上の注意

- 根拠となる実装契約：[`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md)の0.3.9/0.3.10節。top status、stage status、variant/leaf statusを区別する。
- parameter probeの`available`は候補shapeと完全なraw exact matchを示す診断statusにすぎず、実GUI lookupやowner namespaceの同一性を証明しない。
- 75kts / 9kmは静的TTX候補およびユーザー目視の一致としてのみ記録。live速度、補正の有無、単位意味の一般化はしない。

## B18追補：Parameterの複合primary keyと不一致原因

### 実測shape（正本JSONLを逐次解析）

`recordings/without-atm-b18.jsonl`の139 active snapshotを逐次読みし、合計7,506 row（54 row/snapshot）を解析した。個人・戦闘・entityの生IDや他parameter名はこの文書に転記しない。

| 観測 | 結果 |
|---|---|
| component `id` | 全7,506件がavailableな文字列。全件がunderscoreなしのASCII identifier形。異なる値は49種類。 |
| `torpedoSpeed`系 | `torpedoSpeed`は139件（各snapshotに1件）、`torpedoSpeedAlt`/`torpedoSpeedDeepwater`は各0件。 |
| `ownerID` | 全7,506件がavailableな整数。`playerAvatar.entity.id`由来として記録されたowner候補とのstrict型・値一致は全rowで6,394件、不一致は1,112件。 |
| `torpedoSpeed` rowのowner | 139/139件で`ownerID`がowner候補とstrict型・値一致。 |
| 関連ID候補の型 | owner entity ID candidateは整数、GUI形式の`ownerKeyCandidate`は合成文字列、parameter entity ID candidateは整数、component `ownerID`は整数、component `id`は文字列。entity ID candidateとcomponent fieldは別物。 |
| 既存照合 | 139/139 snapshotで`component.id == owner + '_' + parameterName`は0件。`selectedParameter`は全件`noExactMatch`。 |

したがって、今回の`id`は実測上parameter名単独の文字列であり、ownerとの組は`ownerID`側に別fieldとして載る。`ownerID`の全row一致率が100%でない点は他parameter rowも含む集計である。選択対象の`torpedoSpeed` rowに限定すればowner候補との一致は139/139で、少なくともこの対象・このrecordでは両fieldの組が候補を一意に識別する。これだけで他parameter、別build、全namespaceに一般化しない。

### 静的schemaとGUI lookupの照合

抽出GUI `data/Components.xml` L1558-L1565の`Parameter`定義は、`ownerID:EntityId pk="true"`と`id:String pk="true"`の**2 propertyをprimary key**とし、`baseValue/currentValue:Number`を値fieldとして定義する。したがってstatic schema上のParameter component primary keyは`(ownerID, id)`複合であり、`id`単独ではない。今回のJSONL実測（整数ownerID + parameter名文字列id）もこの分離shapeと一致する。

一方、GUI tooltipは`getPrimaryEntity(CC.parameter, ownerEntityId + '_' + parameterName)`へ一つの合成文字列を渡す（既述のGUI参照経路参照）。これはGUI API呼び出し側のkey表現であり、componentの`id` propertyそのものがその合成文字列だという意味ではない。Component XMLはPK fieldを示すが、合成文字列を内部で`(ownerID,id)`へどうencode/decodeするかまでは定義しない。抽出root内で限定検索した範囲では、別のgenerated collection schemaまたはその変換規則を裏付ける定義は見つからなかった。従ってGUI keyの区切り表現・Python entity primary keyへの変換は引き続き未確定。

### 判定と最小修正案（今回は実装変更なし）

旧probeはGUIの合成key候補全体を`component.id`と比較していた。B18ではrowの`id`がparameter名だけなので一致せず、全snapshotが`noExactMatch`となった。これは実測shapeおよび明示PK定義に照らした**単一id lookupと複合PKを混同した選択判定の欠陥**である。owner候補生成・collection取得・TTX経路の失敗ではない。

修正selectorは完全なcollection内で`component.id == parameterName`かつ`component.ownerID == ownerEntityId`を型込みstrict比較し、組の一致がちょうど1件のときだけ`selectedParameter.available`とする。GUI形式の`ownerKeyCandidate`は診断metadataとして保持するが、component `id`の期待値やfallbackには使わない。ID/ownerのどちらかが欠測・不正・truncatedならcollectionをincompleteとしてunknown、partial/truncated collectionや複合PK重複もunknown。両fieldがavailableかつ有効で候補と値不一致のrowだけ除外し、未知fieldを持つrowは除外しない。値fieldも数値・有限・範囲内を要求する。`matchBasis`は2fieldのraw複合PK候補一致を示すだけで、GUI APIの再現ではない。

### オフラインfixtureと確認方針

回帰fixtureは生記録のコピーでなく、匿名化したsnapshot形で作成できる。ownerには合成整数、対象rowには同値の整数`ownerID`と文字列`id="torpedoSpeed"`、数値`baseValue/currentValue`を置き、残り53 rowは異なるparameter名またはownerのdecoyとする。加えて一致0件、同名別owner、同owner別名、複合PK重複、欠field、partial/truncatedの各ケースを作れば、選択一意性とunknown条件を再生できる。生ID・player名をfixtureに含めない。

修正後の実selectorをB18 JSONLの139 active snapshotでoffline再生した。全139件が`available`、選択値はbase/currentとも75.0、別経路のTTX speed 75.0との差はbase/currentとも0.0。個人IDは文書へ掲載しない。この再生は記録済みraw候補に対するselector回帰確認であり、GUI `getPrimaryEntity`実行・tooltip overrideの表示反映・画面値との因果関係を証明するものではない。GUIの目視表示75ktsとも数値上整合するが、表示経路の同一性は未確認。

**残る不明点：** GUI合成keyから複合PKへの実際のencoding、`EntityId`とPython側owner scalarのnamespace同一性の一般保証、他variant/buildのrow分布、Parameter値がGUI表示へ反映される時系列。この追補はshape・schema・選択判定の根拠を記録するもので、補正後speedの確定ではない。

## 実装追補（0.3.11）

上記B18実機JSONLは0.3.10 selectorの記録であり、全139 stateの`noExactMatch`は当時の実機出力の事実として保持する。修正selectorは`(ownerID, id)`の型込みstrict一致に変更し、**同じB18 raw JSONLをofflineで再生して139/139件を一意選択**することを確認した。これは修正版を実機で動かした結果ではなく、GUI lookup/tooltip適用の確認でもない。0.3.10の実機再試験は不要とし、次の実機試験は潜水艦probeの短時間確認へ進む。
