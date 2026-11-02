# 座標・単位・較正・実機安定性の先行調査

更新：2026-11-01。対象は現行ソース `0.3.4-weapon-diagnostics`。0.3.4の実機記録は存在するが、本書の単位・別地図・12対12安定性を確定する根拠とは扱わない。本書は後続タスクの調査メモであり、ゲーム仕様や未実施の試験を確定しない。ソース／ゲーム／配布物は変更していない。テストは今回実行していない（既報のオフラインpytest 133件と、実機結果は別扱い）。録画・JSONLの個人情報は転載していない。

## 結論と区分

| 項目 | 現時点の結論 | 区分 |
| --- | --- | --- |
| ship/torpedo `position` の軸・実単位 | 現行コードは3成分を保持し、水平面をX/Zとして扱う。軸の意味・実長さの単位はソース上のフィールド名だけでは確定しない。`game_world` / `game_world_units_per_second` は意図的に保守的な出力ラベル。 | 静的調査済み、意味未確認 |
| ship `yaw` / `speed` と mapPosition `yaw` | 取得できる値を直接出力し、角度変換・速度換算をしていない。単位・基準方向・符号は未確認。 | 静的調査済み、意味未確認 |
| 時刻・距離 | `_now()` は `utils.getTimeFromGameStart()`、差分は秒扱い。魚雷観測距離はX/Z差分の累積。消耗品 `endTime` 等の時刻基準、実距離単位は確定していない。 | 静的調査済み、意味未確認 |
| 較正 | 現行 `MapCalibration` は戦闘内の時系列対応点を使う。Ocean実績を他地図へ一般化してはならない。別地図の独立した実機検証は未実施。 | 実装確認、別地図未確認 |
| ドリフト | 固定係数に対する不整合バッチ3回で再較正する実装とユニットテストがある。実機でのドリフト検出性能・閾値の妥当性は未確認。 | 静的確認、実機未確認 |
| 負荷・ライフサイクル・build互換 | 状態は既定0.1秒間隔。async writerはlatest-winsで中間フレームを捨て得る。12対12負荷、実機長時間運転、現buildを超えた互換性は未検証。退出ハングは過去報告として保留、原因未確定。 | 静的調査済み、実機未確認 |

## コード上のデータ経路と現在挙動

### 艦の座標・yaw・speed

- `res_mods/PnFMods/WowsExtractor/Main.py::_position_from_obj` は `getPosition()`、`position`、`worldPosition`、`positionHull`、shipGameData、mappingを順に試し、ベクトル3成分をfloat化する。失敗時は `None`。`_get_ship_position` はplayer/vehicle経由も試す。
- `Collector._build_self` はself ship `getPosition()` を `position` に格納。`shipGameData` の `health/maxHealth/yaw/speed` を読み、ship側から不足yaw等を補う。
- `Collector._collect_map_positions` はavatar entityの `mapPosition.position` 2成分と `mapPosition.yaw` を取得し、playerIdでship情報に対応させる。`_map_norm_xy` は0..1近傍を前提に有効性検査するが、正規化仕様を発見・証明する処理ではない。
- `_build_ships` は直接位置がなければ較正済みmap座標をpositionへ補完し、その場合 `positionSource=calibratedMapPosition`。推定位置のYは0固定で、深度取得ではない。yawはship値、なければmapPosition yawを値のまま出力する。
- `yaw` について現行コードには単位・角度範囲・北基準/船首基準を正規化する処理がない。`speed` もshipGameData生値で、出力単位を付けず換算しない。実機でHUD値と照合する必要がある。

### 魚雷の位置・運動・時間・距離

