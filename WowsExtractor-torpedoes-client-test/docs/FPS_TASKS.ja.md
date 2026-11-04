# FPS改善専用タスク：潜水艦戦闘補助に必要な負荷へ絞る

0.3.33ソース実装・独立検証完了：新規・不明は暫定5Hzをユーザー承認。5秒枠再分類、far非dueの位置／owner／派生処理skip、membershipとsampleの分離を実装。実機未確認、導入は行っていない。最終Python3.11全pytestはWOWS_SAMPLING_REPLAY=1で485 passed（B43/B44私有recordの2件も含む）。checkerは9 moduleのPython2 grammarと較正成立後の実sampler／motion／wire／UI抑止の連続tickを確認。sampler内部の判断件数不整合も正常空一覧ではなく取得unknownに落ちることをtest。

### 0.3.33の実装replay・負荷の限界

`tools/check_sampling_recording.py`で私有recordを逐次再生し、ID等は出力せず予算だけ集計する。分類半径は記録内のavailable較正係数とself位置を使用。初回の新規HIGH扱いも実装どおり。下記の行削減はAPI getter回数・後段処理数の削減であり、FPS改善率ではない。

| 記録 | 元魚雷行 | 今回sample行／位置read | 詳細処理を省く行 | 元state compact bytes | 新metadata込み投影bytes |
|---|---:|---:|---:|---:|---:|
| B43 | 95,413 | 85,987 | 9,426（約9.88%） | 137,408,822 | 137,325,492 |
| B44 | 9,671 | 7,870 | 1,801（約18.62%） | 28,110,393 | 27,758,977 |

byte数は元行の観測値をsample対象だけ残し、新sampling metadataとsubset時のUI抑止理由で置換した同一JSON設定での投影。新motion値や実engine取得値・serialize時間の完全再現ではない。初期の冗長metadataでは容量が増えたため、wireはID三つの配列membershipと小さいrow samplingへ絞った。B43の総byte削減は約0.06%、B44約1.25%に留まり、書込み負荷の大幅改善とは扱わない。owner lookup予算はB43で12,654→12,293、B44で1,998→1,833。全件API列挙・最小ID読取りは減らない。

分類contextが使えないstateはB43で43、B44で33あり、安全側highとして再生。toolは欠測件数と警告を出す。既に間引かれた0.3.33記録は全位置入力を復元できないためbaseline再生に使わず拒否する。torpedoes-only等の入力不足を距離分類成立と偽らない。

**ホストの安価なgetterではscheduler overheadが勝る。** Python3.11、216魚雷／22owner、500 tick×3反復の中央値（getter・sampling／metadata生成のみ、motion/map/JSONなし）は、旧→新でall near 1.630→3.546ms、半数far 1.665→2.926ms、all far 1.667→2.546ms。これは実API内部費用を含まないが、単純な条件分岐を追加すれば必ず高速になるという仮定を否定する。実機のgetter削減と追加Python処理の差引きは未計測。改善済みとして通常プレイへ投入しない。

その後、重複record生成・ID変換・decision辞書・context検証を削減。変更前後のB43/B44の行順・sampling・membership・API予算は一致。親の最終5反復中央値は旧0.3.32→0.3.33でall near 1.718→2.526ms、半数far 1.763→2.141ms、all far 1.629→1.605ms。並行replay等のホスト状況でも値は変動し、all farの小差を有意な改善としない。遠距離が少ない場合の固定費リスクは残る。次の実機計測までFPS改善の認定・通常プレイ導入は保留する。

独立レビュー対応：subsetをID照合の完全一覧と扱わず、UI raw probeへ全IDを渡し、identityCandidatesはsubset時notSampled。join抑止にはsampledSubset理由を付けAPI障害と区別する。viewerのheldはゲーム時刻だけでなく受信側壁時計でも失効し、inactiveで保持をclear。これらとrecord入力不足警告をoffline回帰で確認した。

親の事前record試算（実装測定ではない）：B43は95,413行中9,134行（9.57%）、B44は9,671行中1,702行（17.60%）の詳細処理を省略できる計算。現在の較正coefficientsとself.position、5秒再分類・初観測high・平均2Hzを用いた。新metadataのbyte増分は含まないため、FPS・payload削減効果とは扱わない。

0.3.32更新：Bの砲弾道撤去を実装。tracker・専用イベント・計算・出力を削除。魚雷距離別cadence（A）は引き続き未実装。

