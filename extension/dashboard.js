const API_BASE_URL = "https://jangustavo.me/apis/promopulse";
const STORAGE_KEY = "radarConfig";

// ---------------------------------------------------------------------------
// Configurações de Áudio (Fallback para URLs externas para teste imediato)
// ---------------------------------------------------------------------------
const SOUND_SOURCES = {
  "classic.mp3": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
  "discreet.mp3": "https://actions.google.com/sounds/v1/notification/pop_ding.ogg",
  "urgent.mp3": "https://actions.google.com/sounds/v1/alarms/alarm_clock_short.ogg"
};

// ---------------------------------------------------------------------------
// Estado global
// ---------------------------------------------------------------------------
let allGroups = [];
let monitoringActive = false;
let lastAlertId = null;
let audioContextPrimed = false; // Controle de permissão de áudio

const state = {
  selectedGroupIds: new Set(),
  broad_categories: new Set(["celulares"]),
  mid_categories: new Set(),
  current_tab: "broad",
  active_levels: new Set(["broad"]),
  mid_selected_brands: new Set(),
  specific_models: [],
  mid_brands: [],
  broad_keywords: [],
  price_max: null,
  sound_enabled: true,
  sound_selected: "classic.mp3",
  sound_volume: 0.8,
  smart_alert_enabled: true, // Sniper Mode
  theme: "dark",
};

function applyThemeUI() {
  if (state.theme === "light") {
    document.body.classList.add("light-theme");
  } else {
    document.body.classList.remove("light-theme");
  }
}

const BRANDS_MAP = {
  celulares: ["Apple", "Samsung", "Xiaomi", "Motorola", "Poco", "Realme", "Asus"],
  tvs: ["Samsung", "LG", "TCL", "Philips", "AOC", "Philco"],
  audio: ["JBL", "Sony", "Edifier", "Apple", "Samsung", "Sennheiser", "QCY"],
  higiene: ["Dove", "L'Oréal", "Nivea", "Rexona", "Gillette", "Pampers"],
  informatica: ["Dell", "Lenovo", "Acer", "Asus", "Apple", "Avell", "Logitech"],
  casa: ["Mondial", "Electrolux", "Philco", "Oster", "Midea", "Arno"],
  moda: ["Nike", "Adidas", "Puma", "Hering", "Lupo", "Vans", "Reserva", "Olimpikus"],
  games: ["PlayStation", "Xbox", "Nintendo", "Sony", "Microsoft", "Asus", "Gigabyte"],
  esportes: ["Nike", "Adidas", "Puma", "Under Armour", "Asics", "Mizuno", "Penalty"],
};

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------
function storageSet(data) {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      chrome.storage.local.set({ [STORAGE_KEY]: data }, resolve);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      resolve();
    }
  });
}

function storageGet() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      chrome.storage.local.get([STORAGE_KEY], (result) => resolve(result?.[STORAGE_KEY] || {}));
    } else {
      try {
        resolve(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
      } catch {
        resolve({});
      }
    }
  });
}

function clearAuthSession() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      chrome.storage.local.remove(["telegramAuth"], resolve);
    } else {
      localStorage.removeItem("telegramAuth");
      resolve();
    }
  });
}

async function saveState() {
  await storageSet({
    active_levels: [...state.active_levels],
    broad_categories: [...state.broad_categories],
    mid_categories: [...state.mid_categories],
    mid_selected_brands: [...state.mid_selected_brands],
    specific_models: state.specific_models,
    mid_brands: state.mid_brands,
    broad_keywords: state.broad_keywords,
    price_max: state.price_max,
    selectedGroupIds: [...state.selectedGroupIds],
    min_score: state.min_score || 2,
    require_offer_match: state.require_offer_match ?? true,
    relaxed_mode: state.relaxed_mode ?? false,
    lastAlertId: lastAlertId,
    has_configured_groups: state.has_configured_groups ?? false,
    sound_enabled: state.sound_enabled,
    sound_selected: state.sound_selected,
    sound_volume: state.sound_volume,
    smart_alert_enabled: state.smart_alert_enabled,
    theme: state.theme,
  });
}

