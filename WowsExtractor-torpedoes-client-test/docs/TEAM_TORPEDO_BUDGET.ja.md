# 0.3.44-self-owner-id：自艦 shipId によるチーム別魚雷サンプリング

対象版：`0.3.44-self-owner-id`。0.3.40-radius-l5の距離別cadenceを土台に、**自艦判定を `owner.isPlayer` から `battle.getSelfPlayerInfo().shipId == torpedo.ownerId` へ変更**し、チーム関係と合わせて分類へ加える。距離だけの近HIGH／遠LOWは変更せず、自艦・味方・敵の扱いと敵nearの本数budgetは維持する。周期そのもの（HIGH 0.2秒／LOW 0.5秒／再分類5秒）は0.3.40のまま。

**本版はoffline検証のみで、未導入・未実機。** 実機での周期・負荷・分類一致は未確認である。研究用の`high_budget_25`（予算25）は研究のまま維持し、productionは既定20を使う。

## 分類ルール

5秒ごとの再分類と、その間に初観測した新規IDの双方で、次の順に判定する。

| 判定 | 条件 | 群 | 備考 |
| --- | --- | --- | --- |
| 自艦 | `torpedo.ownerId` が同一 snapshot の `self.shipId` と厳密一致 | HIGH（全距離） | 敵予算に数えない |
| 確認済み味方 | 厳密な同一チーム関係 かつ `isOwn is False` | LOW（全距離、初観測含む） | 初観測もLOW |
| 敵 | 厳密な敵チーム関係 かつ 有効ID・既知距離 | nearかつ予算内ならHIGH、それ以外LOW | 予算は**最も近い20本** |
| 安全側HIGH | チーム不明／敵の距離不明／同一チームだが`isOwn`不明 | HIGH | 敵予算に数えない |

- **厳密比較のみ**を使う。整数`1`・文字列・`None`・欠測を自艦や味方へ読み替えない。`ownerId`とplayer／vehicle IDの推測joinもしない。
- `owner.isPlayer` は生の観測値として `owner` 行に残るが、分類には使わない。`isOwn` は毎 sample 新鮮な `self.shipId` と比較して導出する。
- 型不一致の場合は `isOwn: null`（unknown）とし、味方と誤分類しない。
- 距離は0.3.40と同じく`distanceSquared <= R^2`をnearに含める（`R = min(mapWidth,mapHeight) / radius_divisor`）。
- 自艦HIGHは情報量削減ではなく、自艦魚雷の遠方詳細を増やす側の例外である。FPS改善策と呼ばない。

### 同一チームだが`isOwn`不明（重要）

同一チーム関係の行で`isOwn`が**厳密Falseでない**場合、自艦と区別できない。この場合を味方（LOW）へ落とすと、本来HIGHであるべき自艦魚雷を誤ってLOWへ落とす危険がある。したがって**安全側HIGH**として扱い、敵予算には数えない。これは「不明を自艦と断定する」意味ではなく、誤った低頻度化を避けるための保守側の既定である。unknown team（関係自体が不明）も同じく安全側HIGHとする。

## 敵の本数budget

- 半径内の**敵のみ**を水平距離の昇順に安定ソートし（同距離は列挙順を保持し、厳密ID値は比較しない）、先頭`enemy_high_budget`本をHIGH、それ以外をLOWとする。
- 予算超過の敵near、および半径外の敵はLOW。
- 予算の再配分は**5秒再分類のときだけ**行う。再分類間で既存のLOW敵を途中昇格しない。
- **新規の敵は初観測でただちに予算へ参加する。** 予算に空きがあればnearはHIGH、満杯または半径外はLOW。初観測自体は必ず出力する（LOWでも）。「全件いったんHIGH」のような一斉burstは出さない。
- 自艦・味方・安全側HIGH（チーム不明／距離不明）は予算枠を消費しない。

## 分類stateと安全側

