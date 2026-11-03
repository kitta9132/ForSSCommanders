# Avatar IDのGUI定義とAPI対応の限界

2026-11-03。Luna xhighのread-only調査。対象は既存GUI抽出物とローカルsource／公開例。実機操作・runtime変更なし。抽出物そのものはコミットしない。

## 確認できたGUI namespace

参照元は隣接研究フォルダー `mino-smoke/research/extracted/gui/`（以下の相対pathはこの配下）。これはGUI構造の根拠であり、ModsAPIの一般契約ではない。

- `data/Components.xml:1335–1366`：Avatar componentの`id`はIntegerのPK。同定義に`playerId` propertyはない。したがって候補`dataHub.avatar.id`はGUI CC.avatarの主キーとして意味を明示できる。
- `unbound2/pc/battle/observed_avatar_label.unbound:3–13`：`camera.observedPlayerId`を自艦avatar.idと比較し、その値で`getPrimaryEntity(CC.avatar, observedPlayerId)`を引く。観戦UIでの対応を支持する。
- `unbound2/pc/battle/combat_log/combat_log.unbound:289–295`：ログメッセージのplayerIdからCC.avatarを検索する。
- `unbound2/pc/context_menu/context_menu_player.unbound:162–200`：avatar.idをplayerIdというアクション引数に渡す。同ファイル313行の連絡先操作はaccountSimple.dbIdを使い、Components.xml:165–168でもaccountのdbIdは別に定義される。Vehicle.idも同XML:1377–1390に別propertyとして定義される。これらのIDを名称の類似だけで混同しない。

※GUI抽出元の版やruntime wrapperの公開属性まで保証する資料ではない。定義上playerIdがないことはB37/B39の欠測と整合するが、すべてのゲームbuildで属性が存在しないという保証へ広げない。

## ModsAPI側との橋渡し

既存MainはgetPlayersInfoのplayerIdまたはidとshipIdを扱う。公開Gist `https://gist.github.com/rapsealk/0e2948433f9f849966227bb4d076e1fa`もid/shipId等を利用するが、GUI Avatar.idとの対応は明記されない。そこから参照される公式フォーラムのModAPI資料も、今回取得できた範囲では対応契約を確認できなかった。

B39では、同一snapshotでavatar.id候補とships[].playerIdの型・値が一致した。これは当該runtime／条件での強い整合性観測だが一般契約の証明ではない。meta rosterもavatar.id fallbackを使うので、candidateとrosterの一致を独立した検証と数えない。

## 出力上の判断

- namespaceはGUI CC.avatar PKと明示できる。
- API playerIdとの一致は引き続きcandidateConsistencyとして記録し、confirmed joinへ自動昇格しない。
- strict avatar.playerId欠測を理由に同じ実機確認を繰り返さない。現行GUI定義にpropertyがない事実を踏まえ、未観測／候補の契約として扱う。
- API一覧外の位置・HPは、GUI主キー候補を添えた独立観測として利用できる。shipsへの推測補完や、API IDとの確定した対応としての出力はしない。

現在0.3.27のruntime契約は変更していない。開始直後FPS低下の追跡は行わず、追加実機テストも不要。
