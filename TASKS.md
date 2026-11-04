# 開発タスク

## 緊急優先：通常プレイのFPS低下

- B42静的照合終了：GUIの魚雷depthはNumber sync=false宣言のみ、公開API意味定義なし。検索した範囲でUI用途根拠なし。locator/search APIのenum契約もint宣言のみなのでGUI状態名候補を確定値へ昇格しない。深度意味・終了/cooldown等の未確認は明示して保留し、同条件再試験しない。次の未検証領域は敵／味方魚雷の公開owner取得と生座標（自艦以外の観測）。
- B42追加確認：8:30の発射時はHUD深度30mとユーザー確認済み。魚雷depth候補は43行とも0.14で、浮上B40と同値。自艦発射深度の指標とは解釈せず、実魚雷深度／別用途の区別・単位は未確定。同じ30m発射の再試験は不要。
- B42（2026-11-04）：0.3.30・1対1、8:30発射／8:00深度0m／4:28装置作動／効果終了前退出、minFPS60以上・カクつきなし。depth43行raw0.14/exactUiId、発射時HUD深度は未報告。locatorと消耗品state6→0→3、workTimeLeft60→27.879を取得。作動162sampleでendTime-ts=workTimeLeftだがendTimeは約1秒変動し不変deadline外挿不可。終了/cooldown・HUD残秒は未確認、330秒待機を直ちに再要求しない。停止・13fileshash照合退避済み。[B42記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_B42_DEPTH_LOCATOR.ja.md)。
- ATM連携後の棚卸し：新probeは不要。B08 locator/search・消耗品state6→0、endTime-ts330→0は記録内で整合候補と確認したが、HUD/timebase契約ではない。次は既存core＋depth samplerで非浮上深度の魚雷・locator表示遷移を1戦へまとめる。敵魚雷は現れた場合だけowner観測、味方ownerは単独戦で未確認を保持。成功済みping/浮上発射は繰返さない。[残項目確認計画](WowsExtractor-torpedoes-client-test/docs/RESEARCH_POST_ATM_REMAINING_VALIDATION.ja.md)。
- ATMありB08（2026-11-04、with-atm-b08）：0.3.30・1対1、minFPS60以上・カクつきなし。候補418行exactUiId、component/data available278・none140、ATM homing判定true162/false116、spotted推定true108/false170を取得。最初の斉射でflag供給が約22秒遅れ、操作時刻との対応・意味は未確定。collector平均cycle2.981msはATM処理を含まない。停止後collector13＋ATM専用3 filesをhash照合退避済み。同試験の再要求は不要、残項目棚卸しへ。[ATM B08記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_WITH_ATM_B08_0.3.30.ja.md)。
- 0.3.30-atm-derived-state（source only・未実機）：B41を受け、`torpedo_state_provider`で魚雷state候補の供給元を実行時明示する。既定`unknown`・`torpedo_state_sampling_enabled=false`を維持し、`advanced_torpedo_marker`を明示した場合だけATM由来の導出値としてdeclared producer／unverifiedで区別する。`isSpotted`はATM側の推定・第三者判定、`isHoming`も第三者判定であり、ゲーム／サーバーの生状態、誘導先ID、停止距離／理由ではない。provider出力の厳密なfield schemaは別実装で確認中で断定しない。installerは既定のATM退避を維持し、明示`-WithAtm`（別名`-KeepAtm`、wrapper `--with-atm`）のときだけATM存在時に残してcollectorを導入する。UAC昇格時も指定を引き継ぎ、dry-runと実実行のmessageを区別し、rollbackはinstallerが実際に退避したATMだけを戻す。元から残したATM、`TTaroModUtils`、`PnFModsLoader.py`には触れない。自動download・third-party同梱・unknown backup復元は行わない。復元は`restore-atm-13357625.bat`のallowlist strict no-overwrite（conflict時fail closed）。ATMが必要なのはruntime導出stateの情報源のためで、core収集のためではない。試験条件はcore5Hz／state1Hz／heavy OFF／depth OFF、負荷再発時は即中止。同じB41操作はATM producerありという新条件で再試験可能だが、現時点でユーザーへ実機依頼しない。installerのoffline testsを追加（Temp fixtureのみ、実ゲームフォルダー書込なし）。実機取得・FPS・実時間・API内部時間は未確認。[B41供給元調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_B41_MOD_DATA_PRODUCER.ja.md)／[導入](WowsExtractor-torpedoes-client-test/docs/INSTALL.ja.md)。
- B41供給元調査：公式ui APIとGUI定義からmods_DataComponentはmod追加・更新領域と確認。ATM等の値は第三者由来の導出候補であり、公開Torpedo APIの生誘導／被発見boolではない。ATMなしでNoneは現在の根拠と整合し、同じ発射/ping再試験は行わない。外部mod導入は未承認、直接値の代用もしない。範囲判断が必要。[供給元根拠](WowsExtractor-torpedoes-client-test/docs/RESEARCH_B41_MOD_DATA_PRODUCER.ja.md)。
- B41（2026-11-04）：0.3.29・1対1、08:00発射→07:40 1ping→07:30外れ、07:00二重状態発射→06:40命中との報告。minFPS60・カクつきなし。state samplerの84魚雷候補はexactUiIdだがmods_DataComponent実体Noneで両flags未取得（falseではない）。停止・13fileshash照合退避済み。同じ実機試験は再要求せず、GUI/producer/別API経路を調査する。DSFF実依頼は枠切れにつきLuna xhighへ切替済み。[B41候補未取得](WowsExtractor-torpedoes-client-test/docs/VALIDATION_B41_0.3.29_TORPEDO_STATE.ja.md)。
- B40（2026-11-04解析）：0.3.28・6対6、8:22全発射完了／7:30退出、minFPS60・カクつきなし。depth probe147 due sampleで262魚雷行を取得、全行raw0.14・exactUiId、unit null。独立取得の実機可用性確認済み、意味・単位・別深度は未確認。cycle平均5.775ms／最大21.938msを記録したがdepth起因とは断定しない。停止・13fileshash照合退避完了。同じ浮上発射の再試験不要。[B40深度候補](WowsExtractor-torpedoes-client-test/docs/VALIDATION_B40_0.3.28_TORPEDO_DEPTH.ja.md)。
- B39後のnamespace調査完了：GUI Components.xmlではAvatar.idがInteger PK、playerId propertyなし。観戦・combat log・context menuでもこのGUI IDをplayerId名で使う根拠あり。ただしModsAPIとの一般対応契約は見つからず、候補一致をconfirmed joinへ昇格しない。定義にないplayerIdを探すための実機再試験は行わない。現行0.3.27の独立観測＋candidate契約を維持。[namespace調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_AVATAR_ID_NAMESPACE.ja.md)。
- B39（2026-11-03）：0.3.27、minFPS60～70・カクつきなし。roster/avatar12対APIships最大9。候補avatar.idは全12件available、ships内9件とは型値一致、安定168 stateでは未一致3件すべてでmap/raw health取得を確認。strictplayerIdは依然unknownのまま、候補一致を確定joinへ昇格しない。cycle平均5.119ms・最大6.806ms。停止・13fileshash照合退避完了。範囲差の追加実機再現は当面不要、次は既存定義でnamespace根拠を確認。[B39詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B39_0.3.27.ja.md)。
- B37（2026-11-03）：0.3.26・6対6・5Hz、未発射→魚雷最大6本（owner1）。記録時計上torpedoes平均0.020→0.260ms、cycle5.146→5.633ms（全0/全6本窓別集計）。FPS/体感は未報告、多数本数への外挿不可。avatar map/health各12件は取れたが**全738 stateでplayerId対応0・unmatchable12**、識別付き観測として未完成。既存shipsは全8,789行map/playerId保持・indexhit、個別lookup0。停止・13files保全退避済み、識別子取得と実機/fixture差を調査中。開始直後drop追跡なし。[B37詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B37_0.3.26.ja.md)。
- 0.3.27-avatar-id-candidates（source only・未導入）：B37失敗を受け、既存sample済み`avatar.id`をrow内の`identifierCandidates.avatarId`（`namespace=avatar.id`、`semantics=unverified`）として出力。同snapshot `ships[].playerId`とのstrict type+value candidate一致・未一致・重複・不明を別の匿名`candidateConsistency`に計上。確定joinは引き続き`avatar.playerId`のみで、既存`apiPresence`とconfirmed coverageは不変。B37実機問題を解決したものではなく、候補を観測可能にする範囲。field read/API/CC/getter追加なし、既存sampleの欠測理由は`notRecorded`、frame cacheなし。offline testsで実wrapper、型差、重複、0/bool/unsafe/nonfinite、partial/CCNone/未sampleを追加検証。FPS未報告・開始drop追跡なし。追加実機なし。
- 0.3.28-torpedo-depth-sampling（source only・未導入）：0.3.27にあったdepth候補をheavy diagnosticsから分離し、`torpedo_depth_sampling_enabled=true`専用・interval最小1秒で最大64 entityの`CC.torpedo.depth`だけをsample。`diagnostics_enabled=false`でもcollection opt-in下で稼働し、同sampleにheavy diagnosticsもdueなら`getEntityCollections('torpedo')`を共有。collection=false時の追加API 0、非due値の再利用なし。完全collectionかつAPI/UI双方のIDがscalar・型厳密・一意の場合のみ同frame `uiState.depth`へ結合し、partial/truncated・重複・型差では値を付けない。GUI定義は候補根拠のみ、実機取得・意味・単位は未知。B37はdepth sampling OFFで未確認だったが、後続B40で262 rows raw0.14取得を確認（unit/semantics未確認）。同じ浮上発射のdepth再試験は不要。offlineで制限builtins・bounded iteration・same-sample API getter共有・strict join・欠測・failure・cadenceを検証。9 module維持、FPS/実時間/API内部時間は未計測。manifest/ZIP/install/commit/pushなし。
- 0.3.29-torpedo-state-sampling（source only・未導入）：heavy Main probeから`isHoming`/`isSpotted`の読取を分離し、`torpedo_state_sampling_enabled=true`専用・最小1秒で最大64 entityの固定2 fieldだけをsample。diagnostics非依存、collection必須、既定OFF。Python/dataHubでのキー取得保証・producerはunknown、semantics unverified。data object全列挙・公開key探索なし。厳密bool/false/none/missing/readError/nonBooleanを区別し、collection完全＋UI/APIの全IDがscalar・strict型値・一意の場合だけjoin。partial/truncated/ID欠測・重複/API unavailableはcandidate rowsのみ。heavy/depth/state同時due時はsample-local getterと列挙を共有、off追加probe/API calls 0、64 entity budgetのfield callsをfixtureで検証。B40 depth 262 rows raw0.14取得成功・unit未確認の既存事実を併記、新stateは実機未確認。FPS/実時間/API内部時間未計測。Python2 restricted builtins互換、新moduleなし、manifest/ZIP/install/commit/pushなし。
- B36の24対20：avatarは全401 stateでcomplete/count24だがshipsに出現したplayerは20人、未出現4人は両team1/3・全Battleship。全stateで入力len由来totalShipsと出力件数一致、collector/writer/recorderの行フィルターなし。取得経路差まで確認、API上流で未列挙の理由は未確定。0.3.26で既存shipsを変えず、captured avatarの同frame map/health/API presenceを独立出力するsource-only観測を追加。offline 24 avatar/20 API ships fixtureではmap24/20/0 variantsを確認したが、B36の実位置・HPは未確認で実機取得成功とは扱わない。rosterからalive/位置を推測補完しない。[取得範囲調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_B36_SHIP_COVERAGE.ja.md)／[出力仕様](WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md)。
- 残負荷候補の読取り専用レビュー完了：同一PlayerInfoのdamage登録／strict indexでの再読とship.teamIdの2-pass再読を0.3.25-player-field-budgetで最小実装。24行fixtureの通常3 field readsは144→72、ship.teamIdは全経路で最大1回。個別時間・FPS効果は未測定で、体感できる改善の根拠とはしない。avatar全3.935msを削減可能とは扱わない。優先は24対20の取得範囲調査、開始直後の低下は追わない。[残負荷候補](WowsExtractor-torpedoes-client-test/docs/RESEARCH_REMAINING_CORE_COST_0.3.24.ja.md)。
- ユーザー指示（2026-11-03）：**開始直後のFPS低下はこれ以上追わない。startup計測追加は進めない。** 優先対象をB36のroster24対ships最大20の取得範囲調査へ変更。既存記録・collector/reader経路からAPI返却時点の範囲差まで絞り、上流理由は未確定。0.3.26はcaptured avatar rowで観測範囲を分離するsource-only実装。追加実機は依頼せず、次回の魚雷あり実機負荷評価にavatar coverageとplayer budgetをまとめる。
- B36開始処理の読み取り専用レビュー完了：battle-start準備、ballistics/roster初期化、force meta build/atomic write、profiler初期probeは現行cycle計測外。記録最大10.47msだけでmod起因を除外できない。必要時の限定opt-in startup集計は未実装候補として残し、次の実戦負荷評価は魚雷ありの取得・motion・同期write増分を優先する。追加テストは現時点で依頼していない。
- B36（2026-11-03）：0.3.24・24人roster訓練戦、開始数秒min10→その後min50～60/max160～180・平均約120と報告。state艦数は最大20であり24隻同時収集ではない。全7,919行でplayer共有hit・個別lookup0・map/playerId保持。cycle平均7.153ms／最大10.469ms、初窓最大8.286msで開始min10の原因は未説明。停止・13ファイルhash照合退避済み。追加実機なしで開始時の無計測経路を調査中。FPS問題完全解消や24隻同時負荷確認とは扱わない。[B36詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B36_0.3.24.ja.md)。
- B35（2026-11-03）：0.3.24・6対6・5Hz、minFPS約75・カクつきなし。全2,288艦行のplayer共有hit、個別lookup0、map/playerId全行保持。記録時計上ships平均0.583ms／cycle4.823ms（B33は7.438／11.898ms）。12隻で共有の実利用と区間短縮を確認、FPS因果・24隻効果は未確定。停止・13ファイルhash照合退避済み。1対1・6対6を通過したので同設定の24隻短時間確認を次段階として準備し、悪化時即中止・通常戦には進まない。[B35詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B35_0.3.24.ja.md)。
- B34（2026-11-03）：0.3.24・1対1・5Hz、minFPS約80・カクつきなし。全293艦行でplayer共有hit、個別vehicle lookup0、map/playerId全行保持。記録時計上ships平均0.172ms、cycle2.615ms（B32は1.317/3.753ms）。共有実動作と区間短縮を確認、FPS因果・多数艦効果は未確定。停止・13ファイルhash照合退避後、6対6比較を準備。24隻はまだ行わない。[B34詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B34_0.3.24.ja.md)。
- B33（2026-11-03）：0.3.23・6対6・5Hz、minFPS約45・ごく軽微なカクつきと報告。active206件、平均間隔0.20459秒、全2,398艦行のmap座標保持。cycle平均11.898ms／ships7.438msでB31から単発時間短縮は実証できず、頻度半減だけでは未解消。クライアント停止・13ファイルhash照合退避完了。24隻へ拡大せず、後続工程で同sample players一覧と毎艦lookupの共有をoffline調査・実装（0.3.24、下記）。実機追加テストは依頼しない。[B33詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B33_0.3.23.ja.md)。
- 2026-11-03 0.3.24-player-read-sharing（source only・未導入）：既存の`getPlayersInfo()`→戻り値None時のみ`getPlayers()`を同state roster取得で1回だけ行い、その列挙からplayerId/teamIdのみのstrict vehicle ID indexを作成、`_build_ships`へstate-localで渡す。24艦normal full-hit fixtureで`getPlayersInfo` 1回（変更なし）、`getPlayerByVehicleId` 24→0回、ship row出力は従来lookupの成功結果と同値。partial missはmiss分のみlookupし、invalid/duplicate/type mismatchも旧lookupへ戻す。partial列挙は列挙済みvalid rowのみhit可・completeと偽装しない。diagnostic fallback due時はplayer objectを維持するため全個別lookupを継続。team/player ID 0保持・bool/str-int混同なし、damage cacheはcurrent ship identityに転用せず、frame間object/position保持なし。Main producer連結・roster damage・fallback/API exception・次frame unknown・0/None/conflict・5Hz/meta/avatar共有既存ゲートをoffline回帰で確認。FPS・実ゲーム時間/API内部時間は未計測。群別周期・serializer・新性能計測はscope外。詳細は`docs/OUTPUT_SPEC.ja.md`。
- 2026-11-03 0.3.25-player-field-budget（source only・未導入）：0.3.24のstrict player index／lookup省略を維持し、同じraw PlayerInfoのdamage登録とstrict indexで使うitem/attribute field accessを同一row内でmemoize。consumerごとの読取優先規則は維持するためmapping key/attribute競合やNone・raising時に共通getterへ強制統一せず、damage ID正規化・strict ID型判定も分離。24行fixtureで通常`playerId`/`shipId`/`teamId` key readを144→72回、player出力同値、players getter 1回、normal hit lookup 0回を確認。index不要のstart/direct callは元damage経路で追加field readなし、raw object/frame間cacheなし。`_build_ships` pass 1のship.teamIdをpass 2で再利用し、team 0・player team fallbackを維持、観測時点のみpass 1へ早まる。hit/miss/diagnostic fallbackで最大1回/ship。damage cache/partial・duplicate/0/None/failure/direct-call/strict IDと既存producer gateをoffline回帰。FPS・実ゲーム時間・API内部時間は未測定。新moduleなし、実機導入・ZIP/manifest作成なし。詳細は`docs/OUTPUT_SPEC.ja.md`。
- 2026-11-03 0.3.26-avatar-observations（source only・未導入）：既存`ships`は変更せず、同じavatar captureから`avatarObservations`を別fieldで出力。24 avatar/20 API ships fixtureで20 strict match・4 `missingInApi`、map coverage 24/20/0、raw healthの`0 + isAlive=true`と`isAlive=null`、strict ID 0/bool/None・重複競合、partial capture、CC/component欠測・例外を確認。partial/truncatedでもcaptured raw行を出すがhealth indexは無効、partialでshipsに不一致ならunknown。`avatar.id` fallback、roster static scan、synthetic ship、new API/clock read、frame cacheなし。通常completeでavatar collection getter1回・players info1回・full strict hitのvehicle lookup0回を維持。partial時は観測行のhealth.value/max/isAliveを各row最大1回sampleし、strict `avatar.playerId`と既存map index用`avatar.id`の両方が欠けるrowではmap componentを最大1回読む（理由・countを仕様に記録）。observation assemblyは既存ships phase内、新phaseなし。FPS・source-only cycle実時間・実機可用性は未測定。次回実機はavatar coverage＋player budget＋魚雷増分をまとめて評価し、開始min10追跡はしない。manifest/ZIP/git commit/pushなし。詳細は`docs/OUTPUT_SPEC.ja.md`。
- B32（2026-11-03）：0.3.23・1対1・5HzでminFPS 80～60、体感カクつきなし。176 active、平均間隔0.20377秒、全343艦行のmap座標保持。cycle平均3.753msでB30の3.674msとほぼ同等、単発処理時間短縮は未実証。頻度削減・FPS上昇の因果は未確定。試験後にクライアント停止・13ファイルhash照合退避済み。次の段階は6対6の短時間確認（再導入が必要）、24隻はまだ行わない。[B32詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B32_0.3.23.ja.md)。
- 2026-11-03 0.3.23-avatar-read-sharing（source only・未導入）：同一frameのavatar collection getterは既に1回のため変更せず、同じcaptured rowsからroster・health・map positionが必要とするavatar/vehicle/healthのcomponent・ID propertyをstate-localなplain-data sampleとして1回だけ読むよう共有。getter削減は主張しない。24行offline fixtureの読取りは456→336回（component 168→96、ID/health/property 288→240）で、これはFPS・実ゲーム時間の改善根拠ではない。sampleはcapture list内だけに遅延生成し、Collector・global・次frameへ残さない。partial/truncatedはhealth index無効・map/rosterは観測rowのみ、`untickedFull`/alias/`avatar.playerId`限定join/team 0・CC None・欠測・例外規則を維持。avatar phaseはcapture/roster/health、ships phaseはship builder/mapPosition/visibilityのまま。9 module維持、出力coverage変化なし、FPS未確認、mod退避継続。0.3.24で同sample players API lookupを厳密join時のみ削減。群別scheduler・位置frame間cacheは未実施。
- 2026-11-03 0.3.22-cadence-budget（source only・未導入）：負荷削減の最小scopeを実装。state既定を0.2秒（約5Hz）へ変更し、`state_interval=0.1`明示は10Hz互換。全snapshotは一体のままで群別周期・位置のframe間cacheなし。`_refresh_meta`のarena ID探索を0.5秒gateへ制限し、fallback中の期限内再試行・late arena昇格→meta/battleId整合・force即時を維持。探索期限はgame clockの別属性で管理し、失敗時も0.5秒待ち、frozen zero/非finite/逆行を安全化。`_build_ships`は`MapCalibration.observe()`の戻りsnapshotを直接使用。9 module維持。**FPS改善は未確認**で、5Hz化の観測遅延倍化・torn read回復窓・diagnostics実行上限・魚雷motion 1秒上限・較正driftの実時間検出遅延は[出力仕様](WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md)に明記。mod退避継続、追加実機なし。
- 周期調査完了（2026-11-03、実装変更なし）：B31の艦＋avatarはcycleの約80.7%。第一候補は既存state_intervalによる全体5Hz化（未適用）、次に艦＋avatarの周期分離。単発負荷はavatar走査共有・同sample ID index・自艦重複getter・較正snapshot二重生成を検討。meta ID探索がstate gate／profiler開始前にperTickで走る経路も発見。装填／消耗品は停船でも変化しており静的cache不可。取得損失・鮮度契約・offline testsを含む詳細：[周期・負荷削減調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_COLLECTION_CADENCE_B31.ja.md)。mod退避継続、追加実機なし。
- DSFFレビュー統合済み。同モデルの較正reservoir総当たり主因説は、早期returnとB31再生の平均32.26比較/state（最大45、reservoir25）から優先根拠に採用せず。meta全処理の計測外・診断dueのstate周期従属・低頻度化によるmotion/driftへの影響を調査資料に補記した。
- 2026-11-03 B31後：クライアント停止を確認し、収集modの13ファイルをハッシュ照合してロード対象外へ退避済み。次は**一律10Hzの必要性と取得周期の分離**を優先検討する（0.3.22で既定5Hz化まで実装、周期分離は未実施）。B31のcycle平均10.893msを約10Hz実行しているが、時計の意味は未確定でCPU使用率・FPSへの換算はしない。頻度低下は総負荷と発生回数を減らす候補だが、1回の処理時間によるカクつきは別問題。まず既存の設定・イベント経路を調べ、静的情報と動的情報の周期、未取得／未sample／過去値の鮮度契約を設計する。追加実機は今は依頼しない。
- B31（2026-11-03）：0.3.21・12隻でminFPS 45安定、カクつきが出始めたと報告。9窓の記録値はships平均6.849ms、avatar 1.938ms、cycle 10.893ms。拡張fallback 0でも未解消。**24隻への拡大は中止し、追加実機は依頼しない。** ships内部の取得・行構築を次の調査対象とする。[B31詳細](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B31_0.3.21.ja.md)。
- B30（2026-11-03）：0.3.21・1対1でminFPS 70～45と報告。7窓の記録時計上ではships平均1.303ms、snapshot平均2.918ms。全683艦行で地図座標を保持し、拡張探索0・coreDirectOnlyを確認。B28は24隻なのでコード単独の改善率・性能問題解消とは判定しない。追加12対12は依頼しない。詳細：[B30](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B30_0.3.21.ja.md)。
- [ ] **B28で0.3.20を一時導入して計測したところ、12vs12・収集ON／診断OFF／計測ONで「minFPS約20にほぼ固定、カクつき悪化」と報告。試験を中止し、クライアント停止確認後にWowsExtractorのみを再退避済み。** 診断OFFだけでは解消しない。core・書込み・計測器・外部記録の寄与は解析待ちで、追加実機・再導入は行わない。[B28性能記録](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_B28_0.3.20.ja.md)。
- B28の4集計窓では`ships`がsnapshot buildの約84%を占める（同一時計の記録値の比率）。191 sampleの`ships`平均約27.4ms・最大約40ms、魚雷処理平均約0.03ms。診断OFFを確認済み。B28静的調査でposition/worldPosition/positionHullが各9,100 missing、同一frame player lookup重複を確認。0.3.21ではship.getPosition一回、同frame player再利用、重いfallbackをdiagnostic due+opt-inだけにした。FPS因果と`time.clock`のruntime意味は未確定。通常戦での再現・再導入は依頼しない。
- [ ] 0.3.14導入後の通常プレイで「自艦撃沈までminFPS 25、撃沈後110まで回復」と報告（外部記録ツール未使用）。因果未確定。追加FPS比較実機試験は依頼しない。0.3.15で既定収集停止、0.3.16で診断既定1Hz、0.3.17でdiagnostic sample内共有、0.3.18でcore avatar getterを3→1へ、0.3.19でself getterを各state 1回へ共有。0.3.20-opt-in-profiling（source only・未導入）でcollection/diagnostics/profiler既定OFFのまま最大9区間の5秒phase集計を追加。OFF時clock calls 0、FPS未計測・改善未確認、timer候補はWoWS runtime未検証。writer thread/FPS/API内部時間未計測、24艦core処理時間・armament/public_data等は未評価。通常プレイにはmod退避を推奨。0.3.14 mod退避先はユーザー許可済み、再導入禁止。[性能問題記録](WowsExtractor-torpedoes-client-test/docs/PERFORMANCE_INCIDENT_0.3.14.ja.md)。