- 各entryは`group`・`nextDue`・`provisional`・`identity`・`classifiedTs`・`distanceStatus`・`distanceSquared`・`firstSeen`・`teamClass`・`isOwn`を保持する。ゲームobject・owner object・前回位置は保持しない。
- 初観測・安全側は`provisional=True`。再分類後は原則`provisional=False`。
- **分類context喪失時**：自艦はHIGHのまま、確認済み味方はLOWのまま、それ以外（敵・不明）は安全側HIGH。contextが戻っても次回5秒再分類まで昇格状態を維持する。

## 設定とUI adapter契約

設定の単一情報源は`TorpedoSamplingSettings`（`torpedo_telemetry.py`）。`normalize_torpedo_sampling_settings()`がclamp込みで検証し、不正入力でも例外を出さない。

| 設定キー | 既定 | 範囲 | 意味 |
| --- | --- | --- | --- |
| `radius_divisor` | 5.0 | 1.0–100.0 | 分類半径 `min(mapWidth,mapHeight) / N` |
| `enemy_high_budget` | 20 | 1–512 | 半径内でHIGHを維持する最近敵の本数 |
| `high_interval` | 0.2 | 0.02–600 | 内部。HIGHの期限 |
| `low_interval` | 0.5 | 0.02–3600 | 内部。LOWの期限 |
| `classification_interval` | 5.0 | 0.05–3600 | 内部。再分類間隔 |
| `ally_low` | true | — | 内部。確認済み味方をLOWにする |

`radius_divisor`と`enemy_high_budget`の**contract／ini範囲**は上表の広い範囲（`1.0–100.0`／`1–512`）である。一方、TTaro Mod Configパネルが表示・編集する**UI安全範囲はこれより狭く、`enemyHighBudget`=1–64／`radiusDivisor`=2.0–10.0**で、配布schema（`res_mods/ModSchemas/kitta-wows-extractor.schema.json`）と一致する。範囲外clampは**UI入力経路でのみ**行う。ini fallbackの広い値（例：`enemy_high_budget=100`）を狭いUI範囲へ勝手に丸めない。パネルが無い環境ではMainのini値は変更しない。

`config.example.ini`へ次の2キーを追加した（省略時は既定、不正値は既定、clampのみ適用）。

```ini
torpedo_sampling_radius_divisor = 5
torpedo_sampling_enemy_high_budget = 20
```

**UI adapter契約**`torpedo_sampling_ui_contract(settings=None)`は、上記のうち**`radius_divisor`と`enemy_high_budget`の2つだけ**を公開する。残りは`internalFields`として扱い、外部config層へ出さない。

**TTaro Mod Config連携（0.3.41で自作接続済み・ソース登録対応済み／実機表示は未確認）**：

- 自作adapter `ttaro_prefs_adapter.py`（`PrefsAdapter`）と自作bridge `ttaro_prefs_binding.py`を追加した（どちらも本プロジェクトの自作コード。TTaroModUtils／ModForgeのコードはimport・コピー・改変しない）。
- Mod作者`kitta`、slug`wows-extractor`、component `modPrefs.kitta.enemyHighBudget`／`modPrefs.kitta.radiusDivisor`、contract key `enemy_high_budget`／`radius_divisor`（既定20／5.0）。schemaは`res_mods/ModSchemas/kitta-wows-extractor.schema.json`。
- **schema中央登録のgateは無く、文字規約のみ**（`kitta`は予約語ではない）。公式の第三者サポートや実機表示は**未確認**である。本リポジトリでは独自schemaを正本配布に同梱し、installerで`res_mods\ModSchemas`へ明示配置する。
- 値の公開面は、frameworkが全consumer向けに公開する標準表面（`mods_DataComponent`の`data.value`と`evDataChanged`）のみを読む。**設定の定期全列挙はしない**。1キーにつき1回のindexed lookupだけを行う。
- UI編集の反映：`notify`は**純スカラ値のみ**をpendingへ記録し、`tick()`で検証・適用する。bool・非数値・非有限は**現値維持**、有限数はUI安全範囲へclamp。framework不在時はbindingが`None`となり、adapterはini fallback（`source()=='ini'`）へ退避する。

## Main.py側の適用

