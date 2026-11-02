# 潜水艦・WaveHit state のUI意味根拠

## 範囲と結論

静的参照は `C:/Users/kitta/Documents/playground/wows-mods/mino-smoke/research/extracted/gui/data/Components.xml`、同 `gui/data/constants/battle.xml`、同 `gui/unbound2/pc/battle/`。実機根拠は既存の [B27潜水艦記録](VALIDATION_0.3.12_B27_SUBMARINE.ja.md) と [B27 WaveHit記録](VALIDATION_0.3.12_B27_WAVEHIT.ja.md) のみ。外部抽出物は現在の公開UI配線・表示契約の根拠として扱い、B27の実データ値への後方適用やサーバー内部状態一般の断定には使わない。

| データ | UI用途として根拠があること | 確定しないこと |
|---|---|---|
| Submarine `depth` | World markerは `depth` を読み、`round(depth * 10) / 10` で小数1桁表示し、`IDS_METER` を添える。Telegraphもcurrent depthに `m` を付ける。UI表示値の単位はメートル、表示精度は0.1 m。 | raw値のサーバー上の一般的定義・基準面や、他クライアント版への不変性。UI用途の根拠を越えて推測しない。 |
| `depthIndex` | `DEPTH_STATE` enumと一致する用途。Main HUDは `> PERISCOPE` を水中判定に使う。 | 全艦・全条件の物理深度区間境界。 |
| `nearestDepthIndex` | Telegraphで深度目盛りの `$index` と比較してnearest目盛りを選択表示する。 | それ自体を物理深度状態enumや常時同一の `depthIndex` とみなすこと。 |
| `showDepth` | World markerの深度表示の可視条件。 | 深度の値・状態の代替。 |
| Battery `value` | HUDは `floor(value)` を整数化して `countdownFormat` に渡す。艦markerのBattery barは `value / maxCapacity` を描画比率にする。 | B27値を%と解釈すること、あるいはHUDの別カウントダウン表示をBattery残時間と解釈すること。 |
| Battery rates | HUDは `abs(baseSpendRate)` と `abs(currentRate)` を表示・burning multiplier向けに読む。 | raw rateの符号・単位やそこからの残時間算出。 |
| `batteryState` | Constantsのenum: `IDLE=0`, `CHARGING=1`, `FROZEN=2`, `SPENDING_NORMAL=3`, `SPENDING_WARNING=4`, `SPENDING_CRITICAL=5`, `BURNING=6`, `EMPTY=7`。HUDはアイコン・色・警告表示に使う。 | enum値から任意の消費率・回復率や履歴を補完すること。 |
| WaveHit timer | `wave_hit_marker.unbound` は `lifeTime` を直接 `countdownFormat(lifeTime, …)` に渡し、`alertTime` 未満で小数1桁・橙色へ切替。直後に `IDS_SECOND_SPACE` を表示する。従って当該markerの残タイマー表示値は `lifeTime`、単位表示は秒。 | `maxLifeTime - lifeTime` の計算や、`maxLifeTime` を基準としたcountdown。UIにはその計算がない。 |
| WaveHit `hitCount` / `isActive` | `hitCount` はアイコン名の末尾に使う（falsey時は1）。`isActive` はShellTracker時のactive crossとラベル余白に使う。 | `hitCount` の一般的なping回数定義、`isActive=false` をrow消失と同一視すること。 |

## 静的参照詳細

- `Components.xml:2111-2125`: `WaveHit.targetID` はInteger primary key、コメントは `Waved vehicle ID`。`lifeTime`, `alertTime` はNumber、`maxLifeTime` はNumberかつ`sync=false`、`hitCount` Integer、`isActive` Boolean。変更eventも宣言される。
- `Components.xml:4896-4930`: Submarineのdepth/index/show fieldsと変更event、Batteryのvalue/capacity/rates/state型とevent。
- `constants/battle.xml:10-24`: `DEPTH_STATE` は `SURFACE=0`, `PERISCOPE=1`, `WORKING=2`, `INVULNERABLE=3`。Submarine componentの `depthIndex` コメントもこのenumを指す。
- `constants/battle.xml:574-588`: Battery enum値と名前。
- `unbound2/pc/battle/markers/markers_elements.unbound:952-1002`: `depth` / `showDepth` のmarker配線、0.1 m表示、`IDS_METER`。
- `unbound2/pc/battle/telegraph.unbound:727-767, 949-984`: depth valueのメートル単位、nearest indexとの比較、depth ranges/valuesのruler用途。
- `unbound2/pc/battle/main_hud.unbound:67-70`: `depthIndex > PERISCOPE` のHUD水中判定。
- `unbound2/pc/battle/submarine_battery.unbound:49-89, 108-109, 211-219`: own Battery value/rate/state読み取り、Battery valueの整数表示、stateによるUI。
- `unbound2/pc/battle/markers/markers_elements.unbound:888-898`: Battery value/maxによるmarker bar比率。
- `unbound2/pc/battle/markers/wave_hit_marker.unbound:8-18, 24-51`: WaveHit timer・閾値・秒ラベル・hitCount icon・isActive表示。