async function loadState() {
  const saved = await storageGet();
  
  if (saved.active_levels) state.active_levels = new Set(saved.active_levels);
  if (saved.broad_categories) state.broad_categories = new Set(saved.broad_categories);
  if (saved.mid_categories) state.mid_categories = new Set(saved.mid_categories);
  if (saved.mid_selected_brands) state.mid_selected_brands = new Set(saved.mid_selected_brands);

  if (saved.specific_models) state.specific_models = saved.specific_models;
  if (saved.mid_brands) state.mid_brands = saved.mid_brands;
  if (saved.broad_keywords) state.broad_keywords = saved.broad_keywords;
  if (saved.price_max) state.price_max = saved.price_max;
  if (saved.selectedGroupIds) state.selectedGroupIds = new Set(saved.selectedGroupIds);
  
  state.min_score = saved.min_score || 2;
  state.require_offer_match = saved.require_offer_match ?? true;
  state.relaxed_mode = saved.relaxed_mode ?? false;
  state.has_configured_groups = saved.has_configured_groups ?? false;

  state.sound_enabled = saved.sound_enabled ?? true;
  state.sound_selected = saved.sound_selected || "classic.mp3";
  state.sound_volume = saved.sound_volume ?? 0.8;
  state.smart_alert_enabled = saved.smart_alert_enabled ?? true;
  state.theme = saved.theme || "dark";

  if (saved.lastAlertId) lastAlertId = saved.lastAlertId;

  const specInput = document.getElementById("specificModelsInput");
  if (specInput) specInput.value = (state.specific_models || []).join("\n");

  const midInput = document.getElementById("midBrandsInput");
  if (midInput) midInput.value = (state.mid_brands || []).join(", ");

  const broadInput = document.getElementById("broadKeywordsInput");
  if (broadInput) broadInput.value = (state.broad_keywords || []).join(", ");

  const maxPriceInput = document.getElementById("priceMaxInput");
  if (maxPriceInput) maxPriceInput.value = state.price_max !== null ? state.price_max : "";

  updateSoundUI();
  applyThemeUI();
}

function updateSoundUI() {
  const btn = document.getElementById("toggleSoundBtn");
  if (btn) {
    btn.innerHTML = state.sound_enabled ? "🔊" : "🔇";
    btn.classList.toggle("active", state.sound_enabled);
  }
  
  const select = document.getElementById("soundSelect");
  if (select) select.value = state.sound_selected;
  
  const volume = document.getElementById("volumeRange");
  if (volume) volume.value = state.sound_volume;

  const smartToggle = document.getElementById("smartAlertToggle");
  if (smartToggle) smartToggle.checked = state.smart_alert_enabled;
}

/**
 * Toca o som de alerta.
 * @param {string} forcedSound - Nome do arquivo para forçar (ex: "urgent.mp3")
 */
function playAlertSound(forcedSound = null) {
  if (!state.sound_enabled) return;
  
  try {
    const soundFile = forcedSound || state.sound_selected;
    const localPath = `assets/sounds/${soundFile}`;
    const fallbackUrl = SOUND_SOURCES[soundFile];
    
    const audioUrl = (typeof chrome !== "undefined" && chrome.runtime?.getURL) 
      ? chrome.runtime.getURL(localPath) 
      : fallbackUrl;

    const audio = new Audio(audioUrl);
    audio.volume = state.sound_volume;
    
    const playPromise = audio.play();
    
    if (playPromise !== undefined) {
      playPromise.catch(err => {
        if (audioUrl.startsWith('chrome-extension')) {
          console.log("[Audio] Usando fallback CDN para " + soundFile);
          const retryAudio = new Audio(fallbackUrl);
          retryAudio.volume = state.sound_volume;
          retryAudio.play().catch(e => console.warn("Autoplay bloqueado:", e));
        }
      });
    }
  } catch (e) {
    console.error("Erro no motor de áudio:", e);
  }
}

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeText(value) {
  return String(value ?? "").trim().toLowerCase();
}

