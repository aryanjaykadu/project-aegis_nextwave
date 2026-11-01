const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', 'frontend');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const ui = fs.readFileSync(path.join(root, 'aegis-addendum.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'aegis-addendum.css'), 'utf8');
const features = fs.readFileSync(path.join(root, 'aegis-features.js'), 'utf8');
const worker = fs.readFileSync(path.join(root, 'service-worker.js'), 'utf8');
const index = html;

test('map attribution and source/license entry point are present', () => {
  assert.match(html, /attribution:\s*'© OpenStreetMap contributors'/);
  assert.match(ui, /openstreetmap\.org\/copyright/);
  assert.match(ui, /Data sources and licenses/);
  assert.match(css, /#aegis-map-credits/);
  assert.match(css, /@media\(max-width:600px\)\{\.leaflet-control-attribution\{position:fixed/);
});

test('mobile search has explicit clear, recent deletion, and 16px input', () => {
  assert.match(ui, /Clear recent searches/);
  assert.match(ui, /aegis-search-clear/);
  assert.match(css, /\.search-input\{font-size:16px!important/);
});

test('emergency mode has offline actions and never claims dispatch', () => {
  for (const action of ['Call 112', 'Send location by SMS', 'Nearest cached help', "I'm safe", 'Exit emergency mode']) {
    assert.ok(ui.includes(action), `missing emergency action: ${action}`);
  }
  assert.match(ui, /No help is dispatched by this app/);
  assert.match(ui, /aegis-resource-cache-v1/);
  assert.match(ui, /document\.querySelector\('\.top-bar'\) \|\| document\.body/);
  assert.match(css, /\.top-bar #aegis-emergency-open\{position:static/);
});

test('permission prompts gate location, notifications, and camera/photo selection', () => {
  assert.match(ui, /requestLocation\(\)/);
  assert.match(ui, /Notification\.requestPermission\(\)/);
  assert.match(ui, /aegis-community-reports input\[type="file"\]/);
  assert.match(ui, /Not now/);
});

test('crowd reports stay separate from official risk and expire visibly', () => {
  assert.match(features, /REPORT AS FALSE/);
  assert.match(features, /not an official alert/i);
  assert.match(css, /\.aegis-expired-report/);
  assert.match(css, /\.aegis-unverified/);
});

test('update activation is user-triggered and deferred during active work', () => {
  assert.match(ui, /New version available/);
  assert.match(ui, /deferUpdate/);
  assert.match(ui, /SKIP_WAITING/);
  assert.match(worker, /event\.data\?\.type==='SKIP_WAITING'/);
});

test('risk and confidence have non-color visual patterns and text', () => {
  assert.match(css, /repeating-linear-gradient/);
  assert.match(css, /\.status-pill::before/);
  assert.match(features, /role','meter/);
  assert.match(features, /Confidence:/);
});

test('saved-data controls and background handling are present', () => {
  assert.match(ui, /Export my local data/);
  assert.match(ui, /Clear my local data/);
  assert.match(ui, /visibilitychange/);
  assert.match(ui, /aegis-data-saver-v1/);
});

test('largest text mode permits 200 percent scaling', () => {
  assert.match(css, /data-text-size="largest"\]\{font-size:200%\}/);
});

test('estimate dock keeps existing scan and estimate IDs and exposes accessible controls', () => {
  for (const id of ['risk-summary', 'risk-value', 'risk-window', 'risk-badge', 'trigger-btn']) {
    assert.ok(html.includes(`id="${id}"`), `existing element ${id} must remain`);
  }
  assert.match(ui, /id = 'estimate-dock-toggle'/);
  assert.match(ui, /aria-controls', 'risk-summary'/);
  assert.match(ui, /window\.initiateSwarm\?\.\(\)/);
  assert.match(css, /#estimate-dock\.is-open #risk-summary/);
  assert.match(ui, /Your estimate lives here/);
});

test('estimate dock delegates scan-running ownership to the existing scan wrapper', () => {
  const wrapperStart = ui.indexOf('const originalScan = window.initiateSwarm;');
  const scanActionStart = ui.indexOf('const scanAction =', wrapperStart);
  const dockScanWrapper = ui.slice(wrapperStart, scanActionStart);
  assert.ok(wrapperStart >= 0 && scanActionStart > wrapperStart);
  assert.match(dockScanWrapper, /setStatus\('scanning'\)/);
  assert.doesNotMatch(dockScanWrapper, /classList\.add\('aegis-scan-running'\)/);
  assert.match(html, /if\(document\.body\.classList\.contains\('aegis-scan-running'\)\)return/);
});

test('map-layer caption and operations controls are non-overlapping additions', () => {
  assert.match(ui, /aegis-layer-caption/);
  assert.match(ui, /no flood classification/);
  assert.match(ui, /aegis-more-button/);
  assert.match(css, /\.ops-tabs::before/);
  assert.match(css, /aegis-estimate-dock-open \.search-container/);
});

test('Leaflet vendor assets are precached for controlled offline reloads', () => {
  assert.match(worker, /aegis-shell-v20/);
  assert.match(worker, /unpkg\.com\/leaflet@1\.9\.4\/dist\/leaflet\.js/);
  assert.match(worker, /unpkg\.com\/leaflet@1\.9\.4\/dist\/leaflet\.css/);
  assert.match(worker, /aegis-region-packs-v1/);
  assert.match(worker, /resource-packs/);
});

test('satellite swaps retain street tiles until imagery has loaded', () => {
  assert.match(html, /The street map remains visible until imagery is ready/);
  assert.match(html, /candidate\.once\('load'/);
  assert.match(html, /candidate\.on\('tileerror'/);
  assert.match(html, /detectRetina:false/);
  assert.match(css, /\.leaflet-tile\{transition:opacity/);
});
