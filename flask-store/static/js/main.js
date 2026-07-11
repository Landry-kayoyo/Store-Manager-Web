/* main.js — utilitaires partagés */

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

// ── Auto-fermer les alertes après 5 s ────────────────────
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.alert').forEach(function(alert) {
    setTimeout(function() {
      if (alert && alert.parentNode) {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity .3s';
        setTimeout(() => alert.remove(), 300);
      }
    }, 5000);
  });

  // ── Recherche dynamique ──────────────────────────────
  initLiveSearch();
});

/**
 * Recherche dynamique côté client.
 * Cherche un <input id="produit-search"> OU <input class="input-search live-search">
 * et filtre les lignes du premier <tbody> visible sur la page.
 *
 * Les champs de filtre serveur (select, bouton Filtrer) sont désactivés
 * seulement si on tape une valeur — sinon ils restent actifs.
 */
function initLiveSearch() {
  // Cherche les inputs marqués live-search
  document.querySelectorAll('input.live-search').forEach(input => {
    const targetId = input.dataset.target; // id du tbody cible (optionnel)
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
      // Afficher/masquer le message "aucun résultat"
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
