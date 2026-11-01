const CACHE='aegis-shell-v20';
const REGION_PACK_CACHE='aegis-region-packs-v1';
const SHELL=['/','/manifest.webmanifest','/app-icon.svg','/icons/aegis-180.png','/icons/aegis-192.png','/icons/aegis-512.png','/icons/aegis-maskable-512.png','/aegis-splash-1170x2532.png','/aegis-social-preview.png','/aegis-splash.svg','/aegis-social-preview.svg','/aegis-features.css','/aegis-features.js','/aegis-offline-queue.js','/aegis-translations.js','/aegis-premium.css','/aegis-appearance.js','/aegis-addendum.css','/aegis-addendum-logic.js','/aegis-addendum.js'];
self.addEventListener('message',event=>{if(event.data?.type==='SKIP_WAITING')self.skipWaiting();});
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(async c=>{
  await c.addAll(SHELL);
  for(const url of ['https://unpkg.com/leaflet@1.9.4/dist/leaflet.css','https://unpkg.com/leaflet@1.9.4/dist/leaflet.js']){
    try{await c.add(url);}catch(error){console.warn('Leaflet could not be cached for offline use.',error);}
  }
})));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('aegis-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const request=event.request, url=new URL(request.url);
  if(request.method!=='GET'||url.pathname.startsWith('/ws/')) return;
  if(url.origin===self.location.origin&&/^\/api\/resource-packs\/[a-z0-9][a-z0-9-]{1,63}-(?:\d{4}-\d{2}-\d{2}|\d{8}T\d{6}Z)\.geojson\.gz$/.test(url.pathname)){
    event.respondWith(caches.open(REGION_PACK_CACHE).then(async cache=>{
      try{
        const response=await fetch(request);
        if(response.ok)cache.put(request,response.clone()).catch(error=>console.warn('Regional pack could not be cached for offline use.',error));
        return response;
      }catch(error){
        const cached=await cache.match(request);
        if(cached)return cached;
        return new Response('This regional pack has not been downloaded on this device.',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
      }
    }));
    return;
  }
  // These read-only briefs are safe to keep for offline situational awareness.
  // Cached values remain timestamped; mutations and other API data are never cached.
  if(url.origin===self.location.origin&&['/api/situation-room','/api/activity'].includes(url.pathname)){
    event.respondWith(fetch(request).then(response=>{if(response.ok)caches.open(CACHE).then(c=>c.put(request,response.clone()));return response;}).catch(()=>caches.match(request)));
    return;
  }
  if(url.pathname.startsWith('/api/')) return;
  if(url.origin===self.location.origin){
    event.respondWith(fetch(request).then(response=>{if(response.ok)caches.open(CACHE).then(c=>c.put(request,response.clone()));return response;}).catch(()=>caches.match(request).then(cached=>cached||caches.match('/'))));
    return;
  }
  // Keep a small cache of already-viewed static assets. Never cache map tiles or API responses.
  if(url.hostname==='unpkg.com'||url.hostname==='fonts.googleapis.com'||url.hostname==='fonts.gstatic.com') event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response.ok)caches.open(CACHE).then(c=>c.put(request,response.clone()));return response;})));
});
