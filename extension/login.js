const API_BASE_URL = window.PROMOPULSE_API_BASE_URL;
let sendCodeInFlight = false;

function getCodeStep() {
  return document.getElementById("codeStep");
}

function showCodeStep() {
  const codeStep = getCodeStep();
  const sendCodeBtn = document.getElementById("sendCodeBtn");

  requestAnimationFrame(() => {
    codeStep.classList.add("is-visible");
    codeStep.setAttribute("aria-hidden", "false");
    // Esconde o botão de enviar código após o sucesso
    if (sendCodeBtn) sendCodeBtn.style.display = "none";
  });
}

function saveAuthSession() {
  return new Promise((resolve, reject) => {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set(
        {
          telegramAuth: {
            logged: true,
            savedAt: Date.now(),
          },
        },
        () => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          resolve();
        }
      );
    } else {
      // Fallback para desenvolvimento web normal
      localStorage.setItem('telegramAuth', JSON.stringify({ logged: true, savedAt: Date.now() }));
      resolve();
    }
  });
}

function openDashboard() {
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) {
    window.location.href = chrome.runtime.getURL("dashboard.html");
  } else {
    window.location.href = "dashboard.html";
  }
}

function setStatus(message, type = "info") {
  const status = document.getElementById("status");
  status.textContent = message;
  status.className = `status ${type}`;
  
  // Adiciona ícones baseados no tipo
  let icon = "";
  switch(type) {
    case "success": icon = "✅ "; break;
    case "error": icon = "❌ "; break;
    case "info": icon = "ℹ️ "; break;
  }
  status.textContent = icon + message;
}

async function extractErrorMessage(response, fallbackMessage) {
  try {
    const data = await response.json();
    if (data?.detail) {
      if (Array.isArray(data.detail)) {
        return data.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join('; ');
      }
      return data.detail;
    }
    return data?.message || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

async function sendCode() {
  if (sendCodeInFlight) {
    return;
  }

  const phone = document.getElementById("phone").value.trim();
  const sendCodeBtn = document.getElementById("sendCodeBtn");

  if (!phone) {
    setStatus("Digite um telefone para continuar.", "error");
    return;
  }

  sendCodeInFlight = true;
  sendCodeBtn.disabled = true;
  sendCodeBtn.innerHTML = '<span class="spinner"></span> Enviando...';
  setStatus("Enviando código...", "info");

  try {
    const response = await fetch(`${API_BASE_URL}/send.code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phone }),
    });

    if (!response.ok) {
      const detail = await extractErrorMessage(response, "Falha ao enviar o código.");
      setStatus(detail, "error");
      return;
    }

    setStatus("Código enviado no Telegram.", "success");
    showCodeStep();
  } catch (error) {
    setStatus(
      `Não foi possível conectar à API em ${API_BASE_URL}. Confira se o servidor está iniciado.`,
      "error",
    );
    console.error(error);
  } finally {
    sendCodeInFlight = false;
    sendCodeBtn.disabled = false;
    sendCodeBtn.innerHTML = 'Enviar código';
  }
}

async function login() {
  const code = document.getElementById("code").value.trim();
  const loginBtn = document.getElementById("loginBtn");

  if (!code) {
    setStatus("Digite o código recebido.", "error");
    return;
  }

  loginBtn.disabled = true;
  const originalText = loginBtn.innerHTML;
  loginBtn.innerHTML = '<span class="spinner"></span> Validando...';
  setStatus("Validando código...", "info");

  try {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const detail = await extractErrorMessage(response, "Falha no login.");
      setStatus(detail, "error");
      return;
    }

    setStatus("Logado com sucesso!", "success");

    try {
      await saveAuthSession();
    } catch (error) {
      console.error("Não foi possível salvar sessão local:", error);
    }

    setTimeout(openDashboard, 800);
  } catch (error) {
    setStatus(
      `Não foi possível conectar à API em ${API_BASE_URL}. Confira se o servidor está iniciado.`,
      "error",
    );
    console.error(error);
  } finally {
    loginBtn.disabled = false;
    loginBtn.innerHTML = originalText;
  }
}

document.getElementById("sendCodeBtn").addEventListener("click", sendCode);
document.getElementById("loginBtn").addEventListener("click", login);

// Permitir pressionar Enter nos campos
document.getElementById("phone").addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendCode();
});
document.getElementById("code").addEventListener("keypress", (e) => {
  if (e.key === "Enter") login();
});
