const test=require('node:test');
const assert=require('node:assert/strict');
const queue=require('../frontend/aegis-offline-queue.js');
function memoryStorage(){const data=new Map();return {getItem:k=>data.has(k)?data.get(k):null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)}}
test('offline reports persist, transition to failed, retry and clear after a receipt',()=>{
  const storage=memoryStorage(),key='queue',report={id:'r1',state:'pending',report:{description:'water on lane'}};
  assert.equal(queue.enqueue(storage,key,report),true);
  assert.equal(queue.list(storage,key)[0].state,'pending');
  assert.equal(queue.update(storage,key,'r1',{state:'failed',error:'server unavailable'}),true);
  assert.equal(queue.list(storage,key)[0].error,'server unavailable');
  assert.equal(queue.update(storage,key,'r1',{state:'pending',error:''}),true);
  assert.equal(queue.remove(storage,key,'r1'),true);
  assert.deepEqual(queue.list(storage,key),[]);
});
test('queue remains readable after malformed local data',()=>{
  const storage=memoryStorage();storage.setItem('q','not json');
  assert.deepEqual(queue.list(storage,'q'),[]);
});
