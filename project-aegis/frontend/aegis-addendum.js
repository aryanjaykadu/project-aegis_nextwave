(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const safeRead = (key, fallback) => {
    try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback; }
    catch (error) { console.warn(`Could not read local setting ${key}.`, error); return fallback; }
  };
  const safeWrite = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (error) { console.warn(`Could not save local setting ${key}.`, error); return false; }
  };
  const logic = globalThis.AegisAddendumLogic;
  const keys = {
    recent: 'aegis-recent-searches-v1',
    places: 'aegis-saved-places-v1',
    contact: 'aegis-emergency-contact-v1',
    lastOnline: 'aegis-last-server-check-v1',
    errors: 'aegis-technical-errors-v1'
  };
  const t = (en, hi) => (document.documentElement.lang.toLowerCase().startsWith('hi') && hi) ? hi : en;
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[ch]));

  const banner = document.createElement('div');
  banner.id = 'aegis-offline-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.hidden = true;
  document.body.append(banner);
  let bannerTimer = 0;
  function showNetworkState(offline) {
    clearTimeout(bannerTimer);
    if (offline) {
      banner.textContent = logic?.networkBanner({ online: false, lastSuccess: safeRead(keys.lastOnline, '') }) || t('Offline · cached data may be out of date. Check each source time.', 'ऑफ़लाइन · कैश किया डेटा पुराना हो सकता है। हर स्रोत का समय जाँचें।');
      banner.hidden = false;
      return;
    }
    if (banner.hidden) return;
    banner.textContent = t('Connection restored. Refresh data when ready.', 'कनेक्शन वापस आया। तैयार होने पर डेटा रीफ़्रेश करें।');
    bannerTimer = setTimeout(() => { banner.hidden = true; }, 3200);
  }
  window.addEventListener('offline', () => showNetworkState(true));
  window.addEventListener('online', () => showNetworkState(false));
  if (!navigator.onLine) showNetworkState(true);
  async function checkServer() {
    if (!logic?.shouldPoll({ hidden: document.hidden, dataSaver: isDataSaver() }) || !navigator.onLine) {
      if (!navigator.onLine) showNetworkState(true);
      return;
    }
    try {
      const response = await fetch('/api/status', { cache: 'no-store', signal: AbortSignal.timeout?.(5000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      safeWrite(keys.lastOnline, new Date().toISOString());
      showNetworkState(false);
    } catch {
      showNetworkState(true);
    }
  }
  let lowBatterySaver = false;
  const isDataSaver = () => safeRead('aegis-data-saver-v1', false) || Boolean(navigator.connection?.saveData) || lowBatterySaver;
  const statusInterval = () => isDataSaver() ? 300000 : 60000;
  if (navigator.getBattery) navigator.getBattery().then(battery => {
    const updateBatteryMode = () => {
      lowBatterySaver = !battery.charging && battery.level <= 0.15;
      if (statusTimer) clearInterval(statusTimer);
      statusTimer = document.hidden ? 0 : setInterval(checkServer, statusInterval());
    };
    battery.addEventListener('levelchange', updateBatteryMode);
    battery.addEventListener('chargingchange', updateBatteryMode);
    updateBatteryMode();
  }).catch(() => {});
  let statusTimer = setInterval(checkServer, statusInterval());
  checkServer();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearInterval(statusTimer);
      statusTimer = 0;
      document.body.classList.add('aegis-background-paused');
    } else {
      document.body.classList.remove('aegis-background-paused');
      if (!statusTimer) statusTimer = setInterval(checkServer, statusInterval());
      checkServer();
      if (typeof map !== 'undefined') requestAnimationFrame(() => map.invalidateSize());
    }
  });

  const credits = document.createElement('aside');
  credits.id = 'aegis-map-credits';
  credits.innerHTML = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a> · <button type="button" class="aegis-credits-open">Sources &amp; licenses</button>';
  document.body.append(credits);

  function overlay(id, title, content) {
    const root = document.createElement('div');
    root.id = id;
    root.className = 'aegis-overlay';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML = `<section class="aegis-panel" role="dialog" aria-modal="true" aria-labelledby="${id}-title"><div class="aegis-actions" style="justify-content:space-between"><h2 id="${id}-title">${title}</h2><button type="button" class="aegis-close" aria-label="Close">Close</button></div>${content}</section>`;
    document.body.append(root);
    root.addEventListener('click', event => { if (event.target === root) closeOverlay(root); });
    root.querySelector('.aegis-close').addEventListener('click', () => closeOverlay(root));
    root.addEventListener('keydown', event => { if (event.key === 'Escape') closeOverlay(root); });
    return root;
  }
  let lastFocus = null;
  function openOverlay(root) {
    lastFocus = document.activeElement;
    root.setAttribute('aria-hidden', 'false');
    root.querySelector('button, a, input, select')?.focus();
    document.body.classList.add('aegis-overlay-open');
  }
  function closeOverlay(root) {
    root.setAttribute('aria-hidden', 'true');
    if (!$('.aegis-overlay[aria-hidden="false"]')) document.body.classList.remove('aegis-overlay-open');
    lastFocus?.focus?.();
  }

  const emergency = overlay('aegis-emergency-screen', t('EMERGENCY MODE','आपातकालीन मोड'), `
    <p><strong>Research prototype—not an official alert.</strong> No help is dispatched by this app.</p>
    <div class="aegis-emergency-grid">
      <a class="aegis-action" href="tel:112" aria-label="Call India's emergency number 112">Call 112</a>
      <button type="button" id="aegis-emergency-sms">Send location by SMS</button>
      <button type="button" id="aegis-emergency-nearest">Nearest cached help</button>
      <button type="button" id="aegis-emergency-safe">I'm safe</button>
    </div>
    <label><span><input id="aegis-emergency-exact" type="checkbox" style="width:22px;min-height:22px"> Include exact location for this emergency only</span></label>
    <p id="aegis-emergency-status" role="status">Uses cached listings and your chosen map pin unless you request location.</p>
    <button type="button" class="aegis-secondary" id="aegis-emergency-exit">Exit emergency mode</button>`);
  const emergencyButton = document.createElement('button');
  emergencyButton.id = 'aegis-emergency-open';
  emergencyButton.type = 'button';
  emergencyButton.textContent = 'SOS';
  emergencyButton.setAttribute('aria-label', t('Open offline emergency actions','ऑफ़लाइन आपातकालीन विकल्प खोलें'));
  (document.querySelector('.top-bar') || document.body).append(emergencyButton);
  emergencyButton.addEventListener('click', () => openOverlay(emergency));
  $('#aegis-emergency-exit').addEventListener('click', () => closeOverlay(emergency));
  const emergencyStatus = $('#aegis-emergency-status');
  function getCurrentTarget() {
    return typeof currentTarget !== 'undefined' ? { lat: currentTarget.lat, lon: currentTarget.lng } : { lat: 25.5941, lon: 85.1376 };
  }
  function roundedPoint(point) { return { lat: Number(point.lat.toFixed(3)), lon: Number(point.lon.toFixed(3)) }; }
  async function askPermission({ title, explanation, stored }) {
    const prompt = overlay(`aegis-permission-${Date.now()}`, title, `<p>${explanation}</p><p><strong>Stored:</strong> ${stored}</p><div class="aegis-actions"><button type="button" class="aegis-permission-continue">Continue</button><button type="button" class="aegis-secondary aegis-permission-cancel">Not now</button></div>`);
    return new Promise(resolve => {
      let answered = false;
      const finish = allowed => {
        if (answered) return;
        answered = true;
        closeOverlay(prompt);
        prompt.remove();
        resolve(allowed);
      };
      prompt.querySelector('.aegis-permission-continue').addEventListener('click', () => finish(true));
      prompt.querySelector('.aegis-permission-cancel').addEventListener('click', () => finish(false));
      prompt.querySelector('.aegis-close').addEventListener('click', () => finish(false));
      prompt.addEventListener('click', event => { if (event.target === prompt) finish(false); });
      prompt.addEventListener('keydown', event => { if (event.key === 'Escape') finish(false); });
      openOverlay(prompt);
    });
  }
  function requestLocation() {
    return new Promise(async (resolve, reject) => {
      if (!navigator.geolocation) { reject(new Error('Location is not supported on this device.')); return; }
      const allowed = await askPermission({
        title: t('Use your location?','स्थान का उपयोग करें?'),
        explanation: t('Location helps center the map or prepare an emergency message. It is not sent by Aegis unless you choose to share it.','स्थान नक्शे को केंद्रित करने या आपातकालीन संदेश बनाने में मदद करता है। आपकी अनुमति के बिना Aegis इसे साझा नहीं करता।'),
        stored: t('Not stored by this permission prompt.','इस अनुमति अनुरोध से संग्रहित नहीं होता।')
      });
      if (!allowed) { reject(new Error(t('Not now. You can search or use the map pin.','अभी नहीं। आप खोज या नक्शे का पिन इस्तेमाल कर सकते हैं।'))); return; }
      navigator.geolocation.getCurrentPosition(position => resolve(position.coords), error => reject(error), { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
    });
  }
  globalThis.aegisAskLocation = requestLocation;
  function currentPoint({ exact = false } = {}) {
    if (exact) {
      return requestLocation().then(coords => ({ lat: coords.latitude, lon: coords.longitude, exact: true }));
    }
    return Promise.resolve({ ...roundedPoint(getCurrentTarget()), exact: false });
  }
  function smsUrl(number, body) {
    const encoded = encodeURIComponent(body);
    return `sms:${encodeURIComponent(number)}${/iPad|iPhone|iPod/.test(navigator.userAgent) ? '&' : '?'}body=${encoded}`;
  }
  function savedContact() { return String(safeRead(keys.contact, '') || '').trim(); }
  async function prepareSms(messageKind) {
    const number = savedContact();
    if (!number) {
      emergencyStatus.textContent = 'Add a trusted contact in Settings first. No message was sent.';
      return;
    }
    try {
      let point, exactUnavailable = false;
      try { point = await currentPoint({ exact: $('#aegis-emergency-exact').checked }); }
      catch (error) {
        point = { ...roundedPoint(getCurrentTarget()), exact: false };
        exactUnavailable = true;
      }
      const lat = point.exact ? point.lat.toFixed(5) : point.lat.toFixed(3);
      const lon = point.exact ? point.lon.toFixed(5) : point.lon.toFixed(3);
      const body = messageKind === 'safe'
        ? `I'm safe. My location${point.exact ? '' : ' (approximate)'}: ${lat}, ${lon}.`
        : `I need help. My location${point.exact ? '' : ' (approximate)'}: ${lat}, ${lon}.`;
      emergencyStatus.textContent = `${exactUnavailable ? 'Exact location was unavailable; using the approximate map pin. ' : ''}SMS draft: ${body} Review and send it yourself; Aegis does not send messages.`;
      const link = smsUrl(number, body);
      if (/iPad|iPhone|iPod|Android/i.test(navigator.userAgent)) location.href = link;
      else if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(body);
          emergencyStatus.textContent = 'SMS is not available in this browser. The message text was copied; paste it into your SMS app. Nothing was sent.';
        } catch {
          emergencyStatus.textContent = `SMS is not available here. Copy this message manually: ${body}`;
        }
      } else {
        emergencyStatus.textContent = `SMS is not available here. Copy this message manually: ${body}`;
      }
    } catch (error) { emergencyStatus.textContent = error.message || 'Location unavailable. Use the map pin; no message was sent.'; }
  }
  $('#aegis-emergency-sms').addEventListener('click', () => prepareSms('help'));
  $('#aegis-emergency-safe').addEventListener('click', () => prepareSms('safe'));
  $('#aegis-emergency-nearest').addEventListener('click', () => {
    const cache = safeRead('aegis-resource-cache-v1', []);
    const point = getCurrentTarget();
    const items = cache.flatMap(entry => entry.results || []).filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
    if (!items.length) { emergencyStatus.textContent = 'No cached mapped resource is available. Call 112 or search when connected.'; return; }
    const distance = item => {
      const rad = value => value * Math.PI / 180;
      const dLat = rad(Number(item.lat) - point.lat), dLon = rad(Number(item.lon) - point.lon);
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(point.lat)) * Math.cos(rad(Number(item.lat))) * Math.sin(dLon / 2) ** 2;
      return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };
    const nearest = items.sort((a, b) => distance(a) - distance(b))[0];
    emergencyStatus.textContent = `${nearest.name || nearest.kind || 'Mapped place'} · about ${distance(nearest).toFixed(1)} km straight-line from the map pin. Cached OSM listing; availability is unconfirmed.`;
  });

  const settings = overlay('aegis-settings-screen', t('SETTINGS','सेटिंग्स'), `
    <label>Language<select id="aegis-setting-language"><option value="en">English</option><option value="hi">हिन्दी</option></select></label>
    <label>Theme<select id="aegis-setting-theme"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option><option value="high-contrast">High contrast</option></select></label>
    <label>Text size<select id="aegis-setting-text"><option value="normal">Default</option><option value="large">Large</option><option value="largest">Largest</option></select></label>
    <label><span><input id="aegis-data-saver" type="checkbox" style="width:22px;min-height:22px"> Data saver (reduce background refresh)</span></label>
    <label><span><input id="aegis-notifications" type="checkbox" style="width:22px;min-height:22px"> Enable browser notifications (optional)</span></label>
    <label><span><input id="aegis-haptics" type="checkbox" style="width:22px;min-height:22px"> Subtle haptics (off by default)</span></label>
    <label><span><input id="aegis-sound" type="checkbox" style="width:22px;min-height:22px"> Sound (off by default)</span></label>
    <label>Trusted emergency contact (phone number)<input id="aegis-contact-input" type="tel" inputmode="tel" autocomplete="tel" placeholder="+91…"></label>
    <div class="aegis-actions"><button type="button" id="aegis-save-place">Save current map place</button><button type="button" class="aegis-secondary" id="aegis-export-data">Export my local data</button><button type="button" class="aegis-secondary" id="aegis-clear-data">Clear my local data</button></div>
    <div id="aegis-saved-places"></div>
    <details><summary>Privacy policy</summary><p>Search history, saved places, settings, report queue, and scan history are stored in this browser. Export and clear controls are provided here. A scan sends its selected point and inputs to the configured Aegis server. Resource and route requests use coordinates rounded to about 100 m. When you submit a community report, its rounded location, note, optional compressed photo, and pseudonymous reporter key are sent to the configured Aegis server; reports stay there until deleted through Community controls or by its operator. Backups may have separate retention. Search, map, routing, and resource requests may be sent to their named providers. No exact location is shared unless you explicitly select exact location for an emergency SMS draft. Aegis does not send SMS automatically.</p></details>
    <details><summary>Terms of use</summary><p>Project Aegis is a software research prototype, not an official alert, emergency service, validated forecast, or safe-route authority. Data may be missing, delayed, incomplete, or wrong. Verify facilities and routes directly; follow official instructions and call 112 when appropriate. Do not rely on this app for a life-safety decision.</p></details>
    <details><summary>Data sources and licenses</summary><ul><li>OpenStreetMap data © contributors, ODbL: <a href="https://www.openstreetmap.org/copyright">copyright and license</a>.</li><li>Nominatim geocoding: follow the <a href="https://operations.osmfoundation.org/policies/nominatim/">usage policy</a>.</li><li>Open-Meteo: <a href="https://open-meteo.com/en/terms">terms and attribution</a>; products are modeled/reanalysis data.</li><li>GloFAS/Copernicus: <a href="https://global-flood.emergency.copernicus.eu/">provider and data access terms</a>.</li><li>IIT Delhi IFI-Impacts, Zenodo DOI 10.5281/zenodo.16994648: CC BY-NC 4.0 per current record. <a href="https://doi.org/10.5281/zenodo.16994648">Dataset record</a>.</li><li>CivicDataLab Bihar inundation dataset: CC BY-SA 4.0 per dataset listing. <a href="https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25">Dataset page</a>.</li><li>OSRM public routing: <a href="https://project-osrm.org/">project information</a>; routes are not checked for flood or closures.</li></ul></details>
    <details><summary>About and app version</summary><p>Project Aegis · development build (release version not set) · research prototype. Map, routing, and resource data can be incomplete or stale.</p></details>
    <details><summary>Alert types and quiet limits</summary><p>No browser push-alert subscription is configured. Community reports do not trigger notifications. If alerts are added later, group by place and allow each type to be disabled.</p></details>
    <div class="aegis-actions"><button type="button" id="aegis-feedback">Feedback / bug report</button></div>
    <div id="aegis-settings-status" role="status"></div>`);
  const appearance = $('#appearance-dialog');
  if (appearance) {
    const allSettings = document.createElement('button');
    allSettings.type = 'button';
    allSettings.className = 'appearance-field aegis-open-settings';
    allSettings.textContent = 'More settings';
    appearance.append(allSettings);
    allSettings.addEventListener('click', () => { appearance.close(); openOverlay(settings); });
  }
  credits.querySelector('.aegis-credits-open').addEventListener('click', () => openOverlay(settings));
  const settingsButton = document.createElement('button');
  settingsButton.type = 'button';
  settingsButton.className = 'aegis-utility-button';
  settingsButton.textContent = '⚙';
  settingsButton.setAttribute('aria-label', 'Open settings');
  settingsButton.addEventListener('click', () => openOverlay(settings));
  $('#ops-sheet .ops-heading')?.append(settingsButton);

  const themeSetting = $('#aegis-setting-theme');
  const themeCurrent = localStorage.getItem('aegis-theme') || 'system';
  if (themeSetting) themeSetting.value = themeCurrent;
  $('#aegis-setting-language').value = localStorage.getItem('aegis-language') || 'en';
  $('#aegis-setting-language').addEventListener('change', event => {
    if (typeof changeLanguage === 'function') changeLanguage(event.target.value);
  });
  themeSetting.addEventListener('change', event => {
    const selected = event.target.value;
    localStorage.setItem('aegis-theme', selected === 'high-contrast' ? 'system' : selected);
    localStorage.setItem('aegis-high-contrast', String(selected === 'high-contrast'));
    document.documentElement.dataset.contrast = selected === 'high-contrast' ? 'high' : '';
    document.documentElement.dataset.theme = selected === 'dark' ? 'dark' : selected === 'light' ? 'light' : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    const old = $('#theme-select'); if (old) old.value = selected === 'high-contrast' ? 'system' : selected;
    const contrast = $('#contrast-toggle'); if (contrast) contrast.checked = selected === 'high-contrast';
    const color = $('meta[name="theme-color"]'); if (color) color.content = document.documentElement.dataset.theme === 'dark' ? '#211d49' : '#fff8e1';
    const statusBar = $('meta[name="apple-mobile-web-app-status-bar-style"]'); if (statusBar) statusBar.content = document.documentElement.dataset.theme === 'dark' ? 'black' : 'default';
  });
  $('#theme-select')?.addEventListener('change', event => { themeSetting.value = event.target.value; });
  $('#contrast-toggle')?.addEventListener('change', event => {
    if (event.target.checked) themeSetting.value = 'high-contrast';
    else if (themeSetting.value === 'high-contrast') themeSetting.value = localStorage.getItem('aegis-theme') || 'system';
  });
  const textSetting = $('#aegis-setting-text');
  textSetting.value = safeRead('aegis-text-size-v1', 'normal');
  document.documentElement.dataset.textSize = textSetting.value === 'normal' ? '' : textSetting.value;
  textSetting.addEventListener('change', event => {
    safeWrite('aegis-text-size-v1', event.target.value);
    document.documentElement.dataset.textSize = event.target.value === 'normal' ? '' : event.target.value;
  });
  const dataSaver = $('#aegis-data-saver');
  dataSaver.checked = safeRead('aegis-data-saver-v1', false);
  dataSaver.addEventListener('change', () => {
    safeWrite('aegis-data-saver-v1', dataSaver.checked);
    if (statusTimer) clearInterval(statusTimer);
    statusTimer = document.hidden ? 0 : setInterval(checkServer, statusInterval());
  });
  const haptics = $('#aegis-haptics'), sound = $('#aegis-sound');
  haptics.checked = safeRead('aegis-haptics-v1', false);
  sound.checked = safeRead('aegis-sound-v1', false);
  haptics.addEventListener('change', () => safeWrite('aegis-haptics-v1', haptics.checked));
  sound.addEventListener('change', () => safeWrite('aegis-sound-v1', sound.checked));
  globalThis.aegisMeaningfulFeedback = () => {
    try { if (safeRead('aegis-haptics-v1', false)) navigator.vibrate?.(16); } catch {}
    try {
      if (!safeRead('aegis-sound-v1', false)) return;
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      const context = new Audio(), oscillator = context.createOscillator(), gain = context.createGain();
      oscillator.frequency.value = 660; gain.gain.value = 0.035;
      oscillator.connect(gain); gain.connect(context.destination); oscillator.start();
      gain.gain.setTargetAtTime(0, context.currentTime + 0.035, 0.02);
      oscillator.stop(context.currentTime + 0.1);
      oscillator.addEventListener('ended', () => context.close());
    } catch {}
  };
  const notificationToggle = $('#aegis-notifications');
  notificationToggle.checked = safeRead('aegis-notifications-v1', false);
  notificationToggle.addEventListener('change', async () => {
    if (!notificationToggle.checked) { safeWrite('aegis-notifications-v1', false); return; }
    const allowed = await askPermission({
      title: 'Allow notifications?',
      explanation: 'Notifications can show app messages while this page is open. Aegis does not have a verified alert subscription configured.',
      stored: 'Only your preference is stored on this device. No push subscription is created.'
    });
    if (!allowed || !('Notification' in window)) {
      notificationToggle.checked = false;
      safeWrite('aegis-notifications-v1', false);
      $('#aegis-settings-status').textContent = 'Notifications remain off. The app works without them.';
      return;
    }
    const permission = await Notification.requestPermission();
    notificationToggle.checked = permission === 'granted';
    safeWrite('aegis-notifications-v1', notificationToggle.checked);
    $('#aegis-settings-status').textContent = permission === 'granted' ? 'Permission granted. No push alert subscription is configured.' : 'Permission not granted. The app works without notifications.';
  });
  const contactField = $('#aegis-contact-input');
  contactField.value = savedContact();
  contactField.addEventListener('change', () => safeWrite(keys.contact, contactField.value.trim()));
  const placesHost = $('#aegis-saved-places');
  function renderPlaces() {
    placesHost.replaceChildren();
    const places = safeRead(keys.places, []);
    if (!places.length) { placesHost.textContent = 'No saved places yet.'; return; }
    places.forEach((place, index) => {
      const row = document.createElement('p');
      row.textContent = `${place.name} · ${Number(place.lat).toFixed(3)}, ${Number(place.lon).toFixed(3)} `;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.textContent = 'Remove'; remove.setAttribute('aria-label', `Remove ${place.name}`);
      remove.addEventListener('click', () => { const updated = safeRead(keys.places, []); updated.splice(index, 1); safeWrite(keys.places, updated); renderPlaces(); });
      row.append(remove); placesHost.append(row);
    });
  }
  renderPlaces();
  $('#aegis-save-place').addEventListener('click', () => {
    const point = getCurrentTarget();
    const name = $('#sector-display')?.textContent?.replace(/^SECTOR:\s*/i, '').trim() || 'Saved map pin';
    const places = safeRead(keys.places, []);
    if (!places.some(place => Math.abs(place.lat - point.lat) < .001 && Math.abs(place.lon - point.lon) < .001)) {
      places.push({ name, ...roundedPoint(point) });
      safeWrite(keys.places, places.slice(-20));
    }
    renderPlaces();
  });
  $('#aegis-export-data').addEventListener('click', () => {
    const data = Object.fromEntries(Object.keys(localStorage).filter(key => key.startsWith('aegis-')).map(key => [key, localStorage.getItem(key)]));
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), data }, null, 2)], { type: 'application/json' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'aegis-local-data.json'; link.click(); URL.revokeObjectURL(link.href);
  });
  $('#aegis-clear-data').addEventListener('click', async () => {
    if (!confirm('Clear Project Aegis data stored in this browser? This cannot delete reports already sent to the server.')) return;
    Object.keys(localStorage).filter(key => key.startsWith('aegis-')).forEach(key => localStorage.removeItem(key));
    contactField.value = ''; renderPlaces();
    try {
      if ('caches' in window) {
        const names = await caches.keys();
        await Promise.all(names.filter(name => name.startsWith('aegis-shell-')).map(name => caches.delete(name)));
      }
      $('#aegis-settings-status').textContent = 'Local Aegis data and app caches cleared. Server-submitted reports are not deleted by this action.';
    } catch (error) {
      $('#aegis-settings-status').textContent = `Local storage was cleared, but an app cache could not be removed: ${error.message || 'storage unavailable'}`;
    }
  });
  $('#aegis-feedback').addEventListener('click', () => {
    const entries = safeRead(keys.errors, []);
    const summary = entries.map(item => `${item.at} ${item.type}: ${item.message}`).join('\n') || 'No recent technical errors were recorded.';
    const dialog = overlay(`aegis-feedback-${Date.now()}`, 'FEEDBACK / BUG REPORT', `<p>Review the technical details before sending. Location and personal data are excluded.</p><textarea readonly rows="6" aria-label="Technical error details">${escapeHtml(summary)}</textarea><div class="aegis-actions"><button type="button" class="aegis-send-feedback">Send report</button><button type="button" class="aegis-secondary aegis-close">Not now</button></div>`);
    dialog.querySelector('.aegis-send-feedback').addEventListener('click', () => {
      const body = encodeURIComponent(`Project Aegis feedback\n\n${summary}`);
      location.href = `mailto:?subject=Project%20Aegis%20bug%20report&body=${body}`;
      closeOverlay(dialog);
    });
    openOverlay(dialog);
  });

  document.addEventListener('click', async event => {
    const input = event.target.closest?.('#aegis-community-reports input[type="file"]');
    if (!input || input.dataset.permissionPrimed === 'true') return;
    event.preventDefault();
    const allowed = await askPermission({
      title: 'Add a photo?',
      explanation: 'A photo can document your report. It is compressed in this browser before upload.',
      stored: 'Only the photo you submit is sent with your report.'
    });
    if (allowed) { input.dataset.permissionPrimed = 'true'; input.click(); input.dataset.permissionPrimed = 'false'; }
  }, true);

  const search = $('#location-input');
  const dropdown = $('#search-dropdown');
  if (search && dropdown) {
    const clear = document.createElement('button');
    clear.type = 'button'; clear.className = 'aegis-search-clear'; clear.textContent = '×';
    clear.setAttribute('aria-label', 'Clear search');
    search.parentElement.insertBefore(clear, search.nextSibling);
    const recents = document.createElement('div');
    recents.className = 'aegis-recent'; recents.hidden = true;
    dropdown.after(recents);
    function renderRecents() {
      recents.replaceChildren();
      safeRead(keys.recent, []).forEach(item => {
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = item.name; button.title = `Search ${item.name}`;
        button.addEventListener('click', () => selectLocation(item.name, item.lat, item.lon, 14));
        recents.append(button);
      });
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Clear recent searches';
      remove.addEventListener('click', () => { localStorage.removeItem(keys.recent); renderRecents(); });
      if (recents.childElementCount) recents.append(remove);
    }
    renderRecents();
    clear.hidden = !search.value;
    clear.addEventListener('click', () => { search.value = ''; clear.hidden = true; dropdown.style.display = 'none'; search.focus(); });
    search.addEventListener('input', () => { clear.hidden = !search.value; recents.hidden = !!search.value; });
    search.addEventListener('focus', () => { if (!search.value) { renderRecents(); recents.hidden = false; } });
    document.addEventListener('click', event => { if (!event.target.closest('.search-container')) recents.hidden = true; });
    const originalSelect = window.selectLocation;
    if (typeof originalSelect === 'function') {
      window.selectLocation = function(name, lat, lon, zoom) {
        const result = originalSelect.apply(this, arguments);
        const saved = safeRead(keys.recent, []).filter(item => !(Math.abs(item.lat - lat) < .001 && Math.abs(item.lon - lon) < .001));
        saved.unshift({ name: String(name).slice(0, 100), lat: Number(lat), lon: Number(lon), at: new Date().toISOString() });
        safeWrite(keys.recent, saved.slice(0, 8));
        search.value = name; clear.hidden = false; recents.hidden = true; renderRecents();
        return result;
      };
    }
    const originalRender = window.renderDropdown;
    if (typeof originalRender === 'function') {
      window.renderDropdown = function(items, query) {
        dropdown.replaceChildren();
        if (!items?.length) { dropdown.style.display = 'none'; return; }
        items.slice(0, 7).forEach(item => {
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'search-result-item aegis-place-choice';
          const label = document.createElement('span');
          const locality = item.name || 'Unknown place';
          const district = item.district || '';
          const state = item.state || '';
          label.textContent = [locality, district, state].filter(Boolean).join(' · ');
          const badge = document.createElement('span'); badge.className = 'result-badge'; badge.textContent = item.category || 'Place';
          button.append(label, badge);
          button.addEventListener('click', () => selectLocation(label.textContent, Number(item.lat), Number(item.lon), item.zoom || 14));
          dropdown.append(button);
        });
        dropdown.style.display = 'block';
      };
    }
    const originalFetchNominatim = window.fetchNominatim;
    window.fetchNominatim = async function(query, localMatches = []) {
      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&addressdetails=1`, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error(`Geocoder returned ${response.status}`);
        const results = await response.json();
        const remote = results.map(result => ({
          name: result.name || result.display_name.split(',')[0],
          district: result.address?.state_district || result.address?.county || result.address?.district || '',
          state: result.address?.state || '',
          category: result.type || 'Place',
          lat: Number(result.lat),
          lon: Number(result.lon),
          zoom: 13
        }));
        const combined = [...localMatches, ...remote];
        const unique = combined.filter((item, index, list) => list.findIndex(other => Number(other.lat) === Number(item.lat) && Number(other.lon) === Number(item.lon)) === index);
        window.renderDropdown(unique, query);
      } catch (error) {
        if (localMatches.length) window.renderDropdown(localMatches, query);
        else if (typeof originalFetchNominatim === 'function') originalFetchNominatim.call(this, query, localMatches);
      }
    };
    const originalSearch = window.executeSearch;
    if (typeof originalSearch === 'function') {
      window.executeSearch = async function() {
        const raw = search.value.trim();
        if (logic?.hasMultiplePlaces(raw)) {
          const parts = raw.split(/\s+(?:and|versus|vs\.?|near|to)\s+/i).map(value => value.trim()).filter(Boolean);
          if (parts.length >= 2) {
            const chooser = overlay(`aegis-place-query-${Date.now()}`, 'CHOOSE ONE PLACE', '<p>Your search names more than one place. Choose one to search, then repeat for another.</p>');
            const choices = document.createElement('div'); choices.className = 'aegis-actions';
            parts.slice(0, 3).forEach(part => {
              const button = document.createElement('button'); button.type = 'button'; button.textContent = part;
              button.addEventListener('click', () => { search.value = part; closeOverlay(chooser); chooser.remove(); originalSearch.call(window); });
              choices.append(button);
            });
            chooser.querySelector('.aegis-panel').append(choices); openOverlay(chooser); return;
          }
        }
        if (navigator.onLine && raw.length >= 2) {
          let localMatches = [];
          try { if (typeof LOCAL_DATABASE !== 'undefined') localMatches = LOCAL_DATABASE.filter(item => item.name.toLowerCase().includes(raw.toLowerCase())); } catch {}
          if (localMatches.length > 1) { window.renderDropdown(localMatches.map(item => ({ ...item, district: item.district || '', state: item.state || '' })), raw); return; }
          if (localMatches.length === 1) return originalSearch.call(this);
          await window.fetchNominatim(raw, localMatches);
          return;
        }
        return originalSearch.call(this);
      };
    }
  }

  const mapActions = document.createElement('div');
  mapActions.id = 'aegis-map-actions';
  mapActions.innerHTML = '<button type="button" id="aegis-locate" aria-label="Locate me" title="Locate me">◎</button><button type="button" id="aegis-compass" aria-label="Reset map north" title="Reset map north">N</button>';
  document.body.append(mapActions);
  $('#aegis-locate').addEventListener('click', async () => {
    try {
      const point = await requestLocation();
      if (typeof selectLocation === 'function') selectLocation('My location (device)', point.latitude, point.longitude, 14);
    } catch (error) { window.showToast?.(error.message || 'Location unavailable. Search or use the map pin.'); }
  });
  $('#aegis-compass').addEventListener('click', () => {
    if (typeof map !== 'undefined') map.setView(map.getCenter(), map.getZoom(), { animate: !matchMedia('(prefers-reduced-motion: reduce)').matches });
    window.showToast?.('Map aligned north.');
  });
  const glossary = {
    estimate: ['A research-model output based on available inputs; it is not an official warning.', 'उपलब्ध इनपुट पर आधारित शोध-मॉडल परिणाम; यह आधिकारिक चेतावनी नहीं है।'],
    confidence: ['A summary of data coverage and freshness, not certainty that an event will occur.', 'डेटा की उपलब्धता और ताज़गी का सार, घटना होने की निश्चितता नहीं।'],
    'data health': ['Whether a source is available and recent enough for its stated use.', 'स्रोत उपलब्ध है या नहीं और अपने उपयोग के लिए कितना नया है।'],
    'resilience score': ['A planning indicator, not a measured guarantee of safety or service.', 'योजना संकेतक; सुरक्षा या सेवा की मापी हुई गारंटी नहीं।']
  };
  const glossaryDialog = overlay('aegis-glossary', 'PLAIN-LANGUAGE GLOSSARY', '<p id="aegis-glossary-copy"></p>');
  const glossaryCopy = $('#aegis-glossary-copy');
  function makeGlossaryTargets() {
    const targets = [
      ['#risk-value', 'estimate'], ['#risk-window', 'estimate'], ['#risk-source', 'data health'],
      ['.aegis-meter', 'confidence'], ['#aegis-confidence-details', 'confidence']
    ];
    targets.forEach(([selector, term]) => {
      document.querySelectorAll(selector).forEach(node => {
        node.dataset.glossary = term;
        node.tabIndex = 0;
        if (!node.classList.contains('aegis-meter')) node.setAttribute('role', 'button');
        node.setAttribute('aria-label', `${term}: tap for a plain-language explanation`);
      });
    });
    document.querySelectorAll('[id*="resilience"]').forEach(node => {
      node.dataset.glossary = 'resilience score';
      node.tabIndex = 0;
      node.setAttribute('role', 'button');
    });
  }
  makeGlossaryTargets();
  const glossaryObserver = new MutationObserver(makeGlossaryTargets);
  glossaryObserver.observe(document.body, { childList: true, subtree: true });
  document.addEventListener('click', event => {
    const term = event.target.closest?.('[data-glossary]')?.dataset.glossary;
    if (!term) return;
    const explanation = glossary[term] || glossary.estimate;
    glossaryCopy.textContent = t(explanation[0], explanation[1]);
    openOverlay(glossaryDialog);
  });
  document.addEventListener('keydown', event => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches?.('[data-glossary]')) {
      event.preventDefault();
      event.target.click();
    }
  });
  let pullStart = null;
  const estimateCard = $('#risk-summary');
  estimateCard?.addEventListener('touchstart', event => {
    if (estimateCard.scrollTop === 0) pullStart = event.touches[0].clientY;
  }, { passive: true });
  estimateCard?.addEventListener('touchend', event => {
    if (pullStart !== null && event.changedTouches[0].clientY - pullStart > 70) initiateSwarm?.();
    pullStart = null;
  }, { passive: true });
  const priorScan = window.initiateSwarm;
  if (typeof priorScan === 'function') window.initiateSwarm = async function(...args) {
    const result = await priorScan.apply(this, args);
    if ($('#risk-value')?.textContent && $('#risk-value').textContent !== 'N/A' && $('#risk-value').textContent !== '—') globalThis.aegisMeaningfulFeedback();
    return result;
  };
  try { L.control.scale({ position: 'bottomright', imperial: false, metric: true, maxWidth: 100 }).addTo(map); } catch (error) { console.warn('Map scale unavailable.', error); }
  const operationsSheet = $('#ops-sheet');
  function keepMapCreditsVisible(invalidate = true) {
    if (!operationsSheet) return;
    const top = operationsSheet.getBoundingClientRect().top;
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const sheetHeight = window.matchMedia('(max-width: 1023px) and (min-height: 501px)').matches
      ? Math.max(0, viewportHeight - top)
      : 0;
    const bottom = Math.max(8, sheetHeight + 8);
    document.documentElement.style.setProperty('--aegis-map-safe-bottom', `${bottom}px`);
    document.documentElement.style.setProperty('--aegis-map-controls-bottom', `${sheetHeight + 160}px`);
    credits.style.bottom = `calc(${bottom}px + env(safe-area-inset-bottom))`;
    if (invalidate) map.invalidateSize({ pan: false, debounceMoveend: true });
  }
  window.aegisUpdateMapControlClearance = () => keepMapCreditsVisible(false);
  if (operationsSheet) {
    if ('ResizeObserver' in window) new ResizeObserver(keepMapCreditsVisible).observe(operationsSheet);
    new MutationObserver(keepMapCreditsVisible).observe(operationsSheet, { attributes: true, attributeFilter: ['class', 'style'] });
    operationsSheet.addEventListener('transitionend', event => {
      if (event.propertyName === 'transform') keepMapCreditsVisible();
    });
    requestAnimationFrame(() => requestAnimationFrame(keepMapCreditsVisible));
  }
  window.addEventListener('resize', keepMapCreditsVisible, { passive: true });
  keepMapCreditsVisible();

  let pressTimer = 0;
  let pressPoint = null;
  let suppressMapClickAfterLongPress = false;
  if (typeof map !== 'undefined') {
    map.on('mousedown touchstart', event => {
      clearTimeout(pressTimer);
      suppressMapClickAfterLongPress = false;
      pressPoint = event.latlng;
      pressTimer = setTimeout(() => {
        suppressMapClickAfterLongPress = true;
        showMapMenu(pressPoint);
        setTimeout(() => { suppressMapClickAfterLongPress = false; }, 1200);
      }, 650);
    });
    map.on('mouseup touchend mousemove touchmove', () => { clearTimeout(pressTimer); });
    map.getContainer().addEventListener('click', event => {
      if (!suppressMapClickAfterLongPress) return;
      suppressMapClickAfterLongPress = false;
      event.stopImmediatePropagation();
    }, true);
  }
  function showMapMenu(point) {
    if (!point) return;
    const mapBounds = map.getContainer().getBoundingClientRect();
    const searchBounds = $('.search-container')?.getBoundingClientRect();
    const sheetBounds = $('#ops-sheet')?.getBoundingClientRect();
    const topPadding = Math.max(16, Math.ceil((searchBounds?.bottom || mapBounds.top) - mapBounds.top + 16));
    const bottomPadding = window.matchMedia('(max-width: 1023px)').matches
      ? Math.max(16, Math.ceil(mapBounds.bottom - Math.max(mapBounds.top, sheetBounds?.top || mapBounds.bottom) + 16))
      : 16;
    const maxHeight = Math.max(140, (window.visualViewport?.height || window.innerHeight) - topPadding - bottomPadding - 48);
    const fitPopup = () => {
      const popupElement = popup.getElement();
      if (!popupElement) return;
      const mapBounds = map.getContainer().getBoundingClientRect();
      const popupBounds = popupElement.getBoundingClientRect();
      const safe = {
        left: mapBounds.left + 12,
        right: mapBounds.right - 12,
        top: mapBounds.top + topPadding,
        bottom: mapBounds.bottom - bottomPadding
      };
      let rect = { left: popupBounds.left, right: popupBounds.right, top: popupBounds.top, bottom: popupBounds.bottom };
      let dx = rect.left < safe.left ? safe.left - rect.left : rect.right > safe.right ? safe.right - rect.right : 0;
      let dy = rect.top < safe.top ? safe.top - rect.top : rect.bottom > safe.bottom ? safe.bottom - rect.bottom : 0;
      rect = { left: rect.left + dx, right: rect.right + dx, top: rect.top + dy, bottom: rect.bottom + dy };
      const blockers = [
        $('.search-container'), $('#aegis-map-actions'), $('.leaflet-control-zoom'),
        $('.leaflet-control-scale'), $('.leaflet-control-attribution'),
        $('#aegis-layer-caption'), $('#aegis-map-credits')
      ].filter(element => element && getComputedStyle(element).display !== 'none');
      for (const element of blockers) {
        const bounds = element.getBoundingClientRect();
        if (rect.left >= bounds.right || rect.right <= bounds.left || rect.top >= bounds.bottom || rect.bottom <= bounds.top) continue;
        const moves = [
          { x: 0, y: bounds.top - 12 - rect.bottom },
          { x: 0, y: bounds.bottom + 12 - rect.top },
          { x: bounds.left - 12 - rect.right, y: 0 },
          { x: bounds.right + 12 - rect.left, y: 0 }
        ].filter(move => rect.left + move.x >= safe.left && rect.right + move.x <= safe.right && rect.top + move.y >= safe.top && rect.bottom + move.y <= safe.bottom);
        moves.sort((a, b) => Math.abs(a.x) + Math.abs(a.y) - Math.abs(b.x) - Math.abs(b.y));
        if (moves.length) {
          dx += moves[0].x;
          dy += moves[0].y;
          rect = { left: rect.left + moves[0].x, right: rect.right + moves[0].x, top: rect.top + moves[0].y, bottom: rect.bottom + moves[0].y };
        }
      }
      if (dx || dy) map.panBy([-dx, -dy], { animate: false });
    };
    const popup = L.popup({
      closeButton: true,
      autoPan: true,
      closeOnClick: false,
      autoPanPaddingTopLeft: [16, topPadding],
      autoPanPaddingBottomRight: [16, bottomPadding],
      maxWidth: 260,
      maxHeight
    })
      .setLatLng(point)
      .setContent('<div class="aegis-map-menu"><button data-action="scan">Scan here</button><button data-action="report">Drop report</button><button data-action="route">Route from here</button><button data-action="save">Save place</button></div>');
    const closeOnEscape = event => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      map.closePopup(popup);
    };
    document.addEventListener('keydown', closeOnEscape, true);
    popup.once('remove', () => document.removeEventListener('keydown', closeOnEscape, true));
    map.once('moveend', () => requestAnimationFrame(fitPopup));
    popup.openOn(map);
    setTimeout(fitPopup, 300);
    setTimeout(() => {
      const container = popup.getElement();
      container?.querySelectorAll('button[data-action]').forEach(button => button.addEventListener('click', () => {
        const name = `Map pin ${point.lat.toFixed(3)}, ${point.lng.toFixed(3)}`;
        selectLocation(name, point.lat, point.lng, Math.max(map.getZoom(), 14));
        map.closePopup(popup);
        if (button.dataset.action === 'scan') initiateSwarm();
        if (button.dataset.action === 'report') { setOpsTab('community'); $('#aegis-community-reports form')?.scrollIntoView({ block: 'center' }); }
        if (button.dataset.action === 'route') { setOpsTab('respond'); $('#aegis-resources')?.scrollIntoView({ block: 'center' }); }
        if (button.dataset.action === 'save') { $('#aegis-save-place').click(); openOverlay(settings); }
      }));
    }, 0);
  }

  document.addEventListener('click', event => {
    const time = event.target.closest?.('time[datetime], [data-timestamp]');
    if (!time) return;
    const value = time.getAttribute('datetime') || time.dataset.timestamp;
    const parsed = new Date(value);
    if (Number.isFinite(parsed.getTime())) {
      const exact = parsed.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' }) + ' IST';
      time.title = exact;
      time.setAttribute('aria-label', exact);
      window.showToast?.(exact);
    }
  });
  let relativeTimer = 0;
  const updateRelativeTimes = () => {
    document.querySelectorAll('time[datetime], [data-timestamp]').forEach(node => {
      const value = node.getAttribute('datetime') || node.dataset.timestamp;
      if (logic && value && node.dataset.relativeTime === 'true') node.textContent = logic.relativeTime(value);
    });
  };
  const startRelativeTimer = () => {
    if (!document.hidden && !relativeTimer) relativeTimer = setInterval(updateRelativeTimes, 30000);
  };
  startRelativeTimer();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && relativeTimer) { clearInterval(relativeTimer); relativeTimer = 0; }
    else startRelativeTimer();
  });

  const originalTranslations = window.changeLanguage;
  const hindiCopy = {
    'SETTINGS':'सेटिंग्स','Language':'भाषा','Theme':'थीम','System':'डिवाइस के अनुसार','Light':'हल्की','Dark':'गहरी','High contrast':'उच्च कंट्रास्ट',
    'Text size':'पाठ का आकार','Default':'सामान्य','Large':'बड़ा','Largest':'सबसे बड़ा','Data saver (reduce background refresh)':'डेटा बचाएँ (कम बैकग्राउंड अपडेट)',
    'Enable browser notifications (optional)':'ब्राउज़र सूचनाएँ चालू करें (वैकल्पिक)','Subtle haptics (off by default)':'हल्का कंपन (डिफ़ॉल्ट रूप से बंद)',
    'Sound (off by default)':'ध्वनि (डिफ़ॉल्ट रूप से बंद)','Trusted emergency contact (phone number)':'विश्वसनीय आपातकालीन संपर्क (फ़ोन नंबर)',
    'Save current map place':'वर्तमान नक्शा स्थान सहेजें','Export my local data':'मेरा स्थानीय डेटा निर्यात करें','Clear my local data':'मेरा स्थानीय डेटा मिटाएँ',
    'Privacy and terms':'गोपनीयता और शर्तें','Data sources and licenses':'डेटा स्रोत और लाइसेंस','About and app version':'ऐप के बारे में और संस्करण',
    'Alert types and quiet limits':'अलर्ट प्रकार और शांत सीमाएँ','Feedback / bug report':'फ़ीडबैक / बग रिपोर्ट','No saved places yet.':'अभी कोई सहेजा स्थान नहीं।',
    'EMERGENCY':'आपातकाल','EMERGENCY MODE':'आपातकालीन मोड','Call 112':'112 पर कॉल करें','Send location by SMS':'SMS से स्थान भेजें',
    'Nearest cached help':'कैश में नज़दीकी मदद',"I'm safe":'मैं सुरक्षित हूँ','Exit emergency mode':'आपातकालीन मोड से बाहर जाएँ',
    'Open offline emergency actions':'ऑफ़लाइन आपातकालीन विकल्प खोलें','CHOOSE ONE PLACE':'एक स्थान चुनें',
    'This is not confirmed. Share anyway?':'यह पुष्टि नहीं की गई है। फिर भी साझा करें?',
    'ESTIMATE':'अनुमान','SCANNING':'स्कैन जारी','RETRY':'फिर प्रयास करें','Details':'विवरण','Settings':'सेटिंग्स','More':'और',
    'RESEARCH ESTIMATE DETAILS':'शोध अनुमान का विवरण','Close estimate card':'अनुमान कार्ड बंद करें','Close estimate details':'अनुमान विवरण बंद करें',
    'Open place search':'स्थान खोज खोलें','Run scan without opening estimate details':'विवरण खोले बिना स्कैन चलाएँ',
    'Research estimate':'शोध अनुमान','Estimate unavailable. Open to retry.':'अनुमान उपलब्ध नहीं। फिर प्रयास करने के लिए खोलें।',
    'Estimate scan in progress':'अनुमान स्कैन जारी है।','Open estimate card.':'अनुमान कार्ड खोलें।',
    'Close layer notes':'परत जानकारी बंद करें',
    'Your estimate lives here':'आपका अनुमान यहाँ मिलेगा','MAP LAYER NOTES':'मानचित्र परत नोट्स',
    'Satellite imagery:':'उपग्रह चित्र:','imagery is a visual background only; it has no flood classification.':'चित्र केवल पृष्ठभूमि है; इसमें बाढ़ वर्गीकरण नहीं है।',
    'Risk perimeter:':'जोखिम सीमा:','an illustrative research overlay, not a measured flood boundary or official alert.':'यह केवल शोध का उदाहरण है, मापी गई बाढ़ सीमा या आधिकारिक चेतावनी नहीं।',
    'No flood classification · Research overlays are illustrative':'बाढ़ वर्गीकरण नहीं · शोध परतें केवल उदाहरण हैं।',
    'Show language note':'भाषा सूचना दिखाएँ'
  };
  function applyAddendumLanguage(code = document.documentElement.lang) {
    const hindi = String(code).toLowerCase().startsWith('hi');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.__aegisEnglish === undefined) node.__aegisEnglish = node.textContent.trim();
      const original = node.__aegisEnglish;
      if (original && (hindiCopy[original] || !hindi)) node.textContent = node.textContent.replace(node.textContent.trim(), hindi ? (hindiCopy[original] || original) : original);
    }
    document.querySelectorAll('option').forEach(option => {
      const original = option.dataset.aegisEnglishOption || option.textContent;
      option.dataset.aegisEnglishOption = original;
      option.textContent = hindi && hindiCopy[original] ? hindiCopy[original] : original;
    });
  }
  applyAddendumLanguage();
  if (typeof originalTranslations === 'function') {
    window.changeLanguage = function(code) {
      const result = originalTranslations.apply(this, arguments);
      $('#aegis-setting-language').value = code;
      emergencyButton.textContent = t('EMERGENCY', 'आपातकाल');
      emergency.querySelector('h2').textContent = t('EMERGENCY MODE', 'आपातकालीन मोड');
      applyAddendumLanguage(code);
      return result;
    };
  }

  const errorLog = safeRead(keys.errors, []);
  function logTechnicalError(type, message) {
    const sanitized = String(message || 'Unknown error')
      .replace(/-?\d{1,3}\.\d{3,}/g, '[location]')
      .replace(/https?:\/\/\S+/g, '[url]')
      .replace(/[A-Z]:\\[^\s]+/gi, '[path]')
      .slice(0, 240);
    errorLog.push({ at: new Date().toISOString(), type, message: sanitized });
    if (errorLog.length > 10) errorLog.splice(0, errorLog.length - 10);
    safeWrite(keys.errors, errorLog);
  }
  window.addEventListener('error', event => logTechnicalError('error', event.message));
  window.addEventListener('unhandledrejection', event => logTechnicalError('rejection', event.reason?.message || event.reason));

  let updateReady = false;
  let refreshAfterUpdate = false;
  function hasActiveAction() {
    return logic?.deferUpdate({
      scan: document.body.classList.contains('aegis-scan-running'),
      upload: Boolean(document.querySelector('#aegis-community-reports button[disabled]')),
      drag: Boolean(document.querySelector('.aegis-slider-wrap.is-dragging, .ops-tools.dragging, .ops-tools[data-dragging="true"]') || document.body.classList.contains('aegis-sheet-dragging'))
    }) || false;
  }
  function offerUpdate(registration) {
    if (!registration.waiting || updateReady) return;
    updateReady = true;
    const toast = document.createElement('div');
    toast.className = 'aegis-update-toast';
    toast.innerHTML = 'New version available <button type="button">Refresh</button>';
    document.body.append(toast);
    toast.querySelector('button').addEventListener('click', () => {
      if (hasActiveAction()) {
        window.showToast?.('Finish the active scan, upload, or gesture before refreshing.');
        return;
      }
      refreshAfterUpdate = true;
      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    });
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').then(registration => {
      offerUpdate(registration);
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => { if (worker.state === 'installed' && navigator.serviceWorker.controller) offerUpdate(registration); });
      });
    }).catch(error => console.warn('Service worker update check failed.', error));
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!refreshAfterUpdate) return;
      const reloadWhenSafe = () => {
        if (hasActiveAction()) { setTimeout(reloadWhenSafe, 500); return; }
        location.reload();
      };
      reloadWhenSafe();
    });
  }
  document.addEventListener('pointerdown', event => { if (event.target.closest?.('.sheet-handle')) document.body.classList.add('aegis-sheet-dragging'); }, true);
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => document.addEventListener(type, () => document.body.classList.remove('aegis-sheet-dragging'), true));
  window.addEventListener('blur', () => document.body.classList.remove('aegis-sheet-dragging'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) document.body.classList.remove('aegis-sheet-dragging'); });

  const dockEstimateCard = $('#risk-summary');
  const dockSheet = $('#ops-sheet');
  if (dockEstimateCard && dockSheet) {
    const dock = document.createElement('section');
    dock.id = 'estimate-dock';
    dock.setAttribute('aria-label', 'Research estimate controls');
    const controls = document.createElement('div');
    controls.className = 'estimate-dock-controls';
    const toggle = document.createElement('button');
    toggle.id = 'estimate-dock-toggle';
    toggle.type = 'button';
    toggle.className = 'estimate-dock-toggle';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', 'risk-summary');
    toggle.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 17a8 8 0 1 1 16 0M12 13l4-4M7 17h10"/></svg><span class="estimate-dock-label">ESTIMATE</span><span class="estimate-dock-status" aria-live="polite">N/A</span><span class="estimate-dock-dot" aria-hidden="true" hidden></span>';
    const scanButton = document.createElement('button');
    scanButton.id = 'estimate-dock-scan';
    scanButton.type = 'button';
    scanButton.className = 'estimate-dock-scan';
    scanButton.setAttribute('aria-label', t('Run scan without opening estimate details','विवरण खोले बिना स्कैन चलाएँ'));
    scanButton.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
    controls.append(toggle, scanButton);
    dock.append(controls);
    dockEstimateCard.parentNode.insertBefore(dock, dockEstimateCard);
    dock.append(dockEstimateCard);

    const header = $('.risk-summary-head', dockEstimateCard);
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'estimate-dock-close';
    closeButton.setAttribute('aria-label', t('Close estimate card','अनुमान कार्ड बंद करें'));
    closeButton.textContent = '×';
    const searchButton = document.createElement('button');
    searchButton.type = 'button';
    searchButton.className = 'estimate-dock-search';
    searchButton.setAttribute('aria-label', t('Open place search','स्थान खोज खोलें'));
    searchButton.textContent = '⌕';
    header?.append(searchButton);
    header?.append(closeButton);

    const sourceDetails = $('.estimate-details', dockEstimateCard);
    const whyDisclosure = [...dockEstimateCard.querySelectorAll('details')].find(item => $('summary', item)?.textContent.trim() === 'Why this estimate?');
    const secondary = document.createElement('div');
    secondary.className = 'estimate-secondary';
    const detailsButton = document.createElement('button');
    detailsButton.type = 'button';
    detailsButton.className = 'estimate-details-open';
    detailsButton.textContent = 'Details';
    secondary.append(detailsButton);
    if (whyDisclosure) secondary.append(whyDisclosure);
    dockEstimateCard.append(secondary);

    const detailDialog = document.createElement('dialog');
    detailDialog.id = 'estimate-detail-dialog';
    detailDialog.className = 'estimate-detail-dialog';
    detailDialog.setAttribute('aria-labelledby', 'estimate-detail-title');
    const detailHeader = document.createElement('div');
    detailHeader.className = 'estimate-detail-heading';
    detailHeader.innerHTML = '<h2 id="estimate-detail-title">RESEARCH ESTIMATE DETAILS</h2>';
    const detailClose = document.createElement('button');
    detailClose.type = 'button';
    detailClose.className = 'estimate-detail-close';
    detailClose.setAttribute('aria-label', t('Close estimate details','अनुमान विवरण बंद करें'));
    detailClose.textContent = '×';
    detailHeader.append(detailClose);
    detailDialog.append(detailHeader);
    if (sourceDetails) detailDialog.append(sourceDetails);
    document.body.append(detailDialog);
    detailsButton.addEventListener('click', () => {
      if (sourceDetails) sourceDetails.open = true;
      if (typeof detailDialog.showModal === 'function') detailDialog.showModal();
      else detailDialog.setAttribute('open', '');
      detailClose.focus();
    });
    detailClose.addEventListener('click', () => detailDialog.close?.());
    detailDialog.addEventListener('close', () => detailsButton.focus());

    let dockOpen = safeRead('aegis-estimate-dock-open-v1', false) === true;
    let caption = null;
    const dockStatus = $('.estimate-dock-status', toggle);
    const newDot = $('.estimate-dock-dot', toggle);
    const setDockOpen = (open, moveFocus = false, persist = true) => {
      dockOpen = Boolean(open);
      dock.classList.toggle('is-open', dockOpen);
      document.body.classList.toggle('aegis-estimate-dock-open', dockOpen);
      toggle.setAttribute('aria-expanded', String(dockOpen));
      if (persist) safeWrite('aegis-estimate-dock-open-v1', dockOpen);
      placeCaption();
      if (moveFocus) (dockOpen ? closeButton : toggle).focus();
    };
    const placeCaption = () => {
      if (!caption) return;
      if (dockOpen && matchMedia('(max-height: 620px)').matches) document.body.append(caption);
      else if (dockOpen) header?.after(caption);
      else dock.append(caption);
    };
    const setStatus = state => {
      const badge = $('#risk-badge');
      const currentValue = $('#risk-value')?.textContent.trim() || 'N/A';
      const value = currentValue === '—' ? 'N/A' : currentValue;
      if (state === 'scanning') {
        dockStatus.textContent = t('SCANNING','स्कैन जारी');
        dock.dataset.state = state;
        toggle.setAttribute('aria-label', t('Estimate scan in progress','अनुमान स्कैन जारी है'));
        return;
      }
      if (state === 'error') {
        dockStatus.textContent = t('RETRY','फिर प्रयास करें');
        dock.dataset.state = state;
        toggle.setAttribute('aria-label', t('Estimate unavailable. Open to retry.','अनुमान उपलब्ध नहीं। फिर प्रयास करने के लिए खोलें।'));
        return;
      }
      dock.dataset.state = '';
      dockStatus.textContent = value;
      toggle.setAttribute('aria-label', `${t('Research estimate','शोध अनुमान')}: ${value}. ${badge?.textContent.trim() || 'No current estimate'}. ${t('Open estimate card.','अनुमान कार्ड खोलें।')}`);
    };
    const badge = $('#risk-badge');
    if (badge) new MutationObserver(() => {
      setStatus('ready');
      newDot.hidden = false;
      if (!dockOpen && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        dock.classList.remove('has-new-result');
        requestAnimationFrame(() => dock.classList.add('has-new-result'));
      }
    }).observe(badge, { childList: true, characterData: true, subtree: true });
    setStatus('ready');
    toggle.addEventListener('click', () => {
      const next = !dockOpen;
      if (next) newDot.hidden = true;
      setDockOpen(next, true);
    });
    closeButton.addEventListener('click', () => setDockOpen(false, true));
    scanButton.addEventListener('click', event => {
      event.stopPropagation();
      if (dock.dataset.state !== 'scanning') window.initiateSwarm?.();
    });
    dockEstimateCard.addEventListener('touchstart', event => {
      dock.dataset.touchStartY = String(event.touches[0].clientY);
    }, { passive: true });
    dockEstimateCard.addEventListener('touchend', event => {
      const start = Number(dock.dataset.touchStartY);
      if (Number.isFinite(start) && event.changedTouches[0].clientY - start > 70) setDockOpen(false);
      delete dock.dataset.touchStartY;
    }, { passive: true });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && dockOpen && !detailDialog.open) {
        event.preventDefault();
        setDockOpen(false, true);
      }
    });
    caption = document.createElement('button');
    caption.id = 'aegis-layer-caption';
    caption.type = 'button';
    caption.setAttribute('aria-label', 'Explain map imagery and illustrative layers');
    dock.append(caption);
    const layerDialog = document.createElement('dialog');
    layerDialog.id = 'aegis-layer-caption-dialog';
    layerDialog.className = 'estimate-detail-dialog';
    layerDialog.innerHTML = '<div class="estimate-detail-heading"><h2>MAP LAYER NOTES</h2><button type="button" class="estimate-detail-close" aria-label="Close layer notes">×</button></div><p><strong>Satellite imagery:</strong> imagery is a visual background only; it has no flood classification.</p><p><strong>Risk perimeter:</strong> an illustrative research overlay, not a measured flood boundary or official alert.</p>';
    document.body.append(layerDialog);
    layerDialog.querySelector('.estimate-detail-close').addEventListener('click', () => layerDialog.close?.());
    caption.addEventListener('click', () => layerDialog.showModal?.());
    window.addEventListener('resize', () => { if (dockOpen) placeCaption(); }, { passive: true });
    const layerBar = $('#active-layer-bar');
    if (layerBar) {
      layerBar.setAttribute('aria-hidden', 'true');
      const updateCaption = () => {
        const labels = [...layerBar.querySelectorAll('.layer-chip')].map(node => node.textContent.trim()).filter(Boolean);
        const mapLabels = labels.filter(label => /satellite imagery|risk perimeter/i.test(label));
        caption.textContent = mapLabels.length ? mapLabels.join(' · ') : 'No flood classification · Research overlays are illustrative';
      };
      new MutationObserver(updateCaption).observe(layerBar, { childList: true, subtree: true, characterData: true });
      updateCaption();
    }
    searchButton.addEventListener('click', () => {
      setDockOpen(false);
      $('#location-input')?.focus();
    });
    if (dockOpen) setDockOpen(true);

    const updateDockPosition = () => {
      const viewportHeight = window.visualViewport?.height || window.innerHeight;
      const visibleSheetHeight = Math.max(0, viewportHeight - dockSheet.getBoundingClientRect().top);
      document.documentElement.style.setProperty('--estimate-dock-bottom', `${visibleSheetHeight + 10}px`);
    };
    window.aegisUpdateEstimateDockPosition = updateDockPosition;
    if ('ResizeObserver' in window) new ResizeObserver(updateDockPosition).observe(dockSheet);
    new MutationObserver(() => {
      const expanded = dockSheet.classList.contains('sheet-expanded');
      if (expanded && dockOpen) setDockOpen(false, false, false);
      document.body.classList.toggle('aegis-sheet-open', expanded);
      dock.inert = expanded;
      dock.setAttribute('aria-hidden', String(expanded));
      updateDockPosition();
    }).observe(dockSheet, { attributes: true, attributeFilter: ['class', 'style'] });
    dockSheet.addEventListener('transitionend', event => {
      if (event.propertyName === 'transform') updateDockPosition();
    });
    window.addEventListener('resize', updateDockPosition, { passive: true });
    window.visualViewport?.addEventListener('resize', updateDockPosition, { passive: true });
    updateDockPosition();
    requestAnimationFrame(() => requestAnimationFrame(updateDockPosition));
    new ResizeObserver(() => document.documentElement.style.setProperty('--estimate-card-height', `${dockEstimateCard.getBoundingClientRect().height}px`)).observe(dockEstimateCard);

    document.addEventListener('focusin', event => {
      if (event.target.matches?.('input, textarea, [contenteditable="true"]')) document.body.classList.add('aegis-keyboard-focus');
    });
    document.addEventListener('focusout', event => {
      if (event.target.matches?.('input, textarea, [contenteditable="true"]')) setTimeout(() => {
        if (!document.activeElement?.matches?.('input, textarea, [contenteditable="true"]')) document.body.classList.remove('aegis-keyboard-focus');
      }, 0);
    });

    const moreButton = document.createElement('button');
    moreButton.id = 'aegis-more-button';
    moreButton.type = 'button';
    moreButton.textContent = 'More';
    moreButton.setAttribute('aria-expanded', 'false');
    moreButton.setAttribute('aria-haspopup', 'menu');
    const moreMenu = document.createElement('div');
    moreMenu.className = 'aegis-more-menu';
    moreMenu.hidden = true;
    const openSettings = dockSheet.querySelector('.ops-heading .aegis-utility-button');
    if (openSettings) {
      openSettings.className = 'aegis-more-settings-button';
      openSettings.textContent = 'Settings';
      openSettings.setAttribute('aria-label', 'Open Settings');
    }
    const appearanceButton = $('#appearance-button');
    const helpButton = $('.aegis-help-button');
    const heading = dockSheet.querySelector('.ops-heading');
    if (appearanceButton || helpButton) {
      moreMenu.append(openSettings, ...[appearanceButton, helpButton].filter(Boolean));
      heading?.append(moreButton, moreMenu);
      openSettings?.addEventListener('click', () => {
        moreMenu.hidden = true;
        moreButton.setAttribute('aria-expanded', 'false');
      });
      moreButton.addEventListener('click', () => {
        moreMenu.hidden = !moreMenu.hidden;
        moreButton.setAttribute('aria-expanded', String(!moreMenu.hidden));
      });
      document.addEventListener('click', event => {
        if (!moreMenu.contains(event.target) && event.target !== moreButton) {
          moreMenu.hidden = true;
          moreButton.setAttribute('aria-expanded', 'false');
        }
      });
    }
    const tabs = dockSheet.querySelector('.ops-tabs');
    if (tabs) {
      const positionActiveTab = () => {
        const active = tabs.querySelector('.ops-tab.active');
        if (!active) return;
        tabs.style.setProperty('--active-tab-x', `${active.offsetLeft}px`);
        tabs.style.setProperty('--active-tab-width', `${active.offsetWidth}px`);
      };
      new MutationObserver(positionActiveTab).observe(tabs, { subtree: true, attributes: true, attributeFilter: ['class'] });
      positionActiveTab();
      window.addEventListener('resize', positionActiveTab, { passive: true });
    }

    const languageNote = $('.language-note');
    if (languageNote) {
      const languageSelect = $('#language-picker');
      const noteKey = code => `aegis-language-note-dismissed-${code || 'en'}`;
      const dismissNote = document.createElement('button');
      dismissNote.type = 'button';
      dismissNote.className = 'language-note-dismiss';
      dismissNote.setAttribute('aria-label', 'Dismiss language note');
      dismissNote.textContent = '×';
      languageNote.append(dismissNote);
      new MutationObserver(() => {
        if (!languageNote.contains(dismissNote)) languageNote.append(dismissNote);
      }).observe(languageNote, { childList: true });
      const refreshNote = () => { languageNote.hidden = safeRead(noteKey(languageSelect?.value), false) === true; };
      dismissNote.addEventListener('click', () => {
        safeWrite(noteKey(languageSelect?.value), true);
        languageNote.hidden = true;
      });
      languageSelect?.addEventListener('change', refreshNote);
      refreshNote();
      const settingsNote = document.createElement('button');
      settingsNote.type = 'button';
      settingsNote.className = 'aegis-settings-language-note';
      settingsNote.textContent = 'Show language note';
      settings.querySelector('.aegis-panel')?.append(settingsNote);
      settingsNote.addEventListener('click', () => {
        safeWrite(noteKey(languageSelect?.value), false);
        languageNote.hidden = false;
        closeOverlay(settings);
      });
    }

    const originalScan = window.initiateSwarm;
    if (typeof originalScan === 'function') {
      window.initiateSwarm = async function(...args) {
        if (dock.dataset.state === 'scanning') return;
        setStatus('scanning');
        try {
          const result = await originalScan.apply(this, args);
          const failed = $('#trigger-btn')?.textContent.includes('RETRY SCAN');
          setStatus(failed ? 'error' : 'ready');
          if (failed) newDot.hidden = false;
          else newDot.hidden = dockOpen;
          return result;
        } catch (error) {
          setStatus('error');
          throw error;
        }
      };
    }
    const scanAction = $('#trigger-btn');
    const estimateRun = $('.estimate-run', dockEstimateCard);
    if (scanAction && estimateRun) {
      new MutationObserver(() => {
        const label = scanAction.textContent.trim();
        if (label.includes('COMPUTING')) {
          estimateRun.textContent = 'SCANNING…';
          estimateRun.disabled = true;
        } else {
          estimateRun.disabled = false;
          estimateRun.textContent = label.includes('RETRY SCAN') ? 'RETRY SCAN' : label.includes('SWARM DEPLOYED') ? 'RESCAN' : ($('#risk-badge')?.textContent.includes('UNCALIBRATED SCORE') ? 'RESCAN' : 'RUN SCAN');
        }
      }).observe(scanAction, { childList: true, characterData: true, subtree: true });
    }
    if (!safeRead('aegis-estimate-coach-shown-v1', false)) {
      const coachmark = document.createElement('div');
      coachmark.className = 'estimate-dock-coach';
      coachmark.setAttribute('role', 'status');
      coachmark.textContent = 'Your estimate lives here';
      dock.append(coachmark);
      const dismissCoachmark = () => {
        safeWrite('aegis-estimate-coach-shown-v1', true);
        coachmark.remove();
      };
      toggle.addEventListener('click', dismissCoachmark, { once: true });
      scanButton.addEventListener('click', dismissCoachmark, { once: true });
      setTimeout(dismissCoachmark, 9000);
    }
    const refreshDockLocale = () => {
      setStatus(dock.dataset.state || 'ready');
      scanButton.setAttribute('aria-label', t('Run scan without opening estimate details','विवरण खोले बिना स्कैन चलाएँ'));
      closeButton.setAttribute('aria-label', t('Close estimate card','अनुमान कार्ड बंद करें'));
      searchButton.setAttribute('aria-label', t('Open place search','स्थान खोज खोलें'));
      moreButton.setAttribute('aria-label', t('More','और'));
      if (openSettings) openSettings.setAttribute('aria-label', t('Open Settings','सेटिंग्स खोलें'));
    };
    const priorLanguageChange = window.changeLanguage;
    if (typeof priorLanguageChange === 'function') {
      window.changeLanguage = function(...args) {
        const result = priorLanguageChange.apply(this, args);
        refreshDockLocale();
        return result;
      };
    }
    refreshDockLocale();
  }
  applyAddendumLanguage();
})();
