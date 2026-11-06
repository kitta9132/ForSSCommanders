# 導入・削除・設定

## 対象と前提

対象は元プロジェクトと同じWG版WoWS PCクライアントのModsAPI v1です。現行buildとの適合性をこれから確認します。Legends、Blitz、別運営版への互換性は確認していません。
ゲーム内側はPython 2.7を前提とするソースです。`Main.py` をWindowsのPython 3で直接実行しないでください。

導入・構成変更・ATMの入れ替えは、ゲームを終了してから行います。

## 1. コピー先を確認する

一般的な場所は次のとおりです。

```text
<WoWSのインストール先>\bin\<実際のbuild番号>\res_mods\
```

`bin` に複数buildが残ることがあります。通常は最大の番号が候補ですが、**実際に起動するbuildを確認してください**。Steamなどでもランチャーのインストール先を開き、同じ内部構造を確認します。
フォルダーがない場合だけ作成します。ZIPのルート全体をゲームフォルダーへコピーする必要はありません。

## 2. バックアップする

- 既存の `res_mods/PnFMods/WowsExtractor/` があれば、ゲームの `PnFMods` 外へ退避します。
- 既存の `res_mods/PnFModsLoader.py` を保管します。
- 設定を引き継ぐ場合は、元の `config.ini` を保管します。

同名コピーを `PnFMods/WowsExtractor_backup` として残すと、modが二重に読み込まれる可能性があります。バックアップは `PnFMods` の外へ置きます。

## 3. mod本体をコピーする

配布物の `res_mods/PnFMods/WowsExtractor/` を丸ごとコピーします。0.3.30の必要Python sourceは9個と、任意の設定ファイルです。

```text
Main.py                  エントリーポイント、イベント、スナップショット、書き込み
battle_identity.py       戦闘IDの管理
damage_tracker.py        既存のダメージ収集
emit_guard.py            退場後に古い活動中フレームを出さないための判定
ui_health.py             既存のUI由来HPの補助
torpedo_telemetry.py     今回追加した魚雷・発射元・自艦兵装の収集
submarine_telemetry.py   潜水艦・WaveHitの限定診断
map_calibration.py      移動履歴からの地図座標較正
performance_profiler.py opt-in game-thread phase集計
config.example.ini      設定テンプレート
```

初期状態では `.pyc` は配布していません。以前の異なる版のファイルを混在させないよう、既存フォルダーを退避してから入れる方法が確実です。

## 4. ローダー用ファイルを確認する

`res_mods/PnFModsLoader.py` がすでにあればそのまま使用します。なければ同梱ファイルをコピーします。

**同梱の `PnFModsLoader.py` は0バイトです。欠損ではありません。** 公式の導入例で空のファイルの作成が指示されており、この構成を採用しています。既存の非空ファイルを空ファイルで上書きしません。

出典：[公式資料の導入例](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/ShipModification/extracting_ship_resources.md)。

## 5. 設定する

任意で `config.example.ini` を同じフォルダーに `config.ini` としてコピーします。Windowsでは拡張子の非表示に注意し、`config.ini.txt` にしないでください。

```ini
collection_enabled = false
diagnostics_enabled = false
profiler_enabled = false
diagnostics_interval = 1.0
state_interval = 0.2
```

| 設定 | 標準値 | 意味 |
| --- | --- | --- |
| `collection_enabled` | `false` | `true`を明示した場合だけ収集を開始 |
| `diagnostics_enabled` | `false` | `collection_enabled=true`時に診断probeを許可 |
| `profiler_enabled` | `false` | collection有効時だけclockを初期probeし、game-thread区間を集約 |
| `diagnostics_interval` | `1.0` | 診断一式を実行する秒間隔。非due tickは古いprobeを再利用しない |
| `state_interval` | `0.2` | `state.json` の収集・出力を行う目安の秒間隔。0.2=約5Hz、0.1=約10Hz |
| `self_depth_sampling_enabled` | `false` | collection有効時に自艦深度群をcore周期で独立採取 |
| `battery_sampling_enabled` | `false` | collection有効時にBatteryを比較共通1Hzで独立採取 |
| `wave_hit_sampling_enabled` | `false` | collection有効時にWaveHitをcore周期で独立採取 |
| `gun_reload_sampling_enabled` | `false` | collection有効時にgun raw／progressをcore周期で採取。modifier参照探索なし |

