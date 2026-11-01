(() => {
  const root = document.documentElement;
  const dialog = document.getElementById('appearance-dialog');
  const openButton = document.getElementById('appearance-button');
  const closeButton = dialog?.querySelector('.appearance-close');
  const themeSelect = document.getElementById('theme-select');
  const contrastToggle = document.getElementById('contrast-toggle');
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const appleStatusBar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  const themeModes = ['system', 'light', 'dark'];
  const scriptFonts = {
    as: 'Noto Sans Bengali',
    bn: 'Noto Sans Bengali',
    brx: 'Noto Sans Devanagari',
    doi: 'Noto Sans Devanagari',
    gu: 'Noto Sans Gujarati',
    hi: 'Noto Sans Devanagari',
    kn: 'Noto Sans Kannada',
    ks: 'Noto Sans Devanagari',
    gom: 'Noto Sans Devanagari',
    mai: 'Noto Sans Devanagari',
    ml: 'Noto Sans Malayalam',
    mni: 'Noto Sans Meetei Mayek',
    mr: 'Noto Sans Devanagari',
    ne: 'Noto Sans Devanagari',
    or: 'Noto Sans Oriya',
    pa: 'Noto Sans Gurmukhi',
    sa: 'Noto Sans Devanagari',
    sat: 'Noto Sans Ol Chiki',
    sd: 'Noto Sans Arabic',
    ta: 'Noto Sans Tamil',
    te: 'Noto Sans Telugu',
    ur: 'Noto Nastaliq Urdu'
  };
  const systemDark = matchMedia('(prefers-color-scheme: dark)');

  const readPreference = (key, fallback) => {
    try {
      return localStorage.getItem(key) || fallback;
    } catch (error) {
      console.warn('Appearance preference could not be read.', error);
      return fallback;
    }
  };

  const savePreference = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      console.warn('Appearance preference could not be saved.', error);
    }
  };

  const applyTheme = (mode) => {
    const preference = themeModes.includes(mode) ? mode : 'system';
    const dark = preference === 'dark' || (preference === 'system' && systemDark.matches);
    root.dataset.theme = dark ? 'dark' : 'light';
    if (themeSelect) themeSelect.value = preference;
    if (themeColor) themeColor.content = dark ? '#211d49' : '#fff8e1';
    if (appleStatusBar) appleStatusBar.content = dark ? 'black' : 'default';
    return preference;
  };

  let themePreference = applyTheme(readPreference('aegis-theme', 'system'));
  const isHighContrast = readPreference('aegis-high-contrast', 'false') === 'true';
  if (contrastToggle) contrastToggle.checked = isHighContrast;
  if (isHighContrast) root.dataset.contrast = 'high';

  themeSelect?.addEventListener('change', () => {
    themePreference = applyTheme(themeSelect.value);
    savePreference('aegis-theme', themePreference);
  });

  contrastToggle?.addEventListener('change', () => {
    if (contrastToggle.checked) root.dataset.contrast = 'high';
    else delete root.dataset.contrast;
    savePreference('aegis-high-contrast', String(contrastToggle.checked));
  });

  openButton?.addEventListener('click', () => {
    if (dialog && !dialog.open) dialog.showModal();
  });
  closeButton?.addEventListener('click', () => dialog?.close());
  dialog?.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog?.addEventListener('close', () => openButton?.focus());

  systemDark.addEventListener('change', () => {
    if (themePreference === 'system') applyTheme('system');
  });

  const applyScriptFont = () => {
    const language = root.lang.toLowerCase().split('-')[0];
    const font = scriptFonts[language];
    let link = document.getElementById('aegis-script-font');
    if (!font) {
      link?.remove();
      root.style.removeProperty('--font-script');
      return;
    }
    if (!link) {
      link = document.createElement('link');
      link.id = 'aegis-script-font';
      link.rel = 'stylesheet';
      document.head.append(link);
    }
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(font)}:wght@700;800;900&display=swap`;
    root.style.setProperty('--font-script', `"${font}", var(--font-body)`);
  };

  applyScriptFont();
  new MutationObserver(applyScriptFont).observe(root, { attributes: true, attributeFilter: ['lang'] });
})();