- `torpedo_telemetry.py::TorpedoTelemetry.torpedoes` は公開API `battle.getAllTorpedoes()` の `position` を `[x,y,z]` 化。`uiId/ownerId/ownerTeamId/ownerType/shotId/type` も同じ時点で採る。
- `Collector._build_state` で `TorpedoMotion.update(torpedoes, now, ...)` に渡し、各魚雷のpositionを較正器の `world_to_map(x,z)` に通す。魚雷 `mapPosition` は変換が範囲内の場合だけ出る。
- `TorpedoMotion` は同じuiIdかつ(ownerId, shotId)が同じで、時刻差 `0 < dt <= 1.0` の場合のみ差分を計算する。3軸velocity、水平 `hypot(vx,vz)`、`atan2(vx,vz)` heading、観測区間の水平距離累積と経過秒を出力。これは派生値であり、公式速度・全飛翔距離・残り射程・寿命ではない。消失、一覧取得不能、戦闘クリアで履歴を破棄し、外挿しない。
- `Main.py::_now()` は `utils.getTimeFromGameStart()` を使う。状態JSONの `ts` と各差分計算の時刻基準はゲーム開始後時間の想定だが、ゲーム時計のpause/scale/逆行などを含む実機挙動は未検証。消耗品の `endTime` は生値のまま。差し引きで残時間にしない。
- `map_calibration.py::snapshot()` は `coordinateUnit=game_world`、推定係数 `inferred=true` と明示。これは現状の内部単位ラベルであってメートルと同義ではない。座標深度は扱わない。

## 外部抽出GUI資料を使った単位確認

調査対象は隣接フォルダー `../mino-smoke/research/extracted/gui/data/Components.xml`、`data/constants/{battle,common}.xml`、`data/structs/{common,ttx}.xml` と `gui/unbound2`。**抽出物は元ゲーム配布物から再抽出・ハッシュ照合しておらず、対象クライアントbuildとの一致も未確認。** 下記はその静的スナップショットに見える宣言・UI式だけであり、Python ModsAPIの実値・型・単位の証明ではない。

- `Components.xml` の `Visibility` は `visible` と `mapVisible` を別Booleanとして定義。`MapPosition.position` はPoint、`yaw` はNumber。型宣言から角度単位やmap座標範囲は分からない。
- `unbound2/pc/battle/minimap/markers/ship_marker.unbound` は両visibility値を別々に参照し、通常/最終目撃風のmarker表示条件を分ける。`mapVisible` が最終目撃位置の鮮度やserver spottingと同義とはいえない。
- 同ファイルの `radToGrad(mapPosition.yaw)` はUI経路に角度変換がある根拠。ただしPython APIの `ship.yaw` / `mapPosition.yaw` が同じ表現である証明ではなく、換算係数として転用しない。
- `Components.xml` の `Distance.distanceToShipBW` にはコメント `BigWorld meters` がある一方、`unbound2/pc/battle/markers/markers_elements.unbound` は別の `distanceToShip` を `* 10` して `IDS_KILOMETER` 表示。後者はUI表示経路の式であり、Python `position` の座標単位や魚雷motionに適用できる証拠ではない。
- `Components.xml` の `FlightSpeed.value` / 各種 `speed` はNumberの宣言に留まる。`data/structs/ttx.xml` のTorpedoTTXに `maxDist` / `speed` があるが単位は記載されていない。`modal_ship_battle_params.unbound` の艦艇パラメーターはKNOT/KILOMETERの表示ラベルを使うが、TTX値や実行中API値への対応式まではこの調査で追えていない。
- `constants/battle.xml` の `torpedoSpeed`、`torpedoMaxDist` 等は名前のみのparameter定義。単位・計算係数の根拠にはならない。ComponentsのBattleTimer `battleTime`、Timer `currentTime/endTime` もNumber型宣言だけで、互いの時計基準を保証しない。
- 結果：この抽出範囲から「座標をmに変換する係数」「生speedからknotsへの係数」「Python yawの変換」「endTimeのepoch」を採用できる根拠は見つからない。推測換算しない。

## 較正・別地図・ドリフト

`map_calibration.py` はworldX/Zとnormalized nx/nyの軸整列モデルA/Bのみを候補とし、一般回転を含む完全なアフィン変換ではない。最大256サンプル、8点以上、training/holdout分離、2次元移動の共分散条件、world各軸の最小span、robust fit、residual/holdout検査を満たさなければ採用しない。係数はavailable後に固定し、外れ観測で学習データを汚さず、3連続の不整合バッチで係数とサンプルをクリアする。

`Main.py::_build_ships` は直接のworld位置とmapPositionを同時に得られた艦のみを較正入力とする。`mapVisible is False` は較正入力から外す。それ以外の候補値は通るため、座標の鮮度・可視意味は別の未解決課題。座標対応の時差、艦の位置更新周期差、map更新量子化も実機誤差要因になり得る。

