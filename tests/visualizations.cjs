const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = vm.createContext({
  palette: {navy:'#123',teal:'#234',amber:'#345',red:'#456',slate:'#567'},
  esc: v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  num: v=>String(Math.round(v)),pct: v=>`${v*100}%`,
  emptyChart: text=>`<p>${text}</p>`,sparkChart: (rows)=>rows.length?'<svg></svg>':'No historical evidence',
  pages:{},pageNames:{},
});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../web/visualizations.js'),'utf8'),context);
const close=(a,b)=>assert.ok(Math.abs(a-b)<.02,`${a} != ${b}`);
for(const fixture of JSON.parse(fs.readFileSync(process.argv[2],'utf8'))){
  context.fixture=fixture;
  const charts=vm.runInContext('buildVisuals(fixture,[],{events:[]})',context);
  assert.equal(charts.length,30);
  close(charts[0].rows.reduce((s,r)=>s+r.value,0),fixture.totals.orders);
  close(charts[1].rows.reduce((s,r)=>s+r.value,0),fixture.totals.units);
  close(charts[2].rows.reduce((s,r)=>s+r.value,0),fixture.totals.expected_exposure);
  close(charts[5].rows.at(-1).required,fixture.totals.units);
  assert.ok(charts[5].rows.every((r,i,rows)=>!i||r.required>=rows[i-1].required));
  close(charts[11].rows.reduce((s,r)=>s+r.value,0),fixture.totals.planned_manufacturing);
  for(const c of charts) assert.ok(!/NaN|Infinity|<script/i.test(c.html),c.title);
  if(!fixture.history.length) assert.ok(charts[19].html.includes('No historical evidence'));
}
context.fixture={portfolio:[{customer:'__proto__',quantity:1,expected_exposure:2,status:'blocked',id:'<script>alert(1)</script>',factory_id:'F',due_date:'2026-10-15'}],factories:[],days:[],heatmap:[],stage_load:[],history:[],flow:[],pareto:[],coverage:{}};
const unusual=vm.runInContext('buildVisuals(fixture,[],{events:[]})',context);
assert.equal(unusual[2].rows[0].value,2);
assert.ok(!unusual[2].html.includes('<script>'));
// A shared deadline must retain early shipment events and late shipment tails.
context.fixture.portfolio = [
  {id:'early',customer:'QA',quantity:100,status:'on_time',due_date:'2026-11-10',plan:{expected_ship:'2026-11-02'}},
  {id:'late',customer:'QA',quantity:200,status:'late',due_date:'2026-11-10',plan:{expected_ship:'2026-11-20'}},
  {id:'blocked',customer:'QA',quantity:50,status:'blocked',due_date:'2026-11-10'},
];
const timeline=vm.runInContext('buildVisuals(fixture,[],{events:[]})[5].rows',context);
assert.deepEqual(JSON.parse(JSON.stringify(timeline)),[
  {date:'2026-11-02',required:0,planned:100},
  {date:'2026-11-10',required:350,planned:100},
  {date:'2026-11-20',required:350,planned:300},
]);
// Verify actual calendar spacing and step paths rather than linear interpolation.
const enterprise=fs.readFileSync(require('node:path').join(__dirname,'../web/enterprise.js'),'utf8');
context.fmt=x=>x;context.legend=()=>'';
vm.runInContext(enterprise.slice(enterprise.indexOf('function sparkChart('),enterprise.indexOf('lineChart =')),context);
const stepSvg=vm.runInContext("sparkChart([{date:'2026-11-02',v:100},{date:'2026-11-10',v:100},{date:'2026-11-20',v:300}],[{key:'v',label:'Shipments',color:'#123'}],{timeScale:true,step:true})",context);
assert.ok(stepSvg.includes('H319.22222222222223 V'), 'Eight of eighteen days must use proportional spacing');
assert.ok(stepSvg.includes('H662 V'), 'Late shipment must appear at timeline end');
console.log('Visual reconciliation passed: full scenario, order-only file, missing history, and unusual labels.');
