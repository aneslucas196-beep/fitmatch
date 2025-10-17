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

      // Si une adresse est saisie, rediriger vers la carte des salles
      if (addressValue) {
        window.location.href = `/gyms-map?address=${encodeURIComponent(addressValue)}`;
        return;
      }

      // Sinon, rediriger vers la page de recherche classique
      const params = new URLSearchParams();
      if (coachValue) params.append('coach', coachValue);
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
