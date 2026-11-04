# 既知の問題と実用化の到達点

0.3.32更新：砲弾道計算・専用イベント・出力を全撤去済み（未導入・実機未確認）。damage集計は維持。FPS効果は未確認。

更新：2026-11-04、ソース0.3.31。目的は潜水艦の攻撃・回避・潜航判断を補助する外部2Dマップ用modであり、汎用WoWSテレメトリ収集器ではない。完全な内部状態の解明ではなく、必要な情報を誤表示せず、通常利用を妨げないことを目標とする。不要な収集は理由・依存・互換性を確認して削減する。未確認を成功と扱わない。

## 対応タスク

FPS改善を先行する。[専用タスク・距離分岐案](FPS_TASKS.ja.md#fps-torpedoes)、[砲弾道計算の詳細と撤去](FPS_TASKS.ja.md#fps-ballistics)、[検証条件](FPS_TASKS.ja.md#fps-validation)に作業を集約する。

各問題の作業先は以下。リンク先の未完了項目で進捗を管理し、本書は問題・影響・到達点を扱う。

| 本書の問題 | 対応するTASKS |
|---|---|
| 通常利用への負荷 | [性能改善](../../TASKS.md#task-performance)、[距離別周期・削減対象](../../TASKS.md#task-scope) |
| API艦一覧とavatarの範囲差 | [取得範囲の調査実績](../../TASKS.md#task-performance)、[取得漏れ・出力契約の検証](../../TASKS.md#task-stability) |
| 魚雷・艦・pingのID対応 | [魚雷owner識別](../../TASKS.md#task-torpedoes)、[ping対象ID](../../TASKS.md#task-submarine) |
| ファイル読取りの一貫性 | [JSON更新・出力契約](../../TASKS.md#task-stability)、[読取側の取得停止・ID不一致対応](../../TASKS.md#task-consumer) |
| 戦闘ライフサイクル | [連戦・退出・観戦・撃沈](../../TASKS.md#task-stability) |
| タスク・仕様の陳腐化 | [詳細対応表・出力契約更新](../../TASKS.md#task-stability)、[用途別の棚卸し](../../TASKS.md#task-scope) |
| 可視・最終発見 | [可視候補・最終発見時刻](../../TASKS.md#task-visibility)、[アプリ側履歴への移管](../../TASKS.md#task-freshness) |
| 深度 | [対象艦・魚雷深度と深度差](../../TASKS.md#task-submarine) |
| ATM flags | [ATM対応・供給元・更新差](../../TASKS.md#task-torpedoes) |
| 選択魚雷性能 | [TTX・tooltip・ammoParams](../../TASKS.md#task-armament) |
| 管別装填 | [reload・残数・故障状態](../../TASKS.md#task-armament) |
| ping | [命中・対象・効果時間](../../TASKS.md#task-submarine) |
| Battery | [潜航能力・消費・回復](../../TASKS.md#task-submarine) |
| 消耗品・探知装置 | [範囲・状態・時刻基準](../../TASKS.md#task-submarine) |
| 位置・較正・運動 | [魚雷運動・単位](../../TASKS.md#task-torpedoes)、[別地図・境界・drift](../../TASKS.md#task-stability) |
| ダメージ・弾道 | [潜水艦用途に不要な経路の削減](../../TASKS.md#task-scope) |

距離別魚雷収集はユーザー指定により自艦から半径マップサイズ1/3より外を2Hz、内側5Hz案とする。現行は全体5Hzのまま。全魚雷API列挙と分類用位置取得が必要なら、それ自体は低頻度化できない可能性がある。後段の加工・owner取得・出力との費用を分けて判断する。詳細な分岐と周期・互換性は[FPS専用タスク](FPS_TASKS.ja.md#fps-torpedoes)へ集約。詳細診断に束ねられた潜水艦固有情報の独立化も対象。

## 優先度A：実用前に詰める問題

| 問題 | 現状・影響 | 到達点／次の確認 |
|---|---|---|
| 通常利用への負荷 | 過去にFPS低下の報告あり。B43最大216魚雷でmin30以上、B44最大63魚雷でmin40～50。modとの因果は未確定。0.3.31は較正比較を削減したが実機未確認 | まず既存offline検証を維持し、次の必要な実機試験で通常設定の継続動作・phase時間・体感をまとめて確認する。段階的な規模にし、悪化時中止。直ちに高負荷を再現させない。開始直後FPS低下はユーザー指定により追わない |
| API艦一覧とavatarの範囲差 | B39はavatar12対API ships9。API一覧だけでは観測できた地図位置・HPを落とす。avatarは別出力済み | consumerが両一覧・取得範囲を区別できる契約にする。avatar.idを未検証のままplayerIdへ確定joinしない。未取得艦を死亡扱いしない |
| 魚雷・艦・pingのID対応 | ownerIdと同state vehicleIdはB43の93,297行で候補一致、2,116行未一致。一般namespace契約なし。avatar.playerId未取得の実績あり | 確定IDと候補IDを分けたまま使える状態にする。isOwn unknownを保持し、誤った所有者・ping対象・誘導対象を表示しない |
| ファイル読取りの一貫性 | state.jsonは非原子的上書き。読取り途中に不完全JSONとなる可能性。5Hzは厳密周期ではない | 読取側の再試行・鮮度・取得失敗の扱いを確認する。書込契約を変える場合はconsumer互換性も検証。途中失敗を魚雷0本へ変換しない |
| 戦闘ライフサイクル | 開始・終了経路のoffline検証はあるが、連戦・観戦・自艦撃沈等の確認は未完了 | 戦闘切替でbattleId・終端・各履歴が混ざらないこと。次に必要な実機試験へ有用な確認をまとめる。退出ハングは再発時だけ調査 |
| タスク・仕様の陳腐化 | TASKSのチェック欄にはB42/B43/ATM実績の未反映や、取得基盤と意味検証の重複がある | 取得済み・条件限定確認・未取得・保留を分離し、同じ成功条件を繰り返し試験しない |

## 優先度B：情報の意味・用途に制約が残る問題

| 情報 | 確認済み | 残る制約・実用時の扱い |
|---|---|---|
| 可視・最終発見 | mapVisibleの遷移とfalse中の座標保持 | mapVisibleは被発見の確定値ではない。ゲーム由来の最終発見時刻は経路未発見。アプリ観測時刻と混同しない |
| 深度 | 自艦depthはHUD整合あり。魚雷depth rawは浮上・30m発射とも0.14 | 魚雷depthの単位・意味、対象艦深度・深度差は未確定。position.yや較正補助y=0で代用しない |
| ATM flags | ATMありでisHoming/isSpottedのtrue/false取得 | 第三者判定で遅延・欠測あり。サーバーの生状態、誘導対象、誘導停止理由ではない。任意機能として供給元とsample時刻を示す |
| 選択魚雷性能 | Undineで75/9が画面75kts/9kmと整合、tooltip行も取得 | 補正後live値・delta・selector修正版の実機・他艦一般は未確認。ammoParamsは空辞書の実績。静的TTXとlive値を混ぜない |
| 管別装填 | Undine6行の初期・発射後reloadが目視整合 | 物理的管番号、直接残数、発射可否、故障／破壊／修理timerは未完了。進捗からの数え上げは派生扱い |
| ping | hitCount 1→2と二重ping報告が整合。lifeTimeはUI countdown入力 | 対象ID namespace、命中区画、失効条件・時刻等は未確定 |
| Battery | 値の減少・回復、currentRate変化を確認 | 割合・残時間への換算、単位、枯渇条件等は未確定。rawとUI hintを分ける |
| 消耗品・探知装置 | B42でstate6→0→3、workTimeLeft60→約27.88取得 | enumの一般契約・終了/cooldown未確認。endTimeは約1秒変動し、固定deadlineとして外挿しない |
| 位置・較正・運動 | B43全魚雷world位置、B44全魚雷world/map位置取得。新旧較正はreplay同値 | 別地図・境界・drift等の実機検証、単位の一般契約は未完了。motionは観測差分で、寿命や残距離ではない |
| ダメージ・弾道 | damage集計は維持、砲弾道計算は0.3.32で全撤去 | damage側は依存調査後に削減判断。弾道撤去によるFPS効果は未確認 |

## 未取得のまま明示する情報

- ゲーム由来の最終発見時刻。
- 対象艦の確定深度と魚雷との深度差。
- 魚雷の誘導先ID、誘導停止距離・地点・理由。
- 魚雷の消滅理由、直接取得の残り射程・残存寿命。
- 直接取得の装填残数等、上表で未完了とした装填情報。

これらを推測で埋めて完成扱いしない。調査経路・代替案・保留理由を残し、外部マップ側でunknownを扱えるようにする。

## 当面の順序

1. 潜水艦戦闘補助に必要な項目と不要な汎用収集を分ける。タスクの重複・古い状態を整理し、取得情報・更新頻度・制約を仕様へまとめる。
2. 既存記録とofflineで読取失敗・欠測・戦闘切替等を先に確認する。
3. 実機が必要な項目だけを一つの限定試験へまとめ、0.3.31の実負荷・必要なライフサイクル確認を行う。即時再導入や通常PvPへの投入はしない。
4. 確認結果から実用上のblockerを再評価する。未解明の内部値すべてを解明し終えることを、無条件の試験継続理由にはしない。

根拠：[TASKS](../../TASKS.md)、[出力仕様](OUTPUT_SPEC.ja.md)、[B44](PERFORMANCE_B44_TORPEDO_PROFILE.ja.md)、[B43](VALIDATION_B43_OTHER_OWNER_LOAD.ja.md)、[B42](VALIDATION_B42_DEPTH_LOCATOR.ja.md)。
