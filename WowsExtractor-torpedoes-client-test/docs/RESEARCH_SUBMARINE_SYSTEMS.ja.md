# P1先行調査：潜水艦固有情報

調査日：2026-11-01。対象は正本 `WowsExtractor-torpedoes-client-test/` の現行0.3.4ソースと、指定されたローカルGUI抽出物の限定検索・読取。**ゲーム起動、ソース変更、抽出物の再生成、pycの実行／逆解析はしていない。** 本書は静的調査であり、実機取得や意味確定の報告ではない。

## 判定基準・出典の強さ

- **定義あり**：Python／GUI定義に候補名・参照式がある。
- **Python実装あり**：現行ソースに読取経路がある。実行時に取得できることとは別。
- **実機取得確認**：対象buildの記録で実値を確認した段階。現行版は0.3.4。本調査では潜水艦固有候補を実機記録から新たに集計していない。消耗品・探知装置の過去版の取得実績は `ACQUISITION_STATUS.ja.md` および `SPEC_COVERAGE_0.3.1.ja.md` を参照し、今回未集計であることを過去から未取得であるという意味にしない。
- **意味確定**：操作・UI・対象・時間を独立に照合できた段階。GUIラベルや値の取得だけでは確定しない。
- 指定GUI抽出物は第三者WoWSクライアントのbuild 13357625由来とするローカル調査記録（`../mino-smoke/research/FEASIBILITY.ja.md` L9-L13）を参照した。抽出物のハッシュ／再抽出は未確認で、ゲーム全体の網羅性・現在buildとの一致は保証しない。固定git revisionも確認できないため、引用は「ローカル抽出物、revision不明」とする。
- ModsAPIの公開一次資料はWG Mods-API-Documentationの固定revision `01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2`。GUI抽出物はクライアントUIの第三者抽出資料で、ModsAPI契約ではない。`res/scripts.zip` は指定build 13357625からZIP内名だけを一覧した。`scripts/ModsShell/API_v_1_0/Ship.pyc`, `dataHub.pyc`, `Ship.pyc`, `TorpedoesCommon/Components/AcousticTargeter.pyc` 等の存在を確認したが、中身は未読・未解析。

## 現行Pythonの取得経路

- `Main.py` L1212-L1227は公開battle APIの魚雷列挙、`ui_torpedo_probe`、位置差分、地図位置を組み立てる。L1232-L1249で`selfSystems`と`torpedoArmament`を出力する。潜水艦ping/深度専用の処理はない。
- 自艦データは`Main.py` L1260-L1285。`getSelfPlayerInfo().shipGameData`からhealth/maxHealth/yaw/speed等、自艦shipからposition/health/maxHealth/yawを読むが、depthやbatteryは読んでいない。L1288以降のgeneric ship positionにあるx/zからのy補完は地表用fallbackであり深度に転用不可。
- 旧`ui_torpedo_probe`は`dataHub.getEntityCollections('torpedo')`から`type`と`mods_DataComponent.data.isHoming/isSpotted`候補を読む。現行0.3.29のMain heavy pathはstate flagsを読まず、専用1Hz probeだけが固定2 flagsをsampleする（本書下部の0.3.29追記）。どちらも誘導先艦ID・ping対象・命中区画・消滅理由は取得しない。API `uiId`とGUI entity IDのnamespace同一性は一般保証ではない。
- **魚雷位置のyと魚雷深度は別候補**：現行魚雷行は公開API `position` のXYZを出力する（`torpedo_telemetry.py` L506-L535）。GUI抽出`Components.xml` L2277-L2286には別属性`Torpedo.depth:Number`があるが`sync=false`（L2279-L2281）。抽出定義からPythonアクセス可否や意味・単位を確定できない。position[1]を魚雷深度として命名せず、`depth`専用値が取れない間はunknown。
- `systems()`（`torpedo_telemetry.py` L476-L504）は自艦に対し、公開ModsAPIの`getConsumablesState`からicon/num/currentState/endTime、レーダー／水中聴音／潜水艦探知装置APIからdistShip/state/workTimeLeftを読み出す。結果は`Main.py` L1246-L1248の`selfSystems`へ出る。公開資料上のAPI経路は存在するが、endTimeの時刻基準、distShip単位、state列挙値の意味は未確定。これはping被弾状態や敵艦装置情報ではない。