現在の正本ソース：`WowsExtractor-torpedoes-client-test/`。作業版は0.3.30-atm-derived-state（source only・未導入・未実機）。collection/diagnostics/profiler/position fallback/depth/state samplerは既定OFF、state既定0.2秒（約5Hz、0.1明示で10Hz互換）で全snapshot一体。`torpedo_state_provider`は既定`unknown`で、`advanced_torpedo_marker`明示時だけATM由来の導出値をdeclared producer／unverifiedとして区別し、`torpedo_state_sampling_enabled`はfalseのまま。installerは既定でATMを退避し、明示`-WithAtm`のときだけ残す。meta arena探索0.5秒gate、較正observe戻り値再利用、strict players index/row-local field共有を維持。0.3.26 B37ではavatar map/healthを取得したがstrict `avatar.playerId`が全738 stateでunmatchable。0.3.27は既存sampleの`avatar.id`を別namespace candidateとして出力し、ships playerIdとのsame-snapshot型付き値一致を匿名集計するのみ。0.3.28 depth samplerはB40で262行raw0.14を取得したがunit/semantics未確認（unit null）。0.3.29 state samplerは固定2 flagsを独立最小1秒でsampleし、complete collection＋API/UI全IDのstrict scalar/type/value uniqueness時だけjoinするsource-only実装。partial/truncated/ID欠測・重複/API unavailableでは候補のみ、producer unknown/semantics unverified、誘導先・停止理由を推測しない。同時dueのheavy/depth/stateはtorpedo getterと列挙を共有、frame cacheなし。9 module維持。offline全回帰422 passed・1 skipped（installer offline 14件を含む）、py -3.11 checkerで9 modulesのPython 2 grammar確認、diff check clean。新state samplerの実機取得・FPS/実時間/API内部時間は未確認。通常プレイには引き続きmod退避を推奨。更新：2026-11-04。

