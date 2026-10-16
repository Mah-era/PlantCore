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
console.log('Visual reconciliation passed: full scenario, order-only file, missing history, and unusual labels.');
