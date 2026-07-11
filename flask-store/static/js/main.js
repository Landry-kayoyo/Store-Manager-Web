/* main.js — utilitaires partagés */

// Toggle sidebar mobile
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// Fermer sidebar en cliquant en dehors
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.querySelector('.sidebar-toggle');
  if (sidebar && sidebar.classList.contains('open')) {
    if (!sidebar.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  }
});

// Auto-fermer les alertes après 5 secondes
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
});
