# 0.3.0 移動履歴較正・魚雷運動情報

## 0.3.1修正

0.3.0実機試験では、ゲームの制限付き組み込みにAttributeError名がなく、
欠損属性の診断処理でtickが停止した。取得できたのは初期22フレームで、
その後の移動・魚雷試験は記録できていない。消耗品・ソナー情報の生値は初期フレームで確認。
0.3.1ではgetattrのデフォルト値と汎用例外で処理し、AttributeErrorを必要としない。
同名を組み込みから取り除いた回帰テストを追加した。
記録ツールも5秒ごとの状態表示・active状態で更新停止した際の警告を追加した。

実機未確認。手持ちのMinotaurやUndine等で試験でき、T10潜水艦の購入は不要。
0.2.3の試験結果は別の記録として保持する。

## 地図較正

同じフレームの複数艦だけでなく、自艦等の移動履歴から
`(nx,ny,worldX,worldZ)` を戦闘内で蓄積する。
停船や直進だけの退化したデータは採用せず、十分な2D移動と誤差検証が必要。
Oceanの1200等の定数をハードコードしない。新戦闘・退出時に履歴を消す。

- `diag.mapCalibration`：較正状態、サンプル数、係数、誤差等。
  sampleCountは現在の履歴数、fitSampleCount/holdoutCount/rmse等は
  係数採用時の較正データに対応する。driftStreakは連続した不整合観測バッチ数。
- `diag.mapSamples`：従来どおり、そのフレームの直接対応点数。
  履歴を含めた数とは違う。
- `diag.mapCalib`：旧A/B/nullではなく較正statusに変更。読み手は
  `diag.mapCalibration`も参照する。
- `ships[].positionSource`：shipOrPlayerApi / calibratedMapPosition / null。
  後者のワールド位置は推定変換であり、y=0固定で深度は未取得。
- `ships[].mapPositionSource`：dataHub.mapPosition。
- `ships[].mapPositionFreshness`：unverified。UIマーカーを現在の可視位置と
  断定しない。完全な可視/最終目撃の分離はまだ残課題。
- `torpedoes[].mapPosition`：較正成立時の `[nx,ny]`、未成立はnull。
  `mapPositionSource` はcalibratedWorldPosition、mapPositionStatusはavailable/unknown。
- `diag.positionReads`：getPosition/position/worldPosition/positionHullについて
  missing/none/error/invalidVector/availableの回数。
  プレイヤー経由の再試行も数えるので艦数と同一ではない。

## 魚雷ごとのUI状態

`torpedoes[].uiState` に、同じフレームでIDが一意一致したUI状態を付ける。
`isHoming/homingStatus/isSpotted/spottedStatus/uiType` を持ち、
`source=ui.mods_DataComponent`、`producer=unknown` とする。
`matchStatus=exactUiId` は本buildの試験で一致したUI ID同士の直接照合。
ID重複・未一致・取得失敗はunknownで、前フレームの値を流用しない。
供給者は構成上ATMと分かってもフィールド自体で証明できるわけではないため、
ゲーム生値と表記しない。ATMなしでも他の項目は動く。
`uiTorpedoProbe` は診断用に引き続き残す。

## 魚雷の推定運動情報

`torpedoes[].motion`：positionDifference由来、`inferred=true`。

- `velocity`：3軸の座標差/ゲーム時刻差。
- `horizontalSpeed`：水平2軸の速度の大きさ。
- `headingRadians`：atan2(vx,vz)、+Z基準で+X方向が正。停止中はnull。
- `speedUnit`：game_world_units_per_second。ノット・実m/sには換算しない。
- `dt`：差分に使った秒数。
- `observedAge`：連続追跡できた区間の最初からの秒数。
- `observedDistance`：その区間の水平移動距離の合計。

