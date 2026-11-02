# 0.3.8 B14 gun/reload 記録検証

## 結論

B14の記録は読み取り中にサイズ・mtimeが変わらず、1 meta + 1,473 state行（JSON parse errorなし）、末尾改行ありで、最後は`active:false`の軽量終了stateだった。記録としては完了状態と判断する。検査中のstatは前後とも62,461,394 bytes、mtimeNs=`1793561346221855500`。

0.3.8 `gunReloadProbe`では、`gun` collectionのraw `type=2`・index 0–2の3行が最初の約45秒でprogress `0→45/45`、index 3–5の3行が次の約45秒で同様に進み、battleTimer 90秒時点で6行すべてが`state=1`・progress `1/1`となる。その後index 0（以下G0）だけが再進捗し、136秒の隣接frameで`44.9544/45, state=3`から`1/1, state=1`へ戻る。ユーザーの独立目視報告「最初45秒で3/6、装填完了ほぼ直後一本、その後45秒完了、退出7:30」と照合すると、90秒で全6/6となった後、battleTimer 91秒にG0が再進捗を開始し、92秒・JSONL行888で魚雷1本が初出するため、「全装填後ほぼ直後の一本」と整合する。報告は45秒直後の発射とは述べていない。UI enumとpredicateの外部根拠も限定確認できたため、直接state/progress・UI定義・目視を組み合わせ、Undineの当該条件に限り管別reload対応を確認したと結論する。raw indexは物理的な管番号ではなく、全艦への一般保証でもない。

ユーザー報告は実機画面の独立目視根拠として扱い、ログだけで置き換えない。最初の45秒で3行、次の約45秒で残る3行が進む記録、および90秒時点の全6行fullは「最初45秒で3/6、その後45秒で装填完了」と整合する。行875（battleTimer=90）では6行全てfull/READY。行882→883ではG0がfull/READYから`state=3, progress=0.0926/45`へ変わり（battleTimer=91）、行888（battleTimer=92, observedAt=`2026-11-01T19:28:05.324843Z`）で`torpedoes`が初めて1件となる。この時点のG0は`state=3, 0.6093/45`。したがってユーザーの「装填完了ほぼ直後一本、その後45秒完了」という報告とこの時系列は整合し、発射を45秒直後と読み替える必要はない。行1315→1316（battleTimer=136）でG0は`state=3, 44.9544/45`から`state=1, 1/1`へ遷移する。魚雷初出は発射操作の時刻そのものではなく、記録上で魚雷個体が初めて見えた時刻であり、G0との因果joinを直接証明するイベントIDはない。

## enum / UI predicate 根拠（外部抽出資料）

- `../mino-smoke/research/extracted/gui/data/constants/ships.xml` の`SHIP_WEAPON_TYPES` enumは`TORPEDO=2`（175–184行）。同じ記録のgun raw `type=2`に加え、`reloadBar` collectionにも`weaponType=2`かつ`iconName="torpedo"`があり、type 2を魚雷として読む根拠がある。`gun.type`そのものはsource schemaでsemantics unverifiedのため、外部enum・reloadBar・目視の組合せによる限定的な意味づけである。
- `../mino-smoke/research/extracted/gui/data/constants/weapons.xml` の`GUN_STATE`は`READY=1`, `WORK=2`, `RELOAD=3`, `SWITCHING_AMMO=4`, `RELOAD_STOPPED=5`, `CHARGE=6`, `CRITICAL=7`, `DESTROYED=8`, `SWITCHING_CRITICAL=9`, `DISABLED=10`, `BROKEN=11`（3–18行）。したがって記録中のG0 `state=3`はUI enum上RELOAD、`state=1`はREADY。
- `../mino-smoke/research/extracted/gui/unbound2/pc/battle/reload_bar/guns_reload_bar.unbound` はgun collectionから`gun.type`/`gun.position`を読み、weapon typeでgroupを選び、単管/連装バーのprogress entityにgunまたはbarrel entityを使う（438–503行）。時間表示predicateはgun stateとprogressを使い、WORK時・RELOAD_STOPPED時・故障時を分けて残時間候補を計算（538–564行）。`gunState==READY/WORK`、`isIn(gunState,[RELOAD,SWITCHING_AMMO])`等のUI predicateも定義（743行以降）。これはstateのenum意味を裏付けるが、記録のraw indexから物理管番号への対応を与えるものではない。

