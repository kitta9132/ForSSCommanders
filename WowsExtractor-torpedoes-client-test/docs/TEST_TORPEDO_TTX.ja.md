# 選択魚雷TTX診断：短い実機確認

対象は`0.3.10-tooltip-parameter-diagnostics`。通常の訓練戦でUndineを使い、発射・reload・mod reloadは不要。

1. 魚雷兵装を選択し、ツールチップ表示を約10秒保つ。画面に速度75kts・射程9kmと表示された場合はそのメモを残す（過去B15の値であり今回の一致を前提にしない）。
2. そのまま通常記録する。発射・reload・mod reload不要。
3. `state.json`から`selectedTorpedoParamsProbe`のselection/TTX段階と、`torpedoTooltipParameterProbe`の`ownerEntityId`, `ownerKeyCandidate`, `parameterCollection` status/count/partial/truncated、`selectedParameter.status/reason/fields`を確認。top statusとstage statusを分け、unknownもそのまま報告。取得値はraw診断候補で、TTX上書き/live速度とはしない。

記録報告に必要なのはmod version、Undine魚雷を約10秒選択したこと、descriptorとtop/stage status、parameter row countとselectedParameter status/reason、UIに表示された場合は75kts/9km等のメモだけ。個人情報・battle/player/entity/ammo ID/raw owner keyは共有不要。

実機未確認なのはPython playerAvatar/parameter collection route、entity shape、parameter一致/value。GUI owner参照は抽出物上で特定済みだが、Python側取得・namespace対応を保証しない。available候補でもtooltip表示値・補正後live値・単位意味の確定ではない。外部UIだけを根拠にTTXを上書きしたりdeltaを加算・合成しない。