更新：2026-11-04。現行ソース0.3.32。**Bの砲弾道撤去は実装済み、Aの周期変更は設計段階。** 汎用WoWSテレメトリ収集器ではなく、潜水艦の攻撃・回避・潜航判断を優先する。

関連：[既知の問題](KNOWN_ISSUES.ja.md)、[用途の絞り込み](../../TASKS.md#task-scope)、[性能実績](../../TASKS.md#task-performance)、[B44計測](PERFORMANCE_B44_TORPEDO_PROFILE.ja.md)。FPS改善作業の詳細・チェック欄は本書へ集約する。

## 目標・制約

- 通常プレイへの影響を抑え、近距離の回避と魚雷戦に必要な観測を優先する。FPS改善は実機未確認のまま断言しない。
- ユーザー指定：**自艦からマップサイズの1/3を半径とする円の外側の魚雷を2Hzとする。** 内側は既存5Hzを維持する案。
- 遠距離を永久除外しない。非due・取得失敗・正常0本・一覧からの消失を区別する。
- 生のゲームobjectをframe間保存しない。過去sampleを保持する設計では、現在値と別の時刻・状態を持たせる。現行の一体snapshot契約は変更設計が必要。
- 開始直後FPS低下の追加調査、即時の高負荷再試験は行わない。

<a id="fps-order"></a>
## 実施順

1. 不要な砲弾道計算を依存確認のうえ撤去する（下記B）。
2. 距離判定・群別cadence・出力鮮度の契約を確定し、offlineで処理削減を確認する（A）。
3. その後にダメージ集計等の不要経路、重い診断との分離を扱う（C）。
4. 必要な実機確認を一回にまとめ、0.3.31較正最適化も含めてphaseと体感を確認する（D）。

<a id="fps-torpedoes"></a>
## A：距離による魚雷5Hz／2Hz分岐

### 最新の指定：5秒ごとの枠振り分け

ユーザー指定（2026-11-04）：距離による2Hz／5Hz判定は**5秒ごと**に行い、IDを収集枠へ振り分ける。マップサイズは対角線でなく一辺、長方形は`L=min(width,height)`、半径`R=L/3`で確定。以下の毎tick距離判定案は旧案であり、本節を優先する。実装は未着手。

| 処理 | 周期 | 提案する動作 |
|---|---|---|
| 全体再分類 | 5秒 | その時点の自艦・魚雷位置からnear/far/unknownを再判定し、ID別の所属枠を更新 |
| 近距離枠 | 0.2秒（5Hz） | 登録IDの現在観測を収集 |
| 遠距離枠 | 0.5秒（2Hz） | 登録IDの現在観測を収集 |
| 新規ID | 発見時 | 初回観測を出し、次の5秒再分類までは暫定5Hzを推奨。新規発見自体の周期は列挙方式に依存 |
| 距離判定不能 | 再分類時 | 安全側の5Hz。前の距離を現在距離として判定しない |

枠は件数上限の予約ではなく、IDの所属・次回dueを管理する論理的な収集グループ。枠が満杯だから観測を切り捨てる設計にはしない。保持するのはID・所属枠・分類時刻・scheduler情報等のplain dataのみ。ゲームentity/owner objectを5秒保持しない。

```text
if classification_due:  # 5秒ごと
    現在の全体一覧・位置を取得
    for each valid identity:
        if current distance unknown or distanceSquared <= (L/3)^2:
            assign HIGH_5HZ
        else:
            assign LOW_2HZ
    classificationTsを更新

if high_due:
    HIGH枠の現在値を取得してsample
if low_due:
    LOW枠の現在値を取得してsample
```

同tickで再分類と収集が重なる場合は、そのtick内で取得した位置・fieldを共有する。複数枠をdue順に回して同じIDを二重取得しない。移籍で前回位置を現在値として再出力せず、motionのnumeric履歴と新観測を区別する。時計逆行・戦闘切替は枠をreset、初回再分類を即時実行する。

**トレードオフ：farが円内へ入っても次回再分類まで最大約5秒＋実行遅延は2Hzのまま。** 自艦移動でも同じ。2Hz観測自体は続くので5秒間見えないわけではないが、毎tick即時昇格の旧案とは異なる。緊急昇格を追加すれば「判定は5秒ごと」の例外になるため、勝手に追加しない。

**API制約は残る。** 確認済みAPIは全魚雷列挙であり、IDから毎回直接取得できる経路は未確認。全件を5Hz列挙してIDで振り分ければ、距離計算は5秒ごと、遠距離の詳細field・派生計算・出力は2Hzにできる。位置readもIDを読んだ後に遠距離非dueならskipできる構成を検証する。ただし全件列挙・ID読取り費用は残る。非dueのentityを次回用に保存して省略する案は不可。厳密0.5秒schedulerで全件列挙を各群dueに行うなら列挙頻度が増える可能性があり、先に予算testする。

新規IDを5秒ごとの全体再分類だけで発見する方式は、近距離新規魚雷の初観測も最大約5秒遅らせるため推奨しない。全件列挙を使う場合は各列挙で新規IDを検知し暫定HIGHへ登録する。重複・ID再利用・途中列挙失敗を扱い、非dueで未収集のIDを消滅扱いしない。削除判定は正常な全体一覧のmembershipと詳細sampleを分離する。

- [x] 5秒再分類・暫定HIGH・群別dueの状態機械と出力契約を実装・offline検証。
- [x] 現在位置readをID判定後へ遅延し、far非dueの位置／owner／派生処理skipをAPI予算testで確認。
- [x] 5秒再分類による境界進入時の低頻度継続、新規発見、ID再利用、失敗・clock resetをtest。

### 距離・境界の提案

正方形マップの一辺をL、R=L/3とする。横方向world平面の自艦位置(x0,z0)と魚雷(x,z)を同じ座標系で比較する。

```text
distanceSquared = (x - x0)^2 + (z - z0)^2
if distanceSquared <= (L / 3)^2:
    near  # 5Hz。境界上もnear
else:
    far   # 2Hz
```

- sqrtは不要。深度yは距離判定に含めない。
- **マップサイズは対角線ではなく一辺**。長方形ならL=min(width,height)。ユーザー承認済み。短辺基準なので長辺基準より円は小さくなる。
- normalized map座標で判定する場合は自艦と魚雷の両方を同じ変換へ揃える。長方形で単純な正規化距離を使うとworld上の円ではなく楕円になるため、軸別scaleを反映する。worldの単位をkmと推測しない。
- map寸法・変換・自艦位置・魚雷位置が不明／不正なら**距離unknownとして高頻度側**へ送る。観戦対象を無断で自艦の代用にしない。
- 自艦魚雷を距離だけで除外しない。今回の指定どおりなら自艦魚雷も円外は2Hz。5Hz例外を設けるなら別途理由を明示し、ownerId推測joinで選別しない。
- 移籍は最新指定の5秒再分類で行う。新規は暫定HIGH案。ヒステリシスや毎tick緊急昇格は指定外なので無断追加しない。

### 旧案：毎tick距離判定と現APIの限界

現行`TorpedoTelemetry.torpedoes()`は全件列挙、固定6 field、位置、owner取得まで一体。その後Mainでmotion・map変換を行う。現コードの完成rowにifを追加するだけでは、前段のAPI取得費用は減らない。

推奨する第一段階は処理を分類前／後に分割すること：

```text
通常tick（約0.2秒）:
    自艦位置・マップscaleを確認
    getAllTorpedoes()を1回だけ列挙
    各魚雷の現在位置と識別に必要な最小fieldを読む
    near / far / unknown に分類

    for each torpedo:
        if near or unknown:
            今回の観測としてowner・その他field・motion・map変換を実行
        elif far_sample_due:
            今回の遠距離観測として同処理を実行
        else:
            遠距離の詳細収集・派生計算・行encodeをしない

    near sampleと、due時だけfar sampleを発行
    全件列挙の成否・membershipはsample rowsとは別に表す
```

**これは「遠距離の詳細収集・出力2Hz」であり、距離判定用の位置読取りは5Hzのまま。位置取得自体まで2Hzになったとは呼ばない。** 遠距離位置を毎tick確認するため、円内へ入った魚雷を次の通常tickで昇格できる。

| 案 | 削減できる処理 | 残る問題・採否 |
|---|---|---|
| A1：全件5Hzで分類し遠距離詳細だけ2Hz | 遠距離owner・追加field・motion・map変換・行encode | 第一段階の推奨。列挙・分類位置readは残る。API費用の削減上限を測る |
| A2：全件列挙2Hz＋近距離個別取得5Hz | 遠距離の位置read自体も2Hzにできる可能性 | 現行で利用確認済みの魚雷個別取得APIはない。API調査が前提。新規魚雷・far→nearの発見遅延は最大約0.5秒＋処理遅延になり得る |
| A3：前回far位置を信じて位置readをskip | far位置readを削減 | 次tickの再取得に使えるID→entity APIが必要。live object保持・推測移動で補う案は採用しない。真の2Hzにするなら境界検出遅延を契約として受け入れる必要がある |

### 2Hzのスケジュール

- nearの0.2秒tickだけで`last_far = now; next_far = now + 0.5`を繰り返すと、通常0.6秒ごと（約1.67Hz）になってしまう。
- 第一段階案：farの目標時刻は0.5秒刻みで進め、通常tickへ量子化する。例：実sampleが0, 0.6, 1.0, 1.6, 2.0秒なら0.4/0.6秒の交互で平均2Hz。catch-upで同tickに複数sampleを作らず、長い停止後は現在から再設定する。
- **厳密な0.5秒間隔が必要なら別schedulerが必要。** near5Hzとfar2Hzのdueの和集合で処理し、ships/avatarをそのたびに再収集しない。全件列挙が両dueで必要なら平均約6Hzへ増える可能性もあり、単純に軽くなるとは限らない。
- 推奨はまず平均2HzのA1。実sampleTsと目標intervalを出し、厳密周期と偽らない。

### schema・motion・欠測

- near/far別の`sampleTs`、`intervalSeconds`、`status`、分類方法・半径根拠を持たせる。非dueのfarを空配列として通常の全魚雷一覧へ混ぜない。
- 出力案はnear/far別sample（far非dueはnotSampled）を優先。最後のfar表示を保つのはconsumer側。従来`torpedoes[]`を一体の全一覧として読むconsumerとは互換性確認が必要。
- 現行`TorpedoMotion.update()`は渡された全行だけを次回履歴とする。far非dueで行を省くとfar履歴が毎回消えるため、群別sample対応が必須。サンプル移籍時も履歴を消失と混同しない。保持はnumericな過去観測のみ。
- owner cacheはsample内でのみ共有。far非dueのowner値を近距離の現在値として使い回さない。
- 専用depth/state 1Hz probeは最大64 entityで別制限。coreを2Hz化しただけでprobe負荷は減らない。非同時sampleのUI/API値を現在値としてjoinしない。

### Aのタスク

- [x] Lは一辺、長方形は短辺、半径L/3でユーザー承認。境界上near・unknownはHIGHを提案。
- [x] 全件列挙と分類用最小read、詳細取得を分割。
- [x] 平均2Hz・群別sample契約を実装。consumer参照を調査しviewer・recorder・仕様を対応。
- [x] B43/B44 replayで近／遠sample・省略可能な詳細処理数を集計。判定不能はhighと警告で区別。
- [x] API予算test：全件getter重複なし、far非dueの位置／owner取得・motion・map変換なし、近距離行保持。
- [x] 初観測・境界越え・自艦移動・位置不明・ID再利用／重複・取得失敗・時計逆行・戦闘切替をoffline検証。
- [x] motionの非due履歴と移籍、非due／正常0本／列挙失敗を区別するconsumerをoffline検証。

<a id="fps-ballistics"></a>
## B：砲弾道計算の詳細と撤去案

### 何を計算しているか

以下は0.3.31以前の撤去対象の記録。`Main.py:BallisticsTracker`は**飛翔中の全砲弾を追跡する機能ではない**。選択中の砲弾／一部航空爆弾のparamsと自艦照準情報から、着弾・貫通関連値を作っていた。魚雷の速度・射程・誘導計算とは独立。0.3.32では全撤去。

| タイミング | 実処理 |
|---|---|
| collection開始 | `getAmmoModifiers()`、ARTILLERYの`getSelectedAmmoId()`、必要時`getAmmoParams()` |
| 弾種変更 | ammoIdが変わると`getAmmoParams()`でparams更新 |
| 武装変更 | ARTILLERYなら選択弾種更新、それ以外ならammoを解除 |
| squadron開始／終了 | 爆弾params選択／解除、squadron flag更新 |
| 毎state（通常5Hz） | `_ammo`なしならavailable=falseのみ。ありなら下表の計算を実行 |

| 出力・計算 | 条件と実装 |
|---|---|
| ammoType／ammoId／squadronMode | 選択paramsから取得 |
| 照準・着弾速度 | `getSelfHoopRanging()`を1回。非squadronでgunPos/gunDirがありgunPos.y>=0.001なら`getAmmoImpactSpeed(ammo, gunPos, gunDir)`を呼ぶ |
| squadronの速度候補 | APのみbulletSpeed。それ以外はNone |
| 着弾角 | hoop.pitchをdegreesへ変換 |
| HE貫通候補 | `int(alphaPiercingHE)` |
| CS貫通候補 | `int(alphaPiercingCS)` |
| AP貫通候補 | impactSpeedがtruthyなら`getBulletKrupp()`を呼び、`Krupp × (mass × speed²)^0.69 × diameter^-1.07 × 1e-7`を計算。squadron以外はさらに照準を再取得し、正規化角を引いた角度のcosで補正して整数化 |
| 跳弾・強制貫通候補 | AP/CSでbulletRicochetAt、bulletAlwaysRicochetAt、floor(diameter×1000/14.3) |
| 信管 | APでbulletDetonator／bulletDetonatorThreshold |

AP通常経路は1 stateあたり照準getter最大2回、条件次第でimpact speed API1回、Krupp API1回。さらにparams property reads・pow/cos等。実行はammo選択状態に依存し、潜水艦では常に重い計算が走るとは限らない。

### なぜ削るか・削減範囲

- 潜水艦の魚雷戦・回避・潜航判断には砲弾のKrupp貫通／跳弾角／信管情報は不要。全艦・全弾種への一般対応は目標外。
- 現行profilerにballistics専用phaseはなく、B44でこの機能の費用は分離されていない。削除でFPSが何%上がるかは不明。計算が不稼働の戦闘では効果が小さい可能性もある。
- `getAmmoParams`や選択弾薬APIは魚雷性能側でも使う。**API名の一括削除は禁止**。BallisticsTracker専用の呼出し・イベント・出力だけを除く。
- ダメージ側のshell-infoイベントとは別機能。弾道撤去に便乗して未調査のdamage処理を壊さない。

### Bのタスク

- [x] Main内tracker生成／start／stop／snapshotと弾種・武装・squadron専用イベントを全撤去。
- [x] recorder・HTTP server・仮マップの実行コードにballistics参照なし。testsの旧stubを削除、exampleとschema文書を更新。旧版調査資料は履歴として残す。
- [x] ユーザーの全削除指定に従い`ballistics`キー自体を撤去。disabled互換枠・再有効化設定なし。mod.versionで変更境界を明記。
- [x] 全回帰で魚雷ammoParams／TTX・装填・ping・探知・damageを検証。Python3.11で431 passed、checkerで9 moduleのPython2 grammar・collector integration成功。
- [x] collection ONでも撤去対象の照準／着弾速度／Krupp／ammo modifiers API追加呼出し0とballisticsキー不在をcheckerで検証。専用イベントと計算コードの不在も回帰testで確認。

<a id="fps-other"></a>
## C：その他の削減候補

- [ ] damage集計の用途・consumer・vehicle/player対応との依存を分け、不要な集計・イベント・出力だけを撤去する。
- [ ] 自艦depth／Battery／ping／装填を独立sampleへ整理し、実用情報のために詳細診断一式をONにしなくてよい構成へする。
- [ ] HP・avatar／ships観測の重複payloadは、観測範囲を失わないこととconsumer契約を優先して検討する。
- [ ] 0.3.31較正最適化の小reservoir固定費を評価する。現在の比較削減をFPS改善済みとは扱わない。

<a id="fps-validation"></a>
## D：完了判定・検証

- [ ] 変更ごとに全pytest、Python3.11 checker、Python2 grammar、diff・公開schema整合を確認し、版を更新して親がcommitする。
- [ ] 既存B43規模216魚雷／22owner fixtureで、近距離保持・遠距離cadence・総API予算を確認する。byte削減と処理時間・FPSを分けて報告する。
- [ ] 実機が必要になった段階でのみ限定試験を準備し、near/farの実sample間隔・phase・取得範囲と体感をまとめて確認する。悪化時は中止・退避する。
- [ ] 実用化の最終判定はプレイへの支障と取得の誤りで行う。平均2Hz化による遠距離軌跡の粗さ・最大sample遅延等を明記する。
