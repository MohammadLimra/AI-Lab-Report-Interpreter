

let selectedFile = null;
let currentHistory = [];
let activeHistoryId = null;

let activeReportText = "";
let activeAnalysis = "";
let chatHistory = [];

let ollamaAvailable = false;
let visionSupported = false;
let selectedModel = 'gemma4:e2b';

const LOADING_MESSAGES = [
  'Reading report…',
  'Checking values against normal ranges…',
  'Cross-referencing findings…',
  'Composing plain-English summary…'
];

const SYSTEM_PROMPT = `AI Lab Report Interpreter" - a general medical report analysis assistant.

You can read and explain ANY type of medical report, including but not limited to:
- Blood tests (CBC, LFTs, RFTs, lipid profile, blood sugar/HbA1c, electrolytes, thyroid panel, etc.)
- Urine and stool analysis
- CSF (cerebrospinal fluid) reports
- Culture & sensitivity reports
- Biopsy / histopathology reports
- Ultrasound, X-ray, CT, MRI reports
- ECG / cardiac reports
- Prescriptions and discharge summaries
- Any other lab or diagnostic report

Your job is to:
1. Read WHATEVER report is given to you and explain it in simple, clear,
   plain English that any patient or family member can understand —
   regardless of which department or test type it is.
2. Go through EACH test/parameter mentioned in the report. For each one,
   clearly state the value, the normal reference range (if given), and
   whether it is ✅ Normal or ⚠️ Abnormal (High/Low).
3. Mention possible diagnoses or patterns suggested by the overall results
   (e.g. "this pattern can be seen in...").
4. Present the report in a SHORT, clear, bullet-point format - avoid long
   paragraphs unless the user specifically asks for more detail.
5. If the report has multiple sections or pages, summarize all of them,
   not just the first one.

Style Rules:
- Respond in plain, simple English (avoid heavy medical jargon; explain
  terms briefly when you use them).
- Use emojis for clarity (✅ ⚠️ 🔴 🫁 etc).
- Use headings and bullet points for readability.
- Do NOT use math blocks, LaTeX formatting, or dollar signs ($) for numbers, values, ranges, ratios, or units. Write all measurements and statistics in plain text (e.g. write "134 mmol/L" instead of "$134\\text{ mmol/L}$", and "3.27" instead of "$3.27$").
- Recommend a specific dose or a new treatment.
- Do not assume the report is about any specific disease (like TB) unless
  the actual values/findings in front of you support that. Base your
  reading strictly on what is written in the report.`;


if (typeof pdfjsLib !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
}

function updateAnalyzeButtonState() {
  const analyzeBtn = document.getElementById('analyzeBtn');
  if (analyzeBtn) {
    analyzeBtn.disabled = !selectedFile;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  checkEngineStatus();
  loadHistory();
  setInterval(checkEngineStatus, 15000); 

  updateAnalyzeButtonState();
  initializeThemeToggle();
});

function initializeThemeToggle() {
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  if (!themeToggleBtn) return;
  
  themeToggleBtn.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  });
}





const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      selectedFile = e.target.files[0];
      renderFileChip();
    }
  });
}

if (dropzone) {
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      selectedFile = e.dataTransfer.files[0];
      if (fileInput) {
        fileInput.files = e.dataTransfer.files;
      }
      renderFileChip();
    }
  });
}

function renderFileChip() {
  const holder = document.getElementById('fileChipHolder');
  if (!selectedFile) {
    holder.innerHTML = '';
    updateAnalyzeButtonState();
    return;
  }
  const icon = selectedFile.name.toLowerCase().endsWith('.pdf') ? '📄' : '🖼️';
  holder.innerHTML = `<div class="file-chip">${icon} ${escapeHtml(selectedFile.name)}</div>`;
  updateAnalyzeButtonState();
}


function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function showError(msg) {
  const box = document.getElementById('errorBox');
  box.textContent = msg;
  box.style.display = 'block';
}
function hideError() {
  document.getElementById('errorBox').style.display = 'none';
}

function cleanMathLaTeX(text) {
  if (!text) return '';
  return text.replace(/\${1,2}(.*?)\${1,2}/g, (match, mathContent) => {
    return mathContent
      .replace(/\\text\s*\{([^\}]+)\}/g, '$1')
      .replace(/\\mathrm\s*\{([^\}]+)\}/g, '$1')
      .replace(/\\mu\b/g, 'µ')
      .replace(/\\le(q)?\b/g, '≤')
      .replace(/\\ge(q)?\b/g, '≥')
      .replace(/\\times\b/g, '×')
      .replace(/\\pm\b/g, '±')
      .replace(/\\approx\b/g, '≈')
      .replace(/\\cdot\b/g, '·')
      .replace(/\\div\b/g, '÷')
      .replace(/\\degree\b/g, '°')
      .replace(/\\%/g, '%')
      .replace(/\\/g, '');
  });
}

