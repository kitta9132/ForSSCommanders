# B41：mods_DataComponentの供給元とstate候補の限界

2026-11-04。DSFFの読み取り専用調査と親による公式資料・GUI定義の再確認。第三者modの導入・実行・コードコピーは行っていない。

## 独立確認した根拠

- GUI抽出 `data/Components.xml:6696–6702` はMods_DataComponentを「for using in mods only」とし、id/data/evDataChangedを定義する。
- 公式 `wgmods/Mods-API-Documentation` commit `01fb0969` の `docs/PythonAPI/ui.md` は、ui.addDataComponent、addDataComponentWithId、updateUiElementDataによりmodがcomponentを追加・更新することを明記する。clearDataは他modを含む全mods_DataComponentを削除すると警告する。
- 同commitの `docs/PythonAPI/Classes/Torpedo.md` の公開属性はuiId/ownerId/ownerTeamId/ownerType/shotId/type/position。isHoming/isSpottedは掲載されない。非掲載は非公開経路が存在しない証明ではない。

参照URL：

- https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969/docs/PythonAPI/ui.md
- https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969/docs/PythonAPI/Classes/Torpedo.md

## ATMについて確認した範囲

ATM公開commit `6a62b202458484225369725f92b180f23af470d0` のUnboundはmods_DataComponent.data.isHoming/isSpottedを読む。READMEは検出表示をクライアント側距離推定として説明する。ローカル退避pycと公開版のblob一致、pyc内のcomponent書込み関連名・docstringはDSFFの静的調査による追加根拠であり、バイトコード全制御フローの検証ではない。文字列だけからアルゴリズム・producerの排他性・全将来buildの契約を確定しない。

ATMは当該flagsの既知のproducer候補／過去取得実績のある供給元。mods_DataComponentという汎用領域だけから、任意の値のproducerがATMと自動識別できるわけではない。他modも書込み可能である。

## B41の解釈

ATMなしのB41では定数キーavailable、entityのcomponent実体None、両flags未供給。公式定義と照合すると、**mod専用領域にゲームが生の誘導／被発見boolを常時供給すると期待した前提が不適切だった**。この経路をゲームの直接状態とみなさない。操作ミスの根拠はなく、同じ実機試験は繰り返さない。

「ATMなしでは永久に取得不能」「ゲーム側producerがどの版にも絶対存在しない」とまでは証明していない。ただし現在の公開契約と実測に、ATM非依存でこのcomponentから値を取れる根拠はない。

## 以後の境界

- 0.3.29は既定OFFの外部modデータ候補readerとして保持する。field名をゲーム／サーバーの生状態と呼ばず、unknownをfalseへ変換しない。
- ATM値を扱う場合は第三者由来の導出値として別sourceにする必要がある。被発見推定を直接取得値に代用しない。ATMの導入・依存追加は未承認であり自動では行わない。
- 自艦torpedoDrawer/movement.isChasingTargetという非公開経路は静的文字列上の候補に留まる。isHomingとの等価性・他艦への適用・Python可用性は未確認で、現行出力へ追加していない。
- 状態が本当に誘導中か、誰に被発見か、誘導停止理由は未取得のまま。GUIのacoustic/magnetic等の魚雷種別を現在の誘導boolへ置換しない。