開発目標・収集層の責務は [DEVELOPMENT.md](DEVELOPMENT.md)、AI向け指示・自律進行・Git運用は [.ai/INSTRUCTIONS.md](.ai/INSTRUCTIONS.md) を参照。以下は進捗と残課題。

## P0：位置鮮度・失探管理（実質完了／マップ実装時へ移管）

- [x] modとマップアプリの責務を確定。modで最終目撃管理を完成させる作業は進めず、P0は実質完了とする。
- [x] 失探判定・最終確認時刻・経過時間・保持期限・再発見／撃沈時の履歴管理をP2へ移管。

これは鮮度判定の実機検証が完了したという意味ではない。
旧0.3.1の最終目撃キャッシュ・既定60秒TTL・ghost生成は0.3.2で撤去。
旧`lastSeenTs/staleSeconds`はmodの派生値だったため生成を廃止。

## P1：収集層への整理（設計反映・別途コード変更）

状態記号：`[x]` 完了、`[△]` 一部対応・調査済みだが未完了、`[ ]` 未着手。

- [x] 自前の最終目撃キャッシュ・60秒TTL・ghost生成を撤去し、関連設定／出力／テスト／資料／仮ビューアを整理。
- [x] 可視状態の候補値と取得元を位置から分離して出力。意味は未検証と明示し、座標の存在だけで発見中と断定しない。
- [x] 可視判定で捨てていた地図座標を保持して出力。範囲外の生座標も別フィールドに保持。
- [x] 新しい可視状態候補の実値を実機で確認。0.3.2で2艦のmapVisible=true→false→true、false時18行の座標保持を確認。1386 activeフレーム、正常終了、modログエラー0件。
- [△] 可視状態候補の意味を確定。0.3.2に加え、0.3.4実機記録でKREMLIN複数個体のmapVisible候補true/false、false中の座標保持、一覧欠落後の再出現を確認。raw.visible候補はint 1でnonBoolean、ship API候補はmissing。複数個体から報告対象を一意に割り当てられず、残時間・操作・最終目撃UIとの照合もないため、発見状態との同一視はせずsemantics=unverifiedを維持する。詳細は `WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.4_VISIBILITY.ja.md`。
- [△] ゲーム由来の最終発見時刻などの取得経路を調査。抽出GUI参照と公開API資料では経路を発見できず、クライアントpyc指定範囲は安全な静的解析手段がなく中身未確認。取得可否はunknown（未公開経路は未確認）。取得可能なら生値を追加する。アプリ側の履歴推定とは区別し、撤去済みの独自lastSeenTsでは代用しない。

