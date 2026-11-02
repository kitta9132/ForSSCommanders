# 実機テスト記録（コピーして記入）

## 環境

- 実施日・時刻・タイムゾーン：
- WoWSの地域／クライアント種別：
- ゲームバージョン／build番号：
- mod.version：
- 導入したWowsExtractorの絶対パス：
- ATM：なし／あり（版：）
- ATM依存modと他mod：
- state_interval：
- 自艦・魚雷種類：
- 対象艦・協力者の有無：
- リプレイ／録画／JSONLの保存先：

## 読み込み・出力

- loadedログ：あり／なし／不明
- meta.json生成：成功／失敗
- state.json更新：成功／失敗
- torpedoStatus.status：
- 魚雷発射後の配列件数：
- 記録ツール保存件数：

## 対象魚雷

- battleId：
- uiId：
- ownerId：
- shotId：
- ownerType / ownerTeamId：
- relation / isOwn：

## typeの変化

| 観測時刻 | 操作・画面の状況 | ts | APIのtype生値 | ATMの表示 | 備考 |
| --- | --- | --- | --- | --- | --- |
| | 発射直後 | | | | |
| | 1ping命中 | | | | |
| | 2ping命中 | | | | |
| | ping失効／解除 | | | | |
| | 接近・誘導停止の表示 | | | | |
| | 命中／消滅 | | | | |

未実施の行は「未実施」。不明な項目は「不明」。予想を観測結果として記入しません。

## 終了・再入場

- active:falseの終了フレーム：あり／なし／未確認
- 次の戦闘でbattleIdを区別できたか：
- 前の魚雷が残ったか：

## 問題があった場合

- 再現手順：
- 期待した結果：
- 実際の結果：
- 対象時刻のJSONL抜粋：
- `[WowsExtractor]`周辺のログ：
- typeがAPIとUIで違うと判断した根拠：

共有前にプレイヤー名・ID等の不要な個人情報を確認してください。
