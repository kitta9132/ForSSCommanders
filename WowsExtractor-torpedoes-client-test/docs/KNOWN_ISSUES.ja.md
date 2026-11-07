# 既知の問題と実用化の到達点

0.3.45-slow-information-groups：0.3.44 の自艦判定を維持しつつ、③遠距離艦 world position/yaw、④⑤自艦システム群（radar/hydro/locator/consumables）、⑥魚雷 module 群、⑩較正診断 snapshot を独立した 1 Hz 群に分離。minimap の `nx`/`ny`/visibility/IDs、HP 群、avatar 比較群、魚雷分類の動作は変更しない。各群は独立した `enabled`/`interval` 設定を持ち、OFF は core cadence（毎tick）に戻す。`ship_world_position_far_divisor`（既定5）で較正 world 半径を計算し、自艦 world position と各艦 map 座標の `map_to_world` 推定から far/near を判定。較正未成立・自位置不明・model 未確定艦は core で読む。非 due far 艦は `ship.getPosition()` を呼ばず、推定 world 値で補完もしない。`MapCalibration.observe()` は後方互換のため `update()` + `snapshot()` に委譲。core path では `update()` + `live_model_status()` を使い、重い診断 snapshot は独立 1 Hz ゲート `map_calibration_snapshot_interval` で出力する。offline 検証のみで**未導入・未実機**、実機 FPS 改善・周期の実戦確認は未達。FPS 改善を主張しない。研究用 `high_budget_25` は研究のまま維持する。

0.3.44-self-owner-id（履歴）：魚雷の自艦判定を `owner.isPlayer` から、同一 snapshot の `battle.getSelfPlayerInfo().shipId == torpedo.ownerId` へ変更。`owner.isPlayer` は `owner` 行に生の観測値として残すが分類には使わない。`isOwn`・`isOwnSource`・`isOwnReason` を sample 済み行へ公開。自艦（`isOwn is True`）は全距離 HIGH で敵予算外、確認済み味方（同一チームかつ `isOwn is False`）は全距離 LOW（初観測含む）、敵は半径内の最近 `enemy_high_budget` 本（既定20）だけ HIGH。チーム不明・距離不明・同一チームで `isOwn` 不明は安全側 HIGH。型不一致・self shipId 欠測は `isOwn: null`（unknown）とし味方と誤分類しない。`self.shipId` は毎 sample 新鮮に取得し cache/fallback しない。半径・周期（近0.2秒／遠0.5秒／5秒再分類）は0.3.40のまま。TTaro Mod Config 連携・UI adapter 契約も維持。offline検証のみで**未導入・未実機**、実機周期・負荷・分類一致は未確認。FPS改善や実機取得時間短縮を主張しない。研究用`high_budget_25`は研究のまま維持する。\n\n0.3.43（履歴）：自艦 ID candidate 観測。`battle.getSelfPlayerInfo()` から `id`（playerId）と `shipId`、`battle.getSelfPlayerShip()` から公開 `uiId`、Ship 非公開属性候補 `_Ship__id`/`id`/`vehicleId` を別々の candidate として記録。B50 では `getSelfPlayerInfo().shipId` と自艦発射魚雷の `ownerId` が全行厳密一致。`isOwn` 上書きは行わなかった。

0.3.40（履歴）：魚雷分類半径を`R=L/5`（`L=min(mapWidth,mapHeight)`の較正world長）へ正式変更。L/5～L/3帯はLOWになり、自艦は全距離HIGH（0.2秒期限）、他は近5Hz／遠平均2Hz、5秒再分類を維持する。offline検証のみで未導入・未実機、L/5と自艦5Hzの実機周期は未確認。以下の実機根拠は0.3.38で、L/3の履歴である。

0.3.39（履歴）：自艦と厳密bool `owner.isPlayer is True` で確認できた魚雷を全距離HIGH（目標5Hz）に変更。当時の分類半径はL/3。offline564 tests・9 module checker成功。未導入・未実機。所有者不明は距離ルールに従い、low非dueで再確認しない。

## 到達点サマリー（0.3.38・ATM B09後）

追加の[ATM B09負荷試験](PERFORMANCE_WITH_ATM_B09_0.3.38.ja.md)で、minFPS約30になると体感カクつきありと報告。記録上最大95本、near約85%で全detail削減は約9%。遠距離枠は実際に約2Hzで動作したが、負荷課題は未解決。新build・ATMありで条件が変わり、FPSとphaseの時刻同期もないためmod単独の因果は未確定。near情報削減を即採用せず固定費／同期出力の情報維持型改善を調べる。試験後退避済み。

