# WowsExtractor 魚雷出力版（WoWSクライアント用mod）

`0.3.25`は、0.3.24の`diag.playerReads`とindex join契約を維持します。`sampleStatus`（players一覧取得のcomplete/partial/unavailable、direct call時notProvided）、`indexHits`、`vehicleLookups`（試行数、成功数ではない）は引き続きships sample内の個別lookupだけを数え、新しいgame APIや時計読取りは追加しません。

`0.3.26-avatar-observations`は`0.3.25`までの`ships`契約を維持し、同じframeでcaptureしたavatar entityの観測値を独立したトップレベル`avatarObservations`へ追加します。rosterからAPI艦行を合成せず、API列挙の範囲とavatar側で見えた値を混ぜません。

`0.3.27-avatar-id-candidates`は、B37で実機取得できなかったstrict `avatar.playerId`の代替joinを行わず、既存sample済みの`avatar.id`をnamespace付きの未確定candidateとして別出力します。same-snapshotのships playerIdとの厳密scalar一致は匿名countだけで記録し、confirmed coverageとは分離します。

`0.3.28-torpedo-depth-sampling`は既存core魚雷行とowner/guidance契約を変えず、depth候補だけを専用opt-inの1Hz以下sampleに分離します。出力契約は本書後半の「魚雷の明示深度候補」節を参照してください。

## 0.3.27-avatar-id-candidates

```json
{
  "avatarObservations": {
    "status": "complete",
    "source": "dataHub.getEntityCollections(avatar)",
    "sampleTs": 37.5,
    "rows": [{
      "playerId": 123,
      "playerIdStatus": "available",
      "apiPresence": {"status": "missingInApi", "source": "state.ships"},
      "identifierCandidates": {
        "avatarId": {
          "source": "dataHub.avatar.id", "namespace": "avatar.id",
          "status": "available", "raw": 456, "semantics": "unverified"
        }
      },
      "mapPosition": {
        "status": "available", "source": "dataHub.mapPosition",
        "componentStatus": "available", "positionStatus": "available",
        "freshness": "unknown", "raw": [0.25, 0.75], "nx": 0.25, "ny": 0.75
      },
      "health": {
        "status": "available", "source": "dataHub.avatar.health",
        "componentStatus": "available",
        "fieldStatus": {"value": "available", "max": "available", "isAlive": "available"},
        "raw": {"value": 0, "max": 80000, "isAlive": true},
        "normalized": {"health": 80000.0, "maxHealth": 80000.0, "untickedFull": true}
      }
    }],
    "candidateConsistency": {
      "source": "sameSnapshot.avatar.id == state.ships[].playerId",
      "candidateNamespace": "avatar.id", "comparedNamespace": "ships[].playerId",
      "comparison": "strictScalarTypeAndValue", "semantics": "unverified",
      "avatarInputComplete": true, "shipsCompleteness": "unknown",
      "candidateAvailableCount": 24, "candidateExactValueMatchCount": 12,
      "candidateUnmatchedInSnapshotCount": 8, "candidateAmbiguousCount": 4,
      "candidateUnknownCount": 0, "duplicateAvatarIdCount": 2,
      "duplicateShipPlayerIdCount": 1
    },
    "coverage": {
      "sampledEntityCount": 24, "inputStatus": "complete", "inputComplete": true,
      "inputAvailability": "available",
      "reason": null, "limit": 256, "distinctPlayerIdCount": 24,
      "apiMatchedCount": 20, "missingInApiCount": 4,
      "apiPresenceUnknownCount": 0, "unmatchableIdCount": 0,
      "duplicateIdConflictCount": 0, "mapPositionAvailableCount": 24,
      "healthRawAvailableCount": 24
    }
  }
}
```

`identifierCandidates.avatarId`は同一frameの既存`AvatarRows.sample_ids()`に含まれる`avatar.id`のcandidateです。validな有限scalar ID（boolを除く）だけ`raw`を出し、0を保持します。None／欠落／field read status未保存は`status=unknown, reason=notRecorded`、bool・非finite・空文字・非scalar等は`status=unknown, reason=invalidId`としてraw値を出しません。例外文字列や`repr`は出力しません。sample後にゲームcomponentを読み直しません。

`candidateConsistency`は候補値と同snapshotの出力`ships[].playerId`を型・値とも厳密に比較した匿名row countです。`candidateExactValueMatchCount`、`candidateUnmatchedInSnapshotCount`、`candidateAmbiguousCount`、`candidateUnknownCount`は相互排他的にcaptured avatar rowを分類します。重複ID countは重複したdistinct keyの数です。未一致は「この出力snapshotのstrict-valid ship playerIdに値一致がない」というだけで、API上流での不在を意味しません。候補値は`ships`へjoinせず、`playerId`、`apiPresence`、既存`coverage`の全count・意味を変更しません。candidate一致はidentity namespaceの確定でもありません。partial/truncated captureでは`avatarInputComplete=false`を維持し、ships一覧の完全性はunknownです。disabled/notSampled時も同じ形のzero count summaryを出します。

## 0.3.26-avatar-observations

0.3.26から維持する出力・confirmed coverage契約は次のとおりです。

- `status`はavatar captureの`complete` / `partial` / `truncated`を示し、各componentの充足を意味しません。`coverage.inputAvailability`はcollection取得自体の`available` / `unavailable` / `unknown`を示し、None/getter例外時はcapture status `partial`とreason `none`/`getterError`を維持します。`sampleTs`はこのstate buildの`now`で、前frame値を持ち越しません。rowsはcaptureできたentityのみで、ID不明でもraw fieldを観測できればそのrowを出します。
- player join候補は厳密な`avatar.playerId`のみです。`avatar.id`、vehicle ID、roster名簿、team/type/nameから補完しません。整数0は有効、bool・None・空文字・非有限数・非scalarはjoin不能です。IDは型も含めて完全一致させます。非scalar IDを文字列化・`repr`変換して出力しません。
- `apiPresence.status`は`matched` / `missingInApi` / `unknown`です。`missingInApi`は**このsnapshotに出力された`ships`行に厳密一致しなかった**という比較結果だけで、死亡・撃沈・失探・last seenや、上流APIでの非列挙を示しません。現行stateに`getAllShips()`取得成功・完全性のstatusはないため、API一覧の完全性やentity消失をこの値から断定しません。captureがpartial/truncatedで一致しないIDは`unknown`です。avatarまたはships側で同じplayerIdが重複した場合も`unknown` (`duplicateIdConflict`) とし、重複keyをjoinしません。
- `coverage.distinctPlayerIdCount`は有効なavatar playerIdのdistinct数、`unmatchableIdCount`は有効なplayerIdがないcapture row数です。duplicate conflict countは重複したstrict ID値のdistinct数です。その他のcountはrow単位です。`mapPositionAvailableCount`は有限なraw x/yのあるrow数で、roster人数やentity列挙数から位置取得を推定しません。
- `mapPosition`の`raw`は同じentityの`dataHub.mapPosition.position`を読んだ2D値、`nx`/`ny`は既存のminimap正規化候補です。rawが有限なら範囲外でも保持し、範囲検証できない`nx`/`ny`はnullです。`freshness: "unknown"`はゲームcomponentの鮮度保証がないことを表します。component欠測・CC key欠落・component/property例外・position欠測は`componentStatus` / `positionStatus` / `reason`に分け、未知を0へ置換しません。
- `health.raw`は有限scalar等として安全にcopyできた`value` / `max` / `isAlive`そのものです。`fieldStatus`はcomponent/fieldのavailable・欠測・None・例外等を区別します。`normalized`は既存`normalize_ui_health`の結果を別枠で示し、raw 0かつraw `isAlive: true`をdeadへ変換しません（既存規則の`untickedFull`）。raw `isAlive: null`はnullのままです。rawが非scalar/nonfiniteなら出力せず`unsafeScalar`とします。
- partial/truncated captureでも取得済みentityのraw map/health rowsを出しますが、既存ships向けhealth indexは従来どおり無効で、未観測分をalive/deadにしません。未取得 componentとcapture不足はrow statusとtop-level completenessで別々に読めます。
- `avatarObservations`はdisabled時とbattle終端時には空rowsです。disabled出力は`status: "disabled"`、終端は`status: "notSampled"`で、この場合の`coverage.inputAvailability`も`notSampled`です。過去の行をCollector/module/globalへ保存しません。

取得予算：既存の`dataHub.getEntityCollections('avatar')` captureを1回だけ共有し、新しいbattle/API getter、clock read、static roster scanは行いません。0.3.27 candidateは既存sampleにある`avatar.id`を再利用し、ID property/componentの追加readをしません。complete captureでは既存health sampleとmap loopが読んだmapPositionを共有し、観測row組立自体による追加field readはありません。同じentityのmapPosition component/positionは二度読みません。ただしstrict playerIdおよび従来map index用`avatar.id`の両方が欠け、従来map loopでskipしていたrowにもmapPositionを観測するため、そのrowごとにcomponent lookupを最大1回追加します。partial/truncatedの場合は既存health indexを作らない一方、capture済みrowのraw healthを見せるため`health.value/max/isAlive`を各row最大1回ずつsampleします（1 captured entityあたり最大3 property samples。既存attribute/item fallback以外のretryや追加getter/API callなし）。read失敗時のrow無制限fallbackはありません。これらはoffline fixtureで確認したread回数上限であり、新観測処理のruntime時間・FPS影響は未測定です。