function openLogin() {
  if (typeof chrome !== "undefined" && chrome.runtime?.getURL) {
    window.location.href = chrome.runtime.getURL("login.html");
  } else {
    window.location.href = "login.html";
  }
}

// ---------------------------------------------------------------------------
// Renderização
// ---------------------------------------------------------------------------
function renderGroups() {
  const node = document.getElementById("groups");
  if (!node) return;
  const showFiltered = document.getElementById("showFilteredToggle")?.checked;

  let visible = allGroups.filter((g) => {
    if (!showFiltered && g.auto_filtered) return false;
    return true;
  });

  if (visible.length === 0) {
    node.innerHTML = '<div class="empty-state">Nenhum grupo encontrado.</div>';
    return;
  }

  const totalFiltered = allGroups.filter((g) => g.auto_filtered).length;
  const banner =
      totalFiltered > 0
        ? `<div class="filter-banner">
            <div class="filter-banner-content">
              <div class="filter-icon">🛡️</div>
              <div class="filter-text">
                <span class="filter-title"><strong>${totalFiltered}</strong> grupos bloqueados</span>
                <span class="filter-desc">Filtro anti-spam/crypto ativado</span>
              </div>
            </div>
            <label class="show-filtered-label">
              <input type="checkbox" id="showFilteredToggle" ${showFiltered ? "checked" : ""} />
              <span class="custom-checkbox"></span>
              Mostrar grupos ocultos
            </label>
          </div>`
        : "";

  let html = banner;
  for (const group of visible) {
    const isSelected = state.selectedGroupIds.has(group.id);
    const filtered = group.auto_filtered;
    html += `
      <div class="group-item ${filtered ? "group-filtered" : ""}">
        <div class="group-info">
          <div class="group-avatar ${filtered ? "avatar-filtered" : ""}">
            ${filtered ? "🚫" : escapeHtml(group.title.charAt(0).toUpperCase())}
          </div>
          <div>
            ${
              group.link
                ? `<a href="${group.link}" target="_blank" class="group-name link">
                     ${escapeHtml(group.title)}
                   </a>`
                : `<span class="group-name">
                     ${escapeHtml(group.title)}
                   </span>`
            }            ${filtered ? '<span class="filter-badge">auto-filtrado</span>' : ""}
          </div>
        </div>
        <label class="switch ${filtered ? "switch-disabled" : ""}">
          <input type="checkbox"
            ${isSelected && !filtered ? "checked" : ""}
            ${filtered ? "disabled" : ""}
            data-group-id="${group.id}"
            aria-label="Selecionar ${escapeHtml(group.title)}"
          />
          <span class="slider"></span>
        </label>
      </div>`;
  }

  node.innerHTML = html;

  const showToggle = document.getElementById("showFilteredToggle");
  if (showToggle) {
    showToggle.addEventListener("change", renderGroups);
  }

  node.querySelectorAll("input[data-group-id]").forEach((checkbox) => {
    checkbox.addEventListener("change", (e) => {
      const id = parseInt(e.target.getAttribute("data-group-id"));
      if (e.target.checked) {
        state.selectedGroupIds.add(id);
      } else {
        state.selectedGroupIds.delete(id);
      }
      state.has_configured_groups = true;
      saveState();
    });
  });
}

async function testOfferText() {
  const text = document.getElementById("offerTestInput").value.trim();
  const resultNode = document.getElementById("offerTestResult");

  if (!text) {
    resultNode.textContent = "";
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/offers/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();

    const icon = data.would_alert ? "✅" : "❌";
    const categories = data.offer_categories?.join(", ") || "nenhuma";
    const price = data.extracted_price ? `R$ ${data.extracted_price.toLocaleString("pt-BR")}` : "—";

    resultNode.innerHTML = `
      <span class="${data.would_alert ? "test-pass" : "test-fail"}">
        ${icon} ${data.would_alert ? "Seria capturado" : "Não seria capturado"}
      </span>
      <span class="test-meta">
        Score: ${data.offer_score}/5 · Categorias: ${categories} · Preço: ${price}
      </span>`;
  } catch {
    resultNode.textContent = "Erro ao conectar com a API.";
  }
}