2026-11-01追記：可視候補は標準UIでmapVisibleとvisibleが別参照・別用途であることを限定確認。0.3.4実機記録でmapVisibleの実値・遷移・false時の座標保持を確認したが、複数Kremlinの識別とUI/操作時刻の証拠が不足し、最終発見時刻もunknownのため`[△]`を維持。結果は `WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.4_VISIBILITY.ja.md`、診断仕様・JSON形状は `docs/VISIBILITY_RESEARCH.ja.md` と `docs/OUTPUT_SPEC.ja.md`。
調査範囲・制約・具体的な実機試験は
`docs/VISIBILITY_RESEARCH.ja.md`（ソースフォルダー内）を参照。

次の着手順：0.3.4記録の再試験では対象を一隻に識別し、画面録画・残時間・操作時刻とJSONLを同時に照合する。最終目撃表示と候補値の関係を試験条件内で確認し、味方視界のみは再現できる場合だけ別区間で評価する。最終発見時刻の未公開経路調査と魚雷所有者の識別調査は継続。

## P1：魚雷識別・運動・単位（mod）

- [ ] 自艦魚雷／僚艦魚雷／敵魚雷の確実な識別。`ownerId/ownerTeamId/ownerType`はcore rowから取得済み、owner objectは別API `getTorpedoOwnerById(ownerId)`で取得する。現在のcollectorに`ownerShip` field readはなく、`isOwn`は返却ownerの厳密bool `isPlayer`がある場合だけ。ownerIdとplayerId/vehicleId/GUI ownerIDのnamespaceは未確定で推測joinを避ける。
- [ ] 複数魚雷・複数斉射の識別、shotIdの共有範囲、uiId再利用、途中取得／消失を検証。
- [ ] 魚雷の深度を含む位置成分と、艦のyaw／speed、座標軸、時刻・距離単位を検証。
- [ ] ATM `isSpotted=false`の実測とtrue／false／unknownの遷移確認。
- [ ] ATMあり／なしのtype・isHoming・isSpottedの対応、供給元、更新差を整理。0.3.29で`isHoming`/`isSpotted`固定2候補を専用`torpedo_state_sampling_enabled` 1Hz opt-inへ分離する（source only・実機未確認）。producer unknown・semantics unverifiedを維持。`isHoming`は誘導先ID・停止距離／地点／理由ではない。誘導先ID・停止情報は未取得。
- [ ] 停止・旋回・欠測・再取得時の速度／航向／観測距離・時間の挙動を検証。

