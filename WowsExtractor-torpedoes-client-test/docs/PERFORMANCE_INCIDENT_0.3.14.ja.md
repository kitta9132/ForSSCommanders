# 0.3.14 性能問題：初期報告

## 報告と対応状況

- ユーザーが0.3.14導入後の通常プレイで「自身が沈むまでminFPSが25」と報告。
- 追加報告：自艦撃沈後はminFPSが110まで回復し、外部記録ツールは使用していなかった。
- 記録ツール未使用は、mod内部のtick・state.json書込が停止していたことを意味しない。内部収集は戦闘中継続する設計。
- mod・記録ツールによる負荷との因果、通常時FPS、報告されたFPS値の独立確認、戦闘規模、再現性は未確認。
- 生存中25→撃沈後110の差は、live自艦状態に応じた処理差やdiagnostic/core API呼出しを重点候補として調べるが、因果は未確定。FPS比較を目的とした追加実機試験は依頼しない。
- 機能追加・追加実機テストを停止し、性能問題を最優先に調査する。
- 初期確認時はWoWSが稼働中。ゲーム停止・導入先変更は行わず、読み取り専用のログ調査と収集経路の静的レビューを開始。

## 安全方針

- 問題を再現するための通常戦・追加負荷テストは依頼しない。
- ゲーム正常終了後、必要ならWowsExtractor本体だけをロード対象外へバックアップ退避する。他mod・ATMは変更しない。
- 軽量版・過去版も性能確認済みとは扱わず、単純な旧版導入を解決策としない。
- 0.3.15-performance-safetyは既定で収集を停止する安全版。FPS改善版・性能改善確認済みとは主張しない。通常プレイではmodのロード対象外への退避を推奨する。
- 既定停止はbattle API/dataHubの同期収集経路を開始しないための措置であり、ゲーム全体のFPS改善や他modとの因果を保証しない。
- 静的確認ではmodule import/collector生成時にbattle/dataHub/Ballistics収集APIは呼ばず、config用の`utils.getModDir()`参照とevent hook登録を行う。戦闘collection開始時のAPI取得は明示opt-in後に限る。
- `collection_enabled=true`時の従来core収集負荷（state interval 0.1秒、艦船/自艦/魚雷等）は未評価で、低負荷を保証しない。diagnosticsは別途`diagnostics_enabled=true`時のみ実行。
- FPS改善や原因特定を、単体テストの成功だけで主張しない。
- 0.3.17-snapshot-reuseは未導入のsource-only変更。0.3.16の既定収集停止・診断1.0秒間隔を維持し、due sample内のfixed-name collection getterを共有する。offline Main統合fixtureで同名original getter呼出し各1回を確認。FPS未計測で改善を主張しない。collection_enabled/diagnostics_enabled既定falseを維持する。
- 0.3.17でもstate/core intervalは0.1秒。core経路・core 24艦負荷・armament/public_data負荷は未評価で、通常プレイに安全とは宣言しない。0.3.14 mod退避先はユーザー許可済みだが、再導入しない。
- 同一due sample内のgetter call reductionはoffline Main統合fixtureで確認したが、FPS改善量・API内部frame snapshot・field値の時間的一貫性を保証しない。
- 0.3.18-core-avatar-reuseはsource only・未導入。`_build_state`ごとにavatar collectionをfresh captureし、`_remember_roster_vehicles`/`_collect_avatar_health`/`_collect_map_positions`の3 getterを1回に統合する。診断OFFでもcoreの共有contextは使い、collection無効時はstate build自体がないため呼ばない。captureは最大256 rowを保持して257件目を検出し、diagにstatus/count/limit/reasonを出す。None/getter error/iteration errorはpartial/unknownとして明示し、途中例外後にAPIを再試行しない。partial/truncated health indexは適用せず、map/rosterは見えたrowだけ処理するため、欠落をalive/deadや座標として補完しない。各従来経路ではgetter例外は`_try`で空扱いだった一方、取得後のiteration exceptionはroster/health/mapともstate buildまで伝播し得た。新経路は列挙例外を捕捉しstateをpartialとして継続するため、従来のstate中断規則とは異なるが、partial metadataと位置unknown fallbackで明示的に扱う。通常成功時のraw/status同値と3→1 getter countはofflineテスト対象。FPS・API内部一貫性・core 24艦処理時間は未評価。
- 0.3.19-self-snapshot-reuseはsource only・未導入。各`_build_state`で`getSelfPlayerInfo`/`getSelfPlayerShip`を一度だけ呼び、fresh local値（None/例外も含む）を`_self_team`、`_build_self`、`armament`、`systems`へ共有する。teamは同じinfoの`teamId`からmemoizeし、self player別lookupを避ける。observer ship fallbackはself shipがNoneのself表示だけに限定し、weapon/system adapterへobserverを渡さない。adapter直接呼出し（引数省略）のgetter動作は後方互換で、Noneを明示した場合は取得済みunknownとして扱う。stateをまたぐobject cacheはない。既定collection/diagnostics OFF、diagnostics 1Hz、FPS未計測を維持する。通常成功出力同値・例外/None/observer境界はoffline producer/integration testsで検証対象。`armament`のammoParams/public_data列挙負荷・selected ammo取得・getAllShips fallbackと24艦core処理時間は未評価で、今回変更しない。
- 0.3.20-opt-in-profilingはsource only・未導入。`profiler_enabled=false`を追加しcollection有効との明示opt-in時だけ、`time.clock`→`perf_counter`→`monotonic`のcallable候補を8 readでprobe。`time.time`/game clock fallbackなし。利用不能・clock exception・nonNumeric/bool・nonFinite・逆行・resolutionUnknownはdurationに変換せず、battle中の逆行で停止し別時計へ切替えない。最大9区間（state/snapshot total、avatar/self/ships/torpedoes/armament_systems/diagnostics_due/submit）、最大18 clock reads/tick、5秒ごとのcount/total/maxを実装。計測OFFは0 clock calls。submitはasync handoff / sync encode+writeを識別するがwriter worker計測は未実装。実game timer候補、FPS、API内部時間、24艦core実時間は未確認。設計・出力契約は`PLAN_PERFORMANCE_PROFILING.ja.md`と`OUTPUT_SPEC.ja.md`。

## 調査対象

- 既定0.1秒ごとの収集API呼出し・collection再列挙・診断の負荷。
- 艦・魚雷・gun・parameter数に応じた処理量とJSON容量。
- 失敗getter・参照解決等の繰り返しと例外発生。
- JSONシリアライズ・ファイル書込み・記録ツールによるCPU／I/O負荷。
- 生存・撃沈・観戦による収集対象の差。撃沈が原因の識別に十分な比較条件とは限らない。

調査結果が揃うまでは、具体的なボトルネック・CPU/GPU起因・mod起因を断定しない。
