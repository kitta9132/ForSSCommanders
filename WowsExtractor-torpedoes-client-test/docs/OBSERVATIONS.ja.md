# 0.3.3：可視候補の取得診断

現在のソース版は `0.3.3-visibility-diagnostics`。0.3.2の実機記録は履歴として下記に保持し、0.3.3で新設した診断値の実機取得根拠とは扱わない。

## 0.3.3変更（実機未確認）

- `visibility.dataHubCandidates` は `mapVisible`／`visible`／`isVisible`／`isShipVisible` ごとに `source`、`raw`、`type`、`status`、`reason`（正常時はnull）を出力する。
- `visibility.shipApiCandidates` は ship API側の `isVisible`／`isShipVisible` を別sourceで同様に診断する。
- 候補診断statusは厳密なbool判定で `available`（falseも取得成功）、`missing`、`none`、`readError`、`nonBoolean`、`componentMissing`、`componentReadError`、`ccKeyMissing`。数値0/1は候補診断では `nonBoolean` だが、互換 `visibility.raw` には残り旧 `visible` 投影ではfalse/trueとして扱う。欠測をfalse/0に変換しない。
- `raw` は有限なJSON scalarのbounded whitelist。非有限数や任意engine objectはraw値として出さない。従来の `visibility.raw` と `visibility.shipApi` 数値/bool出力は維持（非有限値は安全のため除外）。
- `visibility.status`, `semantics`, `uiMeaning`, `worldVisibleSource`、`visible`へのmapVisible投影と座標保持は従来どおり。意味は引き続き `unverified`。
- 新規モジュールは追加していない。戦闘をまたぐ可視キャッシュ、lastSeen/TTL/ghostは追加していない。

オフラインpytestは取得診断の分岐を検証するだけであり、ゲームbuild 13357625での属性アクセス可否・実値・UI意味は未確認。次の実機試験は [VISIBILITY_RESEARCH.ja.md](VISIBILITY_RESEARCH.ja.md) の診断版手順を参照。

---

# 0.3.2：観測値出力への整理（過去版）

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
- `visibility.status`：互換raw値のいずれかが出力された場合available、なければunknown。候補値の取得有無を示す既存契約であり、候補の意味や発見状態の確定を示さない。
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

新フィールドの値の取得は下記の実機試験で確認済み。意味と操作の厳密な対応は未確定であり、オフライン試験・実機取得確認・意味の検証を区別する。
導入にはゲーム終了、再インストール、ゲーム起動が必要。ATMありの場合は導入後にATM復元。
過去版の取得実績はSPEC_COVERAGE_0.3.1.ja.mdに残すが、出力変更は本書を優先する。

## 0.3.2実機結果（2026-11-01）

テスターは複数艦で発見→失探→再発見を実施、エラーなしと報告。
対象記録はversion=0.3.2-observations、active 1386フレーム、約144.2秒、正常な終了フレームあり。
当該起動のWowsExtractorログエラー0件。

- 艦船延べ11644行でvisibility.raw.mapVisibleを取得（true 11626、false 18）。
- 2艦でtrue→false→trueを観測。最初のフレームから約55.3秒／97.6秒、
  および約91.3秒／95.1秒にfalse／trueへの遷移を観測。
  一覧からの欠落もあり、これらの時間差をそのまま連続したfalse期間とは扱わない。
- falseの18行すべてでもmapPositionRawを保持して出力。
- 旧last*／staleSecondsフィールドは0件。魚雷は延べ235行取得。
- 較正availableは1237フレーム。

これは可視候補値と座標を分けて収集できた確認。操作の厳密な時刻・各艦との対応、
mapVisibleとサーバー発見状態の同一性までは証明しない。semantics=unverifiedは維持する。
ファイル名は再利用され得るため、版と時刻・戦闘で記録を識別する。

## 追加調査・変更（0.3.2時点・実機未確認）

`visibility.raw.visible`（標準UIがworldVisibleとして参照する属性）の収集を追加。
`visibility.uiMeaning=minimapMarkerVisibility` と、取得時のみ
`visibility.worldVisibleSource=dataHub.visibility.visible` を出力する。
上記0.3.2実機結果はこの追加前の記録であり、新属性の取得根拠ではない。
最終発見時刻は未取得。参照元・調査範囲・残る実機手順は
[VISIBILITY_RESEARCH.ja.md](VISIBILITY_RESEARCH.ja.md) を参照。