## 入力と完全性

- 対象：`recordings/without-atm-b14.jsonl`。先頭metaはmod `0.3.8-gun-reload-diagnostics`、TrainingBattle、Undine（`PBSS106_Undine`）。Docにはplayer名・playerId・battleId・entity IDを転記しない。
- 開始meta時刻は2026-11-01 19:26:33.871 UTC。最初のlive stateのbattleTimer候補は0、最後のlive stateは153。続く最終stateは`active:false`で、probeは終了時軽量schemaのため省略。
- 最初のstatは読み取り開始時、2回目は全行逐次読了後。サイズとmtimeが同一であり、観測したstat上は書込み進行なし。終了stateもあるため、読み取り時点の記録を完了扱いにする（将来の追記が絶対ないという保証ではない）。
- 逐次JSON parse：1,474行を読了、meta 1、state 1,473、壊れた行0。probeありの通常stateは1,472行。最後の1行は`active:false`終了state。

## 0.3.8 source/schemaに従った集計

参照した定義：`res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py` の`GUN_FIELDS`等と`gun_reload_probe`（420–620行）、`Main.py`のstate組立（1244–1265行）、`docs/OUTPUT_SPEC.ja.md`「gunReloadProbe」（195–204行）。毎stateを独立に読み、history/比率/ID順によるjoinは行っていない。raw `false`/`0`は値として保持し、unknownは0扱いしていない。

通常state 1,472件すべてで、`gun`=7 rows、`gunBarrel`=6 rows、`reloadBar`=2 rowsが取得され、各collectionは`available`、`partial:false`、`truncated:false`。通常stateのprobeも`available`。終了stateは軽量形で、これらのcollection欠落を空観測とは数えない。

各通常stateの`gun`にはraw `type=2`が6行（index 0–5）、さらに別の`type=6`が1行ある。raw fieldのschema semanticsはunverifiedだが、外部`SHIP_WEAPON_TYPES.TORPEDO=2`定義、reloadBarの`weaponType=2`/`iconName="torpedo"`と照らして、6行を魚雷gun候補と解釈する。6行それぞれの`barrels` modifier listにはID候補1つずつ、計6候補が記録される。一方`serialLoads`は全行でstatus=`unknown`（配列が取得できた空配列とは異なる）。

各frameでmodifier ID候補の`getEntity(id)`参照を6件ずつ試行。合計8,832件で`entityStatus=unknown`かつprogress component statusもunknown、progress rawなし。`getEntity` getter自体は利用可能として記録されるが、sourceはNone返却と例外を同じunknownへ畳む。したがって参照先の管別progressは取得できず、barrels IDとgunBarrel collection行は結び付けられない。IDはこの文書に出さず、以下はgun indexによる記録内仮名。

| 記録内仮名 | gun raw index | raw type | 進捗の主な区間（value/max） |
| --- | ---: | ---: | --- |
| G0 | 0 | 2 | battleTimer 0–45秒：0→45/45。その後約90秒から再進捗し、約137秒に45/45 |
| G1 | 1 | 2 | 0–45秒：0→45/45。その後も1/1 |
| G2 | 2 | 2 | 0–45秒：0→45/45。その後も1/1 |
| G3 | 3 | 2 | 約45–90秒：0→45/45 |
| G4 | 4 | 2 | 約45–90秒：0→45/45 |
| G5 | 5 | 2 | 約45–90秒：0→45/45 |

このG0–G5対応はcollectionのraw indexを読みやすくした仮名で、entity IDや物理的な管番号の主張ではない。`gunBarrel`は別collectionとして6件あり、progress値のまとまり・遷移時刻は上記gun groupと一致するが、行同士のjoinはしていない。`reloadBar`は2件取得できるがprogress componentではなく、装填数・残り時間に使わない。

