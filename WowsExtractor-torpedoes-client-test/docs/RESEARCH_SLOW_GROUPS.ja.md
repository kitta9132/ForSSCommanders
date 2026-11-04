# 潜水艦マップ向け低頻度化：10項目の依存・取り逃し調査

2026-11-04。基準0.3.33、⑧の定期取得撤去は0.3.34で実装。①～⑩は会話中の表の番号を固定して扱う。**本書は低頻度化の安全条件の調査であり、①～⑦⑨⑩の周期変更を実装済みとはしない。** 既存記録・コードを確認し、新規実機は依頼していない。FPS改善は未確認。

関連：[FPS専用タスク](FPS_TASKS.ja.md#fps-slow-groups)、[用途の絞り込み](../../TASKS.md#task-scope)、[既知の問題](KNOWN_ISSUES.ja.md)。

## 結論一覧

| 番号 | 情報 | ユーザー指定 | 調査結果・実装条件 |
|---|---|---|---|
| ① | 艦HP・生存値 | 2Hz | 実装可能。ただしavatar health補完と同じHP群で採取し、生存・0HP sentinel処理も同じsampleへ揃える。約0.5秒＋tick遅延の表示遅延を許容する必要がある |
| ② | avatarのHP・識別・API範囲比較 | 1Hzを検討 | **HPは①と重複**。HP sourceを1Hzにすると①へ新しいHPを2Hz供給できない。推奨はHP source2Hz、比較・coverage集計1Hz。map位置・visibilityのために必要なID読取り／列挙は別扱いで残す。avatar丸ごと1Hz化は非推奨 |
| ③ | 遠距離艦位置・yaw | 1Hzを検討 | 技術的には可能だが、中間の旋回・移動を落とし、位置が約1秒＋tick遅延だけ古くなる。近距離・攻撃対象・位置不明は高頻度を維持する設計が必要。全位置を1Hzにする案とworldだけ1Hz・map位置5Hzの保守案を区別。閾値と対象例外は未決定 |
| ④ | 自艦消耗品の残数・状態 | 1Hzを検討 | 最新状態を最大約1秒遅れで表示する用途なら条件付きで可能。**全状態遷移の記録は保証できない**。B42ではraw state0が2 frameだけで、1Hzでは観測しない位相がある |
| ⑤ | radar/hydro/locator範囲・作動状態 | 1Hzを検討 | 作動中の状態表示なら候補。ただし作動開始検知も約1秒遅れ、短い準備完了等の中間状態は落ち得る。endTimeを不変deadlineとして外挿しない |
| ⑥ | 魚雷発射装置HP・故障・修理 | 1Hzを検討 | HPの最新状態表示には候補。**故障・修理については根拠不足**。B42/B43でmodule stateは0、critTimerは全nullだった。1Hzでも故障を必ず検知できるとは言えない。装填進捗とは別群 |
| ⑦ | 自艦Battery | 1Hzを検討 | 残量・消費／回復状態の表示には条件付きで妥当。現在は詳細診断とdepth/pingに束ねられているため、**Batteryだけ独立化**する。自艦depthやWaveHitまで一緒に遅くしない |
| ⑧ | 選択魚雷の性能・弾薬params | 定期取得を削除、初回のみ | 0.3.34で実装。戦闘ごとの初回取得結果をmetaに保存。通常state・詳細診断で再取得しない。動的補正は外部マップ責務。初回の値を後続時点の補正後性能とは表示しない |
| ⑨ | damage集計出力 | 1Hzを検討 | **イベント受付を維持しsnapshot生成・出力だけ1Hz**なら可能。台帳は単調counterとは限らず、終了時は周期を待たず最新台帳を出す。非dueを空の戦果表へ変換しない |
| ⑩ | 較正の診断値・coverage | 1Hzを検討 | 診断辞書・比較集計の公開だけ1Hz化する案は成立。**observe/fit/drift・位置変換の更新とは分離**し、魚雷分類は古い診断辞書でなく現在のmodelを参照する |

「1Hzにできる」は短い変化をすべて捕捉できるという意味ではない。最新状態表示と、遷移の完全なイベント記録を混同しない。2Hzも短期状態の捕捉保証にはならない。

## ①②：共有HPとavatar依存

`Main._build_state`は同一tickのavatar captureを、roster/player対応、HP、mapPosition/visibility、avatarObservationsへ共有する。`_collect_avatar_health`が作るUI HPは`_build_ships`と`_build_self`へ補助適用される。API艦にHPがない条件ではavatarが実質的なHP源になる。B39ではavatar12に対しAPI ships9で、avatarはAPI未列挙艦の観測源にもなる。

- 推奨：**HP群2Hz／avatar照合・coverage1Hz／地図位置・必要なIDは高頻度側**。HPをships/自艦/avatarへ重複して再取得しない。
- ②のavatar HP自体も厳密に1Hzとする場合：avatar由来HPは1Hzとなり、そこから①へ供給する実効頻度も1Hz。異なるsourceのHPを別周期で出すこと自体は可能だが、同一HP値を二つの現在値として扱わず、各sourceのsample時刻・状態を分ける追加契約が必要。
- `avatar_entities=None`を渡すだけでは下流の独立呼出しが再列挙するため、getter回数が逆に増える。`AvatarRows`・ゲームcomponentをframe間保存する案は使わない。
- HPのraw value/max/isAliveと正規化・untickedFull判定は同じ採取時点で処理する。別時点のvisibilityで古い0HP sentinelを再解釈しない。
- B44の間引き調査では、HP変化の検出遅れは2Hzで最大約0.63秒、1Hzで約1.04秒という記録上の例がある。死亡edgeは同記録にないため評価不能。全条件の上限や同一IDの完全対応を証明した数値ではない。

## ③⑩：位置・較正を診断から切り離す

`_build_ships`はworld+map位置対を毎tick `MapCalibration.observe()`へ渡し、その戻り診断辞書を魚雷距離分類にも使っている。診断出力だけ1Hzへ落としても、この参照を残すと古いstatus/係数で分類する。

- 現在のmodel状態・map extentsを返す軽量accessorを用意し、魚雷分類と変換はlive modelを使う。公開diagnosticsだけsampleTs付き1Hzへ分離する。
- observe本体まで1Hzへ落とすと3 batchのdrift判定が通常約0.6秒から約3秒相当へ遅れる。今回の⑩「診断」1Hz化には含めない。
- 遠距離艦の全位置を1Hzにすると、map側でも同じ低頻度の位置となる。worldだけ1Hz・nx/nyを5Hzに残す案は描画遅延を抑えるが、元の③より削減範囲が小さい。どちらを採るかは実用上の粗さと削減費用で決める。
- 遠距離艦を較正sampleから省く場合、near-onlyでの成立・狭い移動・別地図をoffline fixtureで検証する。過去記録で成立したことを全地図の保証へ拡張しない。

## ④⑤⑥⑦⑨：短期遷移と出力周期

- B42のlocator raw0はts892.010755と892.214902で観測、次のraw3は892.417554。**この2 sampleから実際の連続滞在時間を厳密には決められない**が、1Hzでraw0を取り逃す位相があることは分かる。状態名のREADY等はGUI enum候補で、API契約の確定ではない。
- B42の消耗品endTimeは約1秒幅で変動する。低頻度sampleを現在の不変deadlineへ変換しない。local countdownを出すならマップ側の推定値として別枠にする。
- 親の再確認ではB42 module10,704行／B43 module4,564行にcritTimer非null・state非0は0件。故障・修理の最短継続や意味を判断できない。1Hz化のfixtureはコードの欠測処理を検証できても実機意味の証明にはならない。
- Batteryは`submarine_telemetry`のSubmarine/Battery/WaveHit合同probeから切り離す。既存1Hz診断がOFFならBatteryもdisabledのため、単にintervalを変えるだけでは実用収集にならない。同tickのselfVehicle列挙は共有する。
- damageはイベントをすべて台帳へ渡したまま、1Hzでsnapshotする。再帰属等で合計が減ることもあり、マップ側で差分を無条件加算しない。B43では最終activeより終了frameの総計が859大きいという記録上の例があり、終了時の最新snapshotが必要。

## ⑧：初回のみの契約と残る制約

- 0.3.34の`meta.torpedoInitialParams`に`sampleTs`、`policy=oncePerBattle`、`valueKind=initialObservation`、`liveAdjusted=false`、`dynamicAdjustments=externalMap`を付ける。
- 初回収集開始時に1回だけ、TORPEDO弾薬ID／ammoParamsと固定TTX variantの候補を読む。選択のstrict対応が分からなければunknownのまま。全variantを初回候補として残し、後の選択変更で再取得しない。
- 毎stateの`torpedoArmament`はmodule状態のみ。定期`selectedTorpedoParamsProbe`／`torpedoTooltipParameterProbe`も出力・呼出しを撤去する。
- 初回にAPI未準備／欠測ならunknown、ammoParamsが空辞書なら空辞書のまま記録し、成功した性能値へ昇格しない。**初回失敗を周期retryせず、その戦闘の初回結果として固定する。** 情報不足が残り得る点は実用試験で確認する必要がある。
- マップ側が動的補正を正しく計算できるための入力・式は別途必要。初回TTXが全補正の純粋base値である保証や、マップ側の補正実装が完成済みという意味ではない。

## 実装前の検証項目

- 群別dueは単純な共通gateとし、1Hz群はまとめる。0.2秒tickへの量子化、時計逆行・停止・戦闘切替、catch-upなしをtestする。2Hzは既存同様の0.4/0.6秒相当の平均周期と、実sampleTsを区別する。
- 非dueはnotSampled、取得不能はunknown、設定OFFはdisabled。値を保持する場合は過去sampleであることと元のsampleTsを保つ。JSONだけ間引いてAPI取得を継続する実装を軽量化と呼ばない。
- HP群の同時性・0HP sentinel・alive変化、avatar未列挙艦の位置、same-snapshot strict ID比較、getter共有／非due0追加readを検証する。
- 消耗品・探知装置の短期状態を落とすfixtureを作り、「取り逃しがない」ではなくどこが落ちるかを確認する。
- damageは同じイベント列で5Hz／1Hz＋終了時の最終集計一致、較正は診断周期変更前後のmodel一致を検証する。
- ⑧は初回1回・再戦時reset・初回失敗時の非retry・通常／診断tickで性能API0・metadata再構築でも非refreshを検証する。
