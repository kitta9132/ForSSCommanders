# オフライン確認結果と再現方法

作成日：2026-10-31（日本時間）。以下はパッケージ作成側の結果です。WoWS実機の結果ではありません。

## 実施結果

| 確認 | 結果 | 限界 |
| --- | --- | --- |
| パッケージ単体のpytest | **76件成功** | 公開APIの代替オブジェクト・ローカルファイルを使用 |
| ゲーム用Pythonモジュール6個のPython 2文法解析 | 成功 | lib2to3による解析。実Python 2エンジンでの実行ではない |
| Collectorへの出力連携 | 成功 | API代替・ファイル書き込み代替を使用 |
| 魚雷処理の例外が既存艦船出力を止めないこと | 成功 | 意図的に例外を発生させて確認 |
| 戦闘終了フレーム | 成功 | active=false、魚雷空配列、兵装available=falseを確認 |
| typeの再取得 | 成功 | normal / acoustic / magnetic / normal / 未知値 / nullをそのまま保持 |
| 記録ツール | 成功 | 半書きJSON、非有限数、終了フレーム、上書き防止、JSONLを確認 |
| 配布ファイル | ビルド時にSHA-256とZIP CRCを検証 | 配布者本人の電子署名ではない |
| WoWSへの導入・読み込み | **未実施** | ユーザー側でこれから確認 |
| 実際の魚雷・pingによるtype変化 | **未実施** | 公開APIとUIの一致は未確認 |
| ATMとの共存 | **未実施** | 実際の対象buildとATM版で確認が必要 |
| UI→Flash→Python連携 | **未実装** | この版にはMain.swfもUnbound追加定義もない |

実測時間や表示の更新周期、FPSへの影響を保証する結果ではありません。

## pytestの再実行（開発者向け・任意）

Python 3.10以上とpytestが必要です。ゲーム内modにはpytestは不要です。パッケージのルートから実行します。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest
```

`tests/` は元のサーバーやaiohttpを必要としない構成です。ゲームへテストファイルをコピーしません。

## Python 2文法とCollector連携の確認（任意）

この追加チェックだけは、標準ライブラリー `lib2to3` があるPython 3.10〜3.12で実行してください。Python 3.13以降では本チェックを実行できませんが、それはゲームmodの適合性を示すものではありません。

```powershell
py -3.12 tools\check_collector_offline.py
```

チェック用にMain.pyの例外構文をメモリー内で変換し、自動Collector生成を停止してからAPI代替で一部メソッドを動かします。ゲーム用ソースの書き換えや実ゲームの呼び出しはしません。

## ファイルの整合性確認（任意）

```powershell
py -3 tools\build_bundle.py --verify
```

`Checksums OK`と表示されれば、`SHA256SUMS.txt`記載のファイルが一致しています。`config.ini`や生成されたstate/metaなどを配布物の展開元に追加するとファイル一覧の差として検出されます。配布物の原本と、ゲームへコピーした実行用フォルダーを分けて保管してください。

## ZIPを再生成する（開発者向け）

```powershell
py -3 tools\build_bundle.py --output "..\WowsExtractor-repacked.zip"
```

索引・全ソース一覧・チェックサムを再生成してからZIPを作ります。出力ZIPはパッケージフォルダーの外に置き、既存ファイルとは別名を指定してください。再圧縮するとZIP自体のハッシュが変わる場合があります。

## 次に必要な確認

[TEST_PLAN.ja.md](TEST_PLAN.ja.md)を順に実行し、結果を [TEST_REPORT_TEMPLATE.ja.md](TEST_REPORT_TEMPLATE.ja.md)へ記録してください。最優先はAPIで取れる `type` の実際の値と、ATM有無による変化です。
