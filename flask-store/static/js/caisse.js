/* caisse.js — logique de la caisse enregistreuse
   Supporte les devises mixtes par produit (FC / USD).
   Conversion automatique selon le taux configuré en paramètres.
*/

// PRODUITS, DEVISE, TAUX et CSRF_TOKEN sont injectés par le template caisse.html
let panier = [];
// [{ produit_id, nom, prix_original, prix_final, prix_final_converti, promo_pct,
//    devise, stock, quantite }]
let categorieActive = '';

// ── Initialisation ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  renderCatTabs();
  renderProduitsGrid('');
  renderPanier();
});

// ── Catégories ───────────────────────────────────────────
function renderCatTabs() {
  const cats = [...new Set(PRODUITS.map(p => p.categorie))].sort();
  const container = document.getElementById('cat-tabs');
  let html = `<button class="cat-tab active" onclick="changerCat('')">Tout</button>`;
  cats.forEach(cat => {
    html += `<button class="cat-tab" onclick="changerCat('${escHtml(cat)}')">${escHtml(cat)}</button>`;
  });
  container.innerHTML = html;
}

function changerCat(cat) {
  categorieActive = cat;
  document.querySelectorAll('.cat-tab').forEach(btn => btn.classList.remove('active'));
  const idx = [...document.querySelectorAll('.cat-tab')].findIndex(
    b => b.textContent === (cat || 'Tout'));
  if (idx >= 0) document.querySelectorAll('.cat-tab')[idx].classList.add('active');
  filtrerProduits();
}

// ── Grille produits ───────────────────────────────────────
function filtrerProduits() {
  const q = (document.getElementById('produit-search').value || '').toLowerCase();
  renderProduitsGrid(q);
}

function renderProduitsGrid(q) {
  const grid = document.getElementById('produits-grid');
  const filtered = PRODUITS.filter(p => {
    const matchQ = !q || p.nom.toLowerCase().includes(q) || p.categorie.toLowerCase().includes(q);
    const matchCat = !categorieActive || p.categorie === categorieActive;
    return matchQ && matchCat;
  });
  if (!filtered.length) {
    grid.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;padding:12px 0;">Aucun produit trouvé.</p>';
    return;
  }
  grid.innerHTML = filtered.map(p => {
    const ruptureClass = p.stock === 0 ? ' out-of-stock' : '';
    // Affichage du prix dans la devise d'origine du produit
    const prixOriginalFmt = p.promo_pct ? `<s>${formatMontantDevise(p.prix, p.devise)}</s> ` : '';
    const prixFmt = `${prixOriginalFmt}${formatMontantDevise(p.prix_final, p.devise)}`;
    const promoBadge = p.promo_pct ? `<span class="produit-card-promo">-${Math.round(p.promo_pct)}%</span>` : '';
    // Si la devise du produit differ de la devise caisse, montrer la conversion
    let conversionHint = '';
    if (p.devise !== DEVISE && p.stock > 0) {
      conversionHint = `<div class="produit-card-conv">≈ ${formatMontant(p.prix_final_converti)}</div>`;
    }
    const stockTxt = p.stock === 0
      ? '<span style="color:var(--danger)">Rupture de stock</span>'
      : `${p.stock} en stock`;
    return `
      <div class="produit-card${ruptureClass}" onclick="${p.stock > 0 ? `ajouterAuPanier(${p.id})` : ''}">
        <div class="produit-card-name">${escHtml(p.nom)}</div>
        <div class="produit-card-cat">${escHtml(p.categorie)}</div>
        <div class="produit-card-prix">${prixFmt}${promoBadge}</div>
        ${conversionHint}
        <div class="produit-card-stock">${stockTxt}</div>
      </div>`;
  }).join('');
}

// ── Panier ───────────────────────────────────────────────
function ajouterAuPanier(id) {
  const produit = PRODUITS.find(p => p.id === id);
  if (!produit || produit.stock === 0) return;
  const item = panier.find(i => i.produit_id === id);
  if (item) {
    if (item.quantite < produit.stock) {
      item.quantite++;
    } else {
      showFlash('Stock insuffisant pour "' + produit.nom + '".', 'warning');
      return;
    }
  } else {
    panier.push({
      produit_id: id,
      nom: produit.nom,
      prix_original: produit.prix,            // prix brut (devise produit)
      prix_final: produit.prix_final,          // prix après promo (devise produit)
      prix_final_converti: produit.prix_final_converti, // converti dans devise caisse
      promo_pct: produit.promo_pct,
      devise: produit.devise,                  // devise d'origine du produit
      stock: produit.stock,
      quantite: 1,
    });
  }
  renderPanier();
}

function changerQty(id, delta) {
  const item = panier.find(i => i.produit_id === id);
  if (!item) return;
  item.quantite += delta;
  if (item.quantite <= 0) {
    panier = panier.filter(i => i.produit_id !== id);
  } else if (item.quantite > item.stock) {
    item.quantite = item.stock;
    showFlash('Quantité maximale atteinte.', 'warning');
  }
  renderPanier();
}

function supprimerItem(id) {
  panier = panier.filter(i => i.produit_id !== id);
  renderPanier();
}

function viderPanier() {
  if (panier.length && !confirm('Vider le panier ?')) return;
  panier = [];
  renderPanier();
}