## P1項目別の根拠と現在地

| 項目 | 定義・参照経路（行番号） | 現在取得／不足・安全な扱い |
|---|---|---|
| 自艦・対象艦の深度／深度差 | GUI `Components.xml` L4896-L4912に`Submarine.depthIndex/depthRanges/depth/showDepth/depthValues`。`main_hud.unbound` L67-L70は自艦entity `CC.selfVehicle.submarine.depthIndex`。`telegraph.unbound` L944-L965もdepthIndex/ranges/depthValuesを参照。敵マーカーは`markers_elements.unbound` L952-L972でsubmarine.depthとshowDepthを読む。 | 現行Python未取得。UI定義上、対象艦側の深度値も表示経路あり。ただしマーカーは`showDepth`で表示を制限し、全艦に見えるわけではない。深度差は両者の同時・同単位の直接値が得られるまでunknown。y=0補完、地図座標からの推測は禁止。 |
| 魚雷深度 | GUI `Components.xml` L2277-L2286の`Torpedo.depth:Number sync=false`。現行API魚雷行にはpositionあり（`torpedo_telemetry.py` L506-L535）が明示`depth` fieldなし。 | 定義候補あり、Python取得・実機値・意味いずれも未確認。GUIのsync=falseはPython不可の証明でも可の証明でもない。XYZのyを別名depthとして出さない。 |
| Ping対象・命中区画・一重／二重 | GUI `Components.xml` L2111-L2126の`WaveHit.targetID`（コメントはWaved vehicle ID）、lifeTime/maxLifeTime/alertTime/hitCount/isActive/weaponType。`slot_pinger_info.unbound` L3-L10は`CC.waveHit`件数とTTX maxTargetsを表示、L34-L42は件数/maxを描画。 | PythonにwaveHit列挙／取得がない。targetIDは対象IDの有力候補だが紐付け契約未確認。hitCountは一重／二重表示候補だが意味を断定しない。命中区画・具体的被弾位置の定義は上記限定検索範囲で未確認。`lifeTime/alertTime`はUIタイマー候補であり更新・失効・実残時間の意味は未確定。 |
| 誘導先・誘導停止 | GUI `Torpedo` componentの抽出定義はid/ownerID/shotID/depth/typeのみ（`Components.xml` L2277-L2286）。`torpedo_marker.unbound` L1-L13はtorpedo.typeによるアイコン分岐。0.3.29の独立probeは別経路で`isHoming/isSpotted`を候補sampleする。 | isHoming候補は誘導先ID、停止距離／地点／理由の静的根拠ではない。魚雷と最寄り艦の距離joinで誘導先を作らず、typeやisHomingから停止理由を推定しない。 |
| 魚雷消滅理由 | GUI抽出の`Torpedo` componentに消滅理由event/propertyなし（上記L2277-L2286）。現行APIは毎frameの列挙結果のみ（`torpedo_telemetry.py` L506-L535）。 | 命中・射程切れ・破壊・一覧欠落・列挙失敗は識別不能。行が消えたら「一覧から未観測／消失」だけを示し、理由をunknownとする。WaveHitイベント等を魚雷命中に直結させない。 |
| 潜航能力（battery） | GUI `Components.xml` L4914-L4929にBattery.value/burnedValue/maxCapacity/baseSpendRate/baseRegenRate/currentRate/burnRate/batteryState/isPotentiallyBurning。`submarine_battery.unbound` L49-L67は`CC.selfVehicle.battery`からvalue/rates/state読み、L66ではcountdown.endTime−timer.currentTimeを表示。`telegraph.unbound` L955-L968はbatteryState EMPTYをdepth rulerに反映。 | Python未取得。state/単位・rate符号・時間基準は未確認。GUI表示式は取得API契約ではなく、静的定数/表示既定値を欠測補完に使わない。 |
| ソナー・レーダー・潜水艦探知装置 | 公開ModsAPI `Ship` methodsと現行`systems()` L489-L503が自艦情報を読む。 | ソースに読取処理あり。個別実機値／shape／搭載なしとAPI欠落の区別、単位・state意味は現行記録では未確認。API戻り値Noneはunknown、method不在はunsupported。敵艦情報へ拡張しない。 |
| 消耗品状態・残数・endTime | 公開ModsAPI `_ConsumableState`と現行`systems()` L479-L488はicon/num/currentState/endTimeを列挙。GUI `Components.xml` L2002-L2038にはBattleConsumable.currentCharge/state/work/reload eventsがある。 | Python側に自艦の公開API取得経路あり（個別項目の実機値・単位は未確認）。`endTime`の時刻基準未確認のため`ts`との差を残秒としない。`icon`からソナー等と推定せず、搭載なし／未対応／unknownを分離。GUIのBattleConsumable componentをPython取得済みとは扱わない。 |

