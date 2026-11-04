# バージョン固定インストーラー（build 13357625）

`install-13357625.bat` は、この配布物を次の固定buildへ導入するWindows用スクリプトです。

```text
C:\Program Files (x86)\Steam\steamapps\common\World of Warships\bin\13357625
```

別buildへ入れる場合は、このファイルをそのまま使わず、build番号と対象パスを確認した別スクリプトを用意してください。ゲーム更新後に古いbuildへ導入しても意味がありません。

## 使う前に

1. ゲームとランチャーを完全に終了します。起動中はインストーラーが拒否します。
2. 配布物を展開したフォルダーに、`install-13357625.bat`、`install-wowsmod.ps1`、`restore-atm-13357625.bat`、`restore-atm.ps1`、`res_mods`、`SHA256SUMS.txt` がそろっていることを確認します。
3. まず読み取り専用のdry-runで確認します。

```bat
install-13357625.bat --dry-run
install-13357625.bat --with-atm --dry-run
```

dry-runはファイルを書き込まず、管理者権限も要求しません。次を確認できます。

- 固定buildのフォルダーが存在するか
- 同梱Python 9ファイル、`config.example.ini`、`PnFModsLoader.py` が `SHA256SUMS.txt` と一致するか
- ゲーム／ランチャーが起動していないか
- 既存の `WowsExtractor` と `config.ini` があるか
- 既存の `PnFModsLoader.py` があるか
- ATM本体が見つかるか。既定ではどのファイルをどこへ退避するか、`--with-atm` では何を残すか
- 管理者権限が必要か

## 導入する

`install-13357625.bat` をダブルクリックします。`Program Files` 配下へ書き込むため、UACの昇格確認が出ます。

既定（`--with-atm` なし）で行うこと：

- **ATM本体が見つかれば、ATM専用のロード対象ファイルだけを退避します。** 退避先は `res_mods\_wowsmod_backups\ATM_disabled_<日時>` で、削除はしません。
  - `res_mods\PnFMods\AdvancedTorpedoMarkerPy\`（`Main.pyc` を含むATM本体）
  - `res_mods\gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound`
  - `res_mods\gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound`
- 退避したファイルの元の相対パスは、同じバックアップ内の `atm-disable-manifest.json` に記録します。
- ATMの共有依存 `res_mods\PnFMods\TTaroModUtils` と、他のmodも使う `res_mods\PnFModsLoader.py` は移動しません。
- ATM専用の設定スキーマ `res_mods\ModSchemas\ttaro-advanced-torpedo-marker.schema.json` と画像 `res_mods\gui\ttaro\advanced_torpedo_marker\` も移動しません。これらはATMを起動するPython/unboundではなく、設定スキーマと画像です。
- 既存の `res_mods\PnFMods\WowsExtractor` があれば、`res_mods\_wowsmod_backups\WowsExtractor_<日時>` へ**移動**してから新しいファイルを配置します。削除はしません。
- 既存の `config.ini` があれば、新しい `WowsExtractor` フォルダーへ引き継ぎます。
- 既存の `res_mods\PnFModsLoader.py` は**一切上書きしません**。存在しない場合だけ、同梱の0バイトファイルをコピーします。0バイトは仕様です。
- コピー後にSHA-256で照合します。失敗した場合は成功表示をせず、可能な範囲で元のフォルダーとATMを戻します。

成功すると、導入先とバックアップ先、`config.ini` の引き継ぎ有無、ローダーの扱い、ATMの退避先が表示されます。その後ゲームを起動し、`WowsExtractor\state.json` と `meta.json` が生成・更新されることを確認します。

### ATMを残して導入する（0.3.30の導出state連携）

ATMを魚雷state候補の実行時供給元として使う試験では、ATMを退避せずcollectorだけを入れます。

```bat
install-13357625.bat --with-atm
install-13357625.bat --with-atm --dry-run
```

PowerShellから直接実行する場合の完全な例：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-wowsmod.ps1 `
  -Build 13357625 `
  -GameRoot "C:\Program Files (x86)\Steam\steamapps\common\World of Warships" `
  -WithAtm