## P1：装填・魚雷性能（取得経路調査→mod）

- [△] 0.3.9で`selectedTorpedoParamsProbe`実装。controller selection → unique slot.type → exact slot.id/ammo.id → `viewData.paramsDescriptor` → 固定TTX variantの経路をread-only候補として追加。B15で当該Undine条件の値を確認済み。0.3.10でGUI抽出owner参照を確認し、`torpedoTooltipParameterProbe`を追加。B18でPython playerAvatar singleton、complete parameter collection（54行）、固定field shape/raw valuesを実機確認。正本0.3.10 raw selectorは複合key誤構成でnoExactMatchだった。修正後はB18のraw rowsを使ったoffline選択確認済み。これは実機の修正版再試験ではなく、GUI lookup/namespaceの意味確認も未完了。詳細は[B18記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.10_B18_PARAMETERS.ja.md)。
  - 2026-11-02 B15追記：0.3.9実機のUndine選択魚雷で、selection 162/162 strict一意match、descriptorはpinger 25→torpedo 137、`selfVehicle`/`shipTTX`は162/162 available。選択`torpedo` variantは137/137 available、speed 75.0/delta 0、maxDist 9.0/delta 0（すべてvalue/delta available）。画面報告75kts/9kmとの当該条件内の数値整合を確認。`ttxStatus=partial`は固定3 variant中deepwater/alternativeが`none`のためで、selected leafの失敗ではない。`ammoParams`は162 stateで`{}`のままで、今回の値は別経路。補正後live値・単位・delta意味・Battle tooltip上書き・全艦一般は未確認のため[△]維持。追加実機試験は当該条件では不要。詳細は[B15記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.9_B15_TTX.ja.md)。

