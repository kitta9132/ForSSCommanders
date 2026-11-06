# 大規模な構造変更による高速化余地

2026-11-06。調査時点の対象ソース0.3.39（現行は0.3.40-radius-l5）、実測根拠は[ATM B09・0.3.38](PERFORMANCE_WITH_ATM_B09_0.3.38.ja.md)。調査のみ。以下の削減率はFPS改善率ではない。ユーザー判断により大規模構造変更・外部bridge案は「一旦なし」で保留し、実装キューにはしない。

## 結論

有力なのは **ゲーム内で生値を取得し、軽量な形式で転送、外部プロセスで加工・現行JSONへ展開する構成**。次に、群ごとの取得タイミングを別frameへ分散するscheduler。前者は総作業量とゲーム内加工の削減、後者は単発停止時間の短縮を狙う別の施策である。

現行は`Main._tick`（Main.py:1386）がsnapshot全体を構築してから出力する。B09 S2/S3は平均cycle10.711/10.661ms、avatar4.062/4.005ms、submit1.957/1.922ms。同一最重窓ではcycle15.469/15.141ms、avatar4.216/4.029ms、torpedoes4.331/4.414ms、submit3.046/3.000ms。親子phaseを加算しない。API内部とPython加工の時間は分離できていないため、各phase全体を削減可能額と扱わない。

## 1. 軽量転送＋外部でのJSON復元（優先）

### 今ある構造

- `Main.py:492–549`：同期serializerはengine helper→stdlib→pure Python、非同期はstdlib→pure Python。実機でどのencoderが選ばれたかは記録から不明。
- `Main.py:587–611,1365–1383`：stateはopen/write/closeで全体を上書きする。既にstateの毎回renameは撤去済みなので、「atomic writeをやめる」は新しい改善案ではない。
- `Main.py:617–676`：latest-winsの非同期writerは既存。ただしB09のwriterModeは`syncEncodeWrite`。thread import失敗か初期化失敗か等の理由は未確定。
- `Main.py:116–145`はthreading取得を試みる。既存threadを有効にするだけの提案では実機制約を解消できない。またPython threadにはGIL競合があり、CPU加工の完全な並列化を保証しない。コードコメントの「serializer速度はほぼ問題ない」は性能保証に使わない。

### B09既存記録の容量試算

private JSONLの`kind=state`かつ`data.active=true`、全1,843件（S1も含む）を対象とした。Python 3の`json.dumps(ensure_ascii=False,separators=(',',':'))`をUTF-8化して計数。実機writerのbyte数とは異なる。各fieldの値だけの平均容量：

| 対象 | 平均byte |
| --- | ---: |
| state全体 | 99,438.6 |
| gunReloadProbe | 34,279.1 |
| ships | 22,750.8 |
| avatarObservations | 16,223.0 |
| torpedoes | 15,289.0 |
| torpedoStateProbe | 2,850.8 |

detail95行の最初のstateは全体173,435byte、魚雷82,409byte、装填34,197byte。装填はgun/reloadBar/gunBarrelにfields・fieldStatus・progress・各componentのstatus等が入る。情報を削除せず、共通の説明を一度だけ定義する余地がある。

単純な可逆試算として、各state内の全dict keyを出現順の整数文字列へ置換し、復号用key一覧を**そのstate自身に同梱**した。list順序・全値・欠測表現は保持し、全1,843件で復号結果と元dictの等値をassertした。平均77,822.2byte、**21.74%減**。戦闘間cacheや差分復元を必要としない条件でも重複key削減余地がある。ただしこれは容量の試算で、既存dictを作ってから置換すれば追加CPU処理になる。実装するなら最初から固定schemaのコンパクト行を構築する必要がある。辞書key順序・JSON文字列表現の同一性は保証対象ではない。

