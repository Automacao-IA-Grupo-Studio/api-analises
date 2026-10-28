const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {createQueue} = require('../desktop-gui/server/jobQueue');
const tick = () => new Promise(r => setImmediate(r));
test('navegação, contenção, duplicidade, concorrência e falha isolada', async () => {
 const tmp = await fs.mkdtemp(path.join(os.tmpdir(),'queue-'));
 try {
  const root=path.join(tmp,'root'); await fs.mkdir(root);
  for(const name of ['a','b','c']) await fs.mkdir(path.join(root,name));
  await fs.writeFile(path.join(root,'a','original.txt'),'original');
  await fs.symlink(tmp,path.join(root,'escape'),'dir');
  let active=0,max=0; const finish=[];
  const q=createQueue({root,concurrency:2,analyze: job => new Promise((resolve,reject)=>{
   active++;max=Math.max(max,active);finish.push(()=>{active--;job.num_job==='b'?reject(new Error('falha esperada')):resolve({job:{id:1}});});
  })});
  assert.deepEqual((await q.browse('')).folders.map(x=>x.name),['a','b','c']);
  await assert.rejects(q.browse('../'));await assert.rejects(q.browse('escape'));
  await q.enqueue([{relative:'a'},{relative:'b'},{relative:'c'}]);await tick();
  await q.enqueue([{relative:'a'}]);assert.equal(q.list().items.length,3);assert.equal(active,2);
  finish.shift()();await tick();assert.equal(active,2);
  finish.shift()();finish.shift()();await tick();
  assert.deepEqual(q.list().items.map(x=>x.status),['concluido','erro','concluido']);assert.equal(max,2);
  assert.equal(await fs.readFile(path.join(root,'a','original.txt'),'utf8'),'original');
  await assert.rejects(q.enqueue([{pasta_raiz:tmp}]));
 } finally {await fs.rm(tmp,{recursive:true,force:true});}
});
