# △項目のコード棚卸し：装填・ping・初回性能

2026-11-04。固定版`0f91cfe`（0.3.34）のコード・既存検証資料・testsを読んだ棚卸し。**新しい実機証拠はなく、以下の未知を解消した扱いにはしない。** HP周期分離の並行変更には依存しない。

関連：[装填タスク](../../TASKS.md#task-armament)、[潜水艦固有タスク](../../TASKS.md#task-submarine)、[次のFPSタスクC](FPS_TASKS.ja.md#fps-other)。

## 1. 装填進捗は取得済み、直接loaded countと物理管番号は別

- `torpedo_telemetry.py`の`gun_reload_probe`系はgun id/index/type/state/position/status、progress value/min/max、barrel/serialLoad参照等を出す。これらからloaded countを生成する実装はない。`weaponSlot.shotCount`や`reloadBar.rowsCount`を直接装填残数へ読み替えない。
- B14の3+3→6行READY／発射後再装填との対応は当該Undineの条件限定。gun.indexや列挙順を物理管番号とする契約はない。
- gun／gunBarrel／weaponSlotの確定joinもない。modifier宣言IDのbounded getEntity解決は候補観測であり、B14では解決unknownだった。
- 根拠：`torpedo_telemetry.py:1081-1265`（固定版）、`test_torpedo_telemetry.py`のgun/progress・推測join禁止ケース、[B14](VALIDATION_0.3.8_B14_RELOAD.ja.md)。

## 2. 修理timerは装填とは別feed

- `gunReloadProbe`にはHP・critTimerはない。これらは公開APIの`torpedoArmament.modules[]`のtype/currentHP/maxHP/state/critTimer/position。
- `MODULE_FIELDS`にはmodule IDがない。gun行と対応を確定する直接keyがないため、同一管の「装填中／故障中」を一つのstatusへ統合しない。位置・typeの類似からの対応は直接joinではない。
- critTimerはraw候補で、reload残秒や確定した修理終了時刻へ変換しない。
- 根拠：`torpedo_telemetry.py:23,3526-3545`（固定版）。

## 3. WaveHitの対象一致はcandidate、lifeTimeはTTL契約ではない

- `submarine_telemetry.py`はtargetIDを非bool有限数として観測する。WaveHitの完全列挙・partial/truncatedなし等の条件下でのみ、identityCandidatesが同snapshot ships.vehicleIdと型付き値一致を評価する。
- 一意一致でも「この観測ships集合で一致した」という候補に留まる。上流一覧の完全性やnamespaceは未確定で、targetShipIdを確定出力する経路はない。非一致から敵味方や消滅を決めない。
- lifeTimeの秒hintはUI countdown用途に限る。B27では0への到達・失効を観測しておらず、maxLifeTimeの単位・更新／失効条件も未確定。candidate一致からTTL・寿命を足さない。
- 根拠：`submarine_telemetry.py:190-216,271-277`、`torpedo_telemetry.py:1646-1933`（固定版）、`test_identity_candidates.py`のpartial・重複・型差・次frame・追加API0、[B27](VALIDATION_0.3.12_B27_WAVEHIT.ja.md)。

## 4. 初回性能へ移った後のselector実機未確認は残る

- 0.3.34のTTX selectorは`_capture_initial_torpedo_parameters`から1戦1回だけ呼ぶ。開始時の選択が不明なら選択結果も不明のまま固定する。固定variantのraw値は取得できた範囲で別に残る。
- B15/B18は選択操作後の記録であり、戦闘初回の選択準備状態を保証しない。初回限定の実用性は次の必要な実機試験へ合わせて確認すればよく、単独再試験を直ちに要求しない。
- tooltip parameter selectorはmodule内に旧診断helperとtestsが残るが、0.3.34のMainからimport・定期呼出しを撤去済み。旧△の「修正版再試験未実施」は、現在稼働している定期取得経路の保証と混同しない。
- 根拠：固定版Mainの`_start_collection`／`_capture_initial_torpedo_parameters`／`_build_meta`、`test_initial_torpedo_parameters.py`、[B18](VALIDATION_0.3.10_B18_PARAMETERS.ja.md)。

## FPSタスクCへ持ち込む条件

1. depth／Battery／WaveHit／gun reloadを詳細診断から独立化する場合、同tickのcollection共有を維持する。型付き候補joinは同sample限定のまま。
2. Batteryの低頻度化にdepth／pingを巻き込まない。装填progressとmodule修理timerも統合しない。
3. gun.progressのcandidate辞書とweaponSlot.progressのraw辞書は形状が異なる。安易なschema統一を負荷削減へ混ぜない。
4. damageのID記録処理とships用strict player indexは共通の読取り経路を持つ。集計頻度の変更時も、現在艦のIDを過去のdamage cacheで補完しない。

以上を文書化して△は維持する。今回の読取りから、同じ深度・locator・長い待機試験を追加する必要は見つからなかった。
