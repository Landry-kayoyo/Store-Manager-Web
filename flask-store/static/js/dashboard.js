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

/* ── Formate un montant dans la devise principale avec équivalent ── */
function fmt(val) {
  if (_devise === 'FC') {
    const fc  = Math.round(val).toLocaleString('fr-FR') + ' FC';
    const usd = '$' + (val / _taux).toFixed(2);
    return `${fc} <small class="kpi-equiv">${usd}</small>`;
  } else {
    const usd = '$' + Number(val).toFixed(2);
    const fc  = Math.round(val * _taux).toLocaleString('fr-FR') + ' FC';
    return `${usd} <small class="kpi-equiv">${fc}</small>`;
  }
}

/* Version texte simple (tooltips, pas de HTML) */
function fmtText(val, devise) {
  const d = devise || _devise;
  if (d === 'FC') return Math.round(val).toLocaleString('fr-FR') + ' FC';
  return '$' + Number(val).toFixed(2);
}

/* Version courte pour les axes */
function fmtCourt(val) {
  if (val >= 1000000) return (val/1000000).toFixed(1) + 'M';
  if (val >= 1000)    return (val/1000).toFixed(0) + 'k';
  return String(Math.round(val));
}

/* ── KPIs ─────────────────────────────────────────────── */
function fillKPIs(d) {
  setHtml('kpi-ca-val',     fmt(d.ca_jour));
  setText('kpi-ventes-val', d.nb_ventes_jour);
  setText('kpi-stock-val',  d.stock_bas_count);
  setText('kpi-agents-val', d.agents_actifs);

  /* Statistiques page */
  setHtml('s-ca-jour',  fmt(d.ca_jour));
  setText('s-nb-jour',  d.nb_ventes_jour);
  setText('s-stock-bas', d.stock_bas_count);
  setText('s-agents',   d.agents_actifs);
}

/* ── Graphique ventes 7j ─────────────────────────────── */
function renderChartVentes(ventes7j) {
  const el = document.getElementById('chartVentes');
  if (!el) return;
  new Chart(el, {
    type: 'line',
    data: {
      labels: ventes7j.map(v => v.date),
      datasets: [{
        label: 'Ventes',
        data: ventes7j.map(v => v.montant),
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
              const fc = _devise === 'FC' ? ctx.raw : ctx.raw * _taux;
              const usd = _devise === 'USD' ? ctx.raw : ctx.raw / _taux;
              return [
                ' ' + Math.round(fc).toLocaleString('fr-FR') + ' FC',
                ' $' + usd.toFixed(2),
              ];
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
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels: cats.map(c => c.categorie),
      datasets: [{
        data: cats.map(c => c.montant),
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
              const fc = _devise === 'FC' ? ctx.raw : ctx.raw * _taux;
              const usd = _devise === 'USD' ? ctx.raw : ctx.raw / _taux;
              return ` ${ctx.label}: ${Math.round(fc).toLocaleString('fr-FR')} FC / $${usd.toFixed(2)}`;
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
        ${Math.round(fc).toLocaleString('fr-FR')} FC
        <small class="kpi-equiv">$${usd.toFixed(2)}</small>
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