- `Main.py`は`_load_config`でconfig値を`normalize_torpedo_sampling_settings()`へ渡し、検証済みsnapshotを作る。
- 変更は**tick冒頭のgate**（`_apply_pending_torpedo_sampling_settings`）で適用する。`apply_settings()`は期間・予算・半径を反映しつつ既存entryの期限を再アンカーするだけで、**`clear()`を呼ばない**。したがって設定変更でmotion・較正・群が消えず、一斉HIGH burstも起きない。
- UI側の補正は`queue_torpedo_sampling_settings(values)`で予約し、次のtick gateで適用する。公開2キー以外は受け付けない。
- **TTaro bridgeのライフサイクル**：adapterは`Collector.__init__`で一度だけ生成する（`_ensure_torpedo_prefs_adapter`）。bindingの解決と購読は`events.onLoadModsCompleted`（`_on_load_mods_completed`）で行い、battle開始時にも再bind（`_bind_torpedo_prefs_adapter('battleStart')`）してframe reloadに追従する。battle終了／unloadで`dispose_torpedo_prefs_adapter`が購読handleを解放し、次battleで再購読する。
- **tick順序**：`_tick`冒頭で`_consume_torpedo_prefs(now)`→`_apply_pending_torpedo_sampling_settings(now)`→frame構築の順に実行する。パネル編集がframe途中に反映されることはない。
- frameworkが無い／adapterやbindingモジュールが同梱されない場合、`_bind_torpedo_prefs_adapter`は`False`を返し、config.ini値のまま動作する（absence fallback）。

## ワイヤ出力

`sampling_wire_payload`は、summaryがdictのときだけ`sampling.teamPolicy`を**加算的に**付ける。legacy wireはbyte同一のまま変更しない。`teamPolicy`は次を含む。

- `policy`＝`'0.3.44-self-owner-id'`、`radiusDivisor`、`enemyHighLimit`
- 件数：`ownHigh`、`allyLow`、`enemyHigh`、`enemyLow`、`safetyHigh`、`unknownTeamHigh`、`unknownDistanceHigh`

sample 済み行には `isOwn`・`isOwnSource`・`isOwnReason` を追加する。旧consumerは`teamPolicy`の有無と`isOwnSource`で変更境界を判定できる。schema=1/apiVersion=1.0を維持する。

## 検証状況と既存記録

- offline：`tests/test_self_owner_id.py`（厳密一致・型不一致・self ID 欠測）、`tests/test_own_torpedo_sampling.py`（自艦判定と HIGH 維持）、`tests/test_team_torpedo_budget.py`（設定／UI契約／分類方針／予算／新規／context喪失／`apply_settings`非burst／wire／Main配線）、`tests/test_torpedo_high_budget_25_research.py`、`tests/test_far_torpedo_1hz_research.py`、既存の距離cadence・replayテストを更新して全green。B43／B44の私有replayは研究baseline 0.3.40（`LegacyTorpedoSamplingGroups`）へ固定したまま維持する。
- **未実機**：本版の実機周期・負荷・分類一致は未確認。FPS改善や実機での取得時間短縮を主張しない。
- **既存記録B48**：`recordings/without-atm-b48.jsonl`（129,060,476 bytes、最終更新2026/11/07 9:09:09）は**本版の成果物ではない**。確認時点でゲーム（PID 14432、build 13533378）が動作中で、recorderプロセスは無く、ユーザー報告は11v12（shuttle）である。この記録は既存条件として記録するに留め、0.3.44の検証結果として扱わない。内容は匿名化要約のみを参照する。
- 研究用`high_budget_25`候補・比較tool（`tools/torpedo_high_budget_25_candidate.py`等）はlegacy samplerを土台に固定し、productionへは組み込まない。

関連：[出力仕様](OUTPUT_SPEC.ja.md)、[収集頻度表](COLLECTION_CADENCE.ja.md)、[既知の問題](KNOWN_ISSUES.ja.md)、[FPS専用タスク](FPS_TASKS.ja.md)、[研究：high_budget_25](RESEARCH_TORPEDO_HIGH_BUDGET_25.ja.md)。
