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

## 調査対象

- 既定0.1秒ごとの収集API呼出し・collection再列挙・診断の負荷。
- 艦・魚雷・gun・parameter数に応じた処理量とJSON容量。
- 失敗getter・参照解決等の繰り返しと例外発生。
- JSONシリアライズ・ファイル書込み・記録ツールによるCPU／I/O負荷。
- 生存・撃沈・観戦による収集対象の差。撃沈が原因の識別に十分な比較条件とは限らない。

調査結果が揃うまでは、具体的なボトルネック・CPU/GPU起因・mod起因を断定しない。
