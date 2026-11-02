# B28：艦位置収集の定量調査

更新：2026-11-02。対象は正本 `0.3.20-opt-in-profiling` の既存B28記録とソース。mod再導入・実機再試験は行っていない。本書は候補経路を絞る静的・記録調査であり、実装変更や未計測API時間の推定は含まない。

## 結論

- B28の191 build窓では `ships` が合計5,224.150 ms、窓あたり平均27.35 ms、最大39.952 ms。`snapshot_build_total` 合計6,190.920 msに対して約84.4%で、同じ時計による内訳では最大。`avatar` 720.023 ms、`submit` 192.328 ms、`armament_systems` 81.148 ms、`torpedoes` 5.668 ms。時計は `time.clock` / `basis=assumed` でruntime上の実時間性未検証。これは同じ計測窓内での相対偏りを示すが、FPS低下の因果・実時間コストを確定しない。[性能記録](PERFORMANCE_B28_0.3.20.ja.md)
- active 213 state、ships行4,831（平均22.68行/state）について全行を集計。`diag.positionReads` は `getPosition:available` 2,556、`getPosition:none` 2,275、`getPosition:missing` 6,825、`position:missing` 9,100、`worldPosition:missing` 9,100、`positionHull:missing` 9,100。3候補属性の `missing` は各9,100回であり、記録範囲では値を一度も得ていない。`getPosition` は総11,656試行中2,556成功（21.9%）。これらは候補属性への読み取り／getter呼出回数で、所要時間ではない。
- 同じ4,831行の `positionSource` は `shipOrPlayerApi` 2,556、`calibratedMapPosition` 912、null 1,363。全4,831行に `dataHub.mapPosition` 由来の `nx/ny` があり、したがって位置出力契約上の `positionAvailable` は全行true（world `position` が無い1,363行もmap座標は保持）。較正は213 state中76 `available`、137 `degenerate`。B28内で推定world位置まで補完できた行はあるが、較正済みでない区間もある。
- 全4,831行で可視性 `status=unknown`、`visible=null`、raw map visibilityなし。診断probeがdisabledであった条件の欠測であり、不可視・未発見を示さない。可視性を根拠に位置を隠す変更はしない。

## UI health・可視性・較正との関係

- `_build_state` はavatar entity snapshotを一度取得し、その同じentity列を `_collect_avatar_health` と `_build_ships` / `_collect_map_positions` に渡す。UI health indexは `ui_health.py::index_avatar_health` がhealth/avatar/vehicle componentからID別に作り、各ship entryへ `apply_ui_health` で不足health等を補う。B28ではavatar snapshotは全213 active stateでcomplete/count 24、`diag.uiHealth` は各state 12（`PERFORMANCE_B28_0.3.20.ja.md`）。したがって別のavatar collectionを位置resolver内で再取得する設計ではない。health indexの生成・適用は `avatar` phase内の処理で、`ships` phaseの突出時間と混同しない。
- `_collect_map_positions` は診断OFF時も同じavatar entity列から `mapPosition.position` を読み、playerIdで対応付ける。B28の全ships行でnormalized `nx/ny` が存在する一方、visibility診断はOFFであり `mapVisible` は全行unknown。較正入力条件はworld位置とmap位置の両方があり、`mapVisible != False` の艦。よってB28ではunknownがfalse扱いで除外されず、直接world位置の対応点候補に入る。これはコード動作の説明であって、map markerの鮮度や較正点としての意味を保証しない。
- `_build_ships` は直接world位置とmap座標を同フレームで得た点を `_mapCalibration.observe` に渡し、その後2 pass目で直接positionを優先し、なければ較正逆変換を補助値にする。B28の76 available calibration stateは記録された集計結果であり、他地図一般・可視性意味・worldとmapの更新時差の正しさを証明しない。

## 失敗経路の読み取り

### 静的に確認できる呼出し順