```

- `-WithAtm` の別名は `-KeepAtm` です。UACで昇格し直す場合も、この指定は子プロセスへ引き継がれます。
- ATM専用の3パスが存在する場合だけ退避を省略し、削除・変更はしません。
- ATMが見つからない場合は「no ATM load files detected」と表示し、collector導入は通常どおり続きます。
- dry-runでは `ATM mode : keep (explicit -WithAtm)` と、残すATMパスだけを表示します。既定の退避計画とは表示が分かれます。
- 既存の `PnFModsLoader.py` と `TTaroModUtils` は、どちらのモードでも移動・上書きしません。
- 失敗時のrollbackは、そのinstallerが実際に退避したATMだけを戻します。`-WithAtm` で元から残したATMには触れません。
- ATMが見つかっても、それはstate producerの動作証明ではありません。`torpedo_state_provider=advanced_torpedo_marker` は供給元の明示であり、値はdeclared producer／unverifiedです。

ATMは同梱・自動ダウンロードされません。必要な場合は現行クライアント対応版と作者指定の依存modを別途用意してください。

## 失敗したとき

- 画面の `[ERROR]` を確認してください。失敗時は「Installation completed successfully.」とは表示されません。
- UACをキャンセルした場合や権限不足の場合は、`install-13357625.bat` を右クリックして「管理者として実行」を選びます。
- ロールバックされた場合は、表示されたバックアップ先を確認してください。元の `WowsExtractor` は削除されていません。
- ATMを退避した後にWowsExtractorの導入が失敗した場合、ATMも自動で元の場所へ戻します。戻せなかった場合は `[ERROR]` にATMバックアップ先が表示されます。
- `--with-atm` で元から残したATMは、失敗時のrollbackでも移動・変更しません。
- ゲーム起動中、対象build不在、同梱ファイルの破損・欠落がある場合は、書き込み前に停止します。

## ATMを元に戻す（ATMありのテストへ進む）

ゲームを終了してから、`restore-atm-13357625.bat` を実行します。`res_mods\_wowsmod_backups\ATM_disabled_<日時>` のうち、まだ復元していない最新のバックアップを自動で選びます。

```bat
restore-atm-13357625.bat --dry-run
restore-atm-13357625.bat
```

- dry-runは移動計画だけを表示し、ファイルを書き換えません。
- 復元するのは `atm-disable-manifest.json` に記録されたATM専用ファイルだけです。`PnFModsLoader.py`、`TTaroModUtils`、WowsExtractorには触れません。
- 復元先に同名ファイルやフォルダーが既にある場合は、上書きせず停止します。手動で退避してから再実行してください。
- 復元後、`atm-disable-manifest.json` は `status: restored` に更新されます。バックアップフォルダー自体は記録として残ります。
- 特定のバックアップを選ぶ場合は `restore-atm.ps1` を直接使います。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\restore-atm.ps1 `
  -Build 13357625 `
  -GameRoot "C:\Program Files (x86)\Steam\steamapps\common\World of Warships" `
  -BackupDir "C:\Program Files (x86)\Steam\steamapps\common\World of Warships\bin\13357625\res_mods\_wowsmod_backups\ATM_disabled_20261031-120000" `
  -DryRun
```

`install-13357625.bat --restore-atm` でも同じ復元を呼び出せます。

## WowsExtractorを元に戻す

ゲームを終了し、今回の `PnFMods\WowsExtractor` を `PnFMods` の外へ移動します。その後、`res_mods\_wowsmod_backups\WowsExtractor_<日時>` を元の `PnFMods\WowsExtractor` へ戻します。`PnFModsLoader.py` は他のmodも使うため、導入前から存在した場合は残します。

ATMを元に戻す場合は、WowsExtractorの削除とは別に `restore-atm-13357625.bat` を実行します。

## ATMの識別根拠

このインストーラーは、次の実ゲーム build 13357625 の読み取り調査で確認した固定パスだけをATMとして扱います。

- `res_mods\PnFMods\AdvancedTorpedoMarkerPy\Main.pyc` に `AdvancedTorpedoMarkers` と `AdvancedTorpedoMarkerPy\Main.py` の文字列がある。
- `AdvancedTorpedoMarker.unbound` に `ttaro.advTorpedoMarker` の設定キーと `ATM_LOCK_SCALE` がある。
- `AdvancedTorpedoMarkerMinimapFix.unbound` が同じATMのミニマップ表示を扱う。
- `ModSchemas\ttaro-advanced-torpedo-marker.schema.json` の `modName` が `Advanced Torpedo Marker`。

ATMは [AndrewTaro/AdvancedTorpedoMarker](https://github.com/AndrewTaro/AdvancedTorpedoMarker) を指します。音響魚雷（acoustic torpedo）という別mod名ではありません。`*Torpedo*` のワイルドカードや推測で他のmodを退避しません。

## 0.3.30のATM導出state試験条件

0.3.30はsource only・未実機です。ATMを残す試験では、事前にゲームを終了し、必要なら `restore-atm-13357625.bat --dry-run` で復元計画を確認してから復元してください。復元先に同名ファイル／フォルダーがある場合は上書きせず停止します（fail closed）。

- 実行時設定は `torpedo_state_provider=advanced_torpedo_marker` を明示し、`torpedo_state_sampling_enabled=true` にする場合だけATM由来の導出stateをsampleします。既定は`unknown`／sampler `false`です。
- 負荷を増やさないため、coreは既定5Hz（`state_interval=0.2`）、state samplerは最小1Hz、heavy diagnosticsはOFF、depth samplerはOFFにします。
- FPS低下・カクつき・ロード負荷の再発が疑われたら直ちに中止し、ゲームを終了してmod/ATMを退避します。
- `isSpotted`はATM側の推定・第三者判定、`isHoming`も第三者判定です。生状態、誘導先、停止理由を保証しません。
- 同じB41操作の再試験は、ATM producerありという新しい条件のため可能ですが、現時点のユーザーへの実機依頼にはしません。

## 補足

- `.bat` と `.ps1` の表示は文字化けを避けるためASCIIのみです。この文書は日本語です。
- このスクリプトは配布物内のファイルを変更しません。導入先のゲームフォルダーだけを変更します。
- 初回は必ずdry-runで対象buildと計画を確認してください。
- ATMのファイル構成は将来のATM版で変わる可能性があります。構成が変わった場合、このインストーラーは知らないファイルを推測で退避しません。dry-runの表示と実フォルダーを照合してください。
