# ForSSCommanders

- [開発タスク・残課題](TASKS.md)（仮マップはパラメーター確認用。本番マップはmod完成後に別途開発）

World of Warshipsの潜水艦向け外部2Dマップと、公開ModsAPIを使う戦闘情報収集modの開発プロジェクトです。

現在のソース・日本語資料は [`WowsExtractor-torpedoes-client-test-20261031/`](WowsExtractor-torpedoes-client-test-20261031/) にあります。

- [導入・概要](WowsExtractor-torpedoes-client-test-20261031/README.ja.md)
- [元仕様との詳細対応表](WowsExtractor-torpedoes-client-test-20261031/docs/SPEC_COVERAGE_0.3.1.ja.md)
- [簡易2Dマップ](WowsExtractor-torpedoes-client-test-20261031/docs/SIMPLE_MAP.ja.md)

## 現在の状態

mod `0.3.2-observations`（[出力変更](WowsExtractor-torpedoes-client-test-20261031/docs/OBSERVATIONS.ja.md)、新仕様の実機試験は未実施）。旧0.3.1ではSteam版build 13357625の訓練戦で、魚雷位置・type、
ATM由来の誘導/被発見状態、移動履歴による座標較正などを試験しています。
簡易2Dマップのグリッドとゲーム内位置が概ね一致することをテスターが目視確認しました。
12対12・別地図・失探時の鮮度などは未検証です。完成版ではありません。

ATM本体や第三者の画像、個人情報を含む戦闘ログ・記録は同梱しません。
ATM由来のUI状態はATMの別途導入が必要で、取得できない場合はunknownとして扱います。

## Gitから利用する場合

チェックサム・一覧・一括ソースは生成物のためGitへ含めません。
インストーラーはチェックサムを必要とするため、まずPython 3.10以上で配布物を生成してください。
既存の出力ZIPは上書きされません。必要なら新しい出力名を指定します。

```powershell
cd WowsExtractor-torpedoes-client-test-20261031
python tools/build_bundle.py --output ../ForSSCommanders-bundle.zip
```

その後、同フォルダーの `install-13357625.bat` で導入します。ゲームを先に終了してください。
ATMありで試験する場合、導入後に `restore-atm-13357625.bat` を実行してください。
既存modのバックアップと、実際に起動するbuildの確認を推奨します。

## テスト

```powershell
cd WowsExtractor-torpedoes-client-test-20261031
python -m pytest -q
```

pytestが必要です。現在121件（旧ghost推測の専用テストは機能撤去に伴い削除）。Node.jsがない場合は任意のJSロジックテスト1件をスキップします。
ゲームmodはPython 2.7想定、外部ツールはPython 3.10以上です。

## ライセンス・出自

MIT。[原著作権表示とライセンス](WowsExtractor-torpedoes-client-test-20261031/LICENSE)。
収集modは [Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows) 由来です。
公式リリースやWargamingによる動作保証ではありません。
