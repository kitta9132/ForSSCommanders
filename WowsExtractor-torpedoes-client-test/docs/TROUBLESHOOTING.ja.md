# 問題の切り分け

## ログを探す

まず `python.log` を確認し、`[WowsExtractor]`、`Traceback`、`ImportError`、`SyntaxError` を検索します。
元プロジェクトの案内ではインストール先の `python.log`、公式API資料には `profile/python.log` という記載もあります。buildや構成によって場所が違う可能性があるので、起動後に更新されたファイルをインストール先で探してください。

ログの目印：

```text
[WowsExtractor] loaded v0.3.1-map-motion ...
[WowsExtractor] writing telemetry to: <実際のstate.jsonの絶対パス>
[WowsExtractor] meta.json written ...
[WowsExtractor] tick failed: ...
[WowsExtractor] write failed for ...
```

上は検索用の抜粋です。全文・引数は状況によって変わります。出力パスのログがある場合は、推測したコピー先よりそのパスを優先して確認します。

## 症状別

| 症状 | まず確認すること |
| --- | --- |
| `loaded`がない | 起動build、`res_mods`の階層、空のローダー用ファイルの有無、`Main.py.txt`になっていないか |
| ImportErrorで補助モジュールがない | Pythonファイル6個を同じ `WowsExtractor` フォルダーへ入れたか |
| WindowsのPython 3でSyntaxError | ゲーム用 `Main.py` を直接実行していないか。これはゲーム内Python 2.7用 |
| `state.json`がない | 戦闘へ入ったか、ログの出力パス、書き込み権限、`tick failed`や`write failed` |
| JSONを開くと途中で切れている | 上書き途中に読んだ可能性。数百ms後に再取得。記録ツールは不正JSONを再試行する |
| 戦闘後に魚雷が0本になった | 正常な終了フレームの可能性。戦闘中の履歴はJSONLへ保存する |
| 魚雷未発射で空配列 | `torpedoStatus.available=true`なら正常な0本。falseなら取得不明／非対応 |
| `status=unsupported` | 対象buildで `battle.getAllTorpedoes` が呼び出し口として存在するか。UI側の取得とは別問題 |
| `status=unknown` | 戦闘準備中、戻り値None、呼び出し例外、列挙途中の失敗など。現版は詳細例外をJSONに出さない |
| 魚雷が見えるのに配列が空 | 正常取得か確認。自艦／観戦・発見・可視範囲条件を変えて試す。未発見情報まで返るとは前提にしない |
| `type=null` | 属性が存在しない、読み取りに失敗した、値がNone。`normal`へ置換しない |
| `type`がずっと`normal` | ATMなし／ありを分ける。API側とUI側で値が同じか未確認。ping命中時刻と対象魚雷を照合する |
| ATM表示とAPIのtypeが違う | この版ではあり得る未確認事項。画面と同じ時刻のJSONLを保存し、UI経路の必要性を判断する |
| 1pingから2pingの変化が見えない | 同じ対象への命中か、同じ魚雷を追っているか、魚雷が先に消えていないか、収集間隔の間に変化しなかったか |
| `isHoming`がない | 未実装なので正常。`type`から勝手に生成しない |
| ownerがnull／isOwnがnull | 発射元APIが返さない、PlayerにisPlayerがないなど。IDをプレイヤーIDと決めつけて補わない |
| relationが実際の表示と違う | 発射元team IDの意味が種別で違う可能性。値を保存して確認する |
| 発射管や弾パラメーターがない | 自艦なし、未対応、選択弾IDが無効、APIが魚雷パラメーターを返さない可能性 |
| `critTimer`が装填時間と違う | 故障関連のモジュールタイマーであり、装填時間として出していない |
| stateは止まったがactive=true | クラッシュ、mod停止、書き込み失敗の可能性。更新停止と戦闘終了は別扱い |
| 起動時に前の戦闘のstateが残る | 次の戦闘までファイルが残ることがある。更新日時・battleId・tsを確認 |
| 新しい戦闘の最初だけmetaとstateが違う | 別ファイル・別時刻で書かれる。battleIdで照合して更新を待つ |
| 重くなった | 既定は`state_interval=0.2`（約5Hz）。`0.1`を明示すると10Hzへ戻るが負荷も増える。async不可なら同期書き込みに戻る。特定のFPS改善は保証しない |
| 遅れてarena IDが出た | meta再探索は0.5秒間隔・初期12秒まで。期限後のlate IDは自動反映しない。battleIdとmetaを照合する |
| 記録ツールで0件 | `--mod-dir`が展開元でなく導入先か、JSONが生成済みか、schema/activeが正常か |
| 記録ツールでFileExistsError | 出力JSONLが存在する。別名を指定する |
| 旧サーバーでtorpedoesがunsupported | 元サーバーは今回変更していない。`state.json`を直接読む |

## 既知の設計上の限界

- 取得できないAPIや属性は多くの場合、例外を止めてnull／unknownへ落とします。そのため「エラーログがない＝全項目取得成功」ではありません。
- `state.json`は高頻度の非原子的上書きです。読み手で再試行します。
- 非同期書き込みは最新優先であり、ディスク遅延時は中間フレームが省略されます。
- 誘導先IDや誘導継続フラグをこの版は出しません。外部マップもありません。
- 元から存在する艦船の地図変換やダメージの補助推定は、今回の魚雷取得値とは別の処理です。

## 報告するとき

「何も出ない」だけでなく、modバージョン・起動build・実際の出力パス・status・操作手順・操作前後の記録を添えます。
ログにはプレイヤー情報等が含まれることがあります。共有前に確認してください。