既存 `docs/MAP_COORDINATE_INVESTIGATION.ja.md` にあるOceanの過去試算は、Ocean内での時系列関係を示すだけで、別地図・独立した他艦world位置との検証ではない。現行較正器はすでに時系列方式に更新済みなので同資料の旧「同フレーム3隻」記述は歴史として読む。`docs/MAP_MOTION.ja.md` の0.3.1実機結果も過去版の取得記録であり、0.3.4の別地図保証に流用しない。

### 既存オフラインテストが見る範囲

- `tests/test_map_calibration.py`: 合成軸A/B、単一経路/同一バッチ複数点、停船・直線・片軸移動の棄却、重複/非有限値、holdout outlier、bounded reservoir、時刻逆行/reset、3バッチドリフト、範囲外逆変換を検証。
- `tests/test_torpedo_telemetry.py`: vector/公開field、API欠測/例外/途中enumeration失敗、型を生で保持、運動差分・欠測・同時刻・ID変更・停止・overflowを検証。
- `tests/test_ship_position_diagnostics.py`: position getterのmissing/none/error/invalid vectorとfallbackを検証。
- 未カバー: 実ゲームAPI値の単位・軸・yaw基準、ゲーム時計の挙動、GUI表示との意味照合、別地図、実際の位置更新ずれ、魚雷world軌跡と画面上の独立照合、実機ドリフト、誤って採用した有効そうなfitの検出率。

## 実機安定性・収集フローと未カバー

- `Main.py`: `STATE_INTERVAL=0.1s`。`_tick` がdataHub/ModsAPI収集、state構築、`_write_state` を行う。threadingが利用できれば `_AsyncWriter` が単一daemon threadでJSON化/書込み。pathごとのpendingはlatest-winsであり、遅延時は古いsnapshotを捨てる仕様。threading不可/初期化失敗では同期書込みにフォールバックする。実際のFPS負荷、p95遅延、落とした回数は計測していない。
- `Collector._on_battle_start/_on_battle_shown` は両イベントを待ち、collection開始時にtick登録・即時tick。quitでactiveを落とし、tick取消、キャッシュclear、active=false最終snapshotを出す。observer、死亡、戦闘結果から退出までのイベント順、連続複数戦闘の実ゲーム挙動は未確認。
- `emit_guard.py::should_write_state` はquit後に遅れて完成したlive frameがinactive frameを上書きするケースを拒む。ただしasync writer内部の停止・終了・flushを保証する仕組みではない。writerはdaemonで、shutdown/join/queue drain機構がない。
- `battle_identity.py` はarena id優先、遅延取得時にfallback IDをpromote。`tools/serve_map.py` はmeta/state battleId一致を要求。ID更新が書込み競合した場合を含む実機統合検証はテストされていない。
- `tools/record_telemetry.py` はfile stat前後の安定性とJSON schemaを確認し、digestが変化したファイルのみJSONL記録。poll間に複数のstate更新があれば中間snapshotを復元できない。`--torpedoes-only` はroster/player情報を除くが完全匿名化ではない。デフォルトは0.05秒poll。出力は新規作成専用。
- `tools/serve_map.py` はlocalhost read-only viewer、3回まで読み直し後に直近cacheをstaleとして返す。`tests/test_map_server.py` はローカルHTTP、battleId mismatch、壊れたJSON、staleness、アクセス制御を検証する。server/viewer試験はゲーム取得の完全性や12対12時のフレーム漏れを測らない。
- `tests/test_collector_lifecycle.py` はイベント順、重複start防止、meta retryを、Main.pyから抽出したメソッドとdoubleで確認。`test_emit_guard.py` はquit競合の純関数を確認。`test_battle_identity.py` はfallback/arena昇格を確認。ゲームイベント登録・callback cancel実体、実際のwriter競合、長時間、戦闘切替、終了UI復帰の試験ではない。
- `tests/test_build_bundle.py` はprivate recordingsをbundleに含めないテスト。buildを跨ぐAPI互換はテストしない。配布/install scriptsは`13357625`固有名/既定パスを含む。新buildでは対象bin、MOD_VERSION、導入・復元手順、配布checksumを明示確認する。最新build互換を推定しない。
- 既報のpytest 133件はオフライン自動テストの報告値で、本調査での再実行結果ではない。実機での運転結果を示さない。

