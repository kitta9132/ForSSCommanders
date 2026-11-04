# build13533378：ATM併用12対12の試験準備

2026-11-05。ユーザー指定の12対12試験。最新clientrunnerは15.10.0.13533378の起動を記録し、新buildのres_modsは準備前に空だった。旧build13357625の復元・一括コピーではなく、新buildだけを対象にする。

## 構成と出典

- collector：`0.3.38-independent-gun-reload`。runtimeソースは変更しない。既存installerの`-Build 13533378 -WithAtm`を使い、source checksumと導入先を照合する。
- ATM：作者AndrewTaroの公式AdvancedTorpedoMarker、commit `6a62b202458484225369725f92b180f23af470d0`。
- 必須依存TTaroModUtils：公式commit `29afe93e2aa277e361c70147c2865f3785a9e577`。
- TTaroModUtilsが要求するModForge：公式commit `0ef421f38dad2ba3cdbbb779940c56db4cde818b`。
- 第三者の導入対象129ファイルを一時領域へ取得し、Git blob hashを照合済み。重複loaderは同一bytesのときだけ共用し、異なる既存ファイルへ無断上書きしない。第三者コード・画像・個人設定・記録はコミットしない。
- 作者の現行配布物であり、**build13533378での実動作や供給成功はまだ未確認**。旧buildでのB08成功を今回の互換性保証に使わない。

## 試験設定

collection=true、heavy diagnostics=false、profiler=true、core0.2秒。自艦depth／Battery／WaveHit／gun独立設定はON。魚雷depth独立probeはOFF、ATMの魚雷state samplerはON・1秒、provider=advanced_torpedo_marker。HP平均2Hz・比較／damage1Hz・魚雷near5Hz／far平均2Hzは既存のまま。

ATM出力は第三者由来の導出値。isSpottedをサーバー生値、isHomingを確定誘導先・停止理由に読み替えない。初回TTXは既にユーザー受入済みで、pinger回避やスキル値の再試験を要求しない。

## 確認と安全

- 12対12はユーザーが実際に選んだ艦・bot構成を記録と報告で確認する。指定人数を実現したと開始前に決めつけない。
- 操作は通常の潜水艦魚雷戦。特別な大量一斉発射や長い待機を追加要求しない。FPS悪化・カクつき・表示異常時は退出して中止してよい。
- 最低FPS・カクつき有無・おおよその発射／退出時刻を報告してもらう。録画は必須にしない。開始直後FPS低下の追加調査は再開しない。
- 外部全field recorderを新buildへ向け、既存記録を上書きせず新番号を採る。待機中の時間制限切れで取り逃さないよう、今回は明示的な秒数期限を付けず、結果回収後に停止する。
- 実機でcollector／ATM／依存のロード・エラー、群別周期、near／far実在、取得範囲、ATM供給、profilerを確認する。旧build・他mod構成も変わるためB46比を因果的FPS改善率にしない。
- 終了後はゲーム停止確認・記録回収・hash照合を行い、collectorとATM固有ロード対象を退避する。新規依存・生成ファイルの扱いも導入manifestに従い、旧build・ModPrefsや他modを削除しない。

準備完了：ゲーム停止確認後、既存installerでcollectorを導入し、Python9＋設定例の10 source hash一致を確認。ATM／依存は重複loaderをまとめた127ファイルをhash照合（新規126、既存loader1を保持）、新規試験config.iniを書き込んだ。旧buildのファイル・ModPrefsは変更していない。全field recorderを新buildへ向け、`with-atm-b09.jsonl`への新規出力・プロセス起動を確認した。待機期限なし、進捗stdoutはprivate logへ保存する。試験結果・新buildでの実ロード成功はまだ未確認。