async function pushConfigToApi() {
  try {
    const body = {
      active_levels: [...state.active_levels],
      broad_categories: [...state.broad_categories],
      mid_categories: [...state.mid_categories],
      specific_models: state.specific_models,
      mid_brands: [...state.mid_selected_brands, ...state.mid_brands],
      broad_keywords: state.broad_keywords,
      price_max: state.price_max,
      min_score: state.min_score || 2,
      require_offer_match: state.require_offer_match ?? true,
      relaxed_mode: state.relaxed_mode ?? false,
    };

    await fetch(`${API_BASE_URL}/watch/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {}
}

function collectLevelInputs() {
  state.broad_keywords = (document.getElementById("broadKeywordsInput")?.value || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  state.mid_brands = (document.getElementById("midBrandsInput")?.value || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  state.specific_models = (document.getElementById("specificModelsInput")?.value || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

  const priceRaw = document.getElementById("priceMaxInput")?.value.replace(",", ".");
  state.price_max = priceRaw ? parseFloat(priceRaw) : null;
}

async function toggleScanner() {
  const btn = document.getElementById("startScannerBtn");

  if (monitoringActive) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Parando...';
    try {
      await fetch(`${API_BASE_URL}/watch/stop`, { method: "POST" });
    } catch {}
    monitoringActive = false;
    setScannerState(false);
    btn.disabled = false;
    return;
  }

  collectLevelInputs();
  await saveState();
  await pushConfigToApi();

  const groupIds = [...state.selectedGroupIds];
  if (groupIds.length === 0) {
    showToast("Selecione ao menos um grupo para monitorar.", "warning");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Iniciando...';

  try {
    const res = await fetch(`${API_BASE_URL}/watch/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_ids: groupIds }),
    });
    if (!res.ok) throw new Error();
    monitoringActive = true;
    setScannerState(true);
    
    // PRIME O ÁUDIO
    audioContextPrimed = true;
  } catch {
    showToast("Erro ao iniciar monitoramento. API está rodando?", "error");
  } finally {
    btn.disabled = false;
  }
}

function setScannerState(active) {
  const btn = document.getElementById("startScannerBtn");
  if (!btn) return;
  if (active) {
    btn.classList.add("running");
    btn.style.background = "var(--success)";
    btn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
      Monitorando — Clique para parar`;
  } else {
    btn.classList.remove("running");
    btn.style.background = "var(--primary)";
    btn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>
      Iniciar monitoramento`;
  }
}

let alertsPollingInterval = null;

function startAlertsPolling() {
  clearInterval(alertsPollingInterval);
  alertsPollingInterval = setInterval(loadAlerts, 10_000);
}

function stopAlertsPolling() {
  clearInterval(alertsPollingInterval);
}