TTX（静的諸元）との区別：`structs/ttx.xml` L137-L147はPingerTTXのreloadTime/duration1/duration2/speed/width/maxDist/maxTargets、L151-L175は魚雷TTXのdamage/visibility/maxDist/speedと各魚雷組を定義する。これは性能表候補で、現在のping状態・被弾タイマー・実際の選択値や補正後値を示すlive telemetryではない。`slot_pinger_info.unbound` L8-L10はTTX maxTargets表示例だがPython取得契約ではない。

## 最小追加診断案（将来の別ソース変更として）

ユーザーが実機魚雷発射テスト中のため、今回の変更・導入はしない。静的確認後に別途レビューして実装する場合：

1. **selfSubmarineProbe**：`CC.selfVehicle`に存在する場合のみsubmarineとbattery componentの固定allowlist候補（深度、depthIndex/showDepth、battery value/maxCapacity/burnedValue/currentRate/baseSpendRate/burnRate/batteryState/isPotentiallyBurning）を読み、各fieldを`available/unknown/unsupported`、source、raw type付きで出す。未知オブジェクトの全属性列挙、文字列表現、y補完は禁止。
2. **waveHitProbe**：`CC.waveHit`を取得できる場合に最大32件、targetID/lifeTime/maxLifeTime/alertTime/hitCount/isActive/weaponTypeとentity ID候補だけ。targetIDを既存の艦ID名前空間と確認なしにjoinしない。命中区画候補を追加するのは一次の定義・UI参照が見つかってから。
3. **torpedo depth候補**：既存64行上限の各魚雷entityについて、`CC.torpedo` componentから明示的な`depth`だけを追加候補として読み、欠測statusを保持する。現在の行ID照合（unique exact uiId等）を保ち、距離・最寄り対象でのjoinは禁止。
4. 追加負荷上限案：新規collectionは1回の診断snapshotにつき最大32件、固定fieldのみ。深い再帰・任意`dir()`・component全列挙を避け、既存0.1秒tickに毎回重い処理を足さず1Hz程度の診断sampleに制限する（sample timestampを明示し、値の持越し／lastSeen化はしない）。出力は現行の固定JSONスナップショットだけ。実機でFPS/書込サイズ/欠落への影響を確認するまで通常出力扱いにしない。

全候補で「定義がある」「Pythonが読めた」「値が操作に応じて変化した」「意味・単位・対象を確定した」を独立管理する。欠損・例外・None・型不一致はunknown/unsupported等のstatusで残し、0、false、最寄り対象、最後に見た値で埋めない。

## 静的調査では判定できないこと

- `Components.xml`はcomponent schemaの存在根拠であって、dataHubのPython公開性／現在buildの生値／同期範囲／個体間対応を証明しない。`sync=false`もPythonから読めないことを意味しない。
- UnboundはUIがどのpropertyを表示・条件分岐に使うかの根拠。表示ロジックからサーバー内部意味、攻撃者に公開される範囲、時間単位を確定できない。
- pycはZIP内にあることだけ確認した。実装・呼出し署名・返り値・隠れたfieldは未確認。許可された範囲外の実行・依存導入・逆解析は行わない。
- 個人ログ、player/battle ID、他人の実データは本書に転記していない。

## 最小実機試験案（Minotaur／Undine）

開始条件：現在テスト中の0.3.4環境を変更しない。診断が別途実装・レビュー・導入された後に、ユーザーが通常の手順で行う。ゲームbuild、mod版、ATM有無、艦、操作時刻、画面上の状態だけ記録し、ログ共有は必要範囲を匿名化する。

