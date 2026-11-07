# B49：0.3.41 起動失敗（0.3.42 で有効記録取得済み）

2026-11-07、build13533378。

**訂正：本資料の当初のタイトル「B49：0.3.41 起動失敗（無効試験）」は、0.3.41 試行時点の記録が無効であったことを示すもので、B49 全体が無効という意味ではなかった。**
その後の `0.3.42-launch-restricted-builtins` 起動で `recordings/without-atm-b49.jsonl` に **1,059 records（1 meta + 1,058 state）の有効な記録**が取得された。詳細解析は `PERFORMANCE_B49_TEAM_BUDGET_0.3.42.ja.md` を参照。

## 0.3.41 試行時の条件

- ATMなし。
- `recordings/without-atm-b49.jsonl` が 0 byte。
- `meta.json` / `state.json` なし。
- ゲーム PID 22580 動作中、recorder PID 17048 待機中（.41 試行時）。
- ゲーム／導入／record 停止変更は行わず（親担当）。

## 観察された障害

`profile/python.log` において、10:48:02 と 10:50:44 の両方で `WowsExtractor` 起動時に以下の例外が記録された：

```
NameError: global name 'globals' is not defined
```

## 原因

0.3.41 で追加した TTaro Mod Config 連携・魚雷サンプリング設定の正規化ヘルパーへのアクセスに `globals().get(...)` を使用していた。WoWS クライアントの Python 2 ランタイムは `globals` を含まない restricted builtin 名前空間を提供しており、`Collector.__init__` の初期段階で `NameError` が発生し、mod のコアが全く起動しなかった。

該当箇所：

- `_load_config` 内 `normalize_torpedo_sampling_settings` の解決
- `queue_torpedo_sampling_settings` 内同上
- `torpedo_sampling_ui_contract` 内 `torpedo_sampling_ui_contract` の解決
- `_ensure_torpedo_prefs_adapter` 内 `PrefsAdapter` の解決
- `_discover_torpedo_prefs_binding` 内 `build_ttaro_prefs_binding` の解決
- `_subscribe_torpedo_prefs_load_complete` 内 `events` の解決

## 対応（0.3.42）

- `globals().get(name)` を直接のモジュールグローバル参照に置き換え、存在しない場合は `NameError` を捕まえて `None` として扱う。
- `events` のような optional なトップレベル import は `try/except NameError` で保護し、import 失敗時もコアが継続する。
- restricted builtin 名前空間（`globals` なし）下で `import -> instantiate -> load-complete -> battle start -> battle shown -> tick` の実起動経路を再現する回帰テストを追加。TTaro フレームワーク有無の両方でコアが停止しないことを検証。
- 既存の strict bool / ini broader / UI ranges / 敵 20 policy 等の契約は維持。

## 0.3.42 による有効記録

- 11:36:22（JST）に `WowsExtractor loaded v0.3.42-launch-restricted-builtins` で正常ロード。
- 11:40:11（JST）に telemetry 書き込み開始、`meta.json written (24 players, ready=True)`。
- `recordings/without-atm-b49.jsonl`：185,309,892 byte、SHA256 `991c37056d63cade3766282ab714d67aa5627a484f30ff1e53a0a9015902b00e`、1,059 records、最終フレーム `active=false`。
- 0.3.42 成功以降、python.log 上で WowsExtractor／collector／UserDataGate／schema の ERROR は確認されなかった。

## 結論

- **0.3.41 試行**：mod コアが `NameError: global name 'globals' is not defined` で起動せず、**無効試験**であった。
- **0.3.42 試行**：上記修正後、mod は正常にロードし、**B49 として有効な 1,059 records の記録を取得した**。
- 実機での team-torpedo-budget 動作の詳細は `PERFORMANCE_B49_TEAM_BUDGET_0.3.42.ja.md` に匿名集計済み。