async function loadAlerts() {
  const node = document.getElementById("alertsList");
  if (!node) return;

  try {
    const q = document.getElementById("alertsSearchInput")?.value.trim() || "";
    const minPrice = document.getElementById("alertsMinPriceInput")?.value || "";
    const maxPrice = document.getElementById("alertsMaxPriceInput")?.value || "";

    const params = new URLSearchParams({ limit: 30 });
    if (q) params.append("q", q);
    if (minPrice) params.append("min_price", minPrice);
    if (maxPrice) params.append("max_price", maxPrice);

    const res = await fetch(`${API_BASE_URL}/alerts?${params.toString()}`);
    const data = await res.json();
    const rawAlerts = Array.isArray(data.alerts) ? data.alerts : [];

    if (rawAlerts.length === 0) {
      node.innerHTML = '<div class="empty-state">Nenhum alerta ainda.</div>';
      return;
    }

    const seenIds = new Set();
    const alerts = rawAlerts.filter(a => {
      const id = `${a.group_id}_${a.message_id}`;
      if (seenIds.has(id)) return false;
      seenIds.add(id);
      return true;
    });

    const sorted = [...alerts].reverse();
    const latest = sorted[0];
    if (latest && latest.message_id !== lastAlertId) {
      notify(latest);
      lastAlertId = latest.message_id;
      saveState();
    }

    node.innerHTML = sorted
      .map((a) => {
        const cats = (a.offer_categories || []).join(" · ");
        const price = a.extracted_price
          ? `R$ ${Number(a.extracted_price).toLocaleString("pt-BR")}`
          : "";
        
        // --- Sniper Mode Visual ---
        let isCritical = false;
        if (state.smart_alert_enabled && state.price_max && a.extracted_price) {
            if (a.extracted_price <= (state.price_max * 0.6)) isCritical = true;
        }

        // --- Imagem do Produto ---
        const imageHtml = a.image_url
          ? `<div class="alert-image-container">
               <img src="${API_BASE_URL}/media/${a.image_url}" class="alert-image" alt="Imagem do Alerta" loading="lazy" />
             </div>`
          : "";

        // --- Botão de Ação e Histórico ---
        const chartBtnHtml = a.extracted_price
          ? `<button class="btn-alert-chart" data-message-id="${a.message_id}">📈 Histórico</button>`
          : "";

        const actionHtml = (a.link || a.extracted_price)
          ? `<div class="alert-actions">
               ${chartBtnHtml}
               ${a.link ? `<a href="${a.link}" target="_blank" class="btn-alert-link">Ir para a Oferta ➔</a>` : ""}
             </div>`
          : "";

        return `
        <div class="alert-item ${isCritical ? 'critical' : ''}">
          <div class="alert-header">
            <span class="alert-group">${escapeHtml(a.group_title || a.group_id)}</span>
            ${price ? `<span class="alert-price">${price}</span>` : ""}
          </div>
          ${imageHtml}
          <p class="alert-text">${escapeHtml((a.message || "").slice(0, 200))}</p>
          <div class="alert-meta">
            <span>Score ${a.offer_score}/5</span>
            ${cats ? `<span>${cats}</span>` : ""}
            ${a.timestamp ? `<span>${new Date(a.timestamp).toLocaleTimeString("pt-BR")}</span>` : ""}
          </div>
          <div id="chart-container-${a.message_id}" class="alert-chart-container" style="display: none;"></div>
          ${actionHtml}
        </div>`;
      })
      .join("");
  } catch {}
}