- 0.3.38実装版で全555 tests＋9 module checker成功。
- B46実機（0.3.38・heavy OFF・独立4群ON）：1,335 records（active 1,333）。ユーザー報告 minFPS 約50以上・カクつきなし（録画なし）。HP 2 Hz／比較・damage 1 Hz・非due省略、独立 phase 計上を確認。depth／WaveHit／gun 全1,333 available、Battery 272 available／1,061 notSampled。
- FPSタスク：AのofflineとATM B09でのnear／far実周期確認、B撤去、C実装・独立取得、Dの既存回帰と限定実機試験は実施済み。最終実用FPSは未達。Eは①②③④⑤⑥⑦⑧⑨⑩を0.3.45までに実装。ただし実機確認・因果的FPS改善率は未達。
- ATM B09で最大95魚雷時の負荷を観測し、ユーザーはmin30程度で体感カクつきを報告。200本規模・因果的FPS改善率は未検証。startup追跡中止、同条件再試験は即要求しない。
- 初回 pinger 選択はユーザー見解で仕様上おそらく回避不可とみなす。TTX 値は合っていたため現行初回 variant 表示候補を実用受入済み。スキル発動時の実戦値／動的補正は未確認だが、追加取得・再試験は行わず受入済みとする。`selectedTTXnotApplicable`・`ammoParams={}` は阻害課題として再オープンせず、source／raw／`liveAdjusted=false` 契約を維持。

## 版別到達点（履歴）

魚雷性能の受入更新：ユーザーがTTX値の一致を確認し、初回TTX variant表示候補を現状で実用上受け入れた。初回pinger選択／ammoParams空は追加取得の阻害課題としない。スキル発動による実戦値と動的補正は未確認として残すが、この確認のための追加実機試験は要求しない。[B46](VALIDATION_B46_0.3.38.ja.md)。

