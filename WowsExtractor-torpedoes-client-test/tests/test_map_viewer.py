"""Lightweight JS logic checks; not a real-browser rendering test."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='optional Node.js logic check')
def test_viewer_handles_battle_changes_stale_and_unknown_values():
    html = Path(__file__).resolve().parents[1] / 'viewer/index.html'
    code = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const html=fs.readFileSync(process.argv[1],'utf8');
const script=html.split('<script>')[1].split('</script>')[0];
const ctx=new Proxy({}, {get:(o,k)=>o[k]||(()=>{}),set:(o,k,v)=>(o[k]=v,true)});
const elements={
 '#map': {getContext:()=>ctx, addEventListener:()=>{},getBoundingClientRect:()=>({left:0,top:0,width:680,height:680})},
 '#status':{textContent:''},'#detail':{textContent:''}
};
let wall=1000;class FakeDate extends Date {static now(){return wall;}}
const sandbox={document:{querySelector:s=>elements[s]},fetch:()=>new Promise(()=>{}),setTimeout:()=>{},Date:FakeDate};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
function run(code){return vm.runInContext(code,sandbox);}
function draw(state,stale=false){sandbox.input={state:{data:state,stale,ageSeconds:0},metaMatches:false};run('draw(input)');}
draw({battleId:'a',active:true,self:{playerId:1},ships:[{uiId:1,playerId:1,nx:.2,ny:.3,visible:true}],
 torpedoStatus:{available:true,status:'available'},torpedoes:[{uiId:2,mapPosition:[.4,.5],uiState:{isHoming:false,isSpotted:null}}]});
assert.equal(run('markers.length'),2);
run('show(markers[1],false)');
assert(elements['#detail'].textContent.includes('UI isHoming: false'));
assert(elements['#detail'].textContent.includes('UI isSpotted: unknown'));
draw({battleId:'a',active:false,ships:[],torpedoes:[]});
assert.equal(run('markers.length'),2);
assert(elements['#status'].textContent.includes('inactive'));
draw({battleId:'b',active:true,ships:[],torpedoes:[],torpedoStatus:{available:true}});
assert.equal(run('markers.length'),0);
draw({battleId:'b',active:true,ships:[],torpedoes:[{uiId:3,mapPosition:[2,.5]}],torpedoStatus:{available:true}},true);
assert.equal(run('markers.length'),0);
assert(elements['#status'].textContent.includes('範囲外'));
const unavailable={status:'collecting',coefficients:{worldX:{mapAxis:'nx',scale:1200,offset:-600},worldZ:{mapAxis:'ny',scale:-1200,offset:600}}};
sandbox.cal=unavailable;assert.equal(run('inverse([0,0,0],cal)'),null);
const low={uiId:8,ownerId:3,shotId:4,mapPosition:[.3,.4],sampling:{group:'low',sampleTs:1,intervalSeconds:.5}};
const grouped={available:true,status:'available',sampling:{low:{status:'notSampled'}},membershipComplete:true,membershipFields:['uiId','ownerId','shotId'],membership:[[8,3,4]]};
draw({battleId:'groups',active:true,ts:1,ships:[],torpedoes:[low],torpedoStatus:grouped});
assert.equal(run('markers.length'),1);
draw({battleId:'groups',active:true,ts:1.2,ships:[],torpedoes:[],torpedoStatus:grouped});
assert.equal(run('markers.length'),1);
assert.equal(run('markers[0].obj.viewerSampleHeld'),true);
run('show(markers[0],false)');assert(elements['#detail'].textContent.includes('現在位置ではない'));
draw({battleId:'groups',active:true,ts:1.4,ships:[],torpedoes:[],torpedoStatus:{...grouped,membership:[]}});
assert.equal(run('markers.length'),0);
draw({battleId:'groups',active:true,ts:2,ships:[],torpedoes:[{...low,sampling:{...low.sampling,sampleTs:2}}],torpedoStatus:grouped});
draw({battleId:'groups',active:true,ts:3.6,ships:[],torpedoes:[],torpedoStatus:grouped});
assert.equal(run('markers.length'),0); // expiry is display policy, not proof of disappearance
draw({battleId:'groups',active:true,ts:4,ships:[],torpedoes:[{...low,sampling:{...low.sampling,sampleTs:4}}],torpedoStatus:grouped});
draw({battleId:'next',active:true,ts:4.2,ships:[],torpedoes:[],torpedoStatus:grouped});
assert.equal(run('markers.length'),0);
draw({battleId:'holds',active:true,ts:10,ships:[],torpedoes:[{...low,sampling:{...low.sampling,sampleTs:10}}],torpedoStatus:grouped});
const incomplete={...grouped,membershipComplete:false,membership:[]};
draw({battleId:'holds',active:true,ts:10.2,ships:[],torpedoes:[],torpedoStatus:incomplete});
assert.equal(run('markers.length'),1);
wall+=1600;
draw({battleId:'holds',active:true,ts:10.2,ships:[],torpedoes:[],torpedoStatus:incomplete},true);
assert.equal(run('markers.length'),0); // frozen game timestamp does not freeze hold expiry
draw({battleId:'holds',active:true,ts:11,ships:[],torpedoes:[{...low,sampling:{...low.sampling,sampleTs:11}}],torpedoStatus:grouped});
draw({battleId:'holds',active:true,ts:11.2,ships:[],torpedoes:[],torpedoStatus:grouped});
assert.equal(run('markers.length'),1);
draw({battleId:'holds',active:false,ships:[],torpedoes:[]});
assert.equal(run('markers.length'),0);
assert.equal(run('torpedoSamples.size'),0);
const collision={...grouped,membership:[[8,3,4],[8.0,3,4]]};
draw({battleId:'collision',active:true,ts:12,ships:[],torpedoes:[{...low,sampling:{...low.sampling,sampleTs:12}}],torpedoStatus:collision});
draw({battleId:'collision',active:true,ts:12.2,ships:[],torpedoes:[],torpedoStatus:collision});
assert.equal(run('markers.length'),0);
'''
    result = subprocess.run([shutil.which('node'), '-e', code, str(html)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
