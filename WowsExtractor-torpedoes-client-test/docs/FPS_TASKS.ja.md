# FPS改善専用タスク：潜水艦戦闘補助に必要な負荷へ絞る

更新：2026-11-04。基準ソース0.3.31。**本書は設計・実施タスクであり、以下の周期変更・削除は未実装。** 汎用WoWSテレメトリ収集器ではなく、潜水艦の攻撃・回避・潜航判断を優先する。

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
- **マップサイズは対角線ではなく一辺**とする提案。長方形ならL=min(width,height)を推奨（高頻度領域を定義する保守的な短辺基準ではあるが、円自体は小さくなる）。この解釈は未確定として設定・仕様で明示する。
- normalized map座標で判定する場合は自艦と魚雷の両方を同じ変換へ揃える。長方形で単純な正規化距離を使うとworld上の円ではなく楕円になるため、軸別scaleを反映する。worldの単位をkmと推測しない。
- map寸法・変換・自艦位置・魚雷位置が不明／不正なら**距離unknownとして高頻度側**へ送る。観戦対象を無断で自艦の代用にしない。
- 自艦魚雷を距離だけで除外しない。今回の指定どおりなら自艦魚雷も円外は2Hz。5Hz例外を設けるなら別途理由を明示し、ownerId推測joinで選別しない。
- 初観測はその周期の位置から分類。near→farは次の遠距離sampleを即時作ってから低頻度へ、far→nearは検出した通常tickで直ちに高頻度へ。ヒステリシスを追加する場合は別案として明示し、Rの意味を勝手に変えない。

### 本質的な分岐と現APIの限界

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

- [ ] Lの一辺解釈・長方形・境界・unknown扱いを仕様化する。
- [ ] 全件列挙と分類用最小read、詳細取得を分割する。
- [ ] A1の0.4/0.6秒sampleを含む平均2Hz設計とschema変更を実装・検証する前に、consumer対応箇所を列挙する。
- [ ] B43/B44の既存recordから、近／遠／unknown本数と省略可能な詳細処理数を算出する。必要なmap寸法がなければ推定せず算出不能とする。
- [ ] API予算test：全件getter重複なし、far非dueのowner取得・motion・map変換なし、近距離行の欠落なし。
- [ ] 初観測・境界越え・自艦移動・位置不明・ID再利用／重複・取得失敗・時計逆行・戦闘切替を検証する。
- [ ] near/far間で履歴を移すmotion、非due／正常0本／列挙失敗を区別するconsumerを検証する。

<a id="fps-ballistics"></a>
## B：砲弾道計算の詳細と撤去案

### 何を計算しているか

`Main.py:BallisticsTracker`は**飛翔中の全砲弾を追跡する機能ではない**。選択中の砲弾／一部航空爆弾のparamsと自艦照準情報から、着弾・貫通関連値を作る機能。魚雷の速度・射程・誘導計算とは独立。

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

- [ ] Main内tracker生成／start／stop／snapshotと弾種・武装・squadronイベントの購読／解除を追跡する。
- [ ] recorder・HTTP server・仮マップ・tests・schema文書の`ballistics`参照を調査する。
- [ ] 撤去時は`ballistics`を突然欠落させるか、理由付きdisabled互換枠を残すかをconsumerと合わせて決める。不要機能の再有効化設定は原則追加しない。
- [ ] BallisticsTrackerの処理・専用イベントを撤去し、魚雷ammoParams／TTX・装填・ping・探知・damageが影響を受けないことをtestする。
- [ ] collection OFFだけでなくONでも、撤去対象の照準／着弾速度／Krupp API追加呼出しが0であることを検証する。

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
