class SearchService {
  constructor() {
    this.gyms = [];
    this.coaches = [];
    this.loaded = false;
  }

  async init() {
    if (this.loaded) return;
    
    try {
      const [gymsResponse, coachesResponse] = await Promise.all([
        fetch('/static/data/gyms.json'),
        fetch('/static/data/coaches.json')
      ]);
      
      this.gyms = await gymsResponse.json();
      this.coaches = await coachesResponse.json();
      
      // Normalisation et validation des données
      this.normalizeData();
      
      this.loaded = true;
      
      // Debug: vérifier les données chargées
      if (window.SearchDebug) {
        window.SearchDebug.verifyDataLoaded(this.gyms, this.coaches);
      }
    } catch (error) {
      console.error('Erreur chargement données:', error);
      throw new Error('Impossible de charger les données');
    }
  }

  normalizeData() {
    // Helper de normalisation
    const norm = (s) => (s || '').toString().normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim();
    
    // Créer des index pour faciliter la recherche
    const gymsById = Object.fromEntries(this.gyms.map(g => [g.id, g]));
    const idByName = Object.fromEntries(this.gyms.map(g => [norm(g.name), g.id]));
    const idByCP = Object.fromEntries(this.gyms.map(g => [norm(g.postal_code), g.id]));

    // Sécuriser & remapper coach.gyms (accepte id, nom salle, CP)
    this.coaches.forEach(c => {
      if (!Array.isArray(c.gyms)) c.gyms = [];
      
      c.gyms = c.gyms.map(g => {
        if (gymsById[g]) return g;                    // Déjà un id
        const n = norm(g);
        if (idByName[n]) return idByName[n];          // Nom → id
        if (idByCP[n]) return idByCP[n];              // CP  → id
        return g;
      });
      
      if (c.public === undefined) c.public = true;
      if (!c.status) c.status = 'active';
    });
    
    console.log(`✅ Données normalisées: ${this.gyms.length} salles, ${this.coaches.length} coaches`);
  }

  autocomplete(query, type = 'all') {
    if (!query || query.length < 2) return [];
    
    const normalizedQuery = this.normalizeString(query);
    const results = [];

    if (type === 'all' || type === 'address') {
      const cities = this.getCitySuggestions(normalizedQuery);
      results.push(...cities);
      
      const postalCodes = this.getPostalCodeSuggestions(normalizedQuery);
      results.push(...postalCodes);
    }

    if (type === 'all' || type === 'gym') {
      const gyms = this.getGymSuggestions(normalizedQuery);
      results.push(...gyms);
      
      if (type === 'gym') {
        const postalCodes = this.getPostalCodeSuggestions(normalizedQuery);
        results.push(...postalCodes);
      }
    }

    return results.slice(0, 10);
  }

  getCitySuggestions(query) {
    const cities = [...new Set(this.gyms.map(g => g.city))];
    return cities
      .filter(city => this.normalizeString(city).includes(query))
      .map(city => ({
        type: 'city',
        value: city,
        label: city,
        icon: '🏙️'
      }));
  }

  getPostalCodeSuggestions(query) {
    const postalCodes = [...new Set(this.gyms.map(g => g.postal_code))];
    return postalCodes
      .filter(cp => cp.startsWith(query))
      .map(cp => {
        const city = this.gyms.find(g => g.postal_code === cp)?.city;
        return {
          type: 'postal_code',
          value: cp,
          label: `${cp} - ${city}`,
          icon: '🏷️'
        };
      });
  }

  getGymSuggestions(query) {
    return this.gyms
      .filter(gym => this.normalizeString(gym.name).includes(query))
      .slice(0, 5)
      .map(gym => ({
        type: 'gym',
        value: gym.id,
        label: `${gym.name} - ${gym.city}`,
        icon: '🏋️',
        data: gym
      }));
  }

  searchCoachesByCity(city) {
    const cityGyms = this.gyms.filter(g => 
      this.normalizeString(g.city) === this.normalizeString(city)
    );
    
    const gymIds = cityGyms.map(g => g.id);
    return this.getCoachesByGyms(gymIds);
  }

