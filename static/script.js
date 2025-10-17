// Gestion de la recherche
document.addEventListener('DOMContentLoaded', function() {
  const searchBtn = document.querySelector(".btn-search");
  const coachInput = document.querySelector('input[placeholder*="coach"]');
  const addressInput = document.querySelector('input[placeholder*="Adresse"]');
  const gymInput = document.querySelector('input[placeholder*="salle"]');

  if (searchBtn) {
    searchBtn.addEventListener("click", function() {
      const coachValue = coachInput ? coachInput.value.trim() : '';
      const addressValue = addressInput ? addressInput.value.trim() : '';
      const gymValue = gymInput ? gymInput.value.trim() : '';

      // Rediriger vers la page de recherche avec les paramètres
      const params = new URLSearchParams();
      if (coachValue) params.append('coach', coachValue);
      if (addressValue) params.append('location', addressValue);
      if (gymValue) params.append('gym', gymValue);

      window.location.href = `/search?${params.toString()}`;
    });
  }

  // Permettre la recherche avec la touche Entrée
  const inputs = document.querySelectorAll('.search-box input');
  inputs.forEach(input => {
    input.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        searchBtn.click();
      }
    });
  });
});
