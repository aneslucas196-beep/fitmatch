class SearchApp {
  constructor() {
    this.addressInput = document.getElementById('addressInput');
    this.gymInput = document.getElementById('gymInput');
    this.searchBtn = document.getElementById('searchBtn');
    this.addressAutocomplete = document.getElementById('addressAutocomplete');
    this.gymAutocomplete = document.getElementById('gymAutocomplete');
    this.resultsSection = document.getElementById('resultsSection');
    this.resultsGrid = document.getElementById('resultsGrid');
    this.resultsTitle = document.getElementById('resultsTitle');
    this.resultsCount = document.getElementById('resultsCount');
    this.loadingState = document.getElementById('loadingState');
    this.emptyState = document.getElementById('emptyState');
    this.errorState = document.getElementById('errorState');
    this.sortSelect = document.getElementById('sortSelect');
    
    this.debounceTimers = {};
    this.selectedAddress = null;
    this.selectedGym = null;
    this.currentResults = [];
    this.userLocation = null;
    this.currentFilters = {
      availableToday: false,
      maxDistance: null,
      maxPrice: null
    };
    
    this.init();
  }
  
  async init() {
    try {
      await searchService.init();
      this.attachEventListeners();
      this.loadFromURL();
    } catch (error) {
      console.error('Erreur initialisation:', error);
      this.showError();
    }
  }
  
  attachEventListeners() {
    this.addressInput.addEventListener('input', () => {
      this.handleAutocomplete(this.addressInput, this.addressAutocomplete, 'address');
    });
    
    this.gymInput.addEventListener('input', () => {
      this.handleAutocomplete(this.gymInput, this.gymAutocomplete, 'gym');
    });
    
    this.searchBtn.addEventListener('click', () => this.performSearch());
    
    this.addressInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') this.performSearch();
    });
    
    this.gymInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') this.performSearch();
    });
    
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.input-wrapper')) {
        this.hideAllAutocomplete();
      }
    });
    
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => this.handleFilterClick(btn));
    });
    
    this.sortSelect.addEventListener('change', () => this.applySortAndFilters());
  }
  
  handleAutocomplete(input, dropdown, type) {
    const query = input.value.trim();
    
    clearTimeout(this.debounceTimers[type]);
    
    if (query.length < 2) {
      dropdown.classList.remove('show');
      return;
    }
    
    this.debounceTimers[type] = setTimeout(() => {
      const suggestions = searchService.autocomplete(query, type);
      this.displayAutocomplete(suggestions, dropdown, input);
    }, 300);
  }
  
  displayAutocomplete(suggestions, dropdown, input) {
    if (suggestions.length === 0) {
      dropdown.classList.remove('show');
      return;
    }
    
    dropdown.innerHTML = suggestions.map(suggestion => `
      <div class="autocomplete-item" data-type="${suggestion.type}" data-value="${suggestion.value}">
        <span class="icon">${suggestion.icon}</span>
        <span class="label">${suggestion.label}</span>
      </div>
    `).join('');
    
    dropdown.classList.add('show');
    
    dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('click', () => {
        const type = item.dataset.type;
        const value = item.dataset.value;
        const label = item.querySelector('.label').textContent;
        
        input.value = label;
        
        if (input === this.addressInput) {
          this.selectedAddress = { type, value, label };
        } else {
          this.selectedGym = { type, value, label };
        }
        
        dropdown.classList.remove('show');
      });
    });
  }
  
  hideAllAutocomplete() {
    this.addressAutocomplete.classList.remove('show');
    this.gymAutocomplete.classList.remove('show');
  }
  
  async performSearch() {
    const addressQuery = this.addressInput.value.trim();
    const gymQuery = this.gymInput.value.trim();
    
    if (!addressQuery && !gymQuery) {
      return;
    }
    
    this.showLoading();
    this.updateURL(addressQuery, gymQuery);
    
    try {
      let results = [];
      let resultType = '';
      
      // Priorité 1: Si une salle spécifique est sélectionnée → Afficher ses coachs
      if (this.selectedGym && this.selectedGym.type === 'gym') {
        const coaches = searchService.searchCoachesByGym(this.selectedGym.value);
        results = coaches;
        resultType = 'coaches';
        
        // Récupérer la position de la salle pour le tri par distance
        const gym = searchService.gyms.find(g => g.id === this.selectedGym.value);
        if (gym) {
          this.userLocation = { lat: gym.lat, lng: gym.lng };
          this.resultsTitle.textContent = `Coachs chez ${gym.name}`;
        } else {
          this.resultsTitle.textContent = 'Coachs trouvés';
        }
      }
      // Priorité 2: Si code postal dans "Quelle salle" → Afficher les salles
      else if (gymQuery && /^\d{5}$/.test(gymQuery)) {
        const gyms = searchService.searchGymsByPostalCode(gymQuery);
        results = gyms;
        resultType = 'gyms';
        this.resultsTitle.textContent = 'Salles trouvées';
      }
      // Priorité 3: Si nom de salle tapé → Rechercher salles correspondantes
      else if (gymQuery) {
        const gyms = searchService.searchGymsByName(gymQuery);
        if (gyms.length === 1) {
          // Si une seule salle trouvée → Afficher directement ses coachs
          const coaches = searchService.searchCoachesByGym(gyms[0].id);
          results = coaches;
          resultType = 'coaches';
          this.userLocation = { lat: gyms[0].lat, lng: gyms[0].lng };
          this.resultsTitle.textContent = `Coachs chez ${gyms[0].name}`;
        } else {
          // Plusieurs salles → Les lister
          results = gyms;
          resultType = 'gyms';
          this.resultsTitle.textContent = 'Salles trouvées';
        }
      }
      // Priorité 4: Recherche par adresse/ville uniquement
      else if (addressQuery) {
        if (this.selectedAddress && this.selectedAddress.type === 'city') {
          results = searchService.searchCoachesByCity(this.selectedAddress.value);
          const cityGym = searchService.gyms.find(g => 
            searchService.normalizeString(g.city) === searchService.normalizeString(this.selectedAddress.value)
          );
          if (cityGym) {
            this.userLocation = { lat: cityGym.lat, lng: cityGym.lng };
          }
        } else if (/^\d{5}$/.test(addressQuery)) {
          results = searchService.searchCoachesByPostalCode(addressQuery);
          const gym = searchService.gyms.find(g => g.postal_code === addressQuery);
          if (gym) {
            this.userLocation = { lat: gym.lat, lng: gym.lng };
          }
        } else {
          results = searchService.searchCoachesByCity(addressQuery);
          const cityGym = searchService.gyms.find(g => 
            searchService.normalizeString(g.city) === searchService.normalizeString(addressQuery)
          );
          if (cityGym) {
            this.userLocation = { lat: cityGym.lat, lng: cityGym.lng };
          }
        }
        resultType = 'coaches';
        this.resultsTitle.textContent = 'Coachs trouvés';
      }
      
      this.currentResults = { data: results, type: resultType };
      this.applySortAndFilters();
      
    } catch (error) {
      console.error('Erreur recherche:', error);
      this.showError();
    }
  }
  
  applySortAndFilters() {
    let results = [...this.currentResults.data];
    
    if (this.currentResults.type === 'coaches') {
      if (this.currentFilters.maxDistance && this.userLocation) {
        this.currentFilters.userLocation = this.userLocation;
      }
      
      results = searchService.filterCoaches(results, this.currentFilters);
      results = searchService.sortCoaches(results, this.sortSelect.value, this.userLocation);
    }
    
    this.displayResults(results, this.currentResults.type);
  }
  
  displayResults(results, type) {
    this.hideLoading();
    
    if (results.length === 0) {
      this.showEmpty();
      return;
    }
    
    this.resultsCount.textContent = `${results.length} résultat${results.length > 1 ? 's' : ''}`;
    
    this.resultsGrid.innerHTML = results.map(item => {
      if (type === 'coaches') {
        return this.createCoachCard(item);
      } else {
        return this.createGymCard(item);
      }
    }).join('');
    
    this.resultsGrid.querySelectorAll('.coach-card').forEach((card, index) => {
      card.addEventListener('click', () => {
        window.location.href = `/coach/${results[index].id}`;
      });
    });
    
    this.resultsGrid.querySelectorAll('.gym-card').forEach((card, index) => {
      card.addEventListener('click', () => {
        this.searchGymCoaches(results[index]);
      });
    });
  }
  
  createCoachCard(coach) {
    const gyms = searchService.getGymsByCoach(coach);
    const displayGyms = gyms.slice(0, 2);
    const moreCount = gyms.length - 2;
    const specialtiesDisplay = coach.specialties.slice(0, 3);
    
    return `
      <div class="coach-card">
        <div class="coach-header">
          <img src="${coach.photo}" alt="${coach.full_name}" class="coach-photo">
          <div class="coach-info">
            <div class="coach-name-row">
              <span class="coach-name">${coach.full_name}</span>
              ${coach.verified ? '<span class="verified-badge">✓</span>' : ''}
            </div>
            <div class="coach-rating">
              <span class="star">⭐</span>
              <span>${coach.rating.toFixed(1)}</span>
              <span class="reviews">(${coach.reviews_count} avis)</span>
            </div>
          </div>
        </div>
        
        <div class="coach-badges">
          ${specialtiesDisplay.map(spec => `
            <span class="specialty-badge">${spec}</span>
          `).join('')}
        </div>
        
        <div class="coach-gyms">
          <span>Salles :</span>
          ${displayGyms.map((gym, i) => `
            <span class="gym-name">${gym.name}${i < displayGyms.length - 1 || moreCount > 0 ? ',' : ''}</span>
          `).join('')}
          ${moreCount > 0 ? `<span class="more-gyms">+${moreCount}</span>` : ''}
        </div>
        
        <div class="coach-footer">
          <div class="coach-price">
            ${coach.price_from}€ <span>/ séance</span>
          </div>
          <button class="btn-view-profile">Voir profil</button>
        </div>
      </div>
    `;
  }
  
  createGymCard(gym) {
    return `
      <div class="gym-card">
        <img src="${gym.photo}" alt="${gym.name}" class="gym-photo">
        <div class="gym-content">
          <div class="gym-name-row">
            <h3 class="gym-name-text">${gym.name}</h3>
            <p class="gym-chain">${gym.chain}</p>
          </div>
          <p class="gym-address">📍 ${gym.address}</p>
          <p class="gym-hours">🕐 ${gym.hours}</p>
          <button class="btn-view-gym">Voir les coachs</button>
        </div>
      </div>
    `;
  }
  
  searchGymCoaches(gym) {
    this.gymInput.value = gym.name;
    this.selectedGym = { type: 'gym', value: gym.id, label: gym.name };
    this.performSearch();
  }
  
  handleFilterClick(btn) {
    btn.classList.toggle('active');
    const filter = btn.dataset.filter;
    
    if (filter === 'today') {
      this.currentFilters.availableToday = btn.classList.contains('active');
    } else if (filter === '5km') {
      this.currentFilters.maxDistance = btn.classList.contains('active') ? 5 : null;
    } else if (filter === 'price50') {
      this.currentFilters.maxPrice = btn.classList.contains('active') ? 50 : null;
    }
    
    this.applySortAndFilters();
  }
  
  showLoading() {
    this.resultsSection.style.display = 'block';
    this.loadingState.style.display = 'block';
    this.emptyState.style.display = 'none';
    this.errorState.style.display = 'none';
    this.resultsGrid.style.display = 'none';
    document.getElementById('filtersBar').style.display = 'flex';
  }
  
  hideLoading() {
    this.loadingState.style.display = 'none';
    this.resultsGrid.style.display = 'grid';
  }
  
  showEmpty() {
    this.loadingState.style.display = 'none';
    this.resultsGrid.style.display = 'none';
    this.emptyState.style.display = 'block';
  }
  
  showError() {
    this.resultsSection.style.display = 'block';
    this.loadingState.style.display = 'none';
    this.resultsGrid.style.display = 'none';
    this.emptyState.style.display = 'none';
    this.errorState.style.display = 'block';
  }
  
  updateURL(addressQuery, gymQuery) {
    const params = new URLSearchParams();
    if (addressQuery) {
      if (/^\d{5}$/.test(addressQuery)) {
        params.set('cp', addressQuery);
      } else {
        params.set('city', addressQuery);
      }
    }
    if (gymQuery) {
      params.set('salle', gymQuery);
    }
    
    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({}, '', newURL);
  }
  
  loadFromURL() {
    const params = new URLSearchParams(window.location.search);
    const city = params.get('city');
    const cp = params.get('cp');
    const salle = params.get('salle');
    
    if (city) {
      this.addressInput.value = city;
      this.selectedAddress = { type: 'city', value: city, label: city };
    } else if (cp) {
      this.addressInput.value = cp;
    }
    
    if (salle) {
      this.gymInput.value = salle;
    }
    
    if (city || cp || salle) {
      setTimeout(() => this.performSearch(), 100);
    }
  }
}

function expandRadius() {
  const app = window.searchApp;
  if (app) {
    app.currentFilters.maxDistance = 10;
    app.applySortAndFilters();
  }
}

function clearFilters() {
  const app = window.searchApp;
  if (app) {
    app.currentFilters = {
      availableToday: false,
      maxDistance: null,
      maxPrice: null
    };
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    app.applySortAndFilters();
  }
}

function retrySearch() {
  const app = window.searchApp;
  if (app) {
    app.performSearch();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.searchApp = new SearchApp();
});