`Main.py::_build_ships` は各shipでまず `battle.getPlayerByVehicleId(vehId)` を呼び、player/idを得た後、`_get_ship_position(ship,pid,vehId)` を呼ぶ。位置探索は以下の順で、成功するまで進む。

1. ship本体を `_position_from_obj` に渡す。
2. `pid` があれば `battle.getPlayerShipInfo(pid)`、次に `battle.getPlayerInfo(pid)`。
3. `vehId` があれば再び `battle.getPlayerByVehicleId(vehId)`。playerがあればplayer本体も検査し、位置が無く、別pidならさらに2つのplayer-info APIを試す。

各 `_position_from_obj` は `getPosition` / `position` / `worldPosition` / `positionHull` の順に属性を読む。失敗後は `shipGameData` とmappingも候補にする。B28のカウンタはその候補属性が繰り返しmissing/noneだったことを直接示す。一方、`positionHull` 等がmissingの属性アクセス自体に何msかかるか、ゲームAPI内部時間がどれだけかは未計測であり、カウントからコストを確定してはならない。

ソース上の上限は、通常の1艦につき `getPlayerByVehicleId` が最大2回（初回 + position fallback）、playerIdベースのship-info APIが最大2回。さらにplayerIdが異なる分岐なら、ship-info APIが追加で最大2回となる。したがってship-info APIは最大4回/艦、`getPlayerByVehicleId` は最大2回/艦まで到達し得る。`_position_from_obj` に渡る対象は最大6個（ship、playerIdのinfo 2個、vehicle player、異なるpidのinfo 2個。実際には短絡・重複あり）。各対象で最大4属性を調べる前に有効値で短絡する。これは静的な上限で、B28各frameの実API呼出総数そのものではない。

B28では成功した `getPosition` が2,556行あり、直接経路は実際に有効。一方、world位置がnullの1,363行でもmap `nx/ny` は存在した。したがって、`mapPosition` が既にあることだけを根拠にworld位置API探索を全廃すると、実位置のY成分を含む直接取得値や、較正の直接対応点を失い、較正済みでない時のworld `position` 欠測も増やす。逆に、全候補APIを毎回総当たりする必要性もB28からは支持されない。`mapPosition` は2D UI由来の別フィールドとして保持し、world `position` と同一視・置換しない。

### 繰返し失敗・lookupのボトルネック候補

- `position` / `worldPosition` / `positionHull` はB28の全state累計で各9,100 missing。`_position_from_obj` を経由した各候補アクセスが複数playerオブジェクトにも反復された結果と、実装順が整合する。これは候補属性の診断根拠として強いが、個別のAPI経路別の実時間寄与は不明。
- `getPosition` のnone/missingは合計9,100回、availableは2,556回。失敗は偶発的な一、二回でなく、少なくともこの記録条件で繰り返されている。ship本体・player info・再lookupしたplayerのどの層がどの割合かは、現行カウンタが呼出元ラベルを持たないため識別不能。
- `_build_ships` が既に取得した `player` を位置探索でもう一度lookupする重複はコードで確定。1回のbattle tickで同一vehicleを複数経路から調べる設計であり、ship数増加に比例するAPI回数候補。ただしB28 JSONLにはAPI call counterがなく、perfタイマーも区間内の個別call時間を分離しない。
- ship側可視属性 `isVisible` / `isShipVisible` は各entryで読まれている。B28では `shipApi` の値は全行空で、候補diagnosticsはmissing。dataHub visibilityも全行componentMissing/unknown。可視性診断OFFでもcore出力に必要な読取りが残る箇所はあるが、これは位置API探索とは別の属性readであり、位置の有無や可視性により座標を消す根拠にはならない。

## 最小安全な実装候補（優先順・最大3）