同じactive列の先頭から18件おきの103件について、Python 3のcompact JSON＋UTF-8化を5巡し、1件あたり平均の5巡中央値を参考計測した。既存構造のencodeは1.0685ms、事前変換済みpacketのencodeは1.0113ms、毎回変換してencodeすると2.6052ms。このPC側・I/Oなしの測定では**キーを短くしただけのencode短縮は小さく、後付け変換は逆効果**だった。ゲーム内encoderの性能値ではない。容量削減だけを根拠に方式を採用せず、固定行形式による構築費削減を試作で確認する必要がある。

### 提案する境界

1. ゲームスレッドでAPIの必要fieldを取得し、純粋な数値・文字列・bool・nullと取得状態へ変換する。
2. IDとsample時刻付きのコンパクト行を送る。schema/version/sourceの共通定義と、変動する取得状態を区別する。
3. 外部bridgeが現在のJSON構造へ展開し、record/viewerへ供給する。較正・motion・照合診断の外部化は依存順序を検証して段階追加する。

転送も無料にはならない。第一段階は既存file経路で形式だけ比較できる。socket/pipe/共有メモリ等はゲームsandboxで使用可か未確認で、利用可能と前提しない。外部processへAPI objectを渡さない。

規模感としてsubmitはB09平均cycleの約18%、同一最重窓の約20%。これは現行phaseの占有率であり達成可能な改善率ではない。21.74%のbyte減少をsubmit時間へ比例換算する根拠もない。大幅な短縮には転送に加えてゲーム内の行構築・派生計算も減らす必要がある。

平均99KB×5Hzは概算約0.5MB/sであり、この数字だけではディスク帯域不足とは言えない。狙いは主にネストしたdictの生成・走査・文字列化と、ゲームスレッド上の同期I/O。submit内のencode/write別時間がないため、pipe化だけを第一候補にしない。

通信契約にはbattle/session世代、sequence、schema、群別sampleTs、partial/truncated、notSampled、終了状態を持たせる。差分配信を追加するなら消失と非dueを区別し、欠落検出・定期full snapshot・再接続再同期が必要。初手は自己完結したpacketが扱いやすい。外部側の過去sampleを現在値として出さない。

### 検証方法

B09/B43/B44 replayで既存JSONの意味的な復元一致、厳密ID型、unknown/false/0、partial、時計逆行、battle切替、終了後遅延packetを検証する。旧snapshot構築→encodeと新compact構築→encodeを分けてoffline計測する。PC側Python 3の時間をゲーム内Python 2/API時間に換算しない。

## 2. 外部readerの一本化（補助）

`tools/record_telemetry.py:21–69`は50ms既定pollごとにread→parse→非有限値検証用encode→hashを行い、その後に重複を除外する。静的metaも対象。viewerの`tools/serve_map.py:26–75`も独自にread/parse/検証し、HTTP返却でさらにencodeする。`viewer/index.html:137`は200ms間隔のpoll。

単一bridgeで一度だけ読取り・検証し、変更通知またはsequenceに基づきrecorder/viewerへ配信すれば重複処理を減らせる。mtime/sizeだけのskipは同一signatureで書き換わる可能性と書込み途中を考慮する。これは外部プロセス側の節約で、collectorのsubmit計測値を直接短縮する施策ではない。B09でviewerも同時稼働したとは断定しない。

## 採用判断

### 収集側の追加レビュー

