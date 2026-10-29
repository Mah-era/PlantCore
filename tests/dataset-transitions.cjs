const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('web/app.js', 'utf8');
const surfaces = [{inert:false}, {inert:true}];
const nodes = new Map();
let release, calls = 0, overlays = 0;
const ctx = vm.createContext({
  console, setTimeout, URL,
  document: {
    querySelector: key => { if (!nodes.has(key)) nodes.set(key, {}); return nodes.get(key); },
    querySelectorAll: () => surfaces,
    createElement: () => ({setAttribute(){}, remove(){overlays--;}}),
    body: {appendChild(){overlays++;}},
  },
});
vm.runInContext(source, ctx);
ctx.testApi = async () => {calls++; await new Promise(resolve => {release=resolve;});};
vm.runInContext('api=testApi; loadScenarioCatalog=async()=>{}; go=async()=>{}; toast=()=>{};', ctx);
(async () => {
  const pending = vm.runInContext('changeScenario("first")', ctx);
  assert.equal(overlays, 1);
  assert.ok(surfaces.every(el => el.inert));
  await vm.runInContext('changeScenario("second")', ctx);
  await vm.runInContext('uploadScenario({name:"test.csv",size:1})', ctx);
  await vm.runInContext('downloadReport("management.json")', ctx);
  assert.equal(calls, 1, 'Overlapping changes and exports must not start');
  release(); await pending;
  assert.equal(overlays, 0);
  assert.equal(vm.runInContext('state.datasetBusy', ctx), false);
  assert.deepEqual(surfaces.map(el=>el.inert), [false,true]);
  vm.runInContext('api=async()=>{throw Error("Selection failed")}', ctx);
  await vm.runInContext('changeScenario("invalid")', ctx);
  assert.equal(overlays, 0);
  assert.equal(vm.runInContext('state.datasetBusy', ctx), false);
  await vm.runInContext('uploadScenario({name:"large.csv",size:3000001})', ctx);
  assert.equal(overlays, 0);
  assert.equal(vm.runInContext('state.datasetBusy', ctx), false);
  console.log('Dataset transition regression checks passed');
})().catch(error => {console.error(error); process.exitCode=1;});
