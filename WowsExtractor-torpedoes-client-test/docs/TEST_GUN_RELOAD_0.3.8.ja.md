# 0.3.8 gun reload 最小実機試験

目的は`gunReloadProbe`の取得範囲内で、UI別のgun/progress候補が発射後に変化するかを一度だけ確認すること。意味や全管を一般化しない。B12の時計・選択確認を繰り返さない。

1. **準備**：ゲーム停止状態で通常の導入手順を行い、mod versionが`0.3.8-gun-reload-diagnostics`であることをmetaで確認する。Undineの訓練戦、追加modなしを基本とし、戦闘開始からJSONLを記録する。
2. **初期状態**：魚雷兵装が満装填になってから、画面とstateを数秒記録する。reload UIが表示されていることを目視する。
3. **操作**：選択中の魚雷を1発だけ発射し、以降は追加発射せず45秒以上待つ。発射直前・直後・約45秒後の画面時刻をメモする（画面録画推奨）。
4. **照合**：JSONLの`gunReloadProbe.collections.gun`、`gunBarrel`、`reloadBar`、`references`を別々に追う。`source/status/partial/truncated`、同一gunのprogress、modifier参照ID、解決先progressとUI表示を記録する。slotとtype/orderで結び付けない。
5. **報告**：版/build/艦/ATM有無、発射・完了表示のおおよその時刻、各候補の取得状態と変化の有無を記録する。個人情報・実IDは報告文書へ転記せず、必要な照合はrecord-local pseudonymにする。

## 判定

- getter/key/collectionが未対応・unknown、row欠落、partial/truncated、参照先未取得なら「coverage不足／未検証」。
- raw値が取れてもUIと対応を見ていなければ「取得候補を観測」。
- 同期した画面と候補の変化が一致した場合も「今回の条件で整合」のみ。管数・意味・単位・他艦への一般化はしない。
- 同じB12のclock/選択確認は再実施しない。ZIP生成、manifest更新、ゲーム起動・インストールはこのオフライン作業の範囲外。