- **魚雷の派生処理外部化を先行候補とする。** `TorpedoMotion.update`（torpedo_telemetry.py:3224以降）、`Main.py:2283–2289`のworld→map変換、`Main.py:2209–2254`のUI照合が対象。API列挙・identity/position/owner取得・距離cadenceはゲーム側に残す。外部bridgeが現行schemaへ復元すれば、consumer向けfieldの削除は必須ではない。ただしmod→bridgeの通信契約は新設する。partial・重複・型差・同sampleの照合条件を丸ごと移し、位置差分は元のsampleTsで計算する。latest-winsで途中sampleが落ちるとmotion履歴が変わり得るため、全観測を渡す仕組みか、欠落時の明示的なreset/unknown契約が必要。
- **艦の較正処理の全面外部化は保留。** `_build_ships`の`MapCalibration.observe`（Main.py:3290）は魚雷距離分類にも必要。`_torpedo_sampling_context`（2483–2517）は同snapshotの較正scaleからマップ幅・高さを作る。fitを外へ移すだけではcontextがunknownになり、HIGH fallbackによって逆に取得負荷が増える可能性がある。第一段階では分類に必要な較正を残し、説明field・coverage/consistency集計・出力用座標変換を外へ移す。係数を戻す方式なら、双方向通信・世代・鮮度・未取得時の扱いを別途設計する。
- **avatarのraw sample化は候補、rosterの戦闘中固定cacheは採用しない。** `_build_avatar_observations`（Main.py:2519以降）の正規化・比較集計は外部化対象。一方`_remember_roster_vehicles`（1283以降）のplayers indexは同state限定と明記されている。「rosterは戦闘中不変のはず」だけでは、途中取得・欠測・ID変更・重複・死亡時のAPI可用性を代替できない。getter費用の内訳も未測定なので、毎tick getter撤去による大幅改善を主張しない。

### scheduler分散の位置づけ

`Main._tick`はstate gateを通過した後、各群のdueを決めて一括buildする（Main.py:1416–1439）。群を別frameへずらす方式は、収集頻度を下げずに集中を緩和する候補。ただし各群自身の最長処理時間は残り、総CPU時間の削減とは別である。同frameのAPI/UI照合を異時刻間joinへ変えないよう、依存する群を一緒に取得し、独立群から分散する。現行stateは全項目同時ではないが、さらなる分散には群別sampleTs・出力遅延上限・時計逆行・戦闘終了処理の再設計が必要。

### 評価上の注意

外部レビューにあった「offline encode約1msなので実機のボトルネックは加工」との推論は採用しない。PC側Python 3の時間とゲーム内B09 phase時間は比較できず、API内部費用とrow構築費は依然未分離。イベント駆動化も、位置/membership更新を漏れなく通知するAPIが確認できるまでは設計前提にしない。

記録replayは、記録に含まれる入力についての復元確認に限る。出力されていないraw sampleを復元できるとは扱わない。実producerをfixtureで駆動する検証と合わせる必要がある。offline profilerの結果だけでゲームスレッドの実測改善を確認したとはしない。

最初にコンパクト転送のoffline試作を行い、復元一致と生成費用を比較するのが妥当。収集頻度・半径・近距離本数budgetは現状を維持する。ゲーム内API取得の約4ms固定費まで解消できる保証はなく、転送の削減だけでFPS問題全体が解決するとはしない。

今回ゲーム起動・導入・追加実機試験は行っていない。大規模実装への移行は、出力経路・外部bridgeの必須化という方針選択を伴う。

## 容量試算の再現

Python 3で次を正本ディレクトリから実行する。private記録はGitへ追加しない。元データの値は標準出力へ出さない。

```python
import json

def size(value):
    return len(json.dumps(value, ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8'))

def pack(value, keys):
    if isinstance(value, dict):
        return {str(keys.setdefault(k, len(keys))): pack(v, keys)
                for k, v in value.items()}
    if isinstance(value, list):
        return [pack(v, keys) for v in value]
    return value

def unpack(value, keys):
    if isinstance(value, dict):
        return {keys[int(k)]: unpack(v, keys) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v, keys) for v in value]
    return value

n = before = after = 0
with open('recordings/with-atm-b09.jsonl', encoding='utf-8-sig') as stream:
    for line in stream:
        event = json.loads(line)
        data = event.get('data', {})
        if event.get('kind') != 'state' or not data.get('active'):
            continue
        keys = {}
        packet = pack(data, keys)
        names = list(keys)
        assert unpack(packet, names) == data
        before += size(data)
        after += size({'keys': names, 'data': packet})
        n += 1
print(n, before / n, after / n, 100 * (1 - after / before))
```
