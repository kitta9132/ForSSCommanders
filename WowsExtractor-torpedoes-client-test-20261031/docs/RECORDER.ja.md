# 履歴記録ツール（任意）

`tools/record_telemetry.py` は、ゲーム外で動かすPython 3.10以上用の補助ツールです。標準ライブラリーだけを使用し、pipの追加インストールは不要です。
mod本体とは別です。使わなくてもmodは動きます。サーバーや外部マップではありません。

## なぜ必要か

modは `state.json` を上書きします。戦闘が終わると魚雷配列は空になるため、最後のファイルだけではping前後のtypeの変化を見られません。このツールは見つけたJSONの変更を1行1件のJSONLへ保存します。

ゲームプロセスやATM内部にはアクセスしません。modの出力ファイルを読むだけです。入力のJSONファイルを変更しません。

## Windowsでの実行

1. Python 3.10以上を用意する。
2. ZIPを展開したパッケージのルートでターミナルを開く。
3. 次を実際のインストールパスに書き換えて実行する。

```powershell
py -3 tools\record_telemetry.py --mod-dir "D:\Games\World_of_Warships\bin\12345678\res_mods\PnFMods\WowsExtractor" --output "recordings\without-atm-01.jsonl"
```

`12345678` は例です。実際のbuild番号に置き換えます。`py`がない環境ではPython 3.10以上の `python` を使用します。

ファイルがまだない状態から待機できます。戦闘を始め、必要なテストを行い、退場後に数秒待ってからCtrl+Cで止めます。端末に保存件数と保存先が表示されます。

ATMありの試行は、別名の出力へ保存します。

```powershell
py -3 tools\record_telemetry.py --mod-dir "D:\Games\World_of_Warships\bin\12345678\res_mods\PnFMods\WowsExtractor" --output "recordings\with-atm-01.jsonl" --torpedoes-only
```

10分間だけ記録する例：

```powershell
py -3 tools\record_telemetry.py --mod-dir "D:\Games\World_of_Warships\bin\12345678\res_mods\PnFMods\WowsExtractor" --output "recordings\run-10min.jsonl" --seconds 600
```

## 引数

| 引数 | 標準値 | 意味 |
| --- | --- | --- |
| `--mod-dir` | 必須 | `state.json` / `meta.json` が生成される導入先フォルダー |
| `--output` | `recordings/run-日時.jsonl` | 保存先。実行した場所を基準にする |
| `--interval` | `0.05` | 読み取り間隔の秒数。有限値で0.02以上 |
| `--seconds` | 制限なし | 自動停止までの秒数。有限な正の値 |
| `--torpedoes-only` | 無効 | `self` / `ships` / `damage` / 名簿等を保存対象から除く |

同じ出力ファイルが存在するとエラーにして保護します。追記や上書きはしません。毎回別名を使います。`state.json` / `meta.json` 自体を出力先にする指定も拒否します。

## JSONL形式

```json
{"kind":"state","observedAt":"2026-10-31T00:00:00+00:00","mtimeNs":0,"data":{"schema":1,"active":true,"ts":123.4,"torpedoes":[]}}
```

上は説明用の架空値です。各行は独立したJSONです。

| フィールド | 意味 |
| --- | --- |
| `kind` | `meta` または `state` |
| `observedAt` | 記録ツールが読んだ時刻。UTCのISO 8601表記。ゲーム内時刻ではない |
| `mtimeNs` | 入力ファイルの更新時刻。ファイルシステムの精度に依存 |
| `data` | 読み取った元JSON。`--torpedoes-only`時は指定項目の抜粋 |

`meta` と `state` は別々に読みます。同一時刻に原子的にそろった1組ではありません。`battleId` を見て照合します。初回に前の戦闘のファイルが残っていれば、それも記録されます。

## 読み取りと欠落の扱い

- JSONが半書き・不正・読み取り中に更新された場合は、その回を捨て次回再試行します。
- 同じバイト内容のファイルは再保存しません。
- `schema:1` と、stateの真偽値 `active`、魚雷配列の基本形を確認します。全フィールドを保証する完全なスキーマ検証器ではありません。
- mod自身が書かなかったフレームや、読み取り間隔の間に上書きされたフレームは復元できません。全フレームの保存保証はありません。
- 値が変わらない場合と入力が停止した場合は、JSONLの新規行だけでは区別できません。元ファイルの更新日時やログも併せて確認します。
- 読み取りが失敗したことを `active:false` や魚雷0本として偽造しません。

## 保存したtypeを見る簡単な方法

PowerShellで次を実行すると、state行ごとに時刻と魚雷情報を表示できます。

```powershell
Get-Content "recordings\with-atm-01.jsonl" | ForEach-Object {
    $entry = $_ | ConvertFrom-Json
    if ($entry.kind -eq "state") {
        foreach ($torpedo in $entry.data.torpedoes) {
            "{0} ts={1} uiId={2} owner={3} shot={4} type={5}" -f $entry.observedAt, $entry.data.ts, $torpedo.uiId, $torpedo.ownerId, $torpedo.shotId, $torpedo.type
        }
    }
}
```

`--torpedoes-only`は完全匿名化ではありません。`torpedoes[].owner.playerName`、ID、`battleId`、兵装パラメーターなどは残り得ます。共有前に内容を確認してください。
