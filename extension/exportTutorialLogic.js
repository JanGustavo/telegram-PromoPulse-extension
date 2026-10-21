function hasSeenFirstRun() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["firstRunShown"], (result) => {
        resolve(!!result.firstRunShown);
      });
    } else {
      resolve(!!localStorage.getItem('firstRunShown'));
    }
  });
}

function setFirstRunSeen() {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    try {
      chrome.storage.local.set({ firstRunShown: true });
    } catch (e) {
      console.warn('Could not write chrome.storage:', e);
      localStorage.setItem('firstRunShown', '1');
    }
  } else {
    localStorage.setItem('firstRunShown', '1');
  }
}

async function getAuthSessionLocal() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["telegramAuth"], (result) => {
        resolve(result?.telegramAuth || null);
      });
    } else {
      const stored = localStorage.getItem('telegramAuth');
      resolve(stored ? JSON.parse(stored) : null);
    }
  });
}

function closePopupWindow() {
  // Fecha a janela do popup depois de um pequeno delay para o usuário ver o feedback
  setTimeout(() => window.close(), 800);
}

function showFirstRun() {
  const modal = document.getElementById('firstRunModal');
  if (!modal) return;
  modal.classList.remove('hidden');

  const startBtn = document.getElementById('startTour');
  const dismissBtn = document.getElementById('dismissFirstRun');

  if (startBtn) {
    startBtn.addEventListener('click', async () => {
      setFirstRunSeen();
      startBtn.disabled = true;
      startBtn.textContent = 'Abrindo...';

      try {
        const authSession = await getAuthSessionLocal();
        const page = authSession?.logged ? "dashboard.html" : "login.html";

        if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
          chrome.tabs.create({ url: chrome.runtime.getURL(page) });
        } else {
          window.open(page, '_blank');
        }
      } catch (e) {
        console.error('Erro ao abrir painel:', e);
      } finally {
        closePopupWindow();
      }
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      setFirstRunSeen();

      // Feedback visual antes de fechar
      dismissBtn.textContent = '✓ Ok, não mostrar mais';
      dismissBtn.disabled = true;

      modal.classList.add('hidden');
      closePopupWindow();
    });
  }
}

// Espera o DOM estar pronto antes de verificar o primeiro uso
// Evita race condition com popup.js
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const seen = await hasSeenFirstRun();
    if (!seen) showFirstRun();
  } catch (e) {
    console.error('First-run init error', e);
  }
});

// Expose functions for tests or other modules
window.exportTutorialLogic = {
  hasSeenFirstRun,
  setFirstRunSeen,
  showFirstRun,
};
