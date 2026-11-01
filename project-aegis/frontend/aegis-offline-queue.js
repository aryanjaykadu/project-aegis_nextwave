/* Small localStorage queue adapter, shared by the UI and executable Node tests. */
(()=>{
  const api={
    list(storage,key){try{return JSON.parse(storage.getItem(key)||'[]').filter(x=>x&&typeof x==='object')}catch{return []}},
    enqueue(storage,key,item){const items=api.list(storage,key);items.push(item);try{storage.setItem(key,JSON.stringify(items));return true}catch{return false}},
    update(storage,key,id,patch){const items=api.list(storage,key),index=items.findIndex(x=>x.id===id);if(index<0)return false;items[index]={...items[index],...patch};try{storage.setItem(key,JSON.stringify(items));return true}catch{return false}},
    remove(storage,key,id){const items=api.list(storage,key).filter(x=>x.id!==id);try{storage.setItem(key,JSON.stringify(items));return true}catch{return false}}
  };
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else globalThis.AegisOfflineQueue=api;
})();