初回・同一時刻・時刻逆行・1秒超の欠測・無効位置・識別子の変化では速度を出さない。
魚雷消滅、一覧取得失敗、戦闘切替では履歴を捨てる。
観測距離/時間は全射程/実寿命ではなく、残り射程も算出しない。
魚雷位置の停止が命中を意味するとは判定しない。

## 自艦消耗品・索敵装置（公開API生値）

`selfSystems.consumables`：Ship.getConsumablesStateの
icon/num/currentState/endTimeを取得。種別をiconから推測しない。
endTimeの時刻基準は未検証のため、tsから引いて残時間に変換しない。

`selfSystems.search.radar/hydroAcoustic/submarineLocator`：
Ship.getRadarInfo/getHydroAcousticSearchInfo/getSubmarineLocatorInfoの
distShip/state/workTimeLeftを取得。公開資料に戻り値の単一/list両表記があるため、
実際のshapeも付け、items配列へ格納する。
None・失敗はunknown、取得口欠落はunsupported。非搭載と取得不可を決めつけない。
distShipの単位やstate値の意味は実機未検証。ping対象/命中区画タイマーではない。
いずれも自艦だけを読み、他艦の非公開装置状態の取得は試みない。

静的な速度・射程は外部WoWS艦艇百科APIにもあるが、標準構成の値であり
現在の選択弾や装備を保証しない。APIキーや外部通信を新たに必要とするため、
今回のゲームmodには組み込まず、後で外部マップ側の辞書として検討する。

公開仕様の根拠（固定リビジョン01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2）：
[Ship](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Ship.md)、
[_ConsumableState](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/_ConsumableState.md)、
[_SearchConsumableInfo](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/_SearchConsumableInfo.md)。

## 初回テスト

ゲーム終了→install-13357625.bat→restore-atm-13357625.bat。
ATMあり記録コマンドで記録し、手持ちの艦で訓練戦へ入る。
自艦を十分に動かし、直進だけでなく大きく曲がり、さらに別方向へ進む。
目安として加速後に45～60秒直進し、大きく曲がって別方向へさらに45～60秒進む。
これは較正成立の保証ではなく、低速・短距離・小さな旋回では追加移動が必要。
魚雷を1本発射し、消滅まで待って退出。
独立方向の移動が不足する場合、較正しないのが正しい挙動。
新しい試験であっても課金艦や新艦の購入は不要。

ping残時間、目標ID、誘導停止距離、装填残数・装填時間、最大/残り射程、
確定命中/消滅理由は今回も未取得。取りやすさを理由に推測値で代用しない。

## オフライン記録の再生確認

without-atm-b01のMinotaur記録で時系列較正が成立。
採用後915フレームの自艦水平位置との差はRMS約0.234、最大約0.592ゲーム座標単位。
他艦の地図座標5490行を変換できたが、他艦の正解world位置との独立照合ではない。
with-atm-b01/b02/b03のほぼ直進経路はdegenerateとして較正しないことを確認。
ゲーム内0.3.0の実動作・負荷はまだ未確認。

## 0.3.1実機試験結果

対象戦闘1576フレームを継続収集、終了フレーム正常、WowsExtractorログエラー0件。
開始約78.7秒で較正成立し、その後813フレームで係数を維持。
8隻の他艦の計6504行を地図座標から補助変換。
APIの直接位置は依然自艦のみで、他艦のgetPositionはNoneを観測。
採用係数はworldX約1198.85*nx-599.32、worldZ約-1200.03*ny+599.93。
係数採用時fitSampleCount=72、holdoutCount=15、holdoutRmse約0.0656。
通常魚雷1本の374フレームすべてで地図座標が出力された。
差分運動は初回を除く373フレームで計算、水平速度0～約6.04ゲーム座標単位/秒。
ATM isSpotted=trueを80フレーム取得、同時にisHoming=false（通常魚雷）。
それ以前の294フレームはどちらもunknown。被発見falseやサーバー検出の検証ではない。
他艦・魚雷の画面上の位置一致、別地図、画面外・未発見時の鮮度の試験は残っている。
