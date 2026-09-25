const ICONS = {
  logoMark: (accent) => `
    <svg viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="2.6" fill="#1B1D16"/>
      <path d="M20 20 C 14 16, 9 15, 5 10" stroke="#1B1D16" stroke-width="1.4" stroke-linecap="round" fill="none"/>
      <path d="M20 20 C 12 21, 8 25, 6 31" stroke="#1B1D16" stroke-width="1.4" stroke-linecap="round" fill="none"/>
      <path d="M20 20 C 26 15, 30 9, 29 4" stroke="#1B1D16" stroke-width="1.4" stroke-linecap="round" fill="none"/>
      <path d="M20 20 C 27 23, 33 22, 37 17" stroke="${accent || '#1B8C82'}" stroke-width="1.6" stroke-linecap="round" fill="none"/>
      <circle cx="5" cy="10" r="1.8" fill="#1B1D16"/>
      <circle cx="6" cy="31" r="1.8" fill="#1B1D16"/>
      <circle cx="29" cy="4" r="1.8" fill="#1B1D16"/>
      <circle cx="37" cy="17" r="2.2" fill="${accent || '#1B8C82'}"/>
    </svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>`,
  github: `<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a8 8 0 0 0-2.5 15.6c.4.1.5-.2.5-.4v-1.5c-2 .4-2.5-.5-2.7-1-.1-.2-.5-1-.9-1.2-.3-.1-.7-.5 0-.5.6 0 1.1.6 1.2.9.7 1.2 1.9.9 2.4.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4a3.1 3.1 0 0 1 .8-2.2c-.1-.2-.4-1.1.1-2.3 0 0 .7-.2 2.2.8a7.6 7.6 0 0 1 4 0c1.5-1 2.2-.8 2.2-.8.5 1.2.2 2.1.1 2.3.5.6.8 1.3.8 2.2 0 3.1-1.9 3.8-3.6 4 .3.3.6.8.6 1.6v2.4c0 .2.1.5.6.4A8 8 0 0 0 8 0Z"/></svg>`,
  paper: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M15 2v5h5M9 13h6M9 17h6"/></svg>`,
  tutorial: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></svg>`,
  bookmark: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2a2 2 0 0 0-2 2v18l8-5 8 5V4a2 2 0 0 0-2-2H6z"/></svg>`,
  cite: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 8h10M7 12h10M7 16h6"/></svg>`,
  globe: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18M3 12h18"/></svg>`,
  back: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>`,
  imageAnalysis: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>`,
  stats: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3v18h18"/><path d="M7 14l3-4 3 3 4-6"/></svg>`,
  behavior: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a5 5 0 0 0-5 5v3a5 5 0 0 0 10 0V7a5 5 0 0 0-5-5Z"/><path d="M7 10a5 5 0 0 0 10 0M12 20v-2"/></svg>`,
  ephys: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h4l2-8 4 16 2-8h6"/></svg>`,
  brainImaging: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18M3 12h18"/></svg>`,
  gene: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3v6a3 3 0 0 0 3 3h0a3 3 0 0 0 3-3V3M18 21v-6a3 3 0 0 0-3-3h0a3 3 0 0 0-3 3v6"/></svg>`,
  omics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M6 8v8M18 8v8M8 6h8M8 18h8"/></svg>`,
  nn: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="5" cy="6" r="1.6"/><circle cx="5" cy="18" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="6" r="1.6"/><circle cx="19" cy="18" r="1.6"/><path d="M5 6l7 6M5 18l7-6M19 6l-7 6M19 18l-7-6"/></svg>`,
};