新しいprofiler phaseは追加しません。profiler有効時はavatar observation rowの組立を既存`ships` phase wrapper内の`_build_ships`直後に行い、そのphase時間に含めます。無効時はwrapper closureを作らず、既存ships builderとobservation builderを直接呼びます。mapPosition capture自体も従来どおりships処理内です。`avatar` phaseは既存capture/roster/healthのまま、snapshot/cycle合計には全処理が含まれます。source-only offline countはAPI getter回数維持（avatar 1、players info 1、full strict hit時vehicle lookup 0）と24 avatar/20 API shipsを確認します。FPS・実機API内部時間は未計測です。

## 0.3.25-player-field-budget

players一覧をstrict indexにも使うstate buildでは、同じraw PlayerInfoについてdamage cacheとstrict indexが読む`playerId`/`id`、`shipId`/`vehicleId`/`vehicleID`、`teamId`をrow-localのaccess sampleで共有します。item accessとattribute accessの結果・例外は別々にmemoizeし、damage側の「item例外時のみattributeへfallback」とstrict側の「mapping itemがNoneならattributeも確認」をそれぞれ維持します。したがって、競合するmapping key／属性、None alias、raising getterでも解決ルールは同一です。値を一つの汎用getterへ強制統一はしません。getterが同一row内で呼出しごとに値を変える場合は最初の観測値を両consumerで共有します。

sampleとmemoized access結果はrow処理中だけに限定し、返すindex rowはstrictに許可したscalar IDとscalar teamId（またはNone）のみです。damage IDは従来どおりdamage trackerの数値正規化を使い、team値はdamage側の既存規則を保ちます。raw PlayerInfoや非scalar IDをindex／JSONへコピーせず、`repr`による変換もしません。`_remember_roster_vehicles()`のindex不要なstart/direct経路と既存`_remember_player_vehicle()` direct callは旧経路のままで、strict index用field readを追加しません。frame間cacheはありません。

`_build_ships`のpass 1で観測した`ship.teamId`をinfosへ保存し、pass 2の出力生成で再読しません。team 0を保持し、player teamがNoneのときのship team fallbackを維持します。この変更によりteamIdの観測時点は従来のpass 2からpass 1へ早まります。index hit/missおよびdiagnostic fallback dueを含め、1 shipあたり最大1回です。

24行のoffline fixtureでは通常のdict PlayerInfoで`playerId`/`shipId`/`teamId`のkey readsが従来144回（3 field × 24 row × 2 consumer）から72回（3 field × 24 row）へ減り、damage cacheとstrict indexの値を維持します。players getterは従来どおり1回、normal full index hitのvehicle lookupは0回です。別fixtureでitem/attribute競合・raising getter時も各access pathをrow内で最大1回とし、damage／strictの別々の選択結果を確認します。teamIdはhit/miss/diagnostic fallback各経路で最大1回、team 0と出力を維持します。FPS、実ゲーム時間、API内部時間は未測定です。source only・未導入です。

## 0.3.24-player-read-sharing

`diag.playerReads`は当該ships sampleの`sampleStatus`（players一覧取得のcomplete/partial/unavailable、direct call時notProvided）、`indexHits`、`vehicleLookups`（試行数、成功数ではない）を示します。新しいgame APIや時計読取りは追加せず、実機で共有経路の利用状況を確認するためのカウンターです。ships phaseの個別lookupだけを数え、他phase・イベントのAPI呼出し総数ではありません。

## 0.3.24-player-read-sharing

各state buildの`_remember_roster_vehicles`が既存どおり`getPlayersInfo()`を先に1回呼び、戻り値が`None`の場合だけ`getPlayers()`を1回試します。この同じ列挙から、車両IDをkey、`playerId`/`teamId`だけを値とするframe-local plain indexを作り、`_build_ships`へ渡します。追加のplayers getterはありません。`_build_ships`への第4引数はoptional sentinel付きで、旧direct callやイベント経路は従来どおりです。

index joinは型と値がともに完全一致するscalar IDだけを許可し、bool、None、空文字、非finite値、非scalarを拒否します。`0`は有効で、boolと整数0、文字列と整数の相互join・型変換はしません。vehicle IDが重複した場合（同じplayer情報の重複を含む）はそのkeyをambiguousとして索引から外します。playerIdが不正・欠落のrowもhitに使いません。teamIdがNoneならship側teamIdを使い、teamId=0は保持します。ID namespaceの推測joinはしません。

厳密な一意hitは通常core frameで個別`getPlayerByVehicleId`を省略します。index miss、不正な非None ship ID、重複key、一覧のNone/例外は従来lookupへ戻します。ship ID自体がNoneの場合は従来条件どおりlookupを呼ばず、identity unknownのままです。取得済みplayers列挙が途中例外になった場合は`status=partial`のstate-local contextとし、列挙済みのvalid rowだけhitに使います。取得成功の空listと取得不能はcontext上で区別し、partialを完全列挙と偽装しません。context/player objectはCollectorや次stateへ保存せず、damage trackerの既存cacheを艦の現在player identityとして使いません。

`position_fallbacks_enabled=true`かつdiagnostics sample dueの場合は、player objectを使う既存の診断fallbackを保持するため、一覧hitでも従来の`getPlayerByVehicleId`を実行します。これによりplain rowを「player object既知なし」と誤認してplayer position探索を打ち切りません。非due core frameだけが最適化対象です。ship.getPosition、self/observer、HP、visibility、mapPositionのgetter・raw coverage、次frameへの位置持越しは変更しません。Torpedo identity adapterは従来どおり同snapshotの`ships[].playerId`等をstrict candidateとして読むだけで、namespace推測やisOwn上書きをしません。

24艦のoffline producer fixtureでは`getPlayersInfo()` 1回、全row hit時の`getPlayerByVehicleId` 24→0回を確認し、出力行は従来個別lookupの成功値と同値でした。部分missはmiss分のみ個別lookupし、重複/invalid/type mismatchもlookupへ戻します。これはAPI呼出し予算のoffline根拠であり、FPS・WoWS API内部時間・実機性能の改善を意味しません。source only・未導入です。

## 0.3.23-avatar-read-sharing

同一state build内のavatar collectionは従来どおり1回だけ取得します。この版はcollection getter回数を減らしたのではなく、その同じcaptured rowsに対するavatar/vehicle/healthのcomponent・ID property読取りを、roster・health・map positionの3用途で共有する変更です。captureは`complete`/`partial`/`truncated`のstatusとcount/limit/reasonを維持し、新しいJSON fieldは追加していません。

共有sampleはcaptured list自身にだけ遅延生成するplain-data（avatar/vehicleのID、healthのvalue/max/isAlive）で、`Collector`・module global・次frameへ保存しません。次frameは新しいcaptureから再生成し、前frameのsampleを再利用しません。既存の`index_avatar_health(entities, cc)`単独呼出し、`_remember_roster_vehicles()`/`_collect_map_positions()`の引数省略direct call・イベント経路は維持し、その場合は従来どおり各consumerが必要な分だけ読みます。rosterは従来どおり`avatar.playerId`だけをdamage vehicle cacheのplayer keyに使い、`avatar.id`をplayer IDとしてjoinしません。health indexのaliasは従来と同じ`avatar.playerId` / `avatar.id` / `vehicle.id`で、`untickedFull`・`isAlive`・死亡0・max保持の正規化も変更しません。

24行のoffline fixtureで、同じ3用途を個別に読む従来経路はcomponent key access 168回＋ID/health/property access 288回（合計456回）、共有sample経路は96回＋240回（合計336回）です。これはoffline doubles上の読取り回数であり、実ゲームのAPI内部時間・FPS・処理時間の改善を意味しません。`_capture_avatar_snapshot`のgetterは1回のままで、collection API呼出しの削減は主張しません。

partial/truncated snapshotでは、captured rows自身がincomplete状態を持ち、health readerを直接呼んでもindexを空にして未観測rowをalive/deadの根拠にしません。rosterとmap positionは観測済みrowだけを処理し、地図座標の保持と欠落時のunknown/fallback規則を変えません。`CC`がNone、component欠測、property読取り例外は各fieldでunknownとして局所化し、推測joinやteam 0の補完は行いません。

phaseの意味は維持します。avatar phaseはcapture・roster・health、ships phaseはship builderとmapPosition/visibilityです。avatar/vehicle/healthの読取りがavatar phase内の1回に集約され、ships phaseはavatar IDを再読しません。profilerの`avatar`/`ships`は包含phaseのままで、合計時間として加算しません。群別scheduler、players API lookupの削減、位置のframe間cacheはこの版のscope外です。moduleは既存9個のままで、source only・未導入、FPS未計測です。取得項目・出力coverageは変わりません。

## 0.3.22-cadence-budget

`state_interval`の既定を0.2秒（約5Hz）へ変更しました。`collection_enabled=true`時のstate取得・行構築・JSON書込みは、引き続き1つのsnapshotとして同じdueで実行し、群別周期やframe間の位置cacheは導入していません。`state_interval`を明示的に`0.1`にした場合は従来の約10Hz互換で、取得範囲・出力項目は変わりません。collection/diagnostics/profiler/position fallbackの既定OFFも維持します。