`weaponHubProbe.collections.weaponSlot`は独立に取得される。`torpedo_subdefault` slot候補のprogressは最初の45秒に0→45/45、45秒付近に1/1へ切り替わる。その次の45秒区間には1/1のまま。これはslot progressのraw推移で、6行のどれかへ紐付けたり、slotから6/6・3/6を算出したりしない。ログ内にこのprobe由来の直接的な`loaded=3/6`カウンタはない。

## 時系列のraw根拠

時間はゲームUIの実測報告ではなく、同一state内の`gameClockProbe.observations.battleTimerBattleTime`を第一列にした。clockのsource/unit/formulaは出力契約上unverified。`ts`は収集器の単調値で、battle elapsedとは混同しない。

| JSONL行 | battleTimer raw | inferred remaining raw | gun rawの要点 |
| ---: | ---: | ---: | --- |
| 2–3 | 0秒 | 600秒 | 開始時は6行が1/1。次frameでG0–G2が0.105/45、G3–G5が0/1。初期装填の開始を記録 |
| 437 | 45秒 | 555秒 | G0–G2=`44.9405/45`、G3–G5=`0/1` |
| 438 | 45秒 | 555秒 | G0–G2=`1/1`、G3–G5=`0.042499/45`。境界直後に後半3行が進捗開始 |
| 875 | 90秒 | 510秒 | raw type=2の6行すべて`1/1` |
| 882–883 | 90–91秒 | 510–509秒 | G0は前frameの`state=1, 1/1`から`state=3, 0.092564/45`へ。G1–G5は`state=1, 1/1` |
| 888 | 92秒 | 508秒 | `torpedoes`初出1件。G0=`state=3, 0.609254/45`。ユーザー目視の全装填後ほぼ直後の一本と時間的に一致 |
| 1315 | 136秒 | 464秒 | G0=`44.9544/45`、G1–G5=`1/1` |
| 1316 | 136秒 | 464秒 | G0–G5すべて`1/1`。このログで確認できるG0再進捗完了の隣接frame |
| 1473 | 153秒 | 447秒 | 最後のlive state。probe通常形取得、G0–G5すべて`1/1` |
| 1474 | なし | なし | `active:false`終了state。軽量schemaのためprobe/clockを含まない |

JSONL 438→875は、最初の3行がfullになった後、別の3行が約45秒進んで全6行がfullになる根拠。行875→1316は、後段で1行だけがprogressし約45秒でfullへ戻る根拠。行888の魚雷初出はこの再進捗中であり、目視報告と合わせて時間的整合がある。ただし、後段progressを特定の発射操作に帰属させるevent ID・発射可否・loaded countはprobeにない。

## clock・ユーザー報告との限定照合

clock collectionの直接候補はduration=10、battleTimerは0→153。出力された式候補`duration*60-battleTime`は未検証の単位・意味を仮定するため、表示UIの確定値としては扱わない。参考値として終了直前のlive stateで447秒=7:27（最後の非live stateにはclockなし）。ユーザー報告「退出時7:30」とは約3秒差で同じ終盤位置を指す可能性があるが、退出操作そのもののtimestampはログにない。

最初の3行→次の3行という直接進捗、state enum上のREADY/RELOAD、92秒の魚雷初出、およびユーザーの独立目視は、Undine当該条件の管別reload対応を相互に支持する。ただし、発射操作時刻そのもの・物理管番号・発射可否・直接loaded countは確定しない。装填異常なしはユーザーの目視報告であり、このログだけから全条件でゲーム仕様の不具合なしを確定しない。

## 不足と次のコードアクション

- 残る不足は直接取得のloaded count、各管の発射可否、故障/破壊状態の検証、およびraw indexと物理管番号との対応。loaded countを直接取得したとは扱わない。進捗から数える場合も派生候補と明記する。
- modifier参照IDの`getEntity`解決先progressはunknown、`serialLoads`もunknownで、現行probeではNoneと例外を区別できない。これは別経路の制約であり、同一gun entityの管別進捗6行（通常stateすべて取得）による当該Undine試験の確認を取り消さず、ここでの完了条件にも含めない。追加の実機試験やunknown診断ループは不要。
- 次段階は選択魚雷の性能（ammoParams、速度、最大射程）の取得経路調査。残り射程/寿命や全艦一般保証は未確認のまま別課題とする。今回のソース・ゲーム・manifestは変更していない。
