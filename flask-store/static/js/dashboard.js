/* dashboard.js — stats admin asynchrones + Chart.js */

const GREEN   = '#1A3A2A';
const GOLD    = '#C89B3C';
const PALETTE = ['#1A3A2A','#C89B3C','#2D7D46','#D97706','#2563EB','#7C3AED','#DB2777','#0891B2'];

let _devise = 'FC';
let _taux   = 2800;

document.addEventListener('DOMContentLoaded', loadStats);

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
      document.querySelectorAll('.kpi-card').forEach(el => el.classList.remove('loading'));
    })
    .catch(err => console.error('Erreur chargement stats:', err));
}

/* ── $ en gros, FC en petit dessous — toujours ── */
function fmt(val) {
  const fc  = _devise === 'FC' ? val : val * _taux;
  const usd = _devise === 'USD' ? val : val / _taux;
  return `$${usd.toFixed(2)} <small class="kpi-equiv">${Math.round(fc).toLocaleString('fr-FR')} FC</small>`;
}

/* Version courte pour axes graphiques */
function fmtCourt(val) {
  if (val >= 1000000) return '$' + (val/1000000).toFixed(1) + 'M';
  if (val >= 1000)    return '$' + (val/1000).toFixed(0) + 'k';
  return '$' + Math.round(val);
}

/* ── KPIs ─────────────────────────────────────────────── */
function fillKPIs(d) {
  setHtml('kpi-ca-val',     fmt(d.ca_jour));
  setText('kpi-ventes-val', d.nb_ventes_jour);
  setText('kpi-stock-val',  d.stock_bas_count);
  setText('kpi-agents-val', d.agents_actifs);
}

/* ── Graphique ventes 7j ─────────────────────────────── */
function renderChartVentes(ventes7j) {
  const el = document.getElementById('chartVentes');
  if (!el) return;
  // Convertit en USD pour l'axe (valeur stockée en devise active)
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
              const usd = ctx.raw;
              const fc  = Math.round(usd * _taux).toLocaleString('fr-FR');
              return [` $${usd.toFixed(2)}`, ` ${fc} FC`];
            }
          }
        }
      },
      scales: {
        y: {
          ticks: { callback: v => fmtCourt(v) },
          grid: { color: '#E2DDD6' }
        },
        x: { grid: { display: false } }
      }
    }
  });
}

/* ── Graphique catégories ────────────────────────────── */
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
              const usd = ctx.raw;
              const fc  = Math.round(usd * _taux).toLocaleString('fr-FR');
              return ` ${ctx.label}: $${usd.toFixed(2)} / ${fc} FC`;
            }
          }
        }
      }
    }
  });
}

/* ── Top agents ──────────────────────────────────────── */
function renderTopAgents(agents) {
  const el = document.getElementById('top-agents-container');
  if (!el) return;
  if (!agents.length) {
    el.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">Aucune vente sur les 30 derniers jours.</p>';
    return;
  }
  el.innerHTML = agents.map((a, i) => {
    const av = a.photo
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

/* ── Stock bas ───────────────────────────────────────── */
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

/* ── Utilitaires ─────────────────────────────────────── */
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
function setHtml(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = val;
}
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
