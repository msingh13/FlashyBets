const assert=require('node:assert/strict'),ts=require('typescript'),fs=require('node:fs'),vm=require('node:vm');
const output={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(__dirname+'/board.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:output.exports,Date,Number});
const {scoreState,scoreValue,gameEmptyMessage,ageLabel}=output.exports;
assert.equal(scoreState({state:'post',completed:false}),'unavailable');assert.equal(scoreState({state:'pre',name:'STATUS_POSTPONED'}),'unavailable');assert.equal(scoreState({state:'post',completed:true}),'post');
assert.equal(scoreValue({value:'3'}),3);assert.equal(scoreValue(null),null);assert.equal(scoreValue(''),null);assert.equal(scoreValue(-1),null);
assert.equal(gameEmptyMessage(8,'post','nhl').title,'No games match this filter.');assert.equal(gameEmptyMessage(0,'all','nfl').title,'No games on this date.');assert.equal(ageLabel('2026-10-27T12:00Z',Date.parse('2026-10-27T14:05Z')),'Updated 2h 5m ago');
console.log('Board regression checks passed.');