1. **Minotaur（非潜水艦対照）**：既存の自艦`selfSystems`が取得できる装置・consumableを確認。ゲームUIの搭載・準備／作動／終了遷移と`num/currentState/endTime`、searchのstatus/shape/distShip/state/workTimeLeftを時刻付きで比較する。搭載なしとmissing/unsupportedを区別し、単位・endTime基準を独立照合できなければunknownのまま。Minotaur側に潜水艦UI値が無いことをAPI非存在の証明にしない。
2. **Undine（潜水艦状態）**：浮上／潜望鏡深度／深深度を各一度以上、各状態で安定保持してから移動・上昇/下降し、診断のself depth/depthIndex/battery候補を同時記録。GUI深度表示、Batteryゲージ／状態、枯渇・回復（安全に自然発生する範囲）との時系列を照合。深度表示値と数値・単位を明示比較し、深度とdepthIndexを区別する。
3. **Undine（ping→魚雷誘導）**：練習条件で対象艦を一隻だけ識別し、ping非命中→一重命中→可能なら再pingで二重状態→失効の各時刻を画面録画／メモする。続けて音響魚雷を発射し、ping前・命中後・誘導中・停止／命中・一覧消失を記録する。`waveHit.targetID`候補、hitCount/lifeTime/alertTime/isActive、torpedo uiId/shotId/ownerId/depth候補・isHoming候補を独立追跡する。誘導先はUI上の対象表示との同時対応がない限りunknown、一覧消失理由と命中区画も直接証拠がなければunknown。操作不成立・取得不可は試験失敗でなく未確認と記録。

試験では通常の既存record手順だけを使用。追加fieldを観測するまでは、そのfieldの挙動や意味を過去のJSONLから遡及評価しない。

## 優先順位

1. **P1高**：別途実装前に、固定allowlist self submarine/battery候補とWaveHit候補のread-only診断設計・安全性をレビュー。深度・Battery・WaveHitはGUI上の具体的参照経路がある。
2. **P1高**：Undineで深度／batteryとping対象・重複・タイマーを時系列照合。現行Pythonに不足しているため診断導入後の試験が必要。
3. **P1中**：魚雷明示`depth`、誘導先・停止、命中区画、魚雷消滅理由は一次根拠の探索を継続。現時点では未知扱いを維持。
4. **P1中**：Minotaurで既存公開APIの消耗品／search fieldsの実機値、state・単位・endTime基準を照合。自艦以外へ取得範囲を広げない。

## 2026-11-04追記：0.3.29魚雷state sampling

本書冒頭の0.3.4時点の調査状態に対するsource-only実装追記。0.3.28のdepth-only samplerを維持し、heavy diagnosticsから`isHoming`/`isSpotted`固定2候補を独立1Hz samplerへ分けた。ゲーム起動・新featureの実機取得は行わず、ローカルGUI抽出物と既存記録をread-onlyで参照した。

- GUI根拠はローカル `../mino-smoke/research/extracted/gui/data/Components.xml` の `<component name="Torpedo">`（L2277-L2286）。`id:String pk=true`、`ownerID:Integer sync=false`、`shotID:Integer sync=false`、`depth:Number sync=false`、`type:String`。これは候補名の存在根拠で、Python/dataHub公開性・同期・取得値・単位・意味は保証しない。
- 0.3.28は `torpedo_depth_sampling_enabled` 専用opt-in（collection必須、diagnostics非依存）、interval既定/invalid/minimum 1秒で `CC.torpedo.depth` のみを最大64 entity sampleする。B40では262 rows raw `0.14`を取得したがunit/semanticsは未確認でunit=nullを維持する。既存のMain heavy `uiTorpedoProbe`経路ではdepthを読まない。
- 0.3.29は`torpedo_state_sampling_enabled`専用opt-in（collection必須、diagnostics非依存）、interval既定/invalid/minimum 1秒で`CC.mods_DataComponent.data.isHoming/isSpotted`だけを最大64 entity sampleする。GUI/UI参照と既存ATM実測はフィールド名候補の根拠だが、Python/dataHub field availability・producerはunknown、semantics unverified。data objectのkey列挙はしない。flagは厳密boolだけavailableで、false/None/nonBoolean/missing/readErrorを分ける。
- 同一state内のAPI `uiId`とGUI entity `id`がscalar・strict same-type/valueで全件一意の場合に限り`uiState`へstate flags/depthを付与する。state flagsはGUI/API双方の全IDがvalid・unique、collection complete時だけjoinし、partial/truncated/ID None・不正/API unavailable/duplicateでは候補のみ保持する。過去値・ownerID/ownerId/playerId推測joinは禁止。`isHoming`はtargetID/stop reasonではなく、flagsをserver state一般へ拡張しない。
- heavy diagnostics・depth・stateが同じframeでdueなら、sample-local `DiagnosticCollectionSnapshot`がtorpedo collection getterと元collection iterationを共有する。state samplerは最大64 row + 1 truncation probe、entity ID/component/data/各flagの固定read上限を持ち、off時追加probe/API callsは0。0.3.29 source-onlyで、新featureのPython実機可用性・FPS影響は未確認。