`state_interval` は0.02秒未満を0.02に丸めます。これは50Hzの保証ではありません。ゲームのtick、処理時間、非同期書き込みの状況によってフレームが省略されます。既定は0.2（約5Hz）のcore周期です。HP平均2Hz、比較・damage約1Hz、距離別魚雷等の群別期限は別に維持し、実sample時刻を参照します。0.1（約10Hz）ではcoreの取得・構築・書込み回数が増え、FPS改善は未確認です。
`diagnostics_interval` は0.1秒未満を0.1に丸めます。FPS改善を保証する設定ではありません。
通常の有限な正の数を設定します。不明な設定キーは無視されます。設定は読み込み時と戦闘開始時に読み直されます。戦闘中の変更を即時反映する仕組みではありません。

0.3.30の`torpedo_state_provider`は、魚雷state候補の供給元を実行時に明示する設定です。未指定または`unknown`の既定では従来どおりproducer unknownとして扱い、ATM等の存在を推測しません。`advanced_torpedo_marker`を明示した場合だけ、ATM由来の導出値であることをdeclared producerとして区別します。これはATMの導入・実行・値の実在を証明せず、`isSpotted`は推定・第三者判定、`isHoming`も第三者判定で、ゲーム／サーバーの生boolではありません。provider出力の厳密なfield schemaは実装側で確認中であり、この文書では固定しません。`torpedo_state_sampling_enabled`は既定falseのままで、OFF時は追加probe/API呼出しを行いません。

## 6. 初回確認

1. 起動して訓練戦に入る。
2. modフォルダー内に `meta.json` と `state.json` ができるか確認。
3. `state.json` の更新日時が進むことを確認。
4. `meta.json` の `mod.version` が `0.3.39-own-torpedo-cadence` であることを確認。
5. 魚雷発射後に `torpedoes` を確認。[実機テスト手順](TEST_PLAN.ja.md)に進む。

## ATMとの併用

このmod単体のcore出力にはATMは不要です。最初はATMなしで確認し、その後、現行クライアントに対応したATMと作者指定の依存modを別途導入して比較します。
0.3.30では、ATMを魚雷state候補の**実行時の導出供給元**として明示指定できます。ATMが必要になるのはこの導出state連携のためであり、公開Torpedo APIの基本情報やコア収集のためではありません。ATMの自動ダウンロード・同梱・改変は行いません。
ATMのファイルや署名は編集しません。本パッケージはATMを読み込ませたり改変したりしません。

同梱の `install-13357625.bat` の既定は、従来どおりATMなし条件です。ATM専用のロード対象ファイルを `res_mods\_wowsmod_backups\ATM_disabled_<日時>` へ自動で移動します。

```text
res_mods\PnFMods\AdvancedTorpedoMarkerPy\
res_mods\gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound
res_mods\gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound
```

共有依存の `res_mods\PnFMods\TTaroModUtils` と `res_mods\PnFModsLoader.py` は移動しません。ATM専用schemaと画像も移動しません。ATMありのテストへ進むときは `restore-atm-13357625.bat` で戻します。復元はmanifestに記録されたATM専用パスだけを対象にし、復元先に同名ファイル／フォルダーがある場合は上書きせず停止します（fail closed）。詳細は [バージョン固定インストーラー](INSTALL_BAT.ja.md) を参照してください。

ATMを退避せずcollectorだけを入れる場合は、明示的にoptionを付けます。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-wowsmod.ps1 `
  -Build 13357625 `
  -GameRoot "C:\Program Files (x86)\Steam\steamapps\common\World of Warships" `
  -WithAtm -DryRun
```

`-WithAtm`（別名`-KeepAtm`、wrapperでは`--with-atm`）はATM専用ロードファイルが存在する場合だけ退避を省略します。ATMが見つからない場合は何も残さず、通常のcollector導入を続けます。インストーラーがATMを検出しても、それがstate producerとして動作している証明にはなりません。ATMの有無やユーザー指定だけではproducerを実証できないため、値はdeclared producer／unverifiedとして扱います。
手動でコピーする場合も、ATMを残すかどうかを明示し、上記3つを勝手に削除・移動しないでください。

## 削除・元に戻す

ゲームを終了し、今回コピーした `PnFMods/WowsExtractor/` を削除または `PnFMods` 外へ移動します。元の版を使っていた場合はバックアップを戻します。
`PnFModsLoader.py` は他のmodも使用します。他のModsAPI modがある場合は残します。
ATMをインストーラーで退避した場合は、必要に応じて `restore-atm-13357625.bat` を実行します。
`state.json` / `meta.json` は生成物です。必要なテスト記録を保管した後に削除できます。

## ゲーム更新後

起動buildが変わると古い `res_mods` は使われなくなる場合があります。新buildのフォルダーを確認して導入し直します。ATMなど他のmodの対応状況とは別に、本modの動作も再確認します。