B46詳細確定：独立4群の取得経路は今回の条件で実機確認済み。ただし初回pinger選択のため選択魚雷TTXは対象外、variant表示候補75／9・ammoParams空。必要性能が初回だけで必ず揃うとは保証しない。[装填・性能タスク](../../TASKS.md#task-armament)／[B46](VALIDATION_B46_0.3.38.ja.md)。以下の詳細解析中表記は履歴。

[B46実機](VALIDATION_B46_0.3.38.ja.md)：0.3.38・heavy OFF・独立4群ONでminFPS約50以上／カクつきなし（ユーザー報告）。HP／比較／damage周期と非due省略・独立phase計上を確認した。最大6魚雷・low群0なので遠距離と大量魚雷のFPS課題は未解決。停止・13fileshash照合退避済み。初回性能と各独立rawの詳細解析はB46記録で確認済み（以下は当時の記録）。

0.3.38：[FPS C](FPS_TASKS.ja.md#fps-other)の装填raw独立取得を実装。gun／submarine独立群は既定OFF、意味未確定を維持。B46で限定条件のFPS報告はあるが、因果的FPS改善率・遠距離2Hz・多数魚雷FPSは未確認。mod退避継続。

0.3.37：[FPS C](FPS_TASKS.ja.md#fps-other)の自艦深度／Battery／WaveHitを診断から独立化（既定OFF）。群ごとのsampleTsと非dueを参照する。WaveHit対象namespace／TTL・装填数／管IDは未解決のまま。gun独立runtimeは0.3.38で統合、独立4群の実機可用性はB46で確認済み。FPS効果は未確認、mod退避継続。

0.3.36：[FPS C](FPS_TASKS.ja.md#fps-other)のdamage snapshot生成・出力1Hz化を実装。イベント全受付・終了時最新台帳を維持する。潜水艦の個別read選択は基盤のみで独立runtimeは未完。ゲーム導入・FPS検証は保留継続。

0.3.35更新：HP群平均2Hz・avatar比較1Hzを実装。位置と必要IDは5Hz維持し、非dueのHPを現在値として持ち越さない。付属viewerの過去HP表示はsample時刻付き。実機FPSは未確認。[△コード棚卸し](CODE_AUDIT_PARTIAL_ITEMS.ja.md)では未知を閉じる新実測はなく、装填・修理timer・WaveHit対象候補・TTLを分離して記録した。

0.3.34更新：魚雷性能・弾薬paramsは戦闘初回のみのmetaへ移動し、定期TTX／tooltip性能probeも撤去。初回未準備時の欠測は固定され、再取得しない制約が残る。他情報の低頻度化は[10項目の調査](RESEARCH_SLOW_GROUPS.ja.md)と[FPSタスクE](FPS_TASKS.ja.md#fps-slow-groups)へ。HP源の重複・短期状態の取り逃し等を無条件に安全とは扱わない。

0.3.33更新：5秒距離再分類・近距離5Hz／遠距離平均2Hz、新規・不明暫定5Hzをソース実装。位置read削減を既存記録で確認したが、near中心時のscheduler固定費リスクがありFPS改善は未認定。全体membershipと今回sampleを分けた新契約・consumer対応も実装済み、実機未確認のため通常導入は保留。[予算・固定費・検証結果](FPS_TASKS.ja.md)。

0.3.32更新：砲弾道計算・専用イベント・出力を全撤去済み（未導入・実機未確認）。damage集計は維持。FPS効果は未確認。

更新：2026-11-04、ソース0.3.31（旧更新）。目的は潜水艦の攻撃・回避・潜航判断を補助する外部2Dマップ用modであり、汎用WoWSテレメトリ収集器ではない。完全な内部状態の解明ではなく、必要な情報を誤表示せず、通常利用を妨げないことを目標とする。不要な収集は理由・依存・互換性を確認して削減する。未確認を成功と扱わない。

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

距離別魚雷収集は、0.3.40で自艦から半径`L/5`（L=マップ短辺の較正world長）より外をLOW平均2Hz、内側・境界上をHIGH 5Hzとする。0.3.33～0.3.39はL/3だった。offline 実装は0.3.33で完了し、B43／B44 replay・216魚雷fixtureで検証済み。L/5の実機near／far周期・自艦全距離HIGH・最終FPS判定は未完（B09のnear／far実周期確認はL/3時点の履歴）。全魚雷API列挙と分類用位置取得が必要なら、それ自体は低頻度化できない可能性がある。後段の加工・owner取得・出力との費用を分けて判断する。0.3.44 では自艦判定を `owner.isPlayer` から `battle.getSelfPlayerInfo().shipId == torpedo.ownerId` へ変更。0.3.45 では艦 world position/yaw、自艦システム群、魚雷 module 群、較正診断 snapshot を独立 1 Hz 群に分離した。詳細な分岐と周期・互換性は[FPS専用タスク](FPS_TASKS.ja.md#fps-torpedoes)へ集約。詳細診断に束ねられた潜水艦固有情報の独立化も対象。

## 優先度A：実用前に詰める問題

| 問題 | 現状・影響 | 到達点／次の確認 |
|---|---|---|
| 通常利用への負荷 | 過去にFPS低下の報告あり。B46（0.3.38・heavy OFF・独立4群ON）でユーザー報告minFPS約50以上・カクつきなし。0.3.45で③④⑤⑥⑩を1Hz化したが、実機確認・因果的改善率は未検証。B43最大216魚雷でmin30以上、B44最大63魚雷でmin40～50の記録も残る | 既存offline検証を維持し、必要な実機試験では段階的な規模・悪化時中止を徹底。開始直後FPS低下は追わない。同条件再試験を直ちに追加しない |
| API艦一覧とavatarの範囲差 | B39はavatar12対API ships9。API一覧だけでは観測できた地図位置・HPを落とす。avatarは別出力済み | consumerが両一覧・取得範囲を区別できる契約にする。avatar.idを未検証のままplayerIdへ確定joinしない。未取得艦を死亡扱いしない |
| 魚雷・艦・pingのID対応 | ownerIdと同state vehicleIdはB43の93,297行で候補一致、2,116行未一致。一般namespace契約なし。avatar.playerId未取得の実績あり | 確定IDと候補IDを分けたまま使える状態にする。isOwn unknownを保持し、誤った所有者・ping対象・誘導対象を表示しない |
| ファイル読取りの一貫性 | state.jsonは非原子的上書き。読取り途中に不完全JSONとなる可能性。5Hzは厳密周期ではない | 読取側の再試行・鮮度・取得失敗の扱いを確認する。書込契約を変える場合はconsumer互換性も検証。途中失敗を魚雷0本へ変換しない |
| 戦闘ライフサイクル | 開始・終了経路のoffline検証はあるが、連戦・観戦・自艦撃沈等の確認は未完了 | 戦闘切替でbattleId・終端・各履歴が混ざらないこと。次に必要な実機試験へ有用な確認をまとめる。退出ハングは再発時だけ調査 |
| タスク・仕様の陳腐化 | TASKS/FPS_TASKSを0.3.38/B46の到達点で整理済み。古い版の記述は履歴として参照 | 取得済み・条件限定確認・未取得・保留を分離し、同じ成功条件を繰り返し試験しない |

## 優先度B：情報の意味・用途に制約が残る問題

| 情報 | 確認済み | 残る制約・実用時の扱い |
|---|---|---|
| 可視・最終発見 | mapVisibleの遷移とfalse中の座標保持 | mapVisibleは被発見の確定値ではない。ゲーム由来の最終発見時刻は経路未発見。アプリ観測時刻と混同しない |
| 深度 | 自艦depthはHUD整合あり。魚雷depth rawは浮上・30m発射とも0.14 | 魚雷depthの単位・意味、対象艦深度・深度差は未確定。position.yや較正補助y=0で代用しない |
| ATM flags | ATMありでisHoming/isSpottedのtrue/false取得 | 第三者判定で遅延・欠測あり。サーバーの生状態、誘導対象、誘導停止理由ではない。任意機能として供給元とsample時刻を示す |
| 選択魚雷性能 | Undineで75/9が画面75kts/9kmと整合、tooltip行も取得。ユーザーは現行の初回TTX variant表示候補を実用受入済み | 補正後live値・delta・selector修正版の実機・他艦一般は未確認。ammoParamsは空辞書の実績。selectedTTXnotApplicable／ammoParams空を阻害課題として再オープンせず、追加取得・再試験は行わない。静的TTXとlive値を混ぜない |
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
