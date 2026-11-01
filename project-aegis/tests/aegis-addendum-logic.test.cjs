const test = require('node:test');
const assert = require('node:assert/strict');
const logic = require('../frontend/aegis-addendum-logic.js');

test('duplicate place labels include district and state', () => {
  assert.equal(logic.displayPlace({
    name: 'Rampur',
    address: { county: 'Patna', state: 'Bihar' }
  }), 'Rampur, Patna, Bihar');
});

test('two-place search queries require choosing one place', () => {
  assert.equal(logic.hasMultiplePlaces('Patna and Bihta'), true);
  assert.equal(logic.hasMultiplePlaces('Patna, Bihta'), true);
  assert.equal(logic.hasMultiplePlaces('Rampur, Uttar Pradesh'), false);
  assert.equal(logic.hasMultiplePlaces('Aryabhatta Hostel IIT Patna'), false);
});

test('disputed and old observations remain unverified', () => {
  const now = Date.parse('2026-11-01T00:00:00Z');
  assert.deepEqual(logic.reportState({
    created_at: '2026-10-30T00:00:00Z',
    verification_status: 'disputed'
  }, now), {
    expired: false,
    disputed: true,
    confirmed: false,
    officialVerified: false,
    communityConfirmed: false,
    label: 'DISPUTED · UNVERIFIED'
  });
  assert.equal(logic.reportState({
    created_at: '2026-09-01T00:00:00Z',
    verification_status: 'unverified'
  }, now).label, 'EXPIRED · UNVERIFIED');
  assert.equal(logic.reportState({
    created_at: '2026-10-30T00:00:00Z',
    confirmations: 3,
    disputes: 0,
    verification_status: 'unverified'
  }, now).label, '3+ CROWD CONFIRMS · NOT OFFICIAL');
});

test('relative time uses the provided clock', () => {
  assert.equal(logic.relativeTime('2026-11-01T00:00:00Z', Date.parse('2026-11-01T00:02:00Z')), '2 minutes ago');
});

test('offline banner never invents a cache age', () => {
  assert.equal(logic.networkBanner({ online: false }), 'Offline · cached data may be out of date. Check each source time.');
  assert.match(logic.networkBanner({ online: false, lastSuccess: '2026-11-01T00:00:00Z' }), /last server check .* IST/);
  assert.equal(logic.networkBanner({ online: true }), '');
});

test('SMS fallback respects missing contact and permission denial', () => {
  assert.equal(logic.emergencySmsMode({ mobile: true, contact: '', permission: true }), 'missing-contact');
  assert.equal(logic.emergencySmsMode({ mobile: true, contact: '112', permission: false }), 'permission-denied');
  assert.equal(logic.emergencySmsMode({ mobile: false, contact: '112', permission: true, clipboard: true }), 'copy-message');
});

test('updates wait until scans, uploads, and gestures finish', () => {
  assert.equal(logic.deferUpdate({ scan: true }), true);
  assert.equal(logic.deferUpdate({ upload: true }), true);
  assert.equal(logic.deferUpdate({ drag: true }), true);
  assert.equal(logic.deferUpdate({ scan: false, upload: false, drag: false }), false);
});

test('background and low-data settings suppress polling', () => {
  assert.equal(logic.shouldPoll({ hidden: true, dataSaver: false }), false);
  assert.equal(logic.shouldPoll({ hidden: false, dataSaver: true }), false);
  assert.equal(logic.shouldPoll({ hidden: false, dataSaver: false }), true);
});