function showToast(msg, type = "info") {
  const existing = document.getElementById("toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "toast";
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

async function loadUser() {
  const userNode = document.getElementById("user");
  try {
    const res = await fetch(`${API_BASE_URL}/me`);
    if (res.status === 401) {
      await clearAuthSession();
      openLogin();
      return false; 
    }

    const data = await res.json();
    if (data.logged || data.first_name || data.username) {
      userNode.innerHTML = `
        <div class="user-badge">
          <div class="status-dot online"></div>
          <span>${data.first_name || data.username || "Usuário"}</span>
        </div>`;
      return true;
    } else {
      await clearAuthSession();
      openLogin();
      return false;
    }
  } catch {
    if (userNode) userNode.innerHTML = '<span class="status-text error">API Offline</span>';
    return true; 
  }
}

async function logout() {
  const btn = document.getElementById("logoutBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Saindo..."; }
  try { await fetch(`${API_BASE_URL}/logout`, { method: "POST" }); } catch {}
  await clearAuthSession();
  openLogin();
}

async function loadGroups() {
  const node = document.getElementById("groups");
  if (!node) return;
  node.innerHTML = '<div class="loading-spinner"><div class="spinner"></div> Carregando grupos...</div>';
  try {
    const res = await fetch(`${API_BASE_URL}/groups`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    allGroups = Array.isArray(data.groups) ? data.groups : [];

    if (!state.has_configured_groups) {
      allGroups.forEach((g) => {
        if (!g.auto_filtered && !state.selectedGroupIds.has(g.id)) {
          state.selectedGroupIds.add(g.id);
        }
      });
    }

    renderGroups();
  } catch {
    node.innerHTML = '<div class="error-state">Falha ao conectar com a API.</div>';
  }
}

function renderMidBrands() {
  const container = document.getElementById("dynamicBrandSelect");
  if (!container) return;

  let availableBrands = new Set();
  if (state.mid_categories && state.mid_categories.size > 0) {
    state.mid_categories.forEach(cat => {
      if (BRANDS_MAP[cat]) {
        BRANDS_MAP[cat].forEach(b => availableBrands.add(b));
      }
    });
  }

  if (availableBrands.size === 0) {
    container.innerHTML = '<div class="empty-state" style="width:100%; padding:10px;">Selecione uma categoria acima para ver as marcas.</div>';
    return;
  }

  const sortedBrands = Array.from(availableBrands).sort();
  container.innerHTML = "";
  
  sortedBrands.forEach(brand => {
    const btn = document.createElement("button");
    btn.className = `brand-pill ${state.mid_selected_brands.has(brand) ? "active" : ""}`;
    btn.textContent = brand;
    btn.addEventListener("click", async () => {
      if (state.mid_selected_brands.has(brand)) {
        state.mid_selected_brands.delete(brand);
      } else {
        state.mid_selected_brands.add(brand);
      }
      btn.classList.toggle("active");
      await saveState();
      await pushConfigToApi();
    });
    container.appendChild(btn);
  });
}

function bindEvents() {
  document.getElementById("alertsList")?.addEventListener("click", async (e) => {
    const chartBtn = e.target.closest(".btn-alert-chart");
    if (chartBtn) {
      const msgId = chartBtn.dataset.messageId;
      await togglePriceChart(msgId);
    }
  });

  document.getElementById("themeToggleBtn")?.addEventListener("click", async () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    applyThemeUI();
    await saveState();
  });

  ["alertsSearchInput", "alertsMinPriceInput", "alertsMaxPriceInput"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", () => {
      loadAlerts();
    });
  });

  document.querySelectorAll(".level-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.current_tab = btn.dataset.level;
      renderLevelPanel();
    });
  });

  document.querySelectorAll(".btn-activate-level").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const lvl = btn.dataset.level;
      if (state.active_levels.has(lvl)) state.active_levels.delete(lvl);
      else state.active_levels.add(lvl);
      renderLevelPanel();
      await saveState();
      await pushConfigToApi();
    });
  });

  ["broadKeywordsInput", "midBrandsInput", "specificModelsInput", "priceMaxInput"].forEach((id) => {
    document.getElementById(id)?.addEventListener("blur", async () => {
      collectLevelInputs();
      await saveState();
    });
  });

  document.getElementById("startScannerBtn")?.addEventListener("click", () => {
    toggleScanner().then(() => {
      if (monitoringActive) {
        startAlertsPolling();
        loadAlerts();
      } else {
        stopAlertsPolling();
      }
    });
  });

  document.getElementById("logoutBtn")?.addEventListener("click", logout);

  const testInput = document.getElementById("offerTestInput");
  let debounce;
  testInput?.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(testOfferText, 600);
  });

  document.getElementById("clearAlertsBtn")?.addEventListener("click", async () => {
    await fetch(`${API_BASE_URL}/alerts`, { method: "DELETE" });
    loadAlerts();
  });

  // --- CONTROLES DE SOM ---
  document.getElementById("toggleSoundBtn")?.addEventListener("click", async () => {
    state.sound_enabled = !state.sound_enabled;
    updateSoundUI();
    audioContextPrimed = true;
    if (state.sound_enabled) playAlertSound(); 
    await saveState();
  });

  document.getElementById("soundSelect")?.addEventListener("change", async (e) => {
    state.sound_selected = e.target.value;
    audioContextPrimed = true; 
    playAlertSound(); 
    await saveState();
  });

  document.getElementById("volumeRange")?.addEventListener("input", (e) => {
    state.sound_volume = parseFloat(e.target.value);
  });
  document.getElementById("volumeRange")?.addEventListener("change", async () => {
    audioContextPrimed = true; 
    playAlertSound(); 
    await saveState();
  });

  document.getElementById("testSoundBtn")?.addEventListener("click", () => {
    audioContextPrimed = true;
    playAlertSound();
  });

  // --- SNIPER MODE TOGGLE ---
  document.getElementById("smartAlertToggle")?.addEventListener("change", async (e) => {
      state.smart_alert_enabled = e.target.checked;
      await saveState();
      loadAlerts(); // Re-renderiza para aplicar/remover estilos
  });

  document.querySelectorAll(".cat-card").forEach((card) => {
    card.addEventListener("click", async () => {
      const catName = card.dataset.category;
      const panel = card.dataset.panel;

      if (panel === "broad") {
        if (state.broad_categories.has(catName)) state.broad_categories.delete(catName);
        else state.broad_categories.add(catName);
      } else if (panel === "mid") {
        if (state.mid_categories.has(catName)) state.mid_categories.delete(catName);
        else state.mid_categories.add(catName);
        renderMidBrands(); 
      }

      card.classList.toggle("active", panel === "broad" ? state.broad_categories.has(catName) : state.mid_categories.has(catName));
      await saveState();
      await pushConfigToApi();
    });
  });
}

