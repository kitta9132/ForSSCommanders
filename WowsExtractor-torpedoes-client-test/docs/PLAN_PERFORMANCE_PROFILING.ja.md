# 性能計測の次工程（opt-in profiler 設計）

> 実装状態：0.3.20-opt-in-profilingでsource-only実装済み。実装差分／未確認事項は[出力仕様](OUTPUT_SPEC.ja.md)と[性能事故記録](PERFORMANCE_INCIDENT_0.3.14.ja.md)を参照。root側の同名資料はこの正本への短い参照です。

## 目的・現在地

これは性能最適化案ではなく、負荷の所在を観測するprofilerの設計資料。正本は `WowsExtractor-torpedoes-client-test/`。0.3.20はsource only・未導入。collection / diagnostics / profilerは既定OFFで、0.3.14 modはロード対象外へ退避済み。再導入しない。FPS低下の因果・改善を証明する資料ではない。

profilerはcollectionと独立の明示opt-in。設定不在・不正値・時計使用不可なら測定せず、時計候補・WoWS runtime適合は未確認。ゲームAPI実行や依存追加は不要。

## 静的調査と時計候補

- `Main.py:_now()`（L279）は `utils.getTimeFromGameStart()` を返す既存時計。`_tick()`（L1048）はこれをスケジュール、`_refresh_meta()`も再利用する。これはゲーム開始後時刻であり、tick内で進行する保証がない。durationには流用しない。失敗時に0.0へ落とす現状の `_now()` も計測器の代用にならない。
- 正本のPythonソースを限定検索したところ、mod内で見つかった標準時計利用は `battle_identity.py` の `time.time()`（fallback ID用）。その他の`time.monotonic()`は外部PC用collector toolingに限られ、WoWS埋め込みPythonで使える証拠ではない。ゲームmod側で `time.clock()` / `perf_counter()` / `monotonic()` の使用例は見つからなかった。
- 公開ソースの限定確認： [TTaroTeamPanel `Main.py`](https://github.com/AndrewTaro/TTaroTeamPanel/blob/main/PnFMods/TTaroTeamPanel/Main.py) は参照した範囲でゲーム内timerの根拠にならず、[WoWS Mod API公開例](https://gist.github.com/rapsealk/0e2948433f9f849966227bb4d076e1fa) の `time.time()` はファイルtimestamp用途。どちらも埋め込みruntimeでの単調時計・分解能を保証しない。ゲームbuild / Python runtime / OS APIの対応関係も公開ソースから確定できなかった。
- [Python 2.7 time docs](https://docs.python.org/2.7/library/time.html#time.clock) ではWindows `time.clock()`は初回呼出し以降のelapsed wall time、Unixではprocess timeと記載される。したがってWindows Python 2.7では候補だが、対象WoWS runtimeがその実装・挙動と一致する根拠はない。`time.time()`は壁時計で調整・巻戻りし得る。`time.clock()`がある、単調である、細かい分解能を持つ、と静的推測で採用してはならない。[Python 3.8 docs](https://docs.python.org/3.8/library/time.html#time.clock)では`time.clock()`削除済みで、`perf_counter()` / `monotonic()`の埋め込みruntime対応も未確認。ゲーム内の実clock実行なしに適合を宣言しない。

## 時計のguardと失敗表現

実装時、profiler有効時だけ、標準`time` moduleから候補clockを安全に参照する。まず `time.clock` がcallableかを確認し、なければ `time.perf_counter`、次に `time.monotonic` を候補として存在確認する。候補関数は例外・数値変換失敗・NaN/±Infを捕捉する。候補がない／初期probe不成立ならprofilerを停止し、通常収集を妨げない。時計が有効でない計測は**0msとして記録しない**。

採用前のprobeはbattle APIを呼ばず、profiler有効化時に同じ候補を連続読取りして、値の有限性、少なくとも一度の前進、観測された最小正差を調べる。連続読みで差が出ない場合は `resolutionUnknown` とし、以後のphase durationを無効値とする（ゼロに丸めない）。このprobeは分解能の下限を証明せず、開始時に観測した正差も将来の分解能保証ではない。

開始・終了値が不正ならstatusを保持し、終了時だけでなく全clock readを前回値と比較して逆行を検出する。逆行時は即停止し、別候補へ切替えて同一集計に混ぜない。候補なしは `unsupported`、初期probeで前進しない／正差を確認できないものは `resolutionUnknown`。有効な測定だけ `count/total/max` に加算する。時計statusがavailableでも5秒window未成立なら`status=notSampled`/`clockStatus=available`とし、0msレコードは作らない。未知phaseはallowlistで拒否する。

`time.time()`は初期連続probeを通っても将来の壁時計調整を防げないため、標準fallbackにしない。もし将来候補に加えるなら別途仕様判断が必要で、逆行時に即停止する条件は必須。時計参照元、採用method名、probe観測分解能（確定値でなく観測値）、statusは5秒集約出力に付ける。

## 計測区間と集計契約

計測はcollectorのgame-thread tick上に限定し、timer readは各区間の開始・終了境界だけとする。下記は包含関係があるため、区間値を足してtotalと解釈しない。

1. `state_cycle_total`：state buildを始める直前からsubmit完了まで（snapshot buildとsubmitを含む）。
2. `snapshot_build_total`：`_build_state(now)`全体。
3. 内訳：`avatar`（avatar snapshot capture・roster/health等）、`self`、`ships`、`torpedoes`（collection / motion / map変換）、`armament_systems`（armamentとsystems）、`diagnostic`（due時のdiagnostic probes / diag生成）。
4. `submit`：`_write_state(snap)`の同期game-thread時間。async writer時はslotへのsubmit・lock/event handoff時間であり、serialize / disk I/O時間ではない。同期fallback時はencode/write込みになるためmodeを分けて記録し、値を同列比較しない。

各phaseは `count/total/max` のみを5秒ごとに集約して出力する。p95や平均以外の分位値はbounded histogram等を実装していない限り出さない。毎tickの詳細ログ、各艦・各API単位のtimer、計測目的のAPI追加・再呼出しは禁止。diagnostic区間はdueで実際に走った場合だけ計測し、未実行を0msとして記録しない。tick exception / battle終端時は未完了区間を無効として破棄し、擬似的なdurationを作らない。

各build cycleで計測する区間は最大9個（total 2 read + build total 2 + 6内訳×2 + submit 2 = **最大18 clock calls / tick**）。0.1秒state intervalなら上限は約180 calls/sec、最小許容interval 0.02秒なら約900 calls/sec。これはdiagnostic phaseを含む最悪上限で、diagnostics OFFでは内訳が減る設計も可能。設定上限と計測数はテストで照合する。計測無効時はbranch以外の追加clock callを**0**にする。clock選択probeはopt-in時の初期化時だけの固定回数で、tick予算に含めないが別カウントとして明記する。

名称と境界は実装時に正本の呼出関係に合わせて確定する。計測のために関数分割・API経路変更を行わず、phase boundaryだけを追加する。特に`_build_state`のself getter共有、avatar snapshot共有、diagnosticsの既定抑止を変えない。

## Async writerは別計測

writer threadの処理はgame-thread phaseへ混ぜない。`_AsyncWriter.submit()`にかかったgame-thread待ち時間は上記`submit`でのみ計る。thread側は必要なら別counterで、serialize と file writeを区分して計る。writer固有の統計をgame threadから参照する共有lock・頻繁なcounter同期は避け、writer thread内のlocal accumulatorを基本とする。異なるスレッドの集計出力／状態受渡しを導入する場合は、その同期コスト自体を別途レビューする。

writer処理は現在 `_run()` の `_serialize_safe(obj)` と `_write_file(path, ...)`。個々のobjectに対し2区間を測るなら最大4 clock calls/object（各2 read）。回数はwriterの実処理頻度に依存し、game-threadの上記上限に含めない。thread-safeな標準clock・ログloggerの性質は未確認であり、GIL下でのgame threadとの競合、OS/file I/O待ち、ログ内部lockによる干渉は別問題として残す。集計ログも5秒ごとのみとし、性能測定結果をゲーム内FPS改善の証拠と扱わない。

## 実装・検証の順序と安全条件

1. まずofflineのfixtureで、profiler OFF時に時計関数が一度も呼ばれないこと、全phase境界が成功・例外・early return時に対称になること、invalid/unsupported/reversed/nonfinite/resolutionUnknownが0msへ化けないこと、5秒集約とcount/total/max、上限call数を確認する。
2. 配布・導入ではなくsource-only検証を先行する。collection / diagnostics / profilerの既定OFF、ゲーム退避を維持する。
3. **次の実機確認はユーザー主導の訓練戦・小負荷からのみ**。小規模条件で採用時計・status・resolution・5秒summary形式・負荷兆候・エラー0件を短時間確認し、通常戦や12対12の再現を依頼しない。実機確認を依頼する段階でも、導入・復元手順と退避維持を事前に説明し、 profilerを常時ONにはしない。
4. ゲーム操作中にstutter/FPS悪化、既存収集の例外、出力停滞、時計逆行/非有限、profiler status不明、追加ログの連打、GIL/同期競合が疑われる兆候があれば即停止し、profilerをOFFにしてcollectorを退避状態へ戻す。unsupported / invalid / resolutionUnknownなら測定成立として続行せず、その時計の実装判断に戻る。

## 未確認事項・読み方

- 報告されたminFPS 25と撃沈後110はユーザー報告であり、因果・再現性・外部計測独立性は確定していない。追加FPS比較を目的とする実機試験を依頼しない。
- 区間時間はPythonで囲ったwall durationで、GPU時間、描画thread時間、engine API内部時間、CPU process timeを分離しない。GILでgame threadとwriter threadが互いに遅延し得るため、writerの計測値とgame-threadの計測値は単純加算・独立負荷と解釈しない。
- 集計が示すのは該当条件下の観測値のみ。平均/FPS改善・全艦/全battle一般化・原因確定にはならない。計測器自身のclock、集計、ログのoverheadも残る。

## 次の実装着地点

新設計モジュール（例：`performance_profiler.py`）を正本の`Main.py`から低侵襲に呼び、configに独立した `profiler_enabled=false` を追加する。時計の候補選択/probe・state/status・有限差検査・bounded 5秒 `count/total/max` 集約をそのモジュールに閉じる。`Main.py`側はphase boundaryのみをラップし、AsyncWriter側のworker-local計測を実装するかは別途選択可能にする。実装対象外はTASKS更新、通常戦テスト、依存追加、FPS改善を目的にした推測最適化。
