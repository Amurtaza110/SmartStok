/**
 * SmartStock Global Utilities
 * Loaded on every page via base.html
 */

// ── CSRF helper for fetch() calls ──────────────────────
function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  if (el) return el.value;
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1] : '';
}

// ── Auto-dismiss Bootstrap alerts after 4s ─────────────
document.querySelectorAll('.alert.alert-dismissible').forEach(el => {
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
    if (bsAlert) bsAlert.close();
  }, 4000);
});

// ── Confirm dangerous actions ──────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ── Mobile navigation ────────────────────────────────
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebarBackdrop = document.getElementById('sidebarBackdrop');
function closeSidebar() {
  if (!sidebar || !sidebarToggle || !sidebarBackdrop) return;
  sidebar.classList.remove('open');
  sidebarBackdrop.classList.remove('open');
  sidebarToggle.setAttribute('aria-expanded', 'false');
}
if (sidebar && sidebarToggle && sidebarBackdrop) {
  sidebarToggle.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('open');
    sidebarBackdrop.classList.toggle('open', isOpen);
    sidebarToggle.setAttribute('aria-expanded', String(isOpen));
  });
  sidebarBackdrop.addEventListener('click', closeSidebar);
}

// ── Active sidebar link highlighting ──────────────────
(function() {
  const path = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(link => {
    if (link.getAttribute('href') === path) {
      link.classList.add('active');
    }
  });
})();

// ── Number formatting helper ──────────────────────────
function formatPKR(amount) {
  return 'PKR ' + parseFloat(amount).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// ── Toast notification helper ─────────────────────────
function showToast(message, type = 'info') {
  const colors = {
    success: '#10b981',
    error:   '#ef4444',
    warning: '#f59e0b',
    info:    '#00d4ff',
  };
  const div = document.createElement('div');
  div.style.cssText = `
    position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 9999;
    background: #111827; border: 1px solid ${colors[type] || colors.info};
    color: #e2e8f0; padding: .75rem 1.25rem; border-radius: 10px;
    font-size: .875rem; max-width: 360px;
    box-shadow: 0 4px 20px rgba(0,0,0,.4);
    animation: slideIn .2s ease;
  `;
  div.textContent = message;
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 3500);
}

// ── Barcode scanner support for POS ───────────────────
// Collects rapid keystrokes (barcode scanner sends chars very fast)
let barcodeBuffer = '';
let barcodeTimer  = null;

document.addEventListener('keypress', e => {
  // Only on POS page
  if (!document.getElementById('productSearch')) return;

  clearTimeout(barcodeTimer);
  barcodeBuffer += e.key;

  barcodeTimer = setTimeout(() => {
    if (barcodeBuffer.length >= 6) {
      // Looks like a barcode scan — put it in the search field
      const searchEl = document.getElementById('productSearch');
      if (document.activeElement !== searchEl) {
        searchEl.value = barcodeBuffer;
        searchEl.dispatchEvent(new Event('input'));
        searchEl.focus();
      }
    }
    barcodeBuffer = '';
  }, 80); // Barcodes complete in <80ms
});