function renderPanier() {
  const container = document.getElementById('panier-items');
  const empty = document.getElementById('panier-vide');
  const btnValider = document.getElementById('btn-valider');
  const countEl = document.getElementById('panier-count');

  if (!panier.length) {
    empty.style.display = '';
    container.innerHTML = '';
    btnValider.disabled = true;
    if (countEl) { countEl.textContent = ''; countEl.style.display = 'none'; }
    document.getElementById('total-brut').textContent = '—';
    document.getElementById('total-final').textContent = formatMontant(0);
    document.getElementById('promo-line').style.display = 'none';
    cacherInfoConversion();
    return;
  }

  empty.style.display = 'none';
  btnValider.disabled = false;
  const totalQty = panier.reduce((s, i) => s + i.quantite, 0);
  if (countEl) { countEl.textContent = totalQty; countEl.style.display = ''; }

  let totalBrut = 0, totalFinal = 0;
  let multiDevise = false;

  container.innerHTML = panier.map(item => {
    // sous-totaux dans la devise de la caisse (pour les calculs)
    const subtotal = item.prix_final_converti * item.quantite;
    const subtotalBrut = convertirPrix(item.prix_original, item.devise) * item.quantite;
    totalBrut += subtotalBrut;
    totalFinal += subtotal;

    const promoLine = item.promo_pct
      ? `<div class="panier-item-promo">-${Math.round(item.promo_pct)}% appliqué</div>` : '';

    // Ligne de prix : afficher prix dans devise produit + conversion si différente
    let prixLigne = `${formatMontantDevise(item.prix_final, item.devise)} × ${item.quantite}`;
    if (item.devise !== DEVISE) {
      multiDevise = true;
      prixLigne += ` <span class="conv-hint">(≈ ${formatMontant(item.prix_final_converti)}/u)</span>`;
    }

    return `
      <div class="panier-item">
        <div style="flex:1;min-width:0">
          <div class="panier-item-name">${escHtml(item.nom)}</div>
          ${promoLine}
          <div style="font-size:.78rem;color:var(--text-muted)">${prixLigne}</div>
        </div>
        <div class="panier-qty">
          <button class="qty-btn" onclick="changerQty(${item.produit_id},-1)">−</button>
          <span class="qty-val">${item.quantite}</span>
          <button class="qty-btn" onclick="changerQty(${item.produit_id},1)">+</button>
        </div>
        <div class="panier-subtotal">${formatMontant(subtotal)}</div>
        <button class="panier-remove" onclick="supprimerItem(${item.produit_id})" title="Retirer">
          <svg viewBox="0 0 24 24" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
        </button>
      </div>`;
  }).join('');

  const remise = totalBrut - totalFinal;
  document.getElementById('total-brut').textContent = formatMontant(totalBrut);
  document.getElementById('total-final').textContent = formatMontant(totalFinal);
  if (remise > 0.001) {
    document.getElementById('total-remise').textContent = '- ' + formatMontant(remise);
    document.getElementById('promo-line').style.display = '';
  } else {
    document.getElementById('promo-line').style.display = 'none';
  }

  // Bandeau d'info conversion multi-devises
  if (multiDevise) {
    afficherInfoConversion();
  } else {
    cacherInfoConversion();
  }
}

function afficherInfoConversion() {
  let el = document.getElementById('info-conversion');
  if (!el) {
    el = document.createElement('div');
    el.id = 'info-conversion';
    el.className = 'info-box info-box-sm';
    el.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" style="margin-right:4px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      Panier multi-devises — les totaux sont convertis en <strong>${DEVISE}</strong>
      au taux&nbsp;: <strong>1&nbsp;$&nbsp;=&nbsp;${TAUX.toLocaleString('fr-FR')}&nbsp;FC</strong>.`;
    const footer = document.querySelector('.panier-footer');
    if (footer) footer.insertBefore(el, footer.firstChild);
  }
  el.style.display = '';
}

function cacherInfoConversion() {
  const el = document.getElementById('info-conversion');
  if (el) el.style.display = 'none';
}

// ── Conversion ───────────────────────────────────────────
function convertirPrix(montant, deDevise) {
  if (deDevise === DEVISE) return montant;
  if (deDevise === 'USD' && DEVISE === 'FC') return montant * TAUX;
  if (deDevise === 'FC'  && DEVISE === 'USD') return montant / TAUX;
  return montant;
}

// ── Validation ───────────────────────────────────────────
function validerVente() {
  if (!panier.length) return;
  const modal = document.getElementById('modal-loading');
  modal.style.display = '';

  const lignes = panier.map(i => ({ produit_id: i.produit_id, quantite: i.quantite }));
  const csrfToken = CSRF_TOKEN ||
    (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  fetch(window.location.pathname, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({ lignes }),
  })
    .then(r => r.json())
    .then(data => {
      modal.style.display = 'none';
      if (data.success) {
        panier = [];
        window.location.href = data.recu_url;
      } else {
        showFlash(data.error || 'Erreur lors de la validation.', 'danger');
      }
    })
    .catch(() => {
      modal.style.display = 'none';
      showFlash('Erreur réseau. Veuillez réessayer.', 'danger');
    });
}

// ── Formatage ─────────────────────────────────────────────
/** Formate un montant dans la devise active de la caisse */
function formatMontant(val) {
  return formatMontantDevise(val, DEVISE);
}

/** Formate un montant dans une devise explicite */
function formatMontantDevise(val, devise) {
  if (devise === 'FC') {
    return Math.round(val).toLocaleString('fr-FR') + ' FC';
  } else {
    return '$' + Number(val).toFixed(2);
  }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showFlash(msg, type) {
  const body = document.querySelector('.content-body');
  const div = document.createElement('div');
  div.className = `alert alert-${type}`;
  div.innerHTML = `<span>${escHtml(msg)}</span><button onclick="this.parentElement.remove()">×</button>`;
  body.insertBefore(div, body.firstChild);
  setTimeout(() => { if (div.parentNode) div.remove(); }, 5000);
}