const notificationLinks = new Map();

if (typeof chrome !== "undefined" && chrome.notifications) {
  chrome.notifications.onButtonClicked.addListener((notifId, btnIdx) => {
    const link = notificationLinks.get(notifId);
    if (link && btnIdx === 0) {
      if (typeof chrome !== "undefined" && chrome.tabs) {
        chrome.tabs.create({ url: link });
      } else {
        window.open(link, "_blank");
      }
    }
  });
}

function notify(alert) {
  if (typeof chrome !== "undefined" && chrome.notifications) {
    const options = {
      type: "basic",
      iconUrl: chrome.runtime.getURL("telegram_logo_128.png"),
      title: `🚨 ${alert.group_title || "Nova Oferta!"}`,
      message: alert.clean_title || alert.message || "",
      contextMessage: alert.extracted_price
        ? `R$ ${Number(alert.extracted_price).toLocaleString("pt-BR")}`
        : "Oferta detectada",
      priority: 2,
    };

    if (alert.image_url) {
      options.type = "image";
      options.imageUrl = `${API_BASE_URL}/media/${alert.image_url}`;
    }

    const notificationId = `alert_${alert.group_id}_${alert.message_id}`;

    if (alert.link) {
      options.buttons = [{ title: "Ir para a Oferta ➔" }];
      notificationLinks.set(notificationId, alert.link);
    }

    chrome.notifications.create(notificationId, options);
  } else {
    if (Notification.permission === "granted") {
      const n = new Notification(`🚨 ${alert.group_title}`, {
        body: (alert.clean_title || alert.message || "").slice(0, 120),
        icon: "telegram_logo_128.png"
      });

      if (alert.link) {
        n.onclick = () => {
          window.open(alert.link, "_blank");
        };
      }
    }
  }

  // LÓGICA DE SOM INTELIGENTE
  let soundToPlay = null;
  if (state.smart_alert_enabled && state.price_max && alert.extracted_price) {
    const threshold = state.price_max * 0.6;
    if (alert.extracted_price <= threshold) {
      soundToPlay = "urgent.mp3";
    }
  }

  playAlertSound(soundToPlay);
}

function renderLevelPanel() {
  document.querySelectorAll(".level-btn").forEach((btn) => {
    const lvl = btn.dataset.level;
    btn.classList.toggle("active", state.current_tab === lvl);
  });

  const panelBroad = document.getElementById("panel-broad");
  const panelMid = document.getElementById("panel-mid");
  const panelSpecific = document.getElementById("panel-specific");

  if (panelBroad) panelBroad.style.display = state.current_tab === "broad" ? "block" : "none";
  if (panelMid) panelMid.style.display = state.current_tab === "mid" ? "block" : "none";
  if (panelSpecific) panelSpecific.style.display = state.current_tab === "specific" ? "block" : "none";

  document.querySelectorAll(".btn-activate-level").forEach((btn) => {
    const lvl = btn.dataset.level;
    if (state.active_levels.has(lvl)) {
      btn.classList.add("running");
      btn.innerHTML = "🟢 Radar Ativado";
    } else {
      btn.classList.remove("running");
      btn.innerHTML = "⚪ Pausado";
    }
  });

  document.querySelectorAll(`.cat-card[data-panel="broad"]`).forEach(c => {
    c.classList.toggle("active", state.broad_categories.has(c.dataset.category));
  });
  document.querySelectorAll(`.cat-card[data-panel="mid"]`).forEach(c => {
    c.classList.toggle("active", state.mid_categories.has(c.dataset.category));
  });
}