- [△] B14のUndine当該条件では管別reload対応を確認：gun raw type=2の6行で初期装填が3+3に分かれ、battleTimer約90秒で全6行full/READY。その後1行が再進捗し、記録上の魚雷1本初出と時間的に一致、約45秒後にREADYへ戻る。ユーザーの独立目視（最初45秒で3/6、全装填ほぼ直後に一本、その後45秒完了）とも整合。根拠・隣接frame・UI enum/predicateは[B14記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.8_B14_RELOAD.ja.md)。これは取得したgun state/progressとユーザー目視による当該艦・条件内の確認で、物理的な管番号や全艦一般を保証しない。
- [ ] 未確認は直接取得の装填残数、発射可否、管の故障／破壊状態と修理timerの区別。progressから数える場合は派生候補であり、直接loaded countとして扱わない。
- [△] 0.3.4 weaponSlot/progress/ammo/serialLoad、0.3.6 context/clock、0.3.8 gun/reloadBar/gunBarrel候補をread-only診断。B11時計・選択は試験条件内で整合確認。B12はslot初期装填のみだったが、B14で発射後reloadも含む当該Undine条件を確認済み。gun collection 6行の直接進捗が取得できているため、modifier参照の`getEntity` unknownと`serialLoads` unknownは別経路の制約であり、今回の完了条件ではない。追加実機試験・unknown診断ループは行わない。選択魚雷性能（ammoParams/速度/最大射程）の取得経路調査へ進む。slot/type/order推測joinは禁止。過去記録：[B12](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.7_B12_WEAPONS.ja.md)、[調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_TUBE_RELOAD.ja.md)、[出力仕様](WowsExtractor-torpedoes-client-test/docs/OUTPUT_SPEC.ja.md)。
- [ ] 選択魚雷の種類・速度・最大射程。`ammoParams={}`の取得経路を調査。
  - 2026-11-02 B15追記：Undine当該条件では`shipTTX.torpedoes.torpedo`からspeed 75.0/delta 0、maxDist 9.0/delta 0を実機取得（選択137 state）。これは`ammoParams`ではなくUI descriptor経由の静的TTX候補。`ammoParams={}`は通常162 stateで継続しており、API経路の調査項目自体は未完了。補正後live値・単位・全艦一般は未確認。
  - 2026-11-02 B18追記：tooltip約10秒の実機報告は画面75kts/9kmでB15と同一。今回のJSONLでも選択`torpedo` TTX raw 75.0/9.0・delta 0を取得し、独立目視報告と整合。別経路の`torpedoTooltipParameterProbe`はowner/collection取得済み（54 complete rows）だがcomposite id exact matchなし。これは補正overrideがない証拠ではない。再試験を求めず、GUI lookup/key/namespaceのコード調査後に潜水艦固有情報P1へ進む。詳細は[B18記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.10_B18_PARAMETERS.ja.md)。