これらはクライアントUIが入力stateをどう使うかの根拠であり、状態生成元・サーバーのライフサイクル全体を規定するAPI仕様ではない。

## B27との照合

- B27 WaveHitでは同一rowで `hitCount 1→2`, `maxLifeTime 25→50`, `lifeTime 16.8837→49.9398` が同時更新。その後`lifeTime`は減少したが、終端も12.2101でrowは存在し続けた。これはUIの `lifeTime` countdownと整合し、更新がtimer再始動候補であることを補強する。ただし更新の因果条件・満了時のrow削除/`isActive`変化は観測されていない。
- UIは `lifeTime` を描画値としてcountdown formatするが、Components定義に単位注記はない。秒ラベルがあること、およびB27で約1 raw単位/秒減少した観測から当該UI表示値が秒スケールであるのは強く支持される。`maxLifeTime`の単位やサーバー契約まで拡張しない。
- B27潜水艦記録の `depth=0→30→0` はUIがメートル表示するdepth fieldの遷移と整合する。B27の `depthIndex` 数値は `DEPTH_STATE` の値と突合できるが、B27で `depthIndex=3` を観測した値のenum名は `INVULNERABLE`。値が物理深度そのものを表す、との解釈はしない。
- B27 `batteryState 0→3→1` はConstants enum上で `IDLE→SPENDING_NORMAL→CHARGING` と読め、B27のvalue減少・回復順序とも整合。rateのraw値や残時間の派生は依然行わない。

## WaveHitの更新・失効とID

**更新:** UIは各fieldのChanged eventで再読込する設計。B27ではhitCount/maxLifeTime/lifeTimeの同一sample更新と、その後の `lifeTime` 減少を確認。出力はこれらを別々のraw fieldとして保持し、timer用派生値を作る場合も、UI同様に `lifeTime` だけを使う。`maxLifeTime-lifeTime` は使わない。

**失効:** 今回読んだComponentsとUnboundの参照範囲には、WaveHit rowの削除条件、`lifeTime<=0` 時の削除、`isActive` によるrow存続制御はない。UIはmarker componentを読む側であり、失効実装の証明ではない。B27もゼロ到達/消失を記録していないので、更新後の期限・消失を確定できない。

**ID namespace:** `targetID`の唯一の明示的説明は `Waved vehicle ID`。`ship.vehicleId` / roster / selfVehicleとの等価性やjoin契約は、Components/Constants/該当Unboundから確認できない。WaveHitのrow keyがIntegerであることやmarker entityに紐づくことだけではID空間一致の証明にならない。B27は一つの匿名raw IDが不変だっただけで、値を隠し、艦IDへjoinしていない。よってtargetIDをship `vehicleId`へ推測joinしない。

**区画ID候補:** WaveHit component/UIにhit section/compartment ID fieldまたは区画マッピングは見当たらない。`hitCount`はUI上アイコン種類、`targetID`はコメント上vehicle ID。これらを命中区画IDとして扱う根拠はない。今回の限定探索から区画ID候補を提示できない。

## 次の実装案 / 未確認

- 次の出力契約案は、raw field・型・status・出所を保持する。UI用途に限定した表示派生として、depthの0.1 m表示、Battery bar ratio（分母が有効な場合のみ）、WaveHit marker countdown=`lifeTime`（秒表示）を分離して明記する。`depthIndex`/`batteryState`は公開enum名を併記してもraw整数を保持する。推測join・区画推定・timer引算・率からの残時間はしない。
- 未確認: WaveHitのサーバー側満了/削除条件、`isActive`とrow lifecycleの関係、`targetID`と船vehicle IDのnamespace一致、区画/section IDの公開契約。既存B27ではtimer失効を判定できず、同試験は再要求しない。追加の静的なID contractまたは既存ログに失効遷移が見つかった場合のみ更新する。