### 魚雷戦テレメトリの取得棚卸し（0.3.29 source）

| 項目 | 現在の経路・根拠 | 判定／不足 |
|---|---|---|
| 魚雷個体と位置 | core `TorpedoTelemetry.torpedoes()` は公式ModsAPI `getAllTorpedoes()`から`uiId/ownerId/ownerTeamId/ownerType/shotId/type`と`position`を直接読む。B37で魚雷最大6本を含む1,306魚雷rowを記録。 | 直接取得あり。`position.y`は深度へ読み替えない。`shotId`共有範囲・uiId再利用・全条件の取得完全性は未確定。 |
| 発射元／owner | `ownerId`は `getAllTorpedoes()` rowの公開field。次段で同じ値を `getTorpedoOwnerById(ownerId)`へ渡し、戻りobjectから固定 `OWNER_FIELDS` を読む。現行collectorに`ownerShip` field readや`ownerShip` joinはない。`isOwn`は返却ownerの`isPlayer`が厳密boolの場合だけ出力し、それ以外null。ownerTeamIdは自艦teamとのrelation候補で、自艦owner確定ではない。 | ownerId/ownerTeamId/ownerTypeは過去実機取得済み（0.3.1記録374/374行）。owner API objectの一部fieldはnull。ownerIdとplayerId/vehicleId/GUI `ownerID` namespaceの一般契約は未確認で推測joinしない。GUI `Components.xml` の`ownerID:Integer sync=false`は`ownerShip`の根拠ではない。 |
| 誘導状態／誘導先 | 0.3.29専用opt-inが`CC.mods_DataComponent.data.isHoming/isSpotted`を最大64 rowsの固定fieldとしてsample。通常core魚雷行へ付与するのはcomplete collectionおよびGUI/API双方の全IDがstrict scalar/type/value uniqueの場合だけ。ATMあり等の過去取得範囲は[ACQUISITION_STATUS](ACQUISITION_STATUS.ja.md)。 | 新samplerのPython/dataHub availability・producerは未確認/unknown。semantics unverified。falseとunknownを区別するが、`isHoming`は誘導先ID・停止理由ではなくサーバー状態一般も保証しない。最寄り艦joinは禁止。 |
| 明示魚雷depth | 0.3.28の独立opt-in `dataHub.torpedo.depth` fixed-field probe。GUI抽出 `Torpedo.depth:Number sync=false`が候補名の根拠。B40で262行raw `0.14`を取得。 | 値のunit/semantics未確認。unit=null。position.yから補わない。 |
| 残射程／残存寿命 | 現行coreには直接fieldなし。`TorpedoMotion.observedDistance/Age`はcollector観測開始後の派生区間値。選択TTXのspeed/maxDistは静的性能候補。local GUI `Torpedo`定義にもborn/lifetime/remaining-range fieldなし。 | 直接取得経路は未発見・取得不能とは断定しない。TTX maxDist−observedDistance、速度×経過時間、WaveHit.lifeTime等で魚雷残量を推定しない。詳細は[残射程・寿命調査](RESEARCH_TORPEDO_RANGE_LIFETIME.ja.md)。 |
