(() => {
  const logic = {
    hasMultiplePlaces(query) {
      const value = String(query || '').trim();
      if (/\b(?:and|versus|vs\.?|near|to)\b/i.test(value) || /[|;/&]/.test(value)) return true;
      const parts = value.split(',').map(part => part.trim()).filter(Boolean);
      if (parts.length < 2) return false;
      const admin = /^(india|andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|goa|gujarat|haryana|himachal pradesh|jharkhand|karnataka|kerala|madhya pradesh|maharashtra|manipur|meghalaya|mizoram|nagaland|odisha|punjab|rajasthan|sikkim|tamil nadu|telangana|tripura|uttar pradesh|uttarakhand|west bengal|delhi|jammu and kashmir|ladakh)$/i;
      return parts.slice(1).some(part => !admin.test(part));
    },
    displayPlace(result) {
      const address = result?.address || {};
      const locality = result?.name || result?.display_name?.split(',')[0] || 'Unknown place';
      const district = address.county || address.state_district || address.district || '';
      const state = address.state || address.region || '';
      return [locality, district, state].filter(Boolean).join(', ');
    },
    reportState(report, now = Date.now(), expiryDays = 30) {
      const created = Date.parse(report?.created_at || '');
      const expired = Number.isFinite(created) && now - created > expiryDays * 86400000;
      const officialVerified = report?.verification_status === 'verified';
      const disputed = Number(report?.disputes) > 0 || /disput|reject/i.test(String(report?.verification_status || ''));
      const communityConfirmed = Number(report?.confirmations) >= 3 && Number(report?.confirmations) > Number(report?.disputes || 0);
      const confirmed = officialVerified || communityConfirmed;
      const label = expired ? officialVerified ? 'REVIEWER VERIFIED · STALE' : communityConfirmed ? 'CROWD CONFIRMED · STALE' : 'EXPIRED · UNVERIFIED' : disputed && !officialVerified ? 'DISPUTED · UNVERIFIED' : officialVerified ? 'REVIEWER VERIFIED' : communityConfirmed ? '3+ CROWD CONFIRMS · NOT OFFICIAL' : 'UNVERIFIED';
      return { expired, disputed, confirmed, officialVerified, communityConfirmed, label };
    },
    relativeTime(value, now = Date.now()) {
      const timestamp = Date.parse(value);
      if (!Number.isFinite(timestamp)) return 'Time unavailable';
      const seconds = Math.round((timestamp - now) / 1000);
      const abs = Math.abs(seconds);
      const unit = abs < 60 ? 'second' : abs < 3600 ? 'minute' : abs < 86400 ? 'hour' : 'day';
      const amount = unit === 'second' ? seconds : Math.round(seconds / ({ minute: 60, hour: 3600, day: 86400 }[unit]));
      return new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(amount, unit);
    },
    emergencySmsMode({ mobile, contact, permission, clipboard }) {
      if (!contact) return 'missing-contact';
      if (permission === false) return 'permission-denied';
      if (mobile) return 'open-sms';
      return clipboard ? 'copy-message' : 'manual-message';
    },
    deferUpdate({ scan, upload, drag }) {
      return Boolean(scan || upload || drag);
    },
    shouldPoll({ hidden, dataSaver }) {
      return !hidden && !dataSaver;
    },
    networkBanner({ online, lastSuccess }) {
      if (online) return '';
      const time = Date.parse(lastSuccess || '');
      return Number.isFinite(time)
        ? `Offline · last server check ${new Date(time).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' })} IST. Source timestamps vary.`
        : 'Offline · cached data may be out of date. Check each source time.';
    }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = logic;
  else globalThis.AegisAddendumLogic = logic;
})();
