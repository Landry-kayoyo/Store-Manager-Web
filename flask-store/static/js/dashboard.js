/* dashboard.js — stats admin + statistiques page, Chart.js */

const GREEN   = '#1A3A2A';
const PALETTE = ['#1A3A2A','#C89B3C','#2D7D46','#D97706','#2563EB','#7C3AED','#DB2777','#0891B2'];

let _devise = 'FC';
let _taux   = 2800;

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  startClock();
});

/* ── Horloge ─────────────────────────────────────────────── */
function startClock() {
  function tick() {
    const now  = new Date();
    const time = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const date = now.toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
    const el   = document.getElementById('topbar-clock');
    if (el) el.innerHTML = `<span class="clock-time">${time}</span><br><span>${date}</span>`;
  }
  tick();
  setInterval(tick, 1000);
}

/* ── Chargement des stats (appelé par les deux pages) ────── */
function loadStats() {
  fetch('/api/dashboard-stats')
    .then(r => r.json())
    .then(data => {
      if (data.error) { console.error(data.error); return; }
      _devise = data.devise || 'FC';
      _taux   = data.taux   || 2800;
      fillKPIs(data);
      renderChartVentes(data.ventes_7j);
      renderTopAgents(data.top_agents);
      renderStockBas(data.stock_bas);
      renderChartCategories(data.ventes_cat);
      document.querySelectorAll('.kpi-card.loading').forEach(el => el.classList.remove('loading'));
      const overlay = document.getElementById('stats-loading');
      if (overlay) overlay.style.display = 'none';
    })
    .catch(err => console.error('Erreur chargement stats:', err));
}

/* ── $ en gros, FC en petit dessous ── */
function fmt(val) {
  const fc  = _devise === 'FC' ? val : val * _taux;
  const usd = _devise === 'USD' ? val : val / _taux;
  return `$${usd.toFixed(2)} <small class="kpi-equiv">${Math.round(fc).toLocaleString('fr-FR')} FC</small>`;
}

/* Version courte pour axes */
function fmtCourt(val) {
  const usd = _devise === 'FC' ? val / _taux : val;
  if (usd >= 1000) return '$' + (usd/1000).toFixed(0) + 'k';
  return '$' + Math.round(usd);
}

/* ── KPIs — remplit dashboard.html ET statistiques.html ─── */
function fillKPIs(d) {
  // dashboard.html
  setHtml('kpi-ca-val',     fmt(d.ca_jour));
  setText('kpi-ventes-val', d.nb_ventes_jour);
  setText('kpi-stock-val',  d.stock_bas_count);
  setText('kpi-agents-val', d.agents_actifs);
  // statistiques.html
  setHtml('s-ca-jour',   fmt(d.ca_jour));
  setText('s-nb-jour',   d.nb_ventes_jour);
  setText('s-stock-bas', d.stock_bas_count);
  setText('s-agents',    d.agents_actifs);
  // Taux actif (dashboard banner)
  setText('taux-actif-val', `1 $ = ${Math.round(_taux)} FC`);
}

/* ── Graphique ventes 7j ─────────────────────────────────── */
function renderChartVentes(ventes7j) {
  const el = document.getElementById('chartVentes');
  if (!el) return;
  const toUsd = v => _devise === 'FC' ? v / _taux : v;
  new Chart(el, {
    type: 'line',
    data: {
      labels: ventes7j.map(v => v.date),
      datasets: [{
        label: 'Ventes',
        data: ventes7j.map(v => toUsd(v.montant)),
        borderColor: GREEN, backgroundColor: 'rgba(26,58,42,.08)',
        fill: true, tension: 0.4, pointBackgroundColor: GREEN, pointRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const fc = Math.round(ctx.raw * _taux).toLocaleString('fr-FR');
              return [` $${ctx.raw.toFixed(2)}`, ` ${fc} FC`];
            }
          }
        }
      },
      scales: {
        y: { ticks: { callback: v => fmtCourt(v) }, grid: { color: '#E2DDD6' } },
        x: { grid: { display: false } }
      }
    }
  });
}

/* ── Graphique catégories ────────────────────────────────── */
function renderChartCategories(cats) {
  const el = document.getElementById('chartCategories');
  if (!el || !cats.length) return;
  const toUsd = v => _devise === 'FC' ? v / _taux : v;
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels: cats.map(c => c.categorie),
      datasets: [{
        data: cats.map(c => toUsd(c.montant)),
        backgroundColor: PALETTE,
        borderWidth: 2, borderColor: '#fff',
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const fc = Math.round(ctx.raw * _taux).toLocaleString('fr-FR');
              return ` ${ctx.label}: $${ctx.raw.toFixed(2)} / ${fc} FC`;
            }
          }
        }
      }
    }
  });
}

/* ── Top agents ──────────────────────────────────────────── */
function renderTopAgents(agents) {
  const el = document.getElementById('top-agents-container');
  if (!el) return;
  if (!agents.length) {
    el.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">Aucune vente sur les 30 derniers jours.</p>';
    return;
  }
  el.innerHTML = agents.map((a, i) => {
    const av  = a.photo
      ? `<img src="/uploads/${a.photo}" alt="" class="avatar">`
      : `<div class="avatar avatar-initial">${esc(a.nom[0])}</div>`;
    const fc  = _devise === 'FC' ? a.montant : a.montant * _taux;
    const usd = _devise === 'USD' ? a.montant : a.montant / _taux;
    return `<div class="top-agent-row">
      <div class="top-agent-rank">${i + 1}</div>
      ${av}
      <div class="top-agent-info"><div class="top-agent-name">${esc(a.nom)}</div></div>
      <div class="top-agent-amount">
        $${usd.toFixed(2)}
        <small class="kpi-equiv">${Math.round(fc).toLocaleString('fr-FR')} FC</small>
      </div>
    </div>`;
  }).join('');
}

/* ── Stock bas ───────────────────────────────────────────── */
function renderStockBas(items) {
  const el = document.getElementById('stock-bas-container');
  if (!el) return;
  if (!items.length) {
    el.innerHTML = '<p style="color:var(--success);font-size:.875rem;font-weight:600">✓ Aucun produit en stock critique.</p>';
    return;
  }
  el.innerHTML = items.map(p => {
    const badge = p.stock === 0
      ? `<span class="stock-badge stock-zero">Rupture</span>`
      : `<span class="stock-badge stock-low">${p.stock} unités ⚠</span>`;
    return `<div class="stock-bas-item"><a href="/stock">${esc(p.nom)}</a>${badge}</div>`;
  }).join('');
}

/* ── Utilitaires ─────────────────────────────────────────── */
function setText(id, val) { const e = document.getElementById(id); if (e) e.textContent = val; }
function setHtml(id, val) { const e = document.getElementById(id); if (e) e.innerHTML = val; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