1. **同frameのplayer lookupを再利用**：`_build_ships` で既に得たplayerを位置resolverへ渡し、同一 `vehId` の2回目lookupを避ける。player-info取得は直接位置が無い時のfallbackとして残す。resolver内のAPI順を変える場合も、各経路のsource/statusを保持し、例外やNoneを別の取得成功に偽装しない。B28の直接位置成功2,556件と、player fallback位置の寄与が現在のカウンタでは分離不能な点を踏まえ、lookup自体を捨てず同じ結果の再取得だけを削る。
2. **根拠のない候補属性の通常tick総当たりを抑える**：`position` / `worldPosition` / `positionHull` はB28で各9,100回missing。`getPosition` が失敗した後の追加候補を毎艦毎tick必ず調べるのでなく、頻度を落とした診断サンプルへ分離する案がある。ただしB28外/build差で値が出る可能性は否定できず、廃止は根拠不足。通常tickの `diag.positionReads` に診断未実行を0件として混ぜず、候補ごとにsampled/notSampled/unsupported相当の取得状態と標本数を表せること、既知の直接経路・API fallback・dataHub map座標を継続することが条件。属性getter時間を低頻度化で削減できるという効果量は未計測。
3. **position resolverの試行予算を明示し、重複経路だけを短絡**：同frameで得たplayer、ship自身、各API応答を一度ずつ使い回し、既に得たplayerまたは同じIDへの同一getter再実行を禁止する。異なるAPI経路の試行順・停止条件はオフラインfixtureで同一出力を証明できた範囲に限定する。`getPosition`成功はworld座標（深度成分含む可能性）の直接値として保持し、map2world推定より優先。直接位置が無いときのみ有効な較正から推定world位置を補助し、較正なしなら `position` 欠測のまま `nx/ny` を保持する。別frameの位置再利用、座標保持による可視判定の隠蔽、map座標を直接world位置として扱うことは禁止。

## 出力契約・取得statusの条件

- `ships[].position` / `positionSource` は直接API値 (`shipOrPlayerApi`)、較正推定値 (`calibratedMapPosition`)、未取得(null)を区別する。較正推定値のY=0は深度ではない。world位置が無くても `nx/ny`・`mapPositionSource=dataHub.mapPosition` は独立して出力し、`positionAvailable` はどちらかが利用可能ならtrueを保つ。
- 欠測・例外・invalid vector・未サンプル・候補未対応を互いに混同せず、unknownをfalse/0へ置換しない。位置探索を短絡したため試さなかった候補を `missing` や `unsupported` と捏造しない。`diag.positionReads` の意味（累計かsample内か、サンプル頻度、候補別件数）を明記する。
- `visibility` は従来通りraw候補と取得statusを保持し、unknown時も座標を出す。過去frame位置の再利用や自前可視判定による座標隠しは行わない。
- B28の全行map座標は利用可能だが、`mapPositionFreshness=unverified` の意味、world直接値との時刻整合、較正availableの正確性を一般保証しない。診断OFFという設定を理由に、coreの出力に必要な位置・statusを消さない。

## 根拠の所在と制約

- B28記録：`recordings/without-atm-b28.jsonl`。全213 active stateから `diag.positionReads` と全ships行のposition/map/visibilityフィールドを合算。氏名・player ID・生座標は本書へ転載していない。
- profilerの時計・窓・総計解釈：[`PERFORMANCE_B28_0.3.20.ja.md`](PERFORMANCE_B28_0.3.20.ja.md)。
- 実装：`res_mods/PnFMods/WowsExtractor/Main.py` の `_build_ships`、`_get_ship_position`、`_position_from_obj`、`_collect_map_positions`。
- 出力と較正背景：[`MAP_MOTION.ja.md`](MAP_MOTION.ja.md)、[`RESEARCH_UNITS_STABILITY.ja.md`](RESEARCH_UNITS_STABILITY.ja.md)、[`OUTPUT_SPEC.ja.md`](OUTPUT_SPEC.ja.md)。
- 本調査はJSONL上の件数と静的な呼出構造を示す。候補失敗回数×コード呼出しは反復頻度の根拠であり、API内部時間・getter単価・原因FPSを算出する根拠ではない。既報どおりmodは退避済みであり、追加導入・同条件再テストは求めない。