function renderMarkdown(text) {
  if (!text) return '';
  
  let cleaned = text;
  
  
  const introPattern = /^(?:Based on the|This is an|I have analyzed|Here is)[\s\S]*?(?:(?:\*\*\*|---|___)+|(?:###|##|#)+)\s*(?:Summary|Interpretation|Detailed|📋|📄)[\s\S]*?(?:Report|Findings|Results|Analysis)(?: Findings)?\s*\n*/gi;
  cleaned = cleaned.replace(introPattern, '');
  
  
  const parts = cleaned.split(/\n*(?:\*\*\*|---|___)\n*/);
  if (parts.length > 1) {
    const lastPart = parts[parts.length - 1].trim();
    const disclaimerKeywords = ["ai", "doctor", "physician", "medical advice", "diagnosis", "disclaimer", "not a medical", "clinical correlation"];
    const lowerLast = lastPart.toLowerCase();
    
    let isDisclaimer = false;
    for (const kw of disclaimerKeywords) {
      if (lowerLast.includes(kw)) {
        isDisclaimer = true;
        break;
      }
    }
    
    if (isDisclaimer && (
      lowerLast.startsWith("disclaimer") || 
      lowerLast.startsWith("**disclaimer") ||
      lowerLast.startsWith("###") ||
      lowerLast.startsWith("##") ||
      lowerLast.startsWith("#") ||
      lowerLast.startsWith("⚠️") ||
      lowerLast.startsWith("🚨") ||
      lowerLast.startsWith("🛑") ||
      lowerLast.startsWith("important") ||
      lowerLast.startsWith("note") ||
      lowerLast.startsWith("**note") ||
      lowerLast.startsWith("warning") ||
      lowerLast.startsWith("reminder") ||
      lowerLast.startsWith("caveat") ||
      lowerLast.includes("i am an ai") ||
      lowerLast.includes("not replace a consultation") ||
      lowerLast.includes("cannot replace a consultation")
    )) {
      cleaned = parts.slice(0, -1).join('***').trim();
    }
  }

  
  const disclaimerRegex1 = /\n*(?:\*\*\*|---|___)?\s*(?:###|##|#)?\s*(?:\*\*)?(?:⚠️|🚨|🛑)?\s*(?:Important\s+)?Disclaimer(?:\*\*)?(?::)?\s*[\s\S]*$/gi;
  cleaned = cleaned.replace(disclaimerRegex1, '');

  const disclaimerRegex2 = /\n*(?:\*\*\*|---|___)?\s*(?:###|##|#)?\s*(?:\*\*)?(?:⚠️|🚨|🛑)?\s*Important\s+(?:Disclaimer|Note|Reminder|Warning|Caveats|Medical Disclaimer)(?:\*\*)?(?::)?\s*[\s\S]*$/gi;
  cleaned = cleaned.replace(disclaimerRegex2, '');

  const disclaimerRegex3 = /\n*(?:\*\*\*|---|___)?\s*Please remember that\s*(?:\*\*)?I am an AI assistant\s*not a medical doctor[\s\S]*$/gi;
  cleaned = cleaned.replace(disclaimerRegex3, '');

  cleaned = cleaned.replace(/\n*(?:\*\*\*|---|___)\s*$/, '');
  cleaned = cleanMathLaTeX(cleaned);
  
  let html = escapeHtml(cleaned)
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.*$)/gim, '• $1<br>')
    .replace(/\n/g, '<br>');
  html = html.replace(/^(<br>)+/i, '');
  return html;
}



let parsedParameters = [];
let currentFilter = 'all';
let searchQuery = '';

function parseReportParameters(text) {
  parsedParameters = [];
  if (!text) return text;

  const lines = text.split('\n');
  const remainingLines = [];
  
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    
    
    const paramMatch = line.match(/^[-*]\s+\*\*(.*?)\*\*:\s*(.*?)\s*\((?:Reference Range:\s*)?(.*?)\)\s*—\s*(✅|⚠️|🔴|🛑)\s*([a-zA-Z-\/ ]+)/i);
    
    if (paramMatch) {
      const name = paramMatch[1].trim();
      const value = paramMatch[2].trim();
      const range = paramMatch[3].trim();
      const emoji = paramMatch[4].trim();
      const status = paramMatch[5].trim().toLowerCase();
      
      let note = "";
      
      if (i + 1 < lines.length) {
        const nextLine = lines[i+1].trim();
        const noteMatch = nextLine.match(/^\*Note:\s*(.*?)\*$/i) || nextLine.match(/^Note:\s*(.*?)$/i);
        if (noteMatch) {
          note = noteMatch[1].trim();
          i++; 
        }
      }
      
      parsedParameters.push({
        name,
        value,
        range,
        emoji,
        status,
        note
      });
    } else {
      remainingLines.push(lines[i]);
    }
    i++;
  }
  
  return remainingLines.join('\n');
}

function parseNumericRange(rangeStr) {
  if (!rangeStr) return null;
  const cleanStr = rangeStr.replace(/,/g, '');
  const match = cleanStr.match(/(\d+(?:\.\d+)?)\s*[-\u2013\u2014to]+\s*(\d+(?:\.\d+)?)/);
  if (match) {
    return {
      min: parseFloat(match[1]),
      max: parseFloat(match[2])
    };
  }
  
  const singleMatch = cleanStr.match(/(<|>|<=|>=)\s*(\d+(?:\.\d+)?)/);
  if (singleMatch) {
    const val = parseFloat(singleMatch[2]);
    const operator = singleMatch[1];
    if (operator === '<' || operator === '<=') {
      return { min: 0, max: val };
    } else {
      return { min: val, max: val * 3 };
    }
  }
  return null;
}

function parseNumericValue(valStr) {
  if (!valStr) return null;
  const cleanStr = valStr.replace(/,/g, '');
  const match = cleanStr.match(/(\d+(?:\.\d+)?)/);
  return match ? parseFloat(match[1]) : null;
}

function updateDashboardStats() {
  const totalVal = document.getElementById('statTotalVal');
  const normalVal = document.getElementById('statNormalVal');
  const lowVal = document.getElementById('statLowVal');
  const highVal = document.getElementById('statHighVal');
  
  if (!totalVal) return;
  
  let totalCount = parsedParameters.length;
  let normalCount = 0;
  let lowCount = 0;
  let highCount = 0;
  
  parsedParameters.forEach(p => {
    if (p.status.includes('low') || p.emoji === '⚠️') {
      lowCount++;
    } else if (p.status.includes('high') || p.status.includes('abnormal') || p.emoji === '🔴' || p.emoji === '🛑') {
      highCount++;
    } else {
      normalCount++;
    }
  });
  
  totalVal.textContent = totalCount;
  normalVal.textContent = normalCount;
  lowVal.textContent = lowCount;
  highVal.textContent = highCount;
}

const MEDICAL_GLOSSARY = {
  "glucose": "Blood sugar level. High levels can indicate diabetes or prediabetes; low levels can cause dizziness or confusion.",
  "sugar": "Blood sugar level. High levels can indicate diabetes or prediabetes.",
  "cholesterol": "A waxy substance found in your blood. High total cholesterol increases risk of cardiovascular diseases.",
  "ldl": "Low-Density Lipoprotein (bad cholesterol). Excess LDL builds up in blood vessels, increasing risk of heart attacks.",
  "hdl": "High-Density Lipoprotein (good cholesterol). Helps remove other forms of cholesterol from your bloodstream.",
  "triglycerides": "A type of fat in your blood. High levels can harden arteries and increase risk of stroke and heart disease.",
  "hba1c": "Average blood sugar levels over the past 3 months. Used to diagnose and monitor diabetes.",
  "creatinine": "A waste product from muscle breakdown filtered by kidneys. High levels suggest reduced kidney function.",
  "egfr": "Estimated Glomerular Filtration Rate. Measures how well kidneys filter waste. Values below 60 can suggest kidney disease.",
  "gfr": "Glomerular Filtration Rate. Measures kidney filtration function.",
  "alt": "Alanine Aminotransferase. An enzyme found mostly in the liver. High levels suggest liver injury or inflammation.",
  "ast": "Aspartate Aminotransferase. An enzyme found in liver, heart, and muscles. Elevated levels suggest tissue or liver damage.",
  "sgpt": "Serum Glutamic Pyruvic Transaminase (also known as ALT). High levels suggest liver irritation.",
  "sgot": "Serum Glutamic Oxaloacetic Transaminase (also known as AST). High levels suggest tissue or liver damage.",
  "hemoglobin": "Protein in red blood cells that carries oxygen. Low levels suggest anemia, causing fatigue.",
  "tsh": "Thyroid Stimulating Hormone. High TSH suggests hypothyroidism (underactive thyroid); low TSH suggests hyperthyroidism.",
  "uric acid": "Waste product from purine breakdown. High levels can crystallize in joints, causing gout.",
  "bilirubin": "Yellow pigment from red blood cell breakdown. High levels can cause jaundice and suggest liver/bile issues.",
  "platelets": "Blood cells that help with clotting. Low levels (thrombocytopenia) can cause easy bruising or bleeding.",
  "wbc": "White Blood Cells. Part of the immune system. High levels suggest infection or inflammation.",
  "rbc": "Red Blood Cells. Cells that carry oxygen. Low levels suggest anemia."
};

function renderParameters() {
  const grid = document.getElementById('parametersGrid');
  if (!grid) return;
  
  const filtered = parsedParameters.filter(p => {
    if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (currentFilter === 'normal') {
      return p.status === 'normal' || p.emoji === '✅';
    }
    if (currentFilter === 'abnormal') {
      return p.status === 'low' || p.status === 'high' || p.emoji === '⚠️' || p.emoji === '🔴' || p.emoji === '🛑';
    }
    return true;
  });
  
  if (filtered.length === 0) {
    grid.innerHTML = `<div class="history-empty" style="grid-column: 1/-1; width: 100%;">No parameters match the filter.</div>`;
    return;
  }
  
  grid.innerHTML = filtered.map(p => {
    let statusClass = 'status-normal';
    let badgeClass = 'badge-normal';
    let normStatus = p.status;
    
    if (p.status.includes('low') || p.emoji === '⚠️') {
      statusClass = 'status-low';
      badgeClass = 'badge-low';
      normStatus = 'Low';
    } else if (p.status.includes('high') || p.status.includes('abnormal') || p.emoji === '🔴' || p.emoji === '🛑') {
      statusClass = 'status-high';
      badgeClass = 'badge-high';
      normStatus = 'High';
    } else {
      normStatus = 'Normal';
    }
    
    let scaleVisualHtml = '';
    const numericRange = parseNumericRange(p.range);
    const numericVal = parseNumericValue(p.value);
    
    if (numericRange && numericVal !== null) {
      let percentage = 50;
      const { min, max } = numericRange;
      if (max > min) {
        const rangeSpan = max - min;
        const valDiff = numericVal - min;
        percentage = 25 + (valDiff / rangeSpan) * 50;
        percentage = Math.max(5, Math.min(95, percentage));
      }
      
      scaleVisualHtml = `
        <div class="param-scale-container">
          <span style="font-size: 0.68rem; color: var(--text-muted);">${min}</span>
          <div class="param-scale-bar" title="Value: ${numericVal} (Normal Range: ${min} - ${max})">
            <div class="param-scale-normal-zone"></div>
            <div class="param-scale-marker" style="left: ${percentage}%;"></div>
          </div>
          <span style="font-size: 0.68rem; color: var(--text-muted);">${max}</span>
        </div>
      `;
    }
    
    const noteHtml = p.note ? `
      <div class="param-note">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>${escapeHtml(p.note)}</span>
      </div>
    ` : '';
    
    let nameHtml = escapeHtml(p.name);
    const lookupKey = p.name.toLowerCase().trim();
    if (MEDICAL_GLOSSARY[lookupKey]) {
      nameHtml = `
        <span class="param-name-txt">${escapeHtml(p.name)}</span>
        <span class="tooltip-container">
          <svg class="info-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span class="tooltip-text">${escapeHtml(MEDICAL_GLOSSARY[lookupKey])}</span>
        </span>
      `;
    }
    
    return `
      <div class="parameter-card ${statusClass}">
        <div class="param-name-wrap">
          <span class="param-name">${nameHtml}</span>
          <span class="param-range">Range: ${escapeHtml(p.range)}</span>
        </div>
        ${scaleVisualHtml}
        <div class="param-val-wrap">
          <span class="param-value">${escapeHtml(p.value)}</span>
          <span class="param-badge ${badgeClass}">${p.emoji} ${escapeHtml(normStatus)}</span>
        </div>
        ${noteHtml}
      </div>
    `;
  }).join('');
}

function resetFilterChipActiveState() {
  document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
  const allBtn = document.getElementById('filterAllBtn');
  if (allBtn) allBtn.classList.add('active');
}

function filterParameters() {
  const searchInput = document.getElementById('paramSearchInput');
  searchQuery = searchInput ? searchInput.value : '';
  renderParameters();
}

function setParamFilter(filterType) {
  currentFilter = filterType;
  
  document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
  
  if (filterType === 'all') {
    const allBtn = document.getElementById('filterAllBtn');
    if (allBtn) allBtn.classList.add('active');
  } else if (filterType === 'abnormal') {
    const abnormalBtn = document.getElementById('filterAbnormalBtn');
    if (abnormalBtn) abnormalBtn.classList.add('active');
  } else if (filterType === 'normal') {
    const normalBtn = document.getElementById('filterNormalBtn');
    if (normalBtn) normalBtn.classList.add('active');
  }
  
  renderParameters();
}

function handleDisplayAndParsing(analysis) {
  searchQuery = '';
  currentFilter = 'all';
  const searchInput = document.getElementById('paramSearchInput');
  if (searchInput) searchInput.value = '';
  resetFilterChipActiveState();

  const remainingMarkdown = parseReportParameters(analysis);
  
  const statsDiv = document.getElementById('dashboardStats');
  const toolbarDiv = document.getElementById('filterToolbar');
  const gridDiv = document.getElementById('parametersGrid');
  
  if (parsedParameters.length > 0) {
    if (statsDiv) statsDiv.style.display = 'grid';
    if (toolbarDiv) toolbarDiv.style.display = 'flex';
    if (gridDiv) gridDiv.style.display = 'flex';
    
    updateDashboardStats();
    renderParameters();
  } else {
    if (statsDiv) statsDiv.style.display = 'none';
    if (toolbarDiv) toolbarDiv.style.display = 'none';
    if (gridDiv) gridDiv.style.display = 'none';
  }
  
  document.getElementById('analysisOutput').innerHTML = renderMarkdown(remainingMarkdown);
}


function cleanAnalysisText(text) {
  return cleanMathLaTeX(text);
}

function summarizeForHistory(analysisText, maxLen = 90) {
  const lines = analysisText.split('\n');
  for (let line of lines) {
    let clean = line.trim().replace(/^#+/, '').replace(/^-+/, '').trim();
    clean = clean.replace(/\*/g, '').trim();
    if (clean.length > 3) {
      return clean.slice(0, maxLen) + (clean.length > maxLen ? '…' : '');
    }
  }
  return "Analysis result";
}

function toggleExtracted() {
  const box = document.getElementById('extractedTextBox');
  box.style.display = box.style.display === 'none' || !box.style.display ? 'block' : 'none';
}


async function checkEngineStatus() {
  try {
    const res = await fetch('/health');
    if (!res.ok) throw new Error('Backend connection not OK');
    const data = await res.json();
    
    ollamaAvailable = data.ollama_available;
    selectedModel = data.model || 'gemma4:e2b';
    visionSupported = data.vision_supported;

    if (ollamaAvailable) {
      document.getElementById('ollamaStatusDot').className = 'status-dot online';
      document.getElementById('ollamaStatusText').textContent = 'API Engine online';
      document.getElementById('ollamaModelText').textContent = `Model: ${selectedModel}${visionSupported ? ' (vision)' : ''}`;

      document.getElementById('topbarStatusDot').className = 'status-dot online';
      document.getElementById('topbarStatusText').textContent = 'API Engine online';
    } else {
      throw new Error('Gemini API offline on server');
    }
  } catch (err) {
    ollamaAvailable = false;
    document.getElementById('ollamaStatusDot').className = 'status-dot offline';
    document.getElementById('ollamaStatusText').textContent = 'Cannot reach API';
    document.getElementById('ollamaModelText').textContent = 'Ensure GEMINI_API_KEY is set';

    document.getElementById('topbarStatusDot').className = 'status-dot offline';
    document.getElementById('topbarStatusText').textContent = 'API Engine offline';
  }
}


async function loadHistory() {
  try {
    const res = await fetch('/history');
    if (res.status === 401) {
      window.location.href = '/auth';
      return;
    }
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();
    currentHistory = data.history || [];
    renderHistory();
  } catch (err) {
    currentHistory = [];
    renderHistory();
    console.error('History error:', err);
  }
}

function renderHistory() {
  const list = document.getElementById('historyList');
  const empty = document.getElementById('historyEmpty');

  if (!currentHistory.length) {
    list.innerHTML = '';
    list.appendChild(empty);
    return;
  }

  list.innerHTML = currentHistory.map(item => {
    const dateStr = (item.timestamp_display || '').split(' ')[1] || '';
    const dayStr = (item.timestamp_display || '').split(' ')[0] || '';
    const activeClass = item.id === activeHistoryId ? ' active' : '';
    return `
      <div class="history-item${activeClass}" data-id="${item.id}" onclick="openHistoryItem('${item.id}')">
        <div class="h-title">${escapeHtml(item.title || 'Analysis result')}</div>
        <div class="h-meta">
          <span>${escapeHtml(dayStr)}</span>
          <span>${escapeHtml(dateStr)}</span>
        </div>
        <button class="h-del" title="Delete" onclick="event.stopPropagation(); deleteHistoryItem('${item.id}')">✕</button>
      </div>`;
  }).join('');
}

function openHistoryItem(id) {
  const item = currentHistory.find(h => h.id === id);
  if (!item) return;
  activeHistoryId = id;
  renderHistory();
  displayResult(item.analysis, item.extracted_text, item.timestamp_display, item.source_name);
  document.getElementById('topbarTitle').innerHTML =
    `Viewing report <span class="dim">/ ${escapeHtml(item.source_name || 'Pasted text')}</span>`;
}

async function deleteHistoryItem(id) {
  try {
    const res = await fetch(`/history/${id}`, { method: 'DELETE' });
    if (res.status === 401) {
      window.location.href = '/auth';
      return;
    }
    if (!res.ok) throw new Error('Failed to delete history item');
    const data = await res.json();
    if (data.success) {
      currentHistory = currentHistory.filter(h => h.id !== id);
      if (activeHistoryId === id) startNewAnalysis();
      else renderHistory();
    } else {
      throw new Error(data.error || 'Server failed to delete');
    }
  } catch (err) {
    alert(`Could not delete item: ${err.message}`);
  }
}

function startNewAnalysis() {
  activeHistoryId = null;
  renderHistory();
  selectedFile = null;
  renderFileChip();
  const questionInput = document.getElementById('questionInput');
  if (questionInput) questionInput.value = '';
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('chatPanel').style.display = 'none';
  document.getElementById('uploadPanel').style.display = 'block';
  document.getElementById('introBlock').style.display = 'block';
  hideError();
  document.getElementById('topbarTitle').innerHTML = 'New analysis <span class="dim">/ no report loaded</span>';
  
  activeReportText = "";
  activeAnalysis = "";
  chatHistory = [];
}

async function submitAnalysis() {
  hideError();
  const qInput = document.getElementById('questionInput');
  const question = qInput ? qInput.value.trim() : '';

  document.getElementById('analyzeBtn').disabled = true;
  document.getElementById('uploadPanel').style.display = 'none';
  document.getElementById('introBlock').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('loadingPanel').style.display = 'block';

  let msgIndex = 0;
  document.getElementById('loadingText').textContent = LOADING_MESSAGES[0];
  const msgInterval = setInterval(() => {
    msgIndex = (msgIndex + 1) % LOADING_MESSAGES.length;
    document.getElementById('loadingText').textContent = LOADING_MESSAGES[msgIndex];
  }, 2200);

  try {
    const formData = new FormData();
    formData.append('question', question);

    if (!selectedFile) throw new Error('Select a file before analyzing.');
    formData.append('file', selectedFile);

    document.getElementById('loadingText').textContent = 'Analyzing report with AI model…';

    const response = await fetch('/analyze', {
      method: 'POST',
      body: formData
    });

    if (response.status === 401) {
      window.location.href = '/auth';
      return;
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Server error: ${response.statusText}`);
    }

    
    document.getElementById('analysisOutput').innerHTML = ''; 
    let extText = "";
    let accumulatedInterpretation = "";
    let finalMetadata = null;

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    function processAnalyzeLine(lineText) {
      if (!lineText.trim()) return;
      try {
        const obj = JSON.parse(lineText);
        if (obj.event === "extracted_text") {
          extText = obj.text;
          document.getElementById('extractedTextBox').textContent = extText || '(no text extracted)';
        } else if (obj.event === "token") {
          accumulatedInterpretation += obj.text;
        } else if (obj.event === "error") {
          throw new Error(obj.error);
        } else if (obj.event === "done") {
          finalMetadata = obj;
        }
      } catch (e) {
        console.error("Stream parse error:", e);
        throw e;
      }
    }

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        if (buffer.trim()) {
          processAnalyzeLine(buffer.trim());
        }
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        processAnalyzeLine(line);
      }
    }

    if (!finalMetadata) {
      throw new Error("Analysis stream completed without metadata.");
    }

    clearInterval(msgInterval);
    document.getElementById('loadingPanel').style.display = 'none';
    document.getElementById('resultPanel').style.display = 'block';
    document.getElementById('resultPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });

    const sourceName = selectedFile ? selectedFile.name : 'Report';
    const newId = finalMetadata.history_id;
    const timestampDisp = finalMetadata.timestamp;
    const finalAnalysis = finalMetadata.analysis;

    document.getElementById('topbarTitle').innerHTML =
      `Viewing report <span class="dim">/ ${escapeHtml(sourceName)}</span>`;
    document.getElementById('resultSrc').textContent = sourceName || 'Pasted text';
    document.getElementById('resultTime').textContent = timestampDisp || '';
    handleDisplayAndParsing(finalAnalysis);

    const historyEntry = {
      id: newId,
      title: summarizeForHistory(finalAnalysis),
      source_name: sourceName,
      question: question,
      analysis: finalAnalysis,
      extracted_text: extText,
      timestamp_display: timestampDisp
    };

    currentHistory.unshift(historyEntry);
    if (currentHistory.length > 50) {
      currentHistory = currentHistory.slice(0, 50);
    }

    updateAnalyzeButtonState();

    activeHistoryId = newId;
    renderHistory();
    initChat(extText, finalAnalysis);

  } catch (err) {
    clearInterval(msgInterval);
    document.getElementById('loadingPanel').style.display = 'none';
    updateAnalyzeButtonState();
    document.getElementById('uploadPanel').style.display = 'block';
    showError(err.message);
  }
}


function displayResult(analysis, extractedText, timestamp, sourceName) {
  handleDisplayAndParsing(analysis);
  document.getElementById('extractedTextBox').textContent = extractedText || '(no text extracted)';
  document.getElementById('extractedTextBox').style.display = 'none';
  document.getElementById('resultSrc').textContent = sourceName || 'Pasted text';
  document.getElementById('resultTime').textContent = timestamp || '';
  document.getElementById('resultPanel').style.display = 'block';
  document.getElementById('resultPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });

  
  initChat(extractedText, analysis);
}



function initChat(extractedText, analysis) {
  activeReportText = extractedText || "";
  activeAnalysis = analysis || "";
  chatHistory = [];
  
  const chatHistoryDiv = document.getElementById("chatHistory");
  chatHistoryDiv.innerHTML = `
    <div class="chat-message system">
      <div class="msg-sender">AI Patient Assistant</div>
      <div class="msg-content">Hello! I have loaded your report. How can I help you?</div>
    </div>
  `;
  
  
  document.getElementById("chatInput").value = "";
  document.getElementById("chatInput").disabled = false;
  document.getElementById("chatSendBtn").disabled = false;
  
  
  updateRAGStatus("RAG Retrieval Ready", "online");
  
  
  generateSmartSuggestions(activeReportText, activeAnalysis);
  
  
  document.getElementById("chatPanel").style.display = "block";
  
  
  const input = document.getElementById("chatInput");
  input.onkeydown = function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  };
}

function generateSmartSuggestions(text, analysis) {
  const content = ((text || "") + " " + (analysis || "")).toLowerCase();
  const suggestions = [];
  
  if (parsedParameters && parsedParameters.length > 0) {
    const abnormalParams = parsedParameters.filter(p => p.status.includes("high") || p.status.includes("low") || p.status.includes("abnormal"));
    abnormalParams.forEach(p => {
      const pName = p.name.trim();
      suggestions.push(`What does abnormal ${pName} mean?`);
      suggestions.push(`How can I normalize my ${pName} levels?`);
    });
  }
  
  if (content.includes("cholesterol") || content.includes("lipid") || content.includes("triglyceride") || content.includes("ldl") || content.includes("hdl")) {
    suggestions.push("How can I lower my cholesterol levels naturally?");
    suggestions.push("What foods should I avoid with high cholesterol?");
  }
  if (content.includes("glucose") || content.includes("sugar") || content.includes("hba1c") || content.includes("diabetes") || content.includes("diabetic")) {
    suggestions.push("What diet helps reduce blood sugar and HbA1c?");
    suggestions.push("How does physical activity affect glucose levels?");
  }
  if (content.includes("hemoglobin") || content.includes("iron") || content.includes("ferritin") || content.includes("anemia") || content.includes("rbc")) {
    suggestions.push("How can I raise my hemoglobin levels?");
    suggestions.push("What foods increase iron absorption?");
  }
  if (content.includes("liver") || content.includes("alt") || content.includes("ast") || content.includes("bilirubin") || content.includes("sgpt") || content.includes("sgot")) {
    suggestions.push("What changes improve liver enzyme levels?");
    suggestions.push("What substances/medications are toxic to the liver?");
  }
  if (content.includes("kidney") || content.includes("creatinine") || content.includes("urea") || content.includes("gfr") || content.includes("egfr") || content.includes("bun")) {
    suggestions.push("How do I protect my kidney function?");
    suggestions.push("What medications should I avoid with high creatinine?");
  }
  if (content.includes("thyroid") || content.includes("tsh") || content.includes("t3") || content.includes("t4")) {
    suggestions.push("How should I take thyroid medication correctly?");
    suggestions.push("What causes thyroid levels (TSH) to fluctuate?");
  }
  if (content.includes("vitamin d") || content.includes("vit d")) {
    suggestions.push("How long does it take to correct Vitamin D deficiency?");
    suggestions.push("What are the best dietary sources of Vitamin D?");
  }
  if (content.includes("vitamin b12") || content.includes("b12") || content.includes("cobalamin")) {
    suggestions.push("What are the best sources of Vitamin B12?");
    suggestions.push("How does metformin affect B12 levels?");
  }
  if (content.includes("uric acid") || content.includes("gout") || content.includes("urate")) {
    suggestions.push("What foods are high in purines (avoid for gout)?");
    suggestions.push("How does drinking water reduce uric acid?");
  }
  if (content.includes("blood pressure") || content.includes("bp") || content.includes("hypertension")) {
    suggestions.push("What is the DASH diet for blood pressure?");
    suggestions.push("How does sodium restriction lower BP?");
  }
  
  
  if (suggestions.length < 3) {
    if (!suggestions.includes("How do I interpret my lab report results?")) {
      suggestions.push("How do I interpret my lab report results?");
    }
    if (!suggestions.includes("What lifestyle changes support general health?")) {
      suggestions.push("What lifestyle changes support general health?");
    }
  }
  
  const finalSuggestions = suggestions.slice(0, 3);
  
  const container = document.getElementById("chatSuggestionsContainer");
  const chips = document.getElementById("chatSuggestions");
  
  if (finalSuggestions.length > 0) {
    chips.innerHTML = finalSuggestions.map(q => {
      
      const safeQ = q.replace(/'/g, "\\'");
      return `<button class="suggestion-chip" onclick="clickSuggestion('${escapeHtml(safeQ)}')">${escapeHtml(q)}</button>`;
    }).join("");
    container.style.display = "block";
  } else {
    container.style.display = "none";
  }
}

function clickSuggestion(text) {
  document.getElementById("chatInput").value = text;
  sendChatMessage();
}
function appendStreamingChatMessage(sender, role) {
  const chatHistoryDiv = document.getElementById("chatHistory");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${role}`;
  
  const senderDiv = document.createElement("div");
  senderDiv.className = "msg-sender";
  senderDiv.textContent = sender;
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "msg-content";
  contentDiv.innerHTML = "";
  
  msgDiv.appendChild(senderDiv);
  msgDiv.appendChild(contentDiv);
  chatHistoryDiv.appendChild(msgDiv);
  chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
  
  return contentDiv;
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const question = input.value.trim();
  if (!question) return;
  
  input.value = "";
  input.disabled = true;
  document.getElementById("chatSendBtn").disabled = true;
  
  // Hide suggestions container
  document.getElementById("chatSuggestionsContainer").style.display = "none";
  
  // Append user message to UI
  appendChatMessage("You", question, "user");
  
  const chatHistoryDiv = document.getElementById("chatHistory");
  chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
  
  // Show loading indicator
  updateRAGStatus("Querying retrieval engine...", "pulsing");
  showChatLoading();
  chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
  
  try {
    const payload = {
      question: question,
      report_text: activeReportText,
      analysis: activeAnalysis,
      history: chatHistory
    };
    
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (response.status === 401) {
      window.location.href = '/auth';
      return;
    }
    
    if (!response.ok) {
      throw new Error(`Server returned error: ${response.statusText}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    
    let accumulatedReply = "";
    let finalMetadata = null;
    let contentDiv = null;
    
    function processChatLine(lineText) {
      if (!lineText.trim()) return;
      try {
        const obj = JSON.parse(lineText);
        if (obj.event === "token") {
          accumulatedReply += obj.text;
        } else if (obj.event === "error") {
          throw new Error(obj.error);
        } else if (obj.event === "done") {
          finalMetadata = obj;
        }
      } catch (e) {
        console.error("Chat stream parse error:", e);
        throw e;
      }
    }
    
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        if (buffer.trim()) {
          processChatLine(buffer.trim());
        }
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        processChatLine(line);
      }
    }
    
    hideChatLoading();
    
    if (finalMetadata) {
      const reply = finalMetadata.response;
      appendChatMessage("AI Patient Assistant", reply, "assistant");
      
      const retrieved = finalMetadata.retrieved_guidelines || [];
      if (retrieved.length > 0) {
        const titles = retrieved.map(r => r.title.split(" (")[0]).join(", ");
        updateRAGStatus(`RAG Context: Retrieved guidelines for ${titles}`, "online");
      } else {
        updateRAGStatus("RAG Context: General clinical guidelines used", "online");
      }
      
      chatHistory.push({"role": "user", "content": question});
      chatHistory.push({"role": "assistant", "content": reply});
    } else {
      throw new Error("Chat stream completed without metadata.");
    }
    
  } catch (err) {
    hideChatLoading();
    updateRAGStatus("Retrieval failed", "offline");
    appendChatMessage("Error", `Sorry, I encountered an error: ${err.message}. Please check your server console and try again.`, "system");
  } finally {
    input.disabled = false;
    document.getElementById("chatSendBtn").disabled = false;
    input.focus();
    chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
  }
}
function appendChatMessage(sender, content, role) {
  const chatHistoryDiv = document.getElementById("chatHistory");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${role}`;
  
  const senderDiv = document.createElement("div");
  senderDiv.className = "msg-sender";
  senderDiv.textContent = sender;
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "msg-content";
  contentDiv.innerHTML = renderChatMessageMarkdown(content);
  
  msgDiv.appendChild(senderDiv);
  msgDiv.appendChild(contentDiv);
  chatHistoryDiv.appendChild(msgDiv);
  
  chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
}

function showChatLoading() {
  const chatHistoryDiv = document.getElementById("chatHistory");
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "chat-message assistant chat-loading-bubble";
  loadingDiv.id = "chatLoadingBubble";
  
  const senderDiv = document.createElement("div");
  senderDiv.className = "msg-sender";
  senderDiv.textContent = "AI Patient Assistant";
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "msg-content";
  contentDiv.innerHTML = `
    <span class="loading-text">
      Synthesizing guidance
      <span class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </span>
    </span>`;
    
  loadingDiv.appendChild(senderDiv);
  loadingDiv.appendChild(contentDiv);
  chatHistoryDiv.appendChild(loadingDiv);
}

function hideChatLoading() {
  const bubble = document.getElementById("chatLoadingBubble");
  if (bubble) {
    bubble.remove();
  }
}

function updateRAGStatus(text, statusClass) {
  const textSpan = document.getElementById("chatStatusText");
  const dotSpan = document.querySelector("#chatStatusBadge .status-dot");
  
  if (textSpan) textSpan.textContent = text;
  if (dotSpan) {
    dotSpan.className = `status-dot ${statusClass}`;
  }
}

function renderChatMessageMarkdown(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  
  // Headers
  html = html.replace(/^### (.*$)/gim, '<strong>$1</strong>');
  html = html.replace(/^## (.*$)/gim, '<strong>$1</strong>');
  html = html.replace(/^# (.*$)/gim, '<strong>$1</strong>');
  
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Bullet points
  html = html.replace(/^\s*-\s+(.*$)/gim, '• $1<br>');
  html = html.replace(/^\s*\*\s+(.*$)/gim, '• $1<br>');
  
  // Paragraphs / Newlines
  html = html.replace(/\n/g, '<br>');
  
  return html;
}


/* ==========================================================
   TRENDS TRACKER AND CHART.JS MAPPING
   ========================================================== */
let trendsChartInstance = null;
let historicalTrendsData = {};

function switchResultSubTab(subTab) {
  const reportBtn = document.getElementById("resultReportBtn");
  const trendsBtn = document.getElementById("resultTrendsBtn");
  const reportContainer = document.getElementById("reportContainer");
  const trendsContainer = document.getElementById("trendsContainer");
  
  if (!reportBtn || !trendsBtn || !reportContainer || !trendsContainer) return;
  
  if (subTab === 'report') {
    reportBtn.classList.add("active");
    trendsBtn.classList.remove("active");
    reportContainer.style.display = "block";
    trendsContainer.style.display = "none";
  } else if (subTab === 'trends') {
    trendsBtn.classList.add("active");
    reportBtn.classList.remove("active");
    reportContainer.style.display = "none";
    trendsContainer.style.display = "block";
    fetchAndRenderTrends();
  }
}

function fetchAndRenderTrends() {
  if (window.location.protocol === 'file:') {
    // Standalone mock trends data
    historicalTrendsData = {
      "Glucose": [
        {"date": "2026-06-01", "value": 94, "value_str": "94 mg/dL", "range": "70-99 mg/dL", "status": "normal"},
        {"date": "2026-07-01", "value": 112, "value_str": "112 mg/dL", "range": "70-99 mg/dL", "status": "high"},
        {"date": "2026-07-14", "value": 98, "value_str": "98 mg/dL", "range": "70-99 mg/dL", "status": "normal"}
      ],
      "Cholesterol": [
        {"date": "2026-06-01", "value": 178, "value_str": "178 mg/dL", "range": "< 200 mg/dL", "status": "normal"},
        {"date": "2026-07-01", "value": 224, "value_str": "224 mg/dL", "range": "< 200 mg/dL", "status": "high"},
        {"date": "2026-07-14", "value": 196, "value_str": "196 mg/dL", "range": "< 200 mg/dL", "status": "normal"}
      ],
      "HbA1c": [
        {"date": "2026-06-01", "value": 5.4, "value_str": "5.4%", "range": "4.0-5.6%", "status": "normal"},
        {"date": "2026-07-01", "value": 5.9, "value_str": "5.9%", "range": "4.0-5.6%", "status": "high"},
        {"date": "2026-07-14", "value": 5.5, "value_str": "5.5%", "range": "4.0-5.6%", "status": "normal"}
      ]
    };
    populateTrendSelect(historicalTrendsData);
    return;
  }
  
  fetch('/api/trends')
    .then(res => res.json())
    .then(data => {
      if (data.success && data.trends) {
        historicalTrendsData = data.trends;
        populateTrendSelect(data.trends);
      }
    })
    .catch(err => console.error("Error loading trends:", err));
}

function populateTrendSelect(trends) {
  const select = document.getElementById("trendParamSelect");
  if (!select) return;
  
  const currentVal = select.value;
  select.innerHTML = '<option value="">Select parameter...</option>';
  
  const keys = Object.keys(trends).sort();
  keys.forEach(key => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = key;
    select.appendChild(option);
  });
  
  if (currentVal && trends[currentVal]) {
    select.value = currentVal;
  } else if (keys.length > 0) {
    select.value = keys[0];
  }
  
  updateSelectedTrendChart();
}

function updateSelectedTrendChart() {
  const select = document.getElementById("trendParamSelect");
  const canvas = document.getElementById("trendsChart");
  if (!select || !canvas) return;
  
  const param = select.value;
  if (!param || !historicalTrendsData[param]) {
    if (trendsChartInstance) {
      trendsChartInstance.destroy();
      trendsChartInstance = null;
    }
    return;
  }
  
  const points = historicalTrendsData[param];
  const labels = points.map(p => p.date);
  const values = points.map(p => p.value);
  
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)';
  const textColor = isLight ? '#1e293b' : '#cbd5e1';
  const lineColor = isLight ? '#4f46e5' : '#0ea5e9';
  const pointColor = isLight ? '#3b82f6' : '#22d3ee';
  const pointBorderColor = isLight ? '#ffffff' : '#090d16';
  
  if (trendsChartInstance) {
    trendsChartInstance.destroy();
  }
  
  const ctx = canvas.getContext('2d');
  trendsChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: param,
        data: values,
        borderColor: lineColor,
        backgroundColor: isLight ? 'rgba(79, 70, 229, 0.05)' : 'rgba(14, 165, 233, 0.05)',
        borderWidth: 2.5,
        pointRadius: 6,
        pointHoverRadius: 8,
        pointBackgroundColor: points.map(p => {
          if (p.status.includes("high")) return '#f43f5e';
          if (p.status.includes("low")) return '#fbbf24';
          return pointColor;
        }),
        pointBorderColor: pointBorderColor,
        pointBorderWidth: 1.5,
        tension: 0.3,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const pt = points[context.dataIndex];
              return ` Value: ${pt.value_str} (${pt.status.toUpperCase()})`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: gridColor
          },
          ticks: {
            color: textColor,
            font: {
              size: 10,
              family: 'Inter'
            }
          }
        },
        y: {
          grid: {
            color: gridColor
          },
          ticks: {
            color: textColor,
            font: {
              size: 10,
              family: 'Inter'
            }
          }
        }
      }
    }
  });
}