- [ ] 飛翔中魚雷の残り射程・残存寿命。現行API/GUIの限定調査で個体lifetime・remaining range直接fieldは未確認。TTX maxDistや`observedDistance/Age`から推定しない。[調査](WowsExtractor-torpedoes-client-test/docs/RESEARCH_TORPEDO_RANGE_LIFETIME.ja.md)

## P1：潜水艦固有情報（取得経路調査→mod）

- [△] 0.3.11で`selfSubmarineProbe`と`waveHitProbe`を追加。B23は両probeが列挙例外だった一方、同じ2,622 active frameすべてで既存`weaponContextProbe.collections.selfVehicle`は完全なsingletonとしてavailable。0.3.12で列挙を`for ... in enumerate(...)`へ変更し、制限builtins fixtureを含むoffline回帰を追加。B24の206 active frameでは両collectionが正常取得され、selfVehicle singletonと各Submarine/Battery raw fieldがavailable、WaveHitはcompleteな正常空collection。B23の原因は依然未確定。B27ではUndineの2,233 active samplesとWaveHit 439 snapshotsをraw照合し、depth/Battery/WaveHitのUI用途根拠を静的資料で別metadata化（0.3.13）。depthのmはUI hint、enum名はUI label、`lifeTime`はUIの秒countdown入力に限り、サーバー状態一般は確定しない。同じ潜水試験の再要求は不要。B27記録：[潜水艦](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.12_B27_SUBMARINE.ja.md)／[WaveHit](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.12_B27_WAVEHIT.ja.md)、[UI根拠](WowsExtractor-torpedoes-client-test/docs/RESEARCH_SUBMARINE_STATE_SEMANTICS.ja.md)。
- [△] 対象艦・魚雷の深度および深度差。0.3.28の独立1Hz `dataHub.torpedo.depth`候補はB40で262行raw0.14を取得し、一意UI/API ID対応時だけ`uiState.depth`へ付与。unitはnull。`position.y`・地図補助y=0は代用しない。別深度での変化、単位、対象艦深度・深度差は未確定。同じ浮上発射試験は繰り返さない。
- [△] ping対象艦・命中区画・一重／二重状態・命中／更新／失効時刻・効果残時間。B27では6:42の二重ping報告と`hitCount=1→2`、`maxLifeTime=25→50`が整合。439 snapshotで1 row、1,794 snapshotは正常空。UIが直接countdown表示する`lifeTime`には秒hintを付けたが、期限・失効条件、対象ID namespace、命中区画、`maxLifeTime`単位は未確定。[B27 WaveHit記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.12_B27_WAVEHIT.ja.md)。
- [ ] 魚雷の誘導先ID、誘導停止距離／地点／理由。最寄り艦を確定対象にしない。
- [ ] 魚雷の消滅理由（命中・射程切れ等）。一覧からの消失とは区別する。
- [△] 潜航能力の残量・消費／回復・枯渇など、自艦潜水艦の状態。B27の2,233 active snapshotでSubmarine/Battery全allowlistを取得。潜航・浮上に沿う`depth=0→30→0`とBattery値の減少・回復、`currentRate=-1→0.6`を確認。depthのm hintとdepthIndex/Battery enum labelはUI文脈で記録したが、Battery割合・残時間、rateの単位、枯渇条件、物理的な無敵状態は確定しない。[B27潜水艦記録](WowsExtractor-torpedoes-client-test/docs/VALIDATION_0.3.12_B27_SUBMARINE.ja.md)。同じ潜水試験の再実施は不要。
- [ ] ソナー・レーダー・潜水艦探知装置の距離、作動／準備／クールダウン、残時間。
- [ ] 消耗品の残数・状態・endTimeの時刻基準、搭載なし／取得不可の区別。