`_refresh_meta`のarena ID探索は、state間隔とは独立した`META_RETRY_INTERVAL`（0.5秒）のgateで実行します。metaがreadyでもbattleIdがfallbackなら初期`META_RETRY_SECONDS`（12秒）の期限内は再探索し、遅れてarena IDを取得した場合はmetaを書き直して`battleId`と一致させます。force/戦闘開始時は即時探索します。探索期限の計時はmeta書込み時刻`_lastMetaWrite`と別属性で管理し、build/write失敗時も次の探索まで0.5秒待ちます（catch-upなし）。ゲーム時計の逆行では探索期限を再開放し、非finite時は探索せず、0固定時は同じ時刻で毎frame再探索しません。新しい時計APIは追加していません。

`_build_ships`は`MapCalibration.observe()`が返す同一batchのdiagnostics snapshotを直接使用し、直後の`snapshot()`再構築を削除しました。取得対象・較正sample・24艦あたりの直接位置取得回数は変えていません。

未確認・残る制約：FPS改善は未計測・未確認です。5Hz化により設定上の観測間隔は0.2秒となり、フレーム待ち・処理遅延でさらに延び得ます。従来より短命状態を取り逃がしやすく、表示遅延も増え得ます。`state.json`は非原子的上書きのため、torn readから回復するまでの時間窓も次回の正常な書込みまで続きます（既定間隔は約0.1秒から約0.2秒へ変更）。diagnosticsの設定intervalは1秒で、due評価はstate構築時だけです。実行頻度は診断間隔とstate cadenceの両方に制限されます。魚雷motionは`0 < dt <= 1.0`の差分だけを採用するため、5Hzの通常の更新間隔は範囲内ですが、処理停止やさらに低頻度化して1秒を超えると速度派生が利用不能になります。較正のdrift判定はbatch数基準のため、5Hz化で検出までの実時間は遅くなり得ます。モジュールは既存9個のままで、新しいmoduleはありません。

## 0.3.21-position-read-budget

通常の各ships rowでは、同frameで`_build_ships`が既に得たplayerをresolverへ渡し、艦本体の公開`ship.getPosition()`を最大1回だけ試します。成功した直接world座標を最優先し、失敗時も同frameの`dataHub.mapPosition`、既存の較正補助、visibility unknown時の座標保持は維持します。map座標はworld座標や深度ではなく、較正位置の補助Y=0も深度値ではありません。

`ships[].positionReadStatus`は直接位置取得の`status/source/attempted/reason`、`ships[].positionReadPolicy`はfallbackの`policy/fallbackStatus/attempted`を別々に示します。fallbackを試していない状態は`notSampled`であり、missing/unsupportedを意味しません。直接getter失敗は`unknown`で、None・例外・属性欠落等のreasonを保持します。位置値をframe間でcacheしません。

重い互換fallback（position/worldPosition/positionHull、playerShipInfo/playerInfo、shipGameData等）は既定停止です。`position_fallbacks_enabled=true`を指定しても、`collection_enabled=true`、`diagnostics_enabled=true`かつ1Hz等の診断sample due時だけ実行します。診断OFF・非due時に重い再試行は起動しません。fallbackが試されたships数と未試行ships数は`diag.positionReads`に別カウンタで出し、属性候補read件数と未試行を混同しません。過去版でfallback-onlyだった`position/worldPosition`値は、通常tickでは取得されず、position未取得または較正補助のみとなる場合があります。

## 0.3.20-opt-in-profiling

`profiler_enabled` は既定falseで、`collection_enabled=true`との明示opt-inが両方そろった場合だけ標準timerを固定8 readで初期probeします。collection無効時はtimer read 0回です。`state.performance` はprofiler opt-in時のみ追加されます。5秒window未成立なら`status=notSampled`と`clockStatus=available`を出し、unsupported/disabled/invalid等はclock statusを保持します。window成立時だけ`phases`を含み、各phaseは`count/total/max`のみ（durationはms）。`sampleStartSeconds`/`sampleEndSeconds`はclock自体の秒値です。`timebase.source`と`timebase.basis=assumed`は時計候補と未確認のOS基準を示します。無効なclockで0msレコードは作りません。

区間は `state_cycle_total`, `snapshot_build_total`, `avatar`, `self`, `ships`, `torpedoes`, `armament_systems`, `diagnostics_due`, `submit` の最大9種で、各 `count/total/max` のみです（total/maxはms、countは完了した有効測定数）。`sampleStartSeconds`/`sampleEndSeconds`は選択timerの秒値で、Unix時刻やgame clockではありません。`avatar`はsnapshot capture/roster/health、`self`は自艦info/ship取得とteam解決、`ships`はship builder、`torpedoes`はtorpedo取得・due時UI probe・motion/map変換、`armament_systems`は両adapter、`diagnostics_due`はdue時の詳細probe構築を囲います（schedulerとidentity candidate後処理は含みません）。未知phaseは拒否し、statsを増やしません。計測可能な最大tickでは18 clock readsです。`torpedoes`内のUI probeは同phaseに含まれ、phase値は包含関係を持つため足し算して総時間と解釈しません。p95・毎tick詳細値・各艦/API別timerはありません。`writerMode=asyncHandoff`のsubmitはgame-thread handoff時間でserialize/file I/Oを含まず、`syncEncodeWrite`は同期fallbackのencode/write込みです。異なるmodeの値を同列比較しません。writer thread時間は未計測です。FPS、GPU/draw時間、game API内部時間も未計測です。timer候補・OS基準・分解能は実ゲーム未検証で、`resolutionObserved`はprobeで観測した差であり保証値ではありません。Windows Python 2.7の`time.clock`説明は候補の根拠に留まり、実機runtime挙動は未確認です。詳細は[計測計画](PLAN_PERFORMANCE_PROFILING.ja.md)。

## 0.3.17-snapshot-reuse：既定収集停止・診断sample内collection共有

0.3.14導入後のFPS報告を受けた安全措置として、`collection_enabled` は既定falseです。`config.ini` 不在・読込失敗・不正値も収集停止になり、明示した文字列 `true` のみ有効です。停止中はbattle ship/torpedo API、dataHub収集、Ballistics API、damage/ballistics tracker開始・tick、定期callbackを実行しません。battle lifecycleを維持し、battle shown時のdisabled stateとquit時のinactive stateのみを書きます。stateの`collection`は`{"status":"disabled","source":"config.collection_enabled"}`を示します。外部読取側は通常のtelemetry snapshotが出ないことを許容してください。

収集を明示有効化した場合も `diagnostics_enabled` の既定はfalseです。trueの場合も`diagnostics_interval`（既定1.0秒）で診断一式をまとめてsampleし、非due stateには古いpayloadを再利用せず`status=notSampled`を出します。falseでは`status=disabled`と`source=config.diagnostics_enabled`を出します。0.3.17時点の`state_interval`とcore収集は0.1秒で、core負荷は未評価でした（0.3.22で既定0.2秒へ変更、明示0.1は互換維持）。診断の遅延分catch-upは行わず、時計逆行／不正値・戦闘切替でスケジューラ履歴を初期化します。

診断due時だけsample-local `getEntityCollections` facadeを作り、固定whitelist名の元getter呼出し・戻り値・bounded enumeration結果を同一due sampleの全safe probeで共有します。whitelistはselfVehicle, weaponController, timer, battleTimer, battleInfo, weaponSlot, ammo, serialLoad, gun, gunBarrel, reloadBar, playerAvatar, parameter, torpedo, waveHitです。各名は最大consumer limit+1行をeager captureし、各consumerが従来のlimitでtruncatedを判定します。途中iteration exceptionは取得済み行の後でreplayし、partialを正常完了へ変換しません。getterのNone/exceptionもsample内で再利用します。未指定名や他APIは透過し、新しいgame API呼出しは追加しません。wrapper/row refsはsampleを越えて保持しません。

共有は同じdiagnostic sample内のAPI取得を一度にするものであり、複数field readの原値がゲーム上の厳密な同一frame値である保証ではありません。戻されたrow objectは複数consumerに共有されますが、API側の時間的一貫性は保証しません。元APIが返した例外・None・partial/truncated/unknownをconsumerごとに保ち、getter失敗をbackoffする機能はありません。offline Main統合fixtureで同名original getter呼出しが各1回であることを確認しました。FPSは未評価です。

この変更は同期収集経路の既定停止、診断頻度抑制、診断sample内collection getter共有であり、FPS改善・原因特定を確認したものではありません。通常プレイではmodをロード対象外へ退避することを推奨します。core 0.1秒経路・core 24艦負荷と重いarmament/public_dataは未評価です。詳細は[性能事故記録](PERFORMANCE_INCIDENT_0.3.14.ja.md)。

