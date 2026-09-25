// Add or edit categories here — every page (nav dropdown, homepage grid,
// category pages) reads from this single list.
const CATEGORIES = [
  { slug: 'image-analysis', name: 'Image analysis', desc: 'segmentation, registration, anatomical reconstruction', icon: 'imageAnalysis' },
  { slug: 'statistical-analysis', name: 'Statistical analysis', desc: 'models, inference, testing', icon: 'stats' },
  { slug: 'automated-behavioral-tracking', name: 'Automated behavioral tracking', desc: 'pose, motion, ethograms', icon: 'behavior' },
  { slug: 'electrophysiology', name: 'Electrophysiology', desc: 'spike sorting, LFP, SWR', icon: 'ephys' },
  { slug: 'brain-imaging', name: 'Brain imaging', desc: 'functional or anatomical — MRI, fMRI, MEG/EEG, light-sheet', icon: 'brainImaging' },
  { slug: 'gene-protein-analysis', name: 'Gene and protein analysis', desc: 'sequencing, structure', icon: 'gene' },
  { slug: 'spatial-omics', name: 'Spatial omics', desc: 'tissue-level molecular maps', icon: 'omics' },
  { slug: 'neural-networks', name: 'Neural networks', desc: 'ML/DL models for neuro data', icon: 'nn' },
];

function getCategory(slug){
  return CATEGORIES.find(c => c.slug === slug);
}

function getEntryCategories(entry){
  if (entry.categories && entry.categories.length) return entry.categories;
  return entry.category ? [entry.category] : [];
}