async function init() {
  const auth = await new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      chrome.storage.local.get(["telegramAuth"], (res) => resolve(res.telegramAuth));
    } else {
      resolve(JSON.parse(localStorage.getItem("telegramAuth")));
    }
  });

  if (!auth || !auth.logged) {
    openLogin();
    return;
  }

  await loadState();
  renderLevelPanel();

  const isSessionValid = await loadUser();
  if (!isSessionValid) return;

  loadGroups();
  bindEvents();
  
  try {
    const res = await fetch(`${API_BASE_URL}/watch/status`);
    if (res.ok) {
      const statusData = await res.json();
      if (statusData.active) {
        monitoringActive = true;
        setScannerState(true);
        startAlertsPolling();
        if (statusData.config?.group_ids?.length > 0) {
          state.selectedGroupIds = new Set(statusData.config.group_ids);
          saveState();
        }
      }
    }
  } catch (err) {
    console.error("Erro ao sincronizar status do radar:", err);
  }

  loadAlerts();
  renderMidBrands();
  if ("Notification" in window && Notification.permission !== "granted") {
    Notification.requestPermission();
  }
}

async function togglePriceChart(msgId) {
  const container = document.getElementById(`chart-container-${msgId}`);
  if (!container) return;

  if (container.style.display === "block") {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";
  container.innerHTML = `<div style="font-size: 10px; color: var(--text-muted); text-align: center; padding: 10px;">Carregando histórico...</div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/alerts/${msgId}/price-history`);
    const data = await res.json();
    const history = data.history || [];
    
    container.innerHTML = renderPriceChartSVG(history);
  } catch (err) {
    container.innerHTML = `<div style="font-size: 10px; color: var(--error); text-align: center; padding: 10px;">Erro ao carregar histórico.</div>`;
  }
}

function renderPriceChartSVG(data, width = 300, height = 80) {
  if (!data || data.length < 2) {
    return `<div style="font-size: 10px; color: var(--text-muted); text-align: center; padding: 10px;">Preços insuficientes para gráfico histórico.</div>`;
  }

  const prices = data.map(d => d.price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const padMin = minP - range * 0.1;
  const padMax = maxP + range * 0.1;
  const padRange = padMax - padMin;

  const points = data.map((d, index) => {
    const x = (index / (data.length - 1)) * (width - 20) + 10;
    const y = height - ((d.price - padMin) / padRange) * (height - 20) - 10;
    return { x, y, price: d.price, date: d.date };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaD = `${pathD} L ${points[points.length - 1].x} ${height} L ${points[0].x} ${height} Z`;

  return `
    <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow: visible; margin-top: 8px; margin-bottom: 8px;">
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--primary)" stop-opacity="0.25"/>
          <stop offset="100%" stop-color="var(--primary)" stop-opacity="0.0"/>
        </linearGradient>
        <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path d="${areaD}" fill="url(#areaGrad)" />
      <path d="${pathD}" fill="none" stroke="var(--primary)" stroke-width="2" filter="url(#neonGlow)" />
      ${points.map(p => `
        <circle cx="${p.x}" cy="${p.y}" r="3" fill="var(--success)" stroke="var(--bg-dark)" stroke-width="1">
          <title>R$ ${p.price.toLocaleString('pt-BR')} (${new Date(p.date).toLocaleDateString('pt-BR')})</title>
        </circle>
      `).join('')}
    </svg>
  `;
}

document.addEventListener("DOMContentLoaded", init);