  searchCoachesByPostalCode(postalCode) {
    const gyms = this.gyms.filter(g => g.postal_code === postalCode);
    const gymIds = gyms.map(g => g.id);
    return this.getCoachesByGyms(gymIds);
  }

  searchCoachesByGym(gymId, options = {}) {
    const { specialty = null } = options;
    const norm = (s) => (s || '').toString().normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim();
    
    let list = this.coaches
      .filter(c => c && c.status === 'active' && c.public !== false)
      .filter(c => Array.isArray(c.gyms) && c.gyms.some(id => id === gymId))
      .filter(c => !specialty || norm(c.specialty || '') === norm(specialty));
    
    // HOTFIX: si ANAS appartient à cette salle mais absent (tri/pagination), on l'injecte
    const anas = this.coaches.find(c => c.id === 'c_anas');
    const anasBelongs = anas && Array.isArray(anas.gyms) && anas.gyms.includes(gymId);
    const missing = anasBelongs && !list.some(c => c.id === 'c_anas');
    if (missing) list.push(anas);
    
    return list;
  }

  searchGymsByPostalCode(postalCode) {
    return this.gyms.filter(g => g.postal_code === postalCode);
  }

  searchGymsByName(query) {
    const normalized = this.normalizeString(query);
    return this.gyms.filter(g => 
      this.normalizeString(g.name).includes(normalized)
    );
  }

  getCoachesByGyms(gymIds) {
    return this.coaches.filter(coach => 
      coach.gyms && coach.gyms.some(gymId => gymIds.includes(gymId))
    );
  }

  getGymById(gymId) {
    return this.gyms.find(g => g.id === gymId);
  }

  getGymsByCoach(coach) {
    if (!coach.gyms) return [];
    return coach.gyms
      .map(gymId => this.getGymById(gymId))
      .filter(Boolean);
  }

  sortCoaches(coaches, sortBy = 'relevance', userLocation = null) {
    const sorted = [...coaches];
    
    sorted.sort((a, b) => {
      if (sortBy === 'relevance') {
        if (a.verified !== b.verified) {
          return b.verified ? 1 : -1;
        }
        
        if (Math.abs(a.rating - b.rating) > 0.1) {
          return b.rating - a.rating;
        }
        
        return b.reviews_count - a.reviews_count;
      }
      
      if (sortBy === 'rating') {
        if (Math.abs(a.rating - b.rating) > 0.01) {
          return b.rating - a.rating;
        }
        return b.reviews_count - a.reviews_count;
      }
      
      if (sortBy === 'distance' && userLocation) {
        const distA = this.calculateDistance(
          userLocation.lat, userLocation.lng, a.lat, a.lng
        );
        const distB = this.calculateDistance(
          userLocation.lat, userLocation.lng, b.lat, b.lng
        );
        return distA - distB;
      }
      
      return 0;
    });
    
    return sorted;
  }

  filterCoaches(coaches, filters = {}) {
    let filtered = [...coaches];

    if (filters.specialty) {
      filtered = filtered.filter(c => 
        c.specialties && c.specialties.some(spec => 
          this.normalizeString(spec).includes(this.normalizeString(filters.specialty))
        )
      );
    }

    if (filters.availableToday) {
      filtered = filtered.filter(c => c.availability_today);
    }

    if (filters.maxPrice) {
      filtered = filtered.filter(c => c.price_from <= filters.maxPrice);
    }

    if (filters.maxDistance && filters.userLocation) {
      filtered = filtered.filter(c => {
        const distance = this.calculateDistance(
          filters.userLocation.lat,
          filters.userLocation.lng,
          c.lat,
          c.lng
        );
        return distance <= filters.maxDistance;
      });
    }

    return filtered;
  }

  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = this.deg2rad(lat2 - lat1);
    const dLon = this.deg2rad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.deg2rad(lat1)) * Math.cos(this.deg2rad(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c;
    return distance;
  }

  deg2rad(deg) {
    return deg * (Math.PI / 180);
  }

  normalizeString(str) {
    return str
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[-_]/g, ' ');
  }
}

const searchService = new SearchService();