### 過去の退出ハングについて

`docs/EXIT_INVESTIGATION.ja.md` は0.2.0/build 13357625の過去報告と限定的比較を記録し、相互作用を含む複数仮説を残している。終了JSONが記録されたことはUI退出成功の証明ではない。現状TASKS.mdの扱いどおり「再発した場合のみ切り分け再開」、保留・原因未確定とする。今回の静的調査で再発を確認したわけではなく、writer、cancel、他mod等を原因と断定しない。

## 次に確認するコード箇所・診断案

1. 単位・軸: `Collector._build_self`, `_position_from_obj`, `_collect_map_positions`, `_build_ships`, `TorpedoTelemetry.torpedoes`, `TorpedoMotion.update`, `utils.getTimeFromGameStart`。生値にsourceと観測時刻を保ち、意味の確定前に換算値を追加しない。
2. 較正: `Collector._build_ships` のcalib入力（各点の座標source、map/worldの同一snapshot時刻、map identity）と `MapCalibration.observe/snapshot`。最小診断は既存のstatus/reason/sample/span/係数/train RMSE/holdout RMSE/driftStreakに加え、観測バッチ数・経過時刻・変換後の画面比較結果を記録。player名/IDや不要な座標履歴を公開Docへ含めない。
3. 更新漏れ: `_tick` の収集開始/終了と提出時刻、writer submit/実書込み時刻、pending上書き回数、serialize/write所要時間、同期fallback有無を限定カウンタで測る案。snapshotごとに詳細ログを出さず、秒単位の集計にする。診断追加は別変更・review後に行い、現行配布物へ注入しない。
4. ライフサイクル: `_start_collection`, `_on_battle_quit`, `_stop_tick`, `_write_state`, `_AsyncWriter`、イベント登録順を確認。診断ログはイベント名と開始/終了・所要時間・cancel結果に限定。繰り返し退出操作や停止中の強制killを初回試験にしない。
5. 運転上限: `record_telemetry` の出力先はゲームmodDirと分離し、試験ごと新規ファイル。フルJSONL・画面録画は個人情報を含み得るためローカル保持、共有前にユーザーが識別子等を除去。ログ採取がFPS/容量を押し上げないよう短い区間から始める。

## 段階的MeatProxy実機試験案

共通条件：まず既存の手持ち艦Minotaur（主にworld座標/通常魚雷の取得と比較）またはUndineを使う。協力者なしの訓練戦を基本とし、協力者・敵艦操作を前提にしない。対象mod版/build、ATM有無、map.id/name、艦、各操作のおおよその時刻、`meta.json` のmod versionを記録。画面録画とJSONLを同時に使う場合も、個人情報は外部Docへ転記しない。既報の0.3.4実機結果はvisibility候補等の限定確認であり、今回の未解決単位・別地図・負荷試験を代替しない。

