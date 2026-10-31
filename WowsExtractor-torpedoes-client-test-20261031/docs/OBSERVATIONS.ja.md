# 0.3.2：観測値出力への整理

modは確認できた値を出力し、最終目撃履歴・失探・保持期限は外部アプリが管理する。

## 変更

- 最終目撃キャッシュ、60秒TTL、ghost生成、`last_seen_ttl`設定を撤去。
- `lastPosition/lastNx/lastNy/lastYaw/lastHealth/lastSeenTs/staleSeconds`を生成しない。
- 一覧から消えた艦を、modが過去情報から再生成しない。
- 発見状態による地図座標の除外をやめ、取得できた座標を出力。
- `ships[].mapPositionRaw`：地図座標の生値2成分。範囲外も残す。
- `nx/ny`：従来どおり0～1範囲の座標のみ。`mapPositionFreshness=unverified`。
- `visibility.raw`：dataHub.visibilityのmapVisible/isVisible/isShipVisibleから取得できた数値・bool。
- `visibility.shipApi`：shipのisVisible/isShipVisibleから取得できた数値・bool。
- `visibility.status`：UI候補属性があればavailable、なければunknown。意味の正しさではなく取得可否。
- `visibility.semantics=unverified`：実機で発見／失探との対応は未検証。
- `visible`：UI mapVisibleがboolまたは0/1ならその値、それ以外はnull。座標有無から推測しない。
- `visibleSource`：値がある場合dataHub.visibility.mapVisible。
- `positionAvailable`：直接／推定world位置または有効な地図座標があるか。発見状態ではない。
- `diag.alliesVisible/enemiesVisible`はvisible=trueの件数。unknownは含まない。
- UI mapVisible=falseの座標は出力するが較正用の対応点には採用しない。
- 対象不明の被ダメージを、ghostの位置から推測して艦へ割り当てない。

既存の座標較正・魚雷motionなどの派生値は維持する。これは全派生処理の撤去ではない。
ゲーム由来の最終発見時刻はまだ取得経路未確認。mod独自の時刻で代用しない。
仮ビューアはvisible=falseでも取得座標を表示するが、最終目撃と断定しない。

## 検証と導入

実機での新フィールドの値・意味は未確認。オフライン試験と実機検証を区別する。
導入にはゲーム終了、再インストール、ゲーム起動が必要。ATMありの場合は導入後にATM復元。
過去版の取得実績はSPEC_COVERAGE_0.3.1.ja.mdに残すが、出力変更は本書を優先する。
