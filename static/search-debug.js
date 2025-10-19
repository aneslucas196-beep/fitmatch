// === FONCTIONS DE DEBUG POUR LA RECHERCHE ===

function normalize(s) {
  return (s || '')
    .toString()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim();
}

function debugLog(title, payload) {
  console.log(`\n==== ${title} ====`);
  try {
    console.log(JSON.stringify(payload, null, 2));
  } catch (e) {
    console.log(payload);
  }
}

// Fonction pour vérifier les données chargées
function verifyDataLoaded(gyms, coaches) {
  debugLog('GYMS_COUNT', { count: gyms?.length });
  debugLog('COACHES_COUNT', { count: coaches?.length });

  // Vérifier ANAS et Fitness Park Maurepas
  const anas = coaches?.find(c => 
    normalize(c.full_name) === 'anas' || 
    c.id === 'c_anas'
  );
  
  const gMaurepas = gyms?.find(g => 
    normalize(g.name) === 'fitness park maurepas' || 
    g.id === 'fp_maurepas'
  );

  debugLog('CHECK_ENTITIES', {
    anas_exists: !!anas,
    gMaurepas_exists: !!gMaurepas,
    anas_full_data: anas || null,
    gMaurepas_full_data: gMaurepas || null
  });

  // Vérifier les salles d'ANAS
  if (anas) {
    debugLog('ANAS_GYMS_FIELD', anas.gyms || null);
    if (!Array.isArray(anas.gyms)) {
      console.warn('⚠️ ANAS.gyms is not an array!');
    } else {
      console.log(`✅ ANAS entraîne dans ${anas.gyms.length} salle(s)`);
    }
  } else {
    console.error('❌ ANAS NOT FOUND in coaches data!');
  }

  return { anas, gMaurepas };
}

// Fonction pour tester la recherche par salle
function debugCoachesForGym(coaches, gymId, specialty = null) {
  const result = coaches
    .filter(c => c && (c.public !== false))
    .filter(c => (c.status || 'active') === 'active')
    .filter(c => Array.isArray(c.gyms) && c.gyms.some(g => normalize(g) === normalize(gymId)))
    .filter(c => !specialty || c.specialties?.some(s => normalize(s) === normalize(specialty)));

  debugLog('RESULT_FOR_GYM', {
    gymId,
    specialty,
    count: result.length,
    coach_ids: result.map(c => c.id),
    coach_names: result.map(c => c.full_name)
  });

  return result;
}

// Fonction pour tester la recherche par code postal
function debugCoachesByPostalCode(gyms, coaches, postalCode) {
  const gymsInCP = gyms.filter(g => g.postal_code === postalCode);
  const gymIds = gymsInCP.map(g => g.id);
  
  const coachesInCP = coaches.filter(c => 
    c.gyms && c.gyms.some(gymId => gymIds.includes(gymId))
  );

  debugLog('SEARCH_BY_POSTAL_CODE', {
    postal_code: postalCode,
    gyms_found: gymsInCP.length,
    gym_names: gymsInCP.map(g => g.name),
    coaches_found: coachesInCP.length,
    coach_names: coachesInCP.map(c => c.full_name)
  });

  return coachesInCP;
}

// Export pour utilisation
if (typeof window !== 'undefined') {
  window.SearchDebug = {
    normalize,
    debugLog,
    verifyDataLoaded,
    debugCoachesForGym,
    debugCoachesByPostalCode
  };
}