## P1：実機検証・安定性

- [ ] 別地図で較正の成立、係数・軸・境界を確認。Oceanの係数を一般化しない。
- [ ] 停船・直進・旋回・狭い移動・較正前後・座標ドリフトへの対応を検証。
- [ ] 敵／味方／画面外魚雷、複数本斉射、失探／再取得を確認。
- [ ] 12対12相当で取得漏れ、負荷、JSON更新頻度と容量を確認。
- [ ] 連続戦闘・退出・再入場・観戦・自艦撃沈時のライフサイクルを検証。
- [ ] 退出ハングが再発した場合のみ切り分け再開（現状は保留、原因未確定）。
- [ ] クライアントbuild変更時の互換確認、安全停止、導入／復元手順を維持。
- [ ] 出力契約・取得状態・単位・検証根拠と詳細対応表を更新し、回帰テスト／配布物を維持。

## P2：本番SS用マップ（mod完成後・別途開発）

以下は今の仮マップへの追加要求ではない。modから何を取得できるか確定して設計する。

- [ ] 地形・島・地図境界の表示（素材の取得方法・利用条件も確認）。
- [ ] 拡大縮小・パン・自艦追従、対象選択／追跡、表示フィルター。
- [ ] 距離目盛り・距離円・任意地点間の測距、対象までの距離／方位。
- [ ] 現在位置と最終目撃位置、失探経過時間、撃沈、鮮度不明、取得停止の表示。
- [ ] 観測履歴から最終確認／失探時刻・経過時間を管理。発見→失探→再発見で時刻の固定／更新を検証し、停船を失探と判定しない。
- [ ] 最終位置の保持期限（60秒固定にしない）とghost生成を設計。撃沈・一覧消失・ID別名・戦闘切替で残留／誤復活しないことを検証。
- [ ] 自分の3D視界と味方による発見を区別し、座標が残る場合や可視状態不明時の鮮度表示を検証。
- [ ] 艦・魚雷の航跡、複数魚雷／斉射単位の整理・選択。
- [ ] 接近方向、予測進路、最近接距離／時刻、到達予測時間。前提と不確実性を明示。
- [ ] 深度／深度差、潜航能力、ping対象／区画／残時間、誘導先／停止情報の表示（取得できた項目のみ）。
- [ ] 発射管の装填状態、選択魚雷性能、残り射程／寿命の表示（取得／推定を区別）。
- [ ] ソナー・レーダー・潜水艦探知装置の範囲と作動状態の重ね合わせ。
- [ ] unknownとfalse、直接値と推定値、現在と過去を一貫して区別する。
- [ ] 読み取り専用、安全なローカル接続、個人情報の扱い、戦闘ID不一致／終了／更新停止への対応。

## 既存資料

- [先行調査：潜水艦深度・Battery・ping・誘導・探知装置](WowsExtractor-torpedoes-client-test/docs/RESEARCH_SUBMARINE_SYSTEMS.ja.md)
- [先行調査：座標・単位・較正・実機安定性](WowsExtractor-torpedoes-client-test/docs/RESEARCH_UNITS_STABILITY.ja.md)
- [P1コード調査：収集層・魚雷・装填](WowsExtractor-torpedoes-client-test/docs/P1_CODE_RESEARCH.ja.md)
- [取得状況の詳細対応表](WowsExtractor-torpedoes-client-test/docs/SPEC_COVERAGE_0.3.1.ja.md)
- [仮マップの使い方](WowsExtractor-torpedoes-client-test/docs/SIMPLE_MAP.ja.md)
