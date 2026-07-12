/* main.js — utilitaires partagés (toutes les pages) */

// ── Toggle sidebar mobile ────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  const toggle  = document.querySelector('.sidebar-toggle');
  if (sidebar && sidebar.classList.contains('open')) {
    if (!sidebar.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  }
});

document.addEventListener('DOMContentLoaded', function() {
  // ── Auto-fermer les alertes après 5 s ─────────────────
  document.querySelectorAll('.alert').forEach(function(alert) {
    setTimeout(function() {
      if (alert && alert.parentNode) {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity .3s';
        setTimeout(() => alert.remove(), 300);
      }
    }, 5000);
  });

  // ── Horloge topbar ────────────────────────────────────
  startClock();

  // ── Badge non-lus du chat ────────────────────────────
  pollUnreadBadge();
  setInterval(pollUnreadBadge, 30000);

  // ── Recherche dynamique ───────────────────────────────
  initLiveSearch();
});

/* Horloge — mise à jour chaque seconde */
function startClock() {
  function tick() {
    const now  = new Date();
    const time = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const date = now.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
    const el   = document.getElementById('topbar-clock');
    if (el) el.innerHTML = `<span class="clock-time">${time}</span><br>${date}`;
  }
  tick();
  setInterval(tick, 1000);
}

/* Badge non-lus dans la nav */
function pollUnreadBadge() {
  fetch('/api/chat/non-lus')
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (!d) return;
      const badge = document.getElementById('nav-chat-badge');
      if (!badge) return;
      if (d.count > 0) {
        badge.textContent = d.count;
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    })
    .catch(() => {});
}

/* Recherche dynamique côté client */
function initLiveSearch() {
  document.querySelectorAll('input.live-search').forEach(input => {
    const targetId = input.dataset.target;
    input.addEventListener('input', function() {
      const q = this.value.trim().toLowerCase();
      const tbody = targetId
        ? document.getElementById(targetId)
        : document.querySelector('.table tbody');
      if (!tbody) return;
      tbody.querySelectorAll('tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = q === '' || text.includes(q) ? '' : 'none';
      });
      const visibles = [...tbody.querySelectorAll('tr')].filter(r => r.style.display !== 'none');
      let emptyRow = tbody.querySelector('.live-empty');
      if (q && !visibles.length) {
        if (!emptyRow) {
          emptyRow = document.createElement('tr');
          emptyRow.className = 'live-empty';
          const cols = (tbody.querySelector('tr') || {}).children?.length || 4;
          emptyRow.innerHTML = `<td colspan="${cols}" style="text-align:center;color:var(--text-muted);padding:24px">
            Aucun résultat pour "<strong>${esc(this.value)}</strong>"
          </td>`;
          tbody.appendChild(emptyRow);
        } else {
          emptyRow.style.display = '';
        }
      } else if (emptyRow) {
        emptyRow.style.display = 'none';
      }
    });
  });
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