| 段階 | 最小試験 | 観測・合格の見方 | 制約／進行条件 |
| --- | --- | --- | --- |
| 0: 起動・収集 | 既存0.3.4実機結果/記録の対象版・buildをまず照合。今回追加試験をする場合は通常手順で短時間だけ記録し、艦位置・yaw/speed、mapPosition、ts、ログを確認。退出も通常操作。 | 対象版/buildとstate更新を確認。終了active=false、記録停止は今回の試験で確認した場合のみ報告。エラーや更新停止なら次へ進まず切り分け。 | 過去の限定的な0.3.4結果を今回の単位・安定性の証拠と混同しない。再起動/再導入を独断で繰返さない。 |
| 1: 時計・運動 | 自艦を停船→直進→速度変更→旋回→反対方向へ移動。短い各区間に手操作時刻を記す。 | `ts` が進むこと、raw yaw/speed/positionの変化、差分速度との時間・方向の対応を見る。数値一致だけで単位確定としない。 | HUDは表示丸めや遅延がある。HUD単位からAPI生値の係数を即断しない。 |
| 2: 1地図較正 | 現在入れる訓練戦mapで、停船、十分な直進、独立方向を含む大きな旋回/別方向移動を順に行う。 | collecting/degenerateからavailableへの時刻、sample/span/holdout誤差、係数固定を確認。UI minimap上の自艦と変換位置を録画で比較。 | 停船・直線だけなら較正しないのが正常。Ocean係数を流用しない。無理に必要経路・時間を保証しない。 |
| 3: 別地図・ドリフト | map.idが異なる通常の訓練戦が可能な場合、段階2を新戦闘から反復。正しいmap identityと新規係数を確認。後半で継続移動しdriftStreak/再学習挙動も観察。 | 地図ごとに独立してavailableとなり、画面位置との誤差を記録。自然な座標ズレがないときはドリフト挙動を「未再現」と報告。 | 選べるmapがなければ延期。条件を満たす人工的な異常座標を実機へ注入しない。過去の異常挙動を再現したと偽らない。 |
| 4: 魚雷 | 一度に1本を発射して軌跡を観察し、可能なら消滅まで取得。次に少数複数本/斉射。協力者なしでは他者所有魚雷の取得・敵味方照合を無理に求めない。 | torpedo position、motionのdt/速度/heading、mapPosition、一覧の出入りをmarker/UI時刻と照合。速度/距離の単位は比較根拠が揃うまでunknown。 | 深度、命中理由、残射程は推定で埋めない。視認されない魚雷を取れる条件は未再現なら未検証。 |
| 5: 戦闘境界 | 一戦を通常退出し、次戦に入り、可能なら観戦/死亡/連続戦闘の自然な条件をそれぞれ記録する。異常がなくても試行数を記載。 | battleId分離、前戦状態残留、更新停止、終了フレーム、次戦再開を確認。 | 過去ハングは保留。問題なし一回で全ライフサイクルを保証しない。再発時は操作を増やさず時刻・ログを記録し、原因調査へ戻る。 |
| 6: 12対12相当 | 自然な通常戦で最大規模に近いロスター・魚雷活動の機会が得られた場合のみ記録。外部OS計測を使うなら開始/終了時刻とツールを記録。 | `diag.totalShips`、torpedo件数、state `ts`/mtimeの更新間隔、記録JSONLでの重複/飛び、CPU/FPS/書込み遅延、更新欠落を評価。複数試合で範囲を報告。 | 協力者なし訓練戦で12対12や敵味方の一斉魚雷を再現できるとは限らない。条件不成立は「未実施」。人工負荷・bot注入やゲームプロセス改変はしない。 |
| 7: build互換 | ゲームbuild変更時のみ、通常導入/復元手順でversion/buildを固定して起動確認。 | 起動・ログ・API field status・meta/state更新・終了を最低確認し、対象buildごとに記録する。 | buildが変わったら互換を引き継がず、旧版へ戻す手順を先に確保。配布物/ALL_SOURCE/FILES/SHA256SUMSを試験目的で上書きしない。 |

12対12の完全再現、協力者による艦操作、別地図選択、魚雷の実距離単位の確定は、手持ちMinotaur/Undineと協力者なし条件では常に達成できるとは限らない。再現不能を失敗・合格どちらにも読み替えず、未実施として残す。

## 優先順位

1. **最優先：既報0.3.4実機結果の対象版/build確認と、未確認の通常運転範囲の補完**。取得確認済みの項目を再試験済みに見せず、今回のログで安全な更新・通常退出を確認する。ハング再発時のみ退出原因調査を再開。
2. **次点：座標の意味と較正**。まず一地図で自艦軌跡とmap/world対応を独立目視照合し、別mapで再較正する。別地図確認前に座標換算係数を固定しない。
3. **次点：生yaw/speed/時刻と派生魚雷運動の意味**。UI/HUD比較と停止・旋回・欠測を分けて照合。根拠がなければraw値/unknownのまま維持。
4. **次点：更新漏れ・負荷**。短い通常戦で計測方法と更新頻度を確認し、その後に大規模戦を機会がある場合のみ試す。12対12を再現できないことを明記。
5. **継続：build互換と契約**。buildごとに安全停止・導入/復元、フィールドの取得状態、単位の確度、テスト範囲を更新する。
