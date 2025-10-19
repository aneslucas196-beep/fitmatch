class SearchApp {
  constructor() {
    this.addressInput = document.getElementById('addressInput');
    this.specialtySelect = document.getElementById('specialtySelect');
    this.searchBtn = document.getElementById('searchBtn');
    this.addressAutocomplete = document.getElementById('addressAutocomplete');
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
    this.currentResults = [];
    this.userLocation = null;
    this.currentFilters = {
      availableToday: false,
      maxDistance: null,
      maxPrice: null,
      specialty: null
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
    
    this.searchBtn.addEventListener('click', () => this.performSearch());
    
    this.addressInput.addEventListener('keypress', (e) => {
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
  }
  
  async performSearch() {
    const addressQuery = this.addressInput.value.trim();
    const specialtyQuery = this.specialtySelect.value;
    
    if (!addressQuery && !specialtyQuery) {
      return;
    }
    
    // Si seulement une adresse (sans spécialité) → Rediriger vers Google Maps des salles
    if (addressQuery && !specialtyQuery) {
      window.location.href = `/gyms-map?address=${encodeURIComponent(addressQuery)}`;
      return;
    }
    
    this.showLoading();
    this.updateURL(addressQuery, specialtyQuery);
    
    try {
      let results = [];
      let resultType = 'coaches';
      
      // Recherche par adresse/ville + spécialité
      if (addressQuery) {
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
      } else {
        // Si pas d'adresse, prendre tous les coachs
        results = searchService.coaches;
      }
      
      // Filtrer par spécialité (obligatoire à ce stade)
      if (specialtyQuery) {
        this.currentFilters.specialty = specialtyQuery;
        const specialtyLabel = this.specialtySelect.options[this.specialtySelect.selectedIndex].text.replace(/^[^\s]+\s/, '');
        this.resultsTitle.textContent = addressQuery 
          ? `Coachs ${specialtyLabel}` 
          : `Coachs ${specialtyLabel}`;
      } else {
        this.currentFilters.specialty = null;
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
      return this.createCoachCard(item);
    }).join('');
    
    this.resultsGrid.querySelectorAll('.coach-card').forEach((card, index) => {
      card.addEventListener('click', () => {
        window.location.href = `/coach/${results[index].id}`;
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
  
  updateURL(addressQuery, specialtyQuery) {
    const params = new URLSearchParams();
    if (addressQuery) {
      if (/^\d{5}$/.test(addressQuery)) {
        params.set('cp', addressQuery);
      } else {
        params.set('city', addressQuery);
      }
    }
    if (specialtyQuery) {
      params.set('specialty', specialtyQuery);
    }
    
    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({}, '', newURL);
  }
  
  loadFromURL() {
    const params = new URLSearchParams(window.location.search);
    const city = params.get('city');
    const cp = params.get('cp');
    const specialty = params.get('specialty');
    
    if (city) {
      this.addressInput.value = city;
      this.selectedAddress = { type: 'city', value: city, label: city };
    } else if (cp) {
      this.addressInput.value = cp;
    }
    
    if (specialty) {
      this.specialtySelect.value = specialty;
    }
    
    if (city || cp || specialty) {
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
      maxPrice: null,
      specialty: null
    };
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    if (app.specialtySelect) {
      app.specialtySelect.value = '';
    }
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
