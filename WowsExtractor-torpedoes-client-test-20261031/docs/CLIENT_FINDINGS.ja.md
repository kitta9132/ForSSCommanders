# build 13357625 の実機観測

## 前提

Steam版、ATM退避済み、mod 0.2.0-torpedoes の訓練戦記録。
生データはローカルの `recordings/` に保存し、配布物には含めない。
以下の時間は各魚雷をJSONで初めて取得した時点を0秒とする。
発射操作時刻、ping命中時刻、魚雷命中時刻そのものを直接取得した値ではない。

| 記録 | 操作の申告 | APIのtype遷移 | 最後の魚雷取得 |
| --- | --- | --- | --- |
| without-atm-b01 | Minotaur、通常魚雷1本、命中 | normalのみ | 約31.7秒 |
| without-atm-b02 | Undine、音響魚雷1本、ping約7秒、同一区画2回命中、魚雷命中 | normal → 約14.0秒 acoustic → 約23.0秒 magnetic | 約43.3秒 |
| without-atm-b03 | Undine、音響魚雷1本、ping約7秒、1回命中、魚雷命中 | normal → 約11.9秒 acoustic → 約36.3秒 normal | 約44.1秒 |

3件とも魚雷識別子が安定し、正常取得フレームで魚雷が一覧から消滅した。
音響魚雷でも最初のtypeはnormalだった。typeを固定の搭載魚雷種別として扱わない。
一重・二重pingとacoustic・magneticの対応は仮説であり、APIの定義と追加確認が必要。
体感の時刻は参考にとどめ、API状態の変化や消滅と同一視しない。

## 確認済みの不足

- ammoParamsはavailableだが空オブジェクト。
- 自艦魚雷でもisOwnはnull。名前空間が保証されないIDの比較で勝手に補完しない。
- ping命中時刻・対象・残り時間を直接出力していない。
- 発射管のHP等はあるが、装填残数・再装填残時間は出力していない。
- 魚雷消滅と命中は同義ではない。命中後に座標固定のまま残る可能性がある。

## 0.2.1のライフサイクル修正

実ログでは、初回のmeta書き込みエラーから保存先の解決まで約26～28秒あり、
画面表示イベントが戦闘開始イベントより前に到着していた。
修正前は保存先Noneへの書き込みを試み、失敗してもmeta.json writtenを出していた。

0.2.1は両イベントがそろってから収集を開始し、保存失敗時は成功表示せず再試行可能にする。
両イベント順、次戦闘、重複表示イベント、保存先未設定、保存失敗後の再試行を
オフラインテストで確認済み。Python 2文法・Collector連携チェックも成功。
修正版のゲーム内動作はまだ未確認であり、反映にはゲーム終了と再導入が必要。

## 公開API調査の結論

参照は wgmods/Mods-API-Documentation の固定commit
`01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2`。

- `docs/PythonAPI/Classes/Torpedo.md` の公開属性は現在収集している7項目。
  ping対象・ping残時間・明示的な誘導フラグは一覧にない。
- `docs/PythonAPI/battle.md` の getAmmoParams は砲弾情報objectという説明で、
  魚雷への適用や公開フィールド名一覧は確認できない。空オブジェクトから
  「魚雷の速度・射程データ自体が存在しない」とまでは断定しない。
- `docs/PythonAPI/Classes/_ModuleState.md` の critTimer は再装填時間ではない。
- 退避済みATMのUnboundは、typeとは別にmods_DataComponent.data.isHomingを参照する。
  これはATMの表示データであり、公開Python APIから直接読めると確認したものではない。
- `Ship.isPlayer`の名称だけで自艦を意味すると保証できない。
  isOwnの取得方法は引き続き調査対象とする。

次は修正版の起動確認後、UI/Flash/Python間の最小データ連携を検証する。
ATMのファイルや署名は改変しない。typeから誘導状態を推測して埋めない。

## 0.2.1実機確認・記録の除外

`without-atm-b06.jsonl` と起動ログで0.2.1の動作を確認。
2戦のactiveフレームは261件・250件で、両戦とも終了フレームあり。
両戦すべてtorpedoStatusはavailable、write failed for Noneの再発なし。
ユーザー観測でも2回とも訓練ルームへの退出に成功、不具合なし。
退出不能の根本原因は未確定で、再発時に調査を再開する。

ユーザー指示によりb04・b05は `recordings/discarded/` へ退避し、解析根拠から除外。
これらに基づいた二重ping再現性や2本目の直接magnetic移行の評価は保留する。
先の再導入テストは実際には0.2.0だったため、0.2.1の証拠はb06を正とする。
