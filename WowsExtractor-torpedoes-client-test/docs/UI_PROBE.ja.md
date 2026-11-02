# 0.2.3 読み取り専用UI魚雷プローブ

0.2.3ではisSpottedも抽出する。各行にisSpotted/spottedStatus/spottedSource/
spottedRaw/spottedRawTypeを追加。boolのみavailable、欠損・非boolはnull/unknown。
意味はATM被発見表示用の判定であり、敵がサーバー上で確実に検出したとは断定しない。
毎回読み直し、値の持ち越しは行わない。

`state.json` の戦闘中フレームに `uiTorpedoProbe` を追加する診断版。
ゲーム状態、ATM、UIコンポーネントへの書き込みは行わない。
0.2.1の開始イベント順修正を維持し、Python 2用のUTF-8宣言も補った。

## 取得するもの

- `dataHub.getEntityCollections('torpedo')` の成否と行（最大64件）。
  メソッド自体は公式APIにあるが、collection名のPythonでの可用性は実機未確認。
  表記はATMの公開Unboundが参照するコンポーネント名に基づく。
- `constants.UiComponents.torpedo` と `mods_DataComponent` のキー値。
  キーがなければ推測した定数で読み取らない。
- UIのtype、エンティティのID候補、公開API側のuiId一覧。
  ID候補の名前空間は未確認であり、自動的な結合は行わない。
- mods_DataComponentのdataにあるisHomingの有無・生値・型。
  本物のboolのみavailableとして採用。欠損/取得不能/非boolはnull。
  falseとunknownを区別し、typeから補完しない。

`source` はdataHub.torpedo、誘導フラグ経路はui.mods_DataComponent、
`producer` はunknown。ATMが計算することのある値で、ゲーム生値とはラベルしない。
ATM無効時に値がなくても、それ自体はmodの故障を意味しない。
毎回読み直して保持しないため、前の魚雷・前戦闘の値を持ち越さない。
列挙に失敗した部分的な行は破棄する。
終了フレームにはこの診断枠を含めない。

## 初回テスト

ゲーム終了後、install-13357625.batで再導入。ATMは無効のまま。
record-13357625.batを起動してから訓練戦へ入り、
Undineの音響魚雷1本を発射。飛翔中にpingを1回命中させ、
魚雷消滅後に退出。5秒待ってCtrl+Cで記録終了。
まずはcollection/キー/ID候補/供給有無が読めるかを評価する。
誘導中フラグの取得成功や意味の確定を受入条件にしない。