[Tz-WIND/8111_for_wows](https://github.com/Tz-WIND/8111_for_wows) のクライアント側収集modに、公開ModsAPIの魚雷情報出力を追加したものです。
ベースのコミット: `28470b6ff0c05bac8aa41bd7d986daa6814242e2`。
既存の `state.json` に魚雷関係のフィールドを追加します。
ゲーム外の任意ツールとして [簡易2Dマップ](SIMPLE_MAP.ja.md) とlocalhost読取り専用HTTPサーバーを含みます。

## この文書の対象

本版が書くJSONの仕様です。導入は [INSTALL.ja.md](INSTALL.ja.md)、typeの解釈とATMとの関係は [DESIGN.ja.md](DESIGN.ja.md) を参照してください。
公開API魚雷情報に加え、0.2.2以降はUIのtype/isHomingを診断枠で読み取ります。
0.2.3はisSpottedも追加します。実機の取得状況は [ACQUISITION_STATUS.ja.md](ACQUISITION_STATUS.ja.md)、
診断枠の仕様は [UI_PROBE.ja.md](UI_PROBE.ja.md) を参照してください。

## 追加する出力

既存の `ships`、`self`、`damage` などは維持し、トップレベルに診断項目を追加します。

### `torpedoes`: 可視魚雷の配列

`battle.getAllTorpedoes()` の各 `Torpedo` について、公式資料に記載された7属性をすべて出力します。

| フィールド | 内容 |
| --- | --- |
| `uiId` | 魚雷のUI識別子 |
| `ownerId` | 魚雷の発射元識別子。プレイヤーIDや艦船IDと同一とは扱いません |
| `ownerTeamId` | 発射元のチームID |
| `ownerType` | 発射元種別のAPI値 |
| `shotId` | 射撃ID。同じ斉射の複数魚雷で共有される可能性があるため、魚雷単体の識別には使用しません |
| `type` | 魚雷種別のAPI値をそのまま出力 |
| `position` | `[x, y, z]` のワールド座標。取得できないときは `null` |

追加の整理情報:

| フィールド | 内容 |
| --- | --- |
| `relation` | 自艦のチームとの比較。`1`=味方、`2`=敵、不明=`null` |
| `owner` | `battle.getTorpedoOwnerById(ownerId)` が返す公開情報。取得できないときは `null` |
| `isOwn` | `owner.isPlayer` が真偽値として得られた場合の自艦判定。それ以外は `null` |

`owner` には、公開 `Player` / `Ship` の属性である `teamId`, `isObserver`, `isAlive`, `isBot`, `uiId`, `isPlayer`, `subtype`, `name`, `playerName` を出力します。公式資料では発射元の返り値がPlayerとされる一方、Shipの取得元にも同APIが記載されています。そのため両者の公開属性を読み、存在しない属性は `null` にします。関数として提供される属性を推測して呼ぶことはしません。

位置はAPIの生座標です。`y` をメートル単位の深度と断定せず、距離のメートル換算は行いません。
0.3.0は推定の速度・航向を別枠motionに追加します。詳細は [MAP_MOTION.ja.md](MAP_MOTION.ja.md)。
APIから消えた魚雷は次の正常取得フレームで配列から消えます。

### `torpedoStatus`: 取得状態

```json
{
  "available": true,
  "status": "available",
  "source": "battle.getAllTorpedoes"
}
```

| `status` | 意味 |
| --- | --- |
| `available` | 一覧の取得成功。`torpedoes: []` なら、その取得時点でAPIが返した可視魚雷は0本 |
| `unsupported` | クライアントに `getAllTorpedoes` が存在しない／呼べない |
| `unknown` | 例外、未準備、`None`、列挙途中の失敗など。魚雷0本とは判定できない |

失敗時は `available: false` と空配列を出します。古い魚雷情報を現在情報として残しません。

### `torpedoArmament`: 自艦の魚雷兵装

| フィールド | 内容 |
| --- | --- |
| `available` | 発射管状態または選択弾IDを取得できたか |
| `modulesStatus` | 自艦 `getTorpedoesModulesState()` の取得状態 |
| `modules` | 各発射管の `type`, `currentHP`, `maxHP`, `state`, `critTimer`, `position` をすべて出力 |
| `selectedAmmoStatus` | `getSelectedAmmoId(constants.WeaponType.TORPEDO)` の取得状態 |
| `selectedAmmoId` | 選択中の魚雷弾ID。未取得／無効値 `-1` は `null` |
| `ammoParamsStatus` | 選択弾IDに対する `getAmmoParams()` の取得状態 |
| `ammoParams` | 返り値の公開データ属性をJSON化したもの。未取得なら `null` |

各 `*Status` は `available` / `unknown` / `unsupported` です。発射管の `critTimer` はモジュールの故障関連タイマーであり、装填時間とは扱いません。

`getAmmoParams()` の公式説明は砲弾を中心に記述されているため、魚雷IDでもパラメーターを返すことは保証されていません。クライアントが公開する場合のみ出力します。属性名はクライアント依存で、速度・射程など特定の値が得られることは保証しません。非公開名とメソッドは対象外です。JSON化時は循環参照、非有限数、深さ6以上の複合値を `null` にします。

戦闘終了時の最終フレームは `active: false`, `torpedoes: []`, `torpedoStatus.available: false`, `torpedoStatus.status: "unknown"`, `torpedoArmament.available: false` です。
更新停止の検出は読み手側でファイル更新日時と `ts` を確認してください。

## 出力例

以下の値は説明用の架空値です。`type` / `ownerType` の実際の文字列はAPIの返り値に従います。

```json
{
  "schema": 1,
  "active": true,
  "torpedoes": [
    {
      "uiId": 123,
      "ownerId": 456,
      "ownerTeamId": 0,
      "ownerType": "Ship",
      "shotId": 789,
      "type": "normal",
      "position": [12.0, -3.0, 25.0],
      "relation": 1,
      "owner": null,
      "isOwn": null
    }
  ],
  "torpedoStatus": {
    "available": true,
    "status": "available",
    "source": "battle.getAllTorpedoes"
  },
  "torpedoArmament": {
    "available": true,
    "modulesStatus": "available",
    "modules": [],
    "selectedAmmoStatus": "unknown",
    "selectedAmmoId": null,
    "ammoParamsStatus": "unknown",
    "ammoParams": null
  }
}
```

これは追加項目の抜粋です。実際のファイルには既存の艦船情報なども入ります。ファイル書き込み途中に読む可能性があるため、読み手はJSON解析失敗時に再取得してください。

## 公開APIの範囲と確認状況

通常魚雷・誘導魚雷とも、公開APIが可視魚雷として返した分を同じ方法で出力します。
誘導先、誘導停止までの距離、残存射程、確定寿命、ピンガー命中状態は未取得です。
ATM由来の誘導・被発見状態はuiStateに分離し、type文字列から補完しません。

参照した公式資料（リビジョン `01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2`）:

- [battle API](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/battle.md)
- [Torpedoの全公開属性](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Torpedo.md)
- [Ship](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Ship.md)、[Player](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/Player.md)、[_ModuleState](https://github.com/wgmods/Mods-API-Documentation/blob/01fb0969d4ffa4ec392cdb7f7fdd915092eae6b2/docs/PythonAPI/Classes/_ModuleState.md)

公開APIの代替オブジェクトを使ったオフラインテストに加え、build 13357625で実機試験を行っています。
取得できた値・未検証条件の区別は [SPEC_COVERAGE_0.3.1.ja.md](SPEC_COVERAGE_0.3.1.ja.md) を参照してください。
ゲーム側の追加実測結果は [TEST_REPORT_TEMPLATE.ja.md](TEST_REPORT_TEMPLATE.ja.md) に記録できます。
元プロジェクトのサーバーはこの追加項目をHTTPへ自動公開しないため、外部ツールはまずmodが書く `state.json` を直接読んでください。

ライセンスは元プロジェクトと同じMITです。[LICENSE](../LICENSE) を参照してください。

## state.jsonのトップレベル全項目

以下は今回の収集器が生成する項目です。元プロジェクトのHTTPサーバーが付ける信封ではありません。`serviceId`, `instanceId`, `seq`, `availability`, `capabilities`, `objects`, `bounds` は本modのstateへ追加していません。

| キー | 型 | 内容 |
| --- | --- | --- |
| `schema` | 整数 | ファイル形式。`1` |
| `apiVersion` | 文字列 | ファイル出力契約。`1.0`。ゲーム用 `API_VERSION='API_v1.0'` とは別 |
| `battleId` | 文字列またはnull | 戦闘の識別。実IDが後から得られると途中で昇格することがある |
| `active` | bool | 収集器が戦闘中と認識しているか。明示的退場でfalse |
| `ts` | 数値 | `utils.getTimeFromGameStart()`由来。Unix時刻ではない。取得不能時は0になり得る |
| `self` | オブジェクトまたはnull | 既存の自艦情報 |
| `ships` | 配列 | `battle.getAllShips()`由来の既存艦船情報。avatarから合成しない |
| `avatarObservations` | オブジェクト | 同一frameのcaptured avatar rowから得たstrict player ID・mapPosition・raw/normalized health・shipsとのstrict一致状況。`ships`とは独立 |
| `torpedoes` | 配列 | 今回追加した魚雷の現在フレームの一覧 |
| `identityCandidates` | オブジェクト | 同一snapshotのowner/target ID値一致候補。API契約ではなく、raw fieldを上書きしない（0.3.14） |
| `torpedoStatus` | オブジェクト | 今回の魚雷一覧取得の状態 |
| `torpedoArmament` | オブジェクト | 自艦の魚雷発射管と選択弾の情報 |
| `uiTorpedoProbe` | オブジェクト | UI魚雷の読み取り診断。終了フレームでは省略 |
| `torpedoDepthProbe` | オブジェクト | 専用opt-inの魚雷depth候補sample。disabled/notSampledを含み、過去値を再利用しない |
| `weaponHubProbe` | オブジェクト | UI由来の装填候補を読むread-only診断。終了フレームでは省略 |
| `gunReloadProbe` | オブジェクト | gun/reloadBar/gunBarrel UI候補のread-only診断。終了フレームでは省略 |
| `weaponContextProbe` | オブジェクト | selfVehicle/controller context候補。終了フレームでは省略 |
| `selectedTorpedoParamsProbe` | オブジェクト | 選択descriptorとselfVehicle.shipTTXの限定raw候補。終了フレームでは省略 |
| `gameClockProbe` | オブジェクト | UI参照のraw clock候補と派生残時間候補。終了フレームでは省略 |
| `selfSystems` | オブジェクト | 自艦の消耗品・索敵装置の公開状態。終了フレームでは省略 |
| `damage` | オブジェクト | 既存のダメージ集計 |
| `ballistics` | オブジェクト | 既存の砲弾／航空機弾種の情報。魚雷誘導情報ではない |
| `diag` | オブジェクト | 既存の艦船収集に関する診断値 |
| `performance` | オブジェクト | `profiler_enabled=true`時のみ。5秒集約ができたときだけphase payloadを持ち、その他は小さなstatus metadata。profiler disabledのstateには追加しない |

### `weaponHubProbe`: 装填候補のread-only診断（0.3.4）

調査したunbound UIの参照名から、`weaponSlot`／`ammo`／`serialLoad` collectionと`CC.weaponSlot`／`CC.progress`／`CC.ammo`／`CC.serialLoad` key候補を限定して読む。正式なdataHub公開契約ではなく、Python側の取得可否・shape・意味はいずれも**実機未確認／unverified**。過去版の0.3.3 ZIPとは独立した次版ソース変更。

- collectionごとに`source`, `status`, `semantics`, `componentKeyStatus`, `componentKey`, `rows`, `truncated`, `partial`を出す。getterなし=`unsupported`、例外/None/読み出し不能=`unknown`、正常な空collection=`available`かつ空rows、列挙途中の例外=`partial`、上限超過=`truncated=true`。診断全体の失敗も既存state収集を止めない。
- 各collectionは最大32 entity。slot候補はcomponent `id/type/state/active/selected/shotCount/ammoParamsId/ident`と別component progressの`value/max`。shotCountはUI候補raw値であり残弾断定しない。progressはraw値で残秒や割合と断定しない。
- serialLoadはcomponent `index/weaponType/state`、同じentity上の別progress `value/max`、`entityIdCandidate`を出す。weaponTypeによる絞り込みやslotへの推測joinはしない。
- ammoは独立collection/entityのID候補、component `id/hasSecondaryAmmo/isAutoUsage/squadId`とviewDataの固定限定属性（`ammoId/title/description/subheader/iconPath/secondaryIconPath/uniqueFeatures/paramsDescriptor`）を出す。slot配列とのjoinはしない。
- scalarは有限数、文字列128文字まで。paramsDescriptor/uniqueFeatures等のdict/listも深さ3・各16項目・総64要素以内の安全化だけを行う。任意objectの`dir()`/`repr()`は使わない。各fieldの`fields`はraw scalarそのもので、`fieldStatus`が別に取得可否を持つ。128文字を超えた文字列は`fieldMeta[field]`の`stringLength`/`truncated=true`で元長を示し、既存rawは128文字の互換値を維持する。このmetadataは意味検証ではなく、切り詰めprefixの推測joinを防ぐためのものである。
- status/fieldStatusは値の型・意味を保証しない。falseと0は保持し、欠測はnull/statusで区別する。履歴・UI書き込み・残り射程／寿命計算はない。

### `weaponContextProbe`／`gameClockProbe`（0.3.7）

read-onlyの独立診断。UI/Components.xml由来の候補であり、正式なPython/dataHub契約や全条件の意味を意味しない。B11でnamed collection raw値とユーザー画面報告9:40の整合を当該試験条件内で確認した。これは全条件・確定サーバー情報の保証ではない。

- `weaponContextProbe.selfVehicle`は`keyStatus`、`getterStatus`、`callStatus`、`entityStatus`を段階別に出す。`unsupported`はその段階のAPI/keyが見つからないこと、`unknown`は例外・None・読めない状態であり、runtime key不存在と同義ではない。controller getter pathとnamed collection pathは別経路。
- `weaponContextProbe.collections`は`selfVehicle/weaponController`、`gameClockProbe.candidates`内のcollection routesは`timer/battleTimer/battleInfo`を各最大8 entityだけ試す（重複列挙なし）。各経路でgetter/call/component/row field status、`partial`、`truncated`を記録する。collection名はUI由来の試験候補（semantics unverified）で、空collectionは取得可能な空列挙。複数rowから自艦を選ばず、row間・weaponHubProbeとのjoinを行わない。
- component値は`entity[CC.key]`経路だけで読み、UIの`entity.attr`参照を代用しない。controller候補fieldは`selectedWeapon/activeIdWeapon`、timerは`currentTime/currentServerTime`、battleTimerは`battleTime`、battleInfoは`duration`に限定する。各rawのsource/type/statusは独立している。
- `gameClockProbe.candidates`ではtimer singleton、battleTimer singleton entity上の`battleTimer.battleTime`と兄弟`battleInfo.duration`、battleInfo singleton、named collection routeを別々に記録する。battleTimer entityは一度だけ取得し、フィールド値を経路間の欠損埋めに使わない。raw候補の単位・意味は未検証。
- `battleTimeLeft`は同じ`getSingleEntity(CC.battleTimer)` entityからfiniteな兄弟`battleInfo.duration`と`battleTimer.battleTime`が共に得られた場合のみ計算するUI式候補。`inferred: true`、`formulaStatus: "unverified"`、`sourceUnit: "unverified"`を持つ。別singleton/collection由来値との混合・単位断定はしない。
- `weaponContextProbe.observations.controllerSelectedWeapon/controllerActiveIdWeapon`は成功した`weaponController` named collectionの単一rowだけを明示選択した通常観測。`source/status/raw/type/unit/semantics/scope/sampleTs`を持ち、selectedにはUI predicate参照`VALIDATION_0.3.4_B09_WEAPONS.ja.md` L63とenum未検証を記載する。`weaponSlot.selected`とは別fieldであり、row joinはしない。
- `gameClockProbe.observations`はcollection単一rowから得る直接rawの`timerCurrentTime`、`battleTimerBattleTime`、`battleInfoDuration`と、派生`inferredBattleRemaining`を分ける。残り時間式は`battleInfo.duration * 60 - battleTimer.battleTime`。外部UI静的参照は[`P1_CODE_RESEARCH.ja.md`](P1_CODE_RESEARCH.ja.md)記載の`../mino-smoke/research/extracted/gui/unbound2/pc/battle/battle_timer.unbound` L5-L8、L12。今回の10分duration試験と9:40報告に整合した。durationを分、battleTimeを秒とする解釈を要するため式・単位は未検証。
- collection観測は成功・非partial・非truncatedかつ正確に1 row、field availableの場合のみ値を出す。0/複数row、partial/truncated、null/field失敗はunknownでraw null。collection呼出例外もunknown。時刻は同一stateの`ts`を`sampleTs`に付ける。残り時間は別entityの`battleTimer`／`battleInfo` collectionを同一snapshotで採取した根拠とroute/sourceを持つが、同一entityとは表現しない。scope assumptionとしてduration分・battleTime秒を明示する。booleanを数値時計として扱わず、finite値のみ計算し、負のrawは直接観測で保持するが負のclockから残り時間は推定しない。
- 各候補のstatusと段階statusを確認する。probe全体の`status`だけで個々のfieldの取得可否や意味を判断しない。false/0は保持し、非finite数はunknown/null。呼出しは1 frame内で値を再利用せず、診断にhistoryを持たない。

### `gunReloadProbe`（0.3.8）

UIのreload-bar参照に基づくread-only raw診断であり、正式なPython/dataHub契約や意味・scopeを保証しない。slot progressとは別fieldで、両者をtype/orderで結び付けない。

- `collections.gun`は最大32行、同一entityの`gun` component `id/index/type/state/position/status`と別`progress.value/min/max`、同一gunの`barrelsModifier.barrels/mode`および`serialLoaderModifier.serialLoads`候補を記録する。ID listは各16件まで。
- `collections.reloadBar`は最大32行。`reloadBar.rowsCount/order/prevOrder/iconName/isOutOfBounds`と同entityの`weapon.type`を別々に記録する。reloadBarはprogressを意味しない。
- `collections.gunBarrel`もUI/schemaにある別候補として最大32行取得し、同一entity progressを読む。empty componentや取得不能はavailability statusで区別し、「全管」とは扱わない。
- modifierで明示されたIDだけ、合計最大16個まで`getEntity(id)`で解決を試み、解決先progress候補を記録する。getterの存在状況を明示する。ID一致はUI参照IDとのexact scalar一致に限り、`scope`/source付きでも`unverified`。collection order/typeによるjoinは行わない。取得失敗時はnull/status。
- 各collection 32件、modifier ID各16件、解決ID合計16件、string 128文字、有限scalar、深さ3・限定budget。正常空collection、unsupported key/getter、None/例外、partial enumeration、truncatedを区別する。false/0を保持しunknownをfalse/0へ置換しない。
- 値は毎snapshot独立で、historyなし。割合・残秒・残数の派生なし。probe例外は局所化し、既存state出力を維持する。

### `selectedTorpedoParamsProbe`（0.3.9）

UI参照に基づくread-only診断であり、正式なPython/dataHub契約ではない。`weaponContextProbe.observations.controllerSelectedWeapon`の有限numeric（bool除外）を、成功・completeな最大32行weaponSlotの`fields.type`とstrict scalar一致で一意選択し、そのslot `fields.id`をammo component `fields.id`と型も含めてexact一致させる。選択ammoの`viewData.paramsDescriptor`だけをselectorに使う。`torpedo` / `torpedo_deepwater` / `torpedo_alternative`をそれぞれ`torpedo` / `torpedoDeepwater` / `torpedoAlt`へ対応させる。pingerは`notApplicable`、未知descriptorや複数一致、partial/truncatedはstatus unknown（reasonで原因を保持）。`activeIdWeapon`、`torpedoArmament.selectedAmmoId`、viewData.ammoId、row順/type名による代用joinは禁止。

- producer schemaとの対応：weaponHubの`fields.type`/`fields.id`/`viewData.paramsDescriptor`はraw scalarであり、候補objectではない。取得可否は`fieldStatus`/`viewDataFieldStatus`、元文字列長は`fieldMeta`/`viewDataFieldMeta`を見る。`fieldStatus`がavailableでないfield、componentStatusがavailableでないrowは一致判定に使わない。欠測type/id/component rowが1つでもある場合、それを無視して残り1 rowを一意matchにしない（`reason=incomplete`）。同じtypeのslotが2つ、同じidに一致するammoが2つなら`reason=nonUnique`。row順で選ばない。
- ID一致：空文字・空白のみの文字列は拒否する。前後空白や大文字小文字は正規化しない。`0`は有効な数値IDとして保持する。boolはID・typeに使わず、int/floatは型が異なるため一致しない。Python2のint/long（およびstr/unicode）も型が異なるため等値でも一致しない（安全側の偽陰性として許容）。128文字へ切り詰められた文字列は`fieldMeta.truncated=true`によりjoin不可とし、切り詰め後prefixが同じでも一致扱いにしない。
- `selfVehicle`は完全な単一rowのみ使用し、必要な元entityは`getEntityCollections("selfVehicle")`で一度だけ再取得する。既存のweaponContext/weaponHub collection結果は再利用する。正確な階層は`entity[CC.selfVehicle].shipTTX.torpedoes`のみ。`getFirstWatcher`再利用は旧失敗経路（B11でunsupported確認）のため行わず、entity等への属性総当たりもしない。複数/partial/truncatedはunknown扱い。
- descriptorは型検証済みのstringまたはnullだけを`selection.descriptor`へ出す。非string、None、128文字超過、field未取得はdescriptor nullでunknownとし、descriptor名を文字列化・正規化しない。未知のstringはそのまま記録し既知variantへfallbackしない。
- status段階：`stages`に`selection`、`selfVehicle`、`shipTTX`、`variants`（TTX route全体、`ttxStatus`と同値）、`variant`（選択variantの親status）、`leaf`（選択variantのvalue/delta集約）を分けて出す。top-level `status`は選択結果だけを表し、selfVehicle collectionの取得成功だけでavailableにならない。selectionがunknownならtopもunknown、pingerはtop `notApplicable`。pingerでもTTX routeの失敗は`ttxStatus`/`stages.shipTTX`/`stages.variants`に別途残す。variant親の`available`はspeed/maxDist leafの`available`を意味しないため、`leafStatus`と各field statusを確認する。
- `variants`は最大3候補を固定出力し、選択値へのfallback合成はしない。各variantの`speed.value/delta`、`maxDist.value/delta`のみ、finite numeric・bool除外・±1,000,000以内でrawを保持する。`value`と`delta`は独立に読み、片方の失敗を他方へ流用しない。missing/none/readError/nonNumeric/nonFinite/outOfBoundsを区別し、0と負deltaを保持する。文字列候補は既存固定whitelistで128文字上限。任意の`dir()`/`repr()`なし。
- fieldは`source/status/type/raw/unitHint/semantics`を持つ。UI参照のunitHintはknots/kmであり単位確定ではない。`semantics=unverified`。`displaySemantics.speed`は`candidate=staticTTXDisplayCandidate`、`liveAdjusted=false`、`battleTooltipAlternativeOverridePossible=true`であり、Battle tooltipが代替parameterを使う可能性を許容する。これは静的TTX表示候補であり、補正後live速度・最大射程ではない。alternative variant値の合成やdelta加算をしない。魚雷motionや残射程/残寿命の代用にも使わない。
- probeはsnapshotのみでhistoryなし。safe境界で失敗を局所化し、他のstate fieldを置換しない。

### `torpedoTooltipParameterProbe`（0.3.10）

抽出GUIの読み取り参照を起点にしたread-only診断。Python/dataHub契約・実機可用性・値の意味は未確認。owner経路のGUI根拠は`../mino-smoke/research/extracted/gui/unbound2/pc/battle/weapons_panel/slots/slot_renderer.unbound` L20-L21で、non-airplane weaponは`getSingleEntity(CC.playerAvatar)`、tooltipは同ファイルL291-L292の`ownerEntity.id`を設定する。Pythonでは成功した`getEntityCollections('playerAvatar')`が完全な単一entityで`entity.id`を読めた場合だけowner candidateにする。playerID/vehicleID等からの推測joinは禁止。

- descriptorは既存`selectedTorpedoParamsProbe`を再利用し、`torpedo`→`torpedoSpeed`、`torpedo_alternative`→`torpedoSpeedAlt`、`torpedo_deepwater`→`torpedoSpeedDeepwater`。pingerは`notApplicable`。
- owner key candidateはscalarのUI同等表現だけで作る。bool/null/空文字/長文字列/objectを拒否し、IDの空白除去・case変換・長さ超過文字列の切詰めはしない。
- `getEntityCollections('parameter')`は固定`parameter` component keyだけを使用し最大64行。各行で`entity.id`候補と固定`ownerID/id/baseValue/currentValue/source/status/type`のみ記録。全属性列挙・repr・dirなし。getter/key/call/component/field statusは区別する。
- Parameterの複合primary key候補は`(ownerID, id)`。`selectedParameter.status=available`は、完全なcollection内で`component.id == parameterName`かつ`component.ownerID == ownerEntityId`が型・値ともstrict一致するraw rowがちょうど1件あり、固定fieldが有効な場合のみ成立する。GUI形式の`ownerKeyCandidate`（`<ownerEntityId>_<parameterName>`）は診断metadataであり、component `id`の期待値やfallbackには使わない。このstatusはraw複合PK候補一致で、実GUI lookup成功やowner namespace一般同一性を確定しない。複合PK両fieldがavailableかつ有効で候補と値不一致のrowだけ除外可能。欠測/bool/nonfinite/truncated ID/ownerを含むrowはcollection incompleteとしてunknownを維持し、duplicate/partial/truncatedも選択しない。parameter nameだけへのfallback、型変換、別namespace joinは禁止。
- collection上限超過/途中例外はtruncated/partialでjoin不可。数値候補はfinite・bool除外・±1,000,000以内。historyなし、TTX rawの上書き・delta加算・live速度確定・残射程/寿命推定なし。parameter collectionとraw候補はB18で実機記録済みだが、`selectedParameter.available`は診断上の複合PK候補一致に限り、GUI lookup成功やtooltip実表示の証明ではない。

### `selfSubmarineProbe` / `waveHitProbe`（0.3.12）

`submarine_telemetry.py`のbounded read-only診断。候補名はGUI/schema由来であり、Python取得可用性・値の意味・単位は未確認。active stateに`safe_submarine_probe(dataHub, CC, now)`を一回だけ呼び、同じsnapshot時刻を両probeの`sampleTs`へ渡す。probe失敗時はcallsiteの`_try`が既存state収集を維持する。終了inactive stateは従来どおり軽量schemaでprobeを含まない。

- `selfSubmarineProbe`は`getEntityCollections('selfVehicle')`が完全なsingletonの場合のみ同じentityから固定`CC.submarine`/`CC.battery` componentを読む。深度候補は`depth`, `depthIndex`, `showDepth`, `nearestDepthIndex`。Batteryは`value`, `burnedValue`, `maxCapacity`, `baseSpendRate`, `baseRegenRate`, `currentRate`, `burnRate`, `batteryState`, `isPotentiallyBurning`。false/0を保持し、finite number（bool除外）または厳密bool以外はunknown。
- `waveHitProbe`は`getEntityCollections('waveHit')`を最大32行読み、固定`targetID`, `lifeTime`, `maxLifeTime`, `alertTime`, `hitCount`, `isActive`, `weaponType`だけをraw候補として記録。entity IDはcandidateのままでtargetIDやship IDとjoinしない。
- 追加cache/historyなし。y座標を深度にしない。battery rateの符号/単位・残り時間推定、WaveHit lifetimeからの残秒、ping対象のID join・hitCount解釈は禁止。status/fieldStatus/reasonを確認し、取得状態と意味を分ける。

### UI由来観測metadata（0.3.13）

`interpretations`は既存`fields`と独立したUI用途限定の参考metadataで、raw値・`source`・`fieldStatus`・`fieldType`を置き換えない。metadataは現在snapshotのraw fieldだけから毎回作り、cache/historyや値の持越しをしない。`source`には静的UI参照、`scope`にはB27条件を記録する。UI根拠は公開表示用途を示すものであり、サーバー状態一般の意味/API保証ではない。

| raw field | metadata | 範囲・制約 |
| --- | --- | --- |
| Submarine `depth` | `unitHint: "m"` | UI marker/telegraphがメートル表示する根拠。**出力契約上のraw depthの単位は未確定**で、このmetadataはUI hintであり出力単位の確定ではない。raw depthは丸め・変換しない（UIは0.1 m表示だが、表示丸めは利用側責務）。 |
| `depthIndex` | `interpretation`: `SURFACE`/`PERISCOPE`/`WORKING`/`INVULNERABLE`（enum 0..3） | enum名の併記のみ。unknown enumはmetadata status unknown・interpretation nullでrawは保持する。`INVULNERABLE`を物理的無敵の保証と解釈しない。 |
| Battery `batteryState` | `interpretation`: `IDLE`/`CHARGING`/`FROZEN`/`SPENDING_NORMAL`/`SPENDING_WARNING`/`SPENDING_CRITICAL`/`BURNING`/`EMPTY`（enum 0..7） | unknown enumはrawを保持しmetadataだけunknown。割合、残時間、rateからの派生は出さない。 |
| WaveHit `lifeTime` | `unitHint: "s"`、rawを直接示すinterpretation | UI markerがこの値をcountdown formatterへ直接渡し、秒ラベルを表示する根拠。**秒は当該UI表示値のhintであり、wire raw unitの一般契約ではない**。`maxLifeTime`との引算は禁止。`maxLifeTime`自体の単位はUI根拠から確定しない。 |

`status`は対応raw fieldが現在availableかつ解釈可能なときだけavailable。欠測・不正型・非有限値・bool numeric・未知enumはinterpretation null/unknownとし、従来fieldのraw/status/type保持規則を変えない。bool fieldも従来どおり厳密boolのみavailable。Metadataのvalidation scopeはB27 Undine TrainingBattleのactive 2,233 state samples（Submarine/Battery）および同battle内WaveHit 439 snapshotsに限る。B27はraw取得と操作順との整合を確認した範囲であり、一般条件を確定しない。depth/Battery/WaveHitの同じ実機試験は再要求しない。
- collection列挙はPython builtin名`iter`/`next`を直接参照せず、実績のある`for ... in enumerate(entities)`を使う。上限判定は従来どおりselfVehicleの2件目でmultiple、waveHitのlimit+1件目でtruncated。列挙例外は部分行を破棄し`unknown`/`iterationException`を維持し、`failureStage="enumeration"`とallowlist済み`exceptionType`（不明な型は`other`）を記録する。例外文字列・reprは出力しない。これはPython側互換性テストであり、WoWS sandbox実機での成功保証ではない。

### `identityCandidates`: ID名前空間の同一snapshot候補（0.3.14、未導入）

`identityCandidates`は既存`ships`/`self`/`torpedoes`/`waveHitProbe`だけを読み、同じframe内で厳密scalar値が一致するshipを候補として別出力する診断です。新しいAPI呼出し・history・前frame値の再利用はありません。`ownerId`、WaveHit `targetID`、`ships[].vehicleId`、`ships[].playerId`、`self.playerId`、legacy `isOwn`/`owner`は読み取りのみで、raw値や意味を上書きしません。候補はAPI契約・名前空間確定ではなく、`source.contractStatus=unverified`、`inferred.status=candidate`です。

- トップレベルは`source`, `status`, `semantics`, `contractStatus`, `history="none"`, `apiCallsAdded=0`, `shipsCollection`, `torpedoRowsStatus`, `waveHitUsage`, `evaluatedCount`, `exactCount`, `identityCandidates`を持ちます。`identityCandidates[]`は`candidateRef`/`rowRef`と、魚雷なら`ownerNamespaceCandidate`、WaveHitなら`targetIdNamespaceCandidate`のどちらかを持ちます。raw ID実値は候補側へ複製せず、`candidateMatches[]`は`collection`/`field`/`match`/`rowRef`だけの参照です。
- 入力は厳密scalarだけです。boolは拒否し、数値はfiniteのみ、`int`と`float`、`str`と`unicode`は型が異なれば一致しません。空文字・空白のみ、128文字以上または`fieldMeta.truncated=true`のIDは一致判定に使いません。`0`は有効なIDです。文字列化・trim・case変換・数値変換をしません。
- `shipsCollection.completeness`は常に`unknown`です。現行`ships`列挙は例外・部分列挙・正常空を区別しないため、`diag.totalShips`やroster件数をcompleteの根拠にしません。観測rowがすべて有効IDで重複がなければ`indexStatus=uniqueObserved`、vehicleId欠測/不正があれば`incomplete`、重複があれば`duplicate`です。
- 一致1件かつ`uniqueObserved`のとき`matchStatus=uniqueExact`、`completeness=unknown`、`resolution=candidate`。一致0件は`noExactMatch`かつ`resolution=indeterminate`で、`nonself`/`false`/`noTarget`へ変換しません。一致複数は`ambiguousMultiple`/`ambiguous`で先頭を選ばず、`candidateMatches`は最大8件、超過時は`matchesTruncated=true`と`matchCount`で総数を示します。観測indexがincomplete/duplicateのときは1件一致でも`uniqueExact`にしません。
- 魚雷の`ownerNamespaceCandidate`は、一致shipがちょうど1件で利用可能な場合、そのshipの`playerId`と`self.playerId`の厳密一致を`selfMatchCandidate`へ`exactCandidate`/`nonExactCandidate`/`unknown`の候補statusとして出します。boolを出さず、legacy `isOwn`の生成・上書きには使いません（`isOwnOverride=false`、`usedForIsOwn=false`）。
- WaveHitの`targetIdNamespaceCandidate`は`waveHitProbe.status=available`、`collection.complete=true`、`collection.truncated=false`、`partial=false`のときだけ現在rowを評価します。partial/truncated/complete不明なら`waveHitUsage.status=skipped`と理由を出し、部分rowをjoinしません。`targetShipId`のような単一確定fieldは出さず、`candidateMatches`の候補参照だけにします。一致0件は`indeterminate`です。
- `validationScope`はoffline根拠の範囲を明記します。魚雷はB10/B12/B14の2,014行・4 track・active/selfOnly/singleShipSnapshot、WaveHitはB27の439行・1 target・active/enemyTarget/sevenShipSnapshotです。敵魚雷、僚艦魚雷、多艦snapshot、cross-battle、self target、target切替は未確認（`notCovered`）です。
- helper失敗時は`error=probeFailed`のunknown objectを返し、呼出し側の既存state・raw fieldを置き換えません。

上表は通常フレームです。**終了フレームは軽量形**で、`schema`, `apiVersion`, `battleId`, `active`, `ts`, `ships`, `self`, `torpedoes`, `torpedoStatus`, `torpedoArmament`, `avatarObservations`, `damage`を含みます。`avatarObservations`は`status=notSampled`かつ空rowsで、前frameの値は保持しません。`ballistics`と`diag`はありません。`torpedoStatus.source`も終了フレームではありません。読み手は項目欠落を許容します。

### self（元プロジェクト継承）

候補フィールドは `playerId`, `teamId`, `health`, `maxHealth`, `yaw`, `speed`, `isVisible`, `isShipVisible`, `position`, `isObserver`。
属性の取得可否でキーの有無・nullが変わります。自艦を取得できないときは観戦艦を補助的に読む処理もあります。すべての値が常に揃う保証はありません。

### ships（元プロジェクト継承）

各行の候補フィールド：

- 識別・状態：`uiId`, `vehicleId`, `playerId`, `teamId`, `relation`, `alive`, `visible`。
- 属性・現在位置：`name`, `shipType`, `position`, `nx`, `ny`, `yaw`, `health`, `maxHealth`。
- 最終目撃：`lastPosition`, `lastNx`, `lastNy`, `lastYaw`, `lastHealth`, `lastSeenTs`, `staleSeconds`。

`relation`はこの収集器では原則1=味方、2=敵、不明=-1です。魚雷の不明値nullとは形が異なります。
艦船の位置には地図コンポーネントからの補助変換を含む場合があります。最終目撃情報は現在の敵位置ではありません。魚雷にこの最終目撃保持は適用していません。

### damage（元プロジェクト継承）

```json
{
  "inflicted": {"attackerId": {"total": 1000, "byVictim": {"victimId": 1000}}},
  "received": {"victimId": {"total": 1000, "byAttacker": {"attackerId": 1000}}},
  "teamTotal": {"teamId": 1000}
}
```

上は形の説明用です。実際のキーはIDを文字列にしたものです。未集計では3表とも空です。既存の補助推定・重複抑制のロジックを継承しており、魚雷だけを分類した戦果表ではありません。

### ballistics（元プロジェクト継承）

未取得時は `{"available": false}`。
取得時の候補は `available`, `squadronMode`, `ammoType`, `ammoId`, `penetration`, `impactSpeed`, `impactAngle`。
AP/CSでは `startRicochet`, `alwaysRicochet`, `overmatch`、APでは `detonatorDelay`, `detonatorThreshold`も候補になります。砲弾用情報・計算値であり、魚雷の速度や誘導停止距離として流用しません。

### diag（元プロジェクト継承）

候補は `totalShips`, `allies`, `alliesVisible`, `enemies`, `enemiesVisible`, `ghosts`, `mapCalib`, `mapSamples`, `uiHealth`。0.3.18から`avatarSnapshotStatus`も出力し、core state内で共有したavatar collectionの`status`（`complete`/`partial`/`truncated`）、観測`count`、上限`limit`、`reason`を示します。上限は256 entityで、257件目を検出した場合は`truncated`です。getter戻り値None・getter例外・列挙途中例外は`partial`で、それぞれ`reason=none`/`getterError`/`iterationError`となります。空collectionは`complete,count=0`です。0.3.19ではself/team/armament/systemsのstate-local再利用を追加しましたが、新しいself getter status fieldは追加せず、既存のunknown/unsupported出力を維持します。
`mapCalib`は地図座標の補助変換方式、`mapSamples`はその校正用サンプル数です。魚雷のtype取得成功を示す診断値ではありません。
このsnapshotは各state build内で一度だけ取得し、roster vehicle、avatar health、map positionへ渡します。healthはsnapshotがcompleteの場合のみ補助適用し、partial/truncatedの未観測を死亡判定に使いません。partial/truncated時のmap/rosterは観測済みrowだけを扱い、欠落位置は通常fallback/unknownのままです。前stateからの値持越し・global dataHub書換えはありません。イベント経路のroster lookupは独立取得を維持します。

## meta.jsonの全トップレベル項目

| キー | 内容 |
| --- | --- |
| `schema` | 1 |
| `apiVersion` | ファイル出力契約1.0 |
| `battleId` | 戦闘識別。stateと照合する |
| `mod` | `name=WowsExtractor`、`version=0.3.1-map-motion` |
| `ts` | 収集時刻。stateと同じゲーム由来の時間 |
| `battleType` | 戦闘種別。取れない場合gameMode等を補助として使う |
| `gameMode` | ゲームモード、欠損時null |
| `selfPlayerId` | 自プレイヤーID、欠損時null |
| `map` | 取得できた地図の公開属性 |
| `roster` | 既存の名簿・消耗品情報 |

`map`は動的です。候補は `geometryName`, `geometry`, `mapName`, `spaceName`, `spaceId`, `mapPath`, `name`, `mapId`, `arenaName`, `width`, `height`, `size`, `worldSize`, `spaceBounds`, `bounds`, `minX`, `maxX`, `minY`, `maxY`, `minZ`, `maxZ`, および認識用に補った `id`。常に境界が得られるわけではありません。

`roster[]`の候補は `playerId`, `teamId`, `relation`, `name`, `shipType`, `shipName`, `shipTier`, `consumables`。
`consumables[]`は `title`, `abilityId`, および公開属性から作る動的な `params`。これは魚雷の装填状態表ではありません。

metaは戦闘表示時に書き、遅れて到着する地図情報等のため初期に再試行することがあります。終了時に空のmetaへ置き換えません。stateとmetaは別ファイルなので、一方だけ新戦闘の状態になる短い期間があります。

## 読み手の契約

1. UTF-8のJSONとして読む。解析失敗や一時的なファイル欠落では再試行する。
2. `active`、`battleId`、`ts`とファイル更新日時を確認する。`ts`だけをUnix時刻として扱わない。
3. `torpedoStatus.available`がtrueの場合だけ、その回の配列を正常な観測として扱う。
4. `type`の未知値、null、他の任意項目の欠落を許容する。未知typeをnormalへ置き換えない。
5. 更新停止を終了と同一視しない。必要に応じ最後の観測を「古い」と明示し、現在の誘導状態として使わない。
6. IDの別名前空間を混ぜず、戦闘をまたいで同じ魚雷と扱わない。battleId昇格時は同じ戦闘の可能性も考慮する。

各収集間隔は目標値です。ディスク遅延や非同期ライターの最新優先によって、すべてのtickがファイルへ出る保証はありません。

## 型・欠損の補足

- 魚雷7属性とownerの候補属性は原則キーを持ち、取れない属性はnullです。positionもnullになり得ます。
- ownerのisAliveがメソッドとして返る場合、勝手に呼び出さずnullとして出します。
- 発射管modulesの空配列は、取得成功なら0個として扱います。取得失敗の空配列とはStatusで区別します。
- `torpedoArmament.available=true`でも、すべての下位項目が取れたとは限りません。下位Statusを確認します。
- 状態生成の外側の保護で例外を捕捉した場合、torpedoArmamentが `{"available":false}`だけになることがあります。
- 引数不足等の呼び出し例外はunknown、取得口自体がない場合はunsupportedです。細かい失敗理由をこの版のJSONは出しません。
# 0.3.2以前の出力変更について

現行の観測値・可視状態・最終目撃フィールド撤去は [OBSERVATIONS.ja.md](OBSERVATIONS.ja.md) を優先してください。

## 0.3.3 可視候補診断

`ships[].visibility` は既存フィールドを維持し、追加で以下を出力する。

```json
{
  "dataHubCandidates": {
    "mapVisible": {"source":"dataHub.visibility.mapVisible","status":"available","raw":false,"type":"bool","reason":null},
    "visible": {"source":"dataHub.visibility.visible","status":"missing","raw":null,"type":"NoneType","reason":"attributeMissing"}
  },
  "shipApiCandidates": {
    "isVisible": {"source":"shipApi.isVisible","status":"available","raw":true,"type":"bool","reason":null}
  },
  "dataHubComponentStatus":"available",
  "semantics":"unverified"
}
```

候補別statusは厳密なbool判定で、`available`（bool値。falseを含む）、`missing`、`none`、`readError`、`nonBoolean`、`componentMissing`、`componentReadError`、`ccKeyMissing`。したがって数値0/1は候補診断では `nonBoolean` だが、有限数値として互換フィールド `visibility.raw` に残り、旧 `visible` 投影では0/1をfalse/trueとして扱う。`type`は `bool/int/float/string/NoneType/object` の限定ラベル。`raw`は有限な数値・bool・128文字以内の文字列だけを複製し、それ以外はnull。非有限数は `nonBoolean` と `reason=nonFiniteNumber` で診断し、JSON rawへ出さない。通常互換フィールド `visibility.raw`／`shipApi` は有限数値/boolのみを従来形式で維持する。

`dataHubCandidates` と `shipApiCandidates` はそれぞれ別取得経路で、API候補をdataHub値の代用にはしない。旧 `visibility.status` は互換raw値のいずれかが出力されたことを表すだけで、候補の意味や発見状態を確定しない。mapVisible由来の `visible` 投影と座標出力は変更しない。診断値が取得できても発見状態の意味は未検証。新フィールドのゲーム実機取得は未確認。
# 魚雷の明示深度候補（0.3.28-torpedo-depth-sampling、source only）

`torpedo_depth_sampling_enabled=true`で、`collection_enabled=true`かつ`diagnostics_enabled=false`でも専用samplerが動作します。設定例は`res_mods/PnFMods/WowsExtractor/config.example.ini`を参照してください。interval既定値は1.0秒、invalid値は1.0秒、最小値も1.0秒です。due判定は通常state構築ごとに行うため、実行間隔はこのintervalと`state_interval`（既定0.2秒）の双方で制約されます。遅延分のcatch-upはありません。collectionが無効ならsamplerは有効にならず追加dataHub API callは0回です。

- due時だけ`dataHub.getEntityCollections('torpedo')`から`CC.torpedo` componentの固定`id`／`depth`候補を最大64 entity読みます。65個目はtruncation検出だけに使い、そのentityのcomponent/fieldは読まず、元collectionが巨大でも最大65件でiterationを止めます。ゲームentity objectはsample-localで、frame間へ保持しません。任意`dir()`／`repr()`、owner/player ID、距離、`position.y`、前frame値による補完はありません。
- 同じstate sampleで従来のheavy diagnosticsもdueの場合、同じ`DiagnosticCollectionSnapshot`を使い、`getEntityCollections('torpedo')` getter／元collection iterationを重複させません。専用samplerはheavy `safe_*` probe群を起動しません。heavy diagnosticsの既存scheduler/設定とは独立です。
- `torpedoDepthProbe.status`と`collection.status`は`disabled`／`notSampled`／`unsupported`／`unknown`／`available`／`partial`／`truncated`を区別します。partialでは列挙済みraw rowsを残しますが、全体の一意性を保証できないためAPI行へjoinしません。`sampleTs`はdue sample時だけ設定し、それ以外はnull。非due stateではrows空、depth未付与で、前回値を再利用しません。
- `rows[]`は`entityIdStatus`／`entityIdCandidate`、`depth`、`apiMatchStatus`を持ちます。`depth`は`source=dataHub.torpedo.depth`、`status`、`type`、`raw`、`unit=null`、`semantics=unverified`です。有限numeric（bool除外）のrawだけを保持し、0もそのまま保持します。欠落／None／readError／nonNumeric／nonFiniteとcomponent欠測を分離します。ローカルGUI抽出`Components.xml`の`Torpedo.depth:Number sync=false`は候補名の根拠のみで、現在buildのPython/dataHub可用性・値の意味・単位の根拠ではありません。
- `torpedoes[].uiState.depth`への付与は同じstate内のAPI rowsとGUI rowsの両側で、IDがscalarかつ同じPython型・値で、各側一意、GUI collection complete (`available`)、API列挙availableの場合だけです。API rowsが64件を超える場合も一意性確認を打ち切り付与しません。`1`と`"1"`、bool/int、float/intは一致させません。重複・型違い・不一致・API unavailable・partial/truncatedでは付与しません。owner／playerID名前空間の推測joinは禁止です。
- `uiTorpedoProbe`の既存公開関数signatureは維持します。Mainのheavy diagnostic経路ではdepthを読まないdepth-free helperを使い、独立samplerが有効なdue sampleでだけdepthを読みます。単独呼出しの既存`ui_torpedo_probe` helperは後方互換のため従来のcandidate fieldを出せますが、Mainでは使いません。

B37ではdepth専用sampleがOFFだったため取得実績はありません。0.3.28はsource only・未導入であり、次回は通常の魚雷発射記録に同乗するdepth候補の取得可否確認だけが必要です。単位・基準面・`position.y`との関係、対象艦深度・深度差は未確定です。新moduleは追加せず既存9 module構成を維持します。
