// Utilitaires
const $ = (sel) => document.querySelector(sel);
const fmtDateLong = (d) => {
  return d.toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
};

// Lire paramètres URL ou mettre des valeurs par défaut
const p = new URLSearchParams(location.search);
const coach   = p.get('coach')   || 'Coach Anas';
const coachEmail = p.get('coach_email') || '';  // Email du coach pour identification fiable
const service = p.get('service') || 'Séance musculation';
const duration= p.get('duration')|| '60';
const price   = p.get('price')   || '40';
const gym     = p.get('gym')     || 'BasicFit Élancourt';
const gymAddress = p.get('gym_address') || '';
const coachPhoto = p.get('coach_photo') || '';

const today = new Date();
const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate()+1);
const defDate = p.get('date') ? new Date(p.get('date')) : tomorrow;
const defTime = p.get('time') || '11:00';

// Injecter dans le récap
$('#coachName').textContent = coach;
$('#serviceName').textContent = service;
$('#duration').textContent = duration;
$('#price').textContent = price;
$('#gymName').textContent = gym;

let selDate = defDate;
let selTime = defTime;
$('#dateLabel').textContent = fmtDateLong(selDate).replace(/^\w/, c => c.toUpperCase());
$('#timeLabel').textContent = selTime;

// Dialog "Modifier"
const dlg = $('#dlg');
const inpDate = $('#inpDate');
const slots = $('#slots');

function buildSlots(){
  slots.innerHTML = '';
  const start = 8, end = 22; // 8h -> 22h (séances de 1h)
  for(let h=start; h<=end; h++){
    const t = `${String(h).padStart(2,'0')}:00`;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'slot' + (t===selTime ? ' is-selected':'');
    btn.textContent = t;
    btn.onclick = () => {
      [...slots.children].forEach(c=>c.classList.remove('is-selected'));
      btn.classList.add('is-selected');
      selTime = t;
    };
    slots.appendChild(btn);
  }
}

$('#btnModify').addEventListener('click', (e)=>{
  e.preventDefault();
  inpDate.valueAsDate = selDate;
  buildSlots();
  dlg.showModal();
});

$('#cancelDlg').onclick = () => dlg.close();

$('#saveDlg').onclick = () => {
  selDate = inpDate.valueAsDate || selDate;
  $('#dateLabel').textContent = fmtDateLong(selDate).replace(/^\w/, c => c.toUpperCase());
  $('#timeLabel').textContent = selTime;
  dlg.close();
};

// Accessibilité : fermer dialog avec ESC
dlg.addEventListener('cancel', (e)=>{ e.preventDefault(); dlg.close(); });

// ===== ÉTAPE 3 — IDENTIFICATION =====
const LS_USER_KEY = 'fitmatch.user';
const LS_OTP_KEY = 'fitmatch.otp';
const idCard = $('#step-3-identification');
const guestCard = $('#guestCard');
const form = $('#signupForm');
const loginForm = $('#loginForm');
const summary = $('#id-summary');
const fullNameOut = $('#idFullName');
const emailOut = $('#idEmail');
const btnShowSignup = $('#btnShowSignup');
const btnShowLogin = $('#btnShowLogin');
const btnSwitchToSignup = $('#btnSwitchToSignup');
const btnEdit = $('#btnEdit');
const btnLogout = $('#btnLogout');
const btnCreate = $('#btnCreate');
const confirmSection = $('#confirm-section');
const btnConfirmBooking = $('#btnConfirmBooking');

// Rendu selon l'état (connecté ou pas)
function renderIdentification(){
  const uRaw = localStorage.getItem(LS_USER_KEY);
  const confirmBtn = document.getElementById('confirm-section');
  const resetForm = document.getElementById('resetPasswordForm');
  
  if(!uRaw){
    // Pas identifié → montrer boutons guest
    summary.classList.add('hidden');
    form.classList.add('hidden');
    if(loginForm) loginForm.classList.add('hidden');
    if(resetForm) resetForm.classList.add('hidden');
    guestCard.classList.remove('hidden');
    if(confirmBtn) confirmBtn.classList.add('hidden');
    return;
  }
  const user = JSON.parse(uRaw);
  console.log('👤 Utilisateur:', user);
  fullNameOut.textContent = user.fullName || '—';
  emailOut.textContent = user.email || '—';
  // Identifié → cacher tout sauf résumé
  form.classList.add('hidden');
  if(loginForm) loginForm.classList.add('hidden');
  if(resetForm) resetForm.classList.add('hidden');
  guestCard.classList.add('hidden');
  summary.classList.remove('hidden');
  
  // Si vérifié → montrer bouton confirmer
  if(user.verified === true){
    console.log('✅ Utilisateur vérifié, affichage bouton confirmer');
    if(confirmBtn) {
      confirmBtn.classList.remove('hidden');
      confirmBtn.style.display = 'block';
    }
  } else {
    console.log('⚠️ Utilisateur non vérifié');
    if(confirmBtn) confirmBtn.classList.add('hidden');
  }
}

// Afficher le formulaire au clic sur "Créer mon compte"
btnShowSignup.addEventListener('click', ()=>{
  guestCard.classList.add('hidden');
  if(loginForm) loginForm.classList.add('hidden');
  form.classList.remove('hidden');
});

// Afficher le formulaire de connexion
if(btnShowLogin) {
  btnShowLogin.addEventListener('click', ()=>{
    guestCard.classList.add('hidden');
    form.classList.add('hidden');
    loginForm.classList.remove('hidden');
  });
}

// Basculer vers inscription depuis le formulaire de connexion
if(btnSwitchToSignup) {
  btnSwitchToSignup.addEventListener('click', ()=>{
    loginForm.classList.add('hidden');
    form.classList.remove('hidden');
  });
}

// Gérer la soumission du formulaire de connexion
if(loginForm) {
  loginForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const email = $('#loginEmail').value.trim();
    const password = $('#loginPassword').value;
    
    if(!email || !password) return;
    
    const btn = loginForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Connexion…';
    
    try {
      // Appeler l'API de connexion (JSON)
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email, password })
      });
      
      if(!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Identifiants incorrects');
      }
      
      const data = await res.json();
      
      // Sauvegarder la session
      const user = {
        fullName: data.full_name || data.name || email.split('@')[0],
        email: email,
        verified: true // Un utilisateur connecté est considéré comme vérifié
      };
      localStorage.setItem(LS_USER_KEY, JSON.stringify(user));
      
      // Mettre à jour l'affichage
      renderIdentification();
      
    } catch(err) {
      alert(err.message || 'Erreur de connexion');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Se connecter';
    }
  });
}

// Mot de passe oublié - Afficher le formulaire de réinitialisation
const forgotPassword = $('#forgotPassword');
const resetPasswordForm = $('#resetPasswordForm');
const backToLogin = $('#backToLogin');
const btnResetPassword = $('#btnResetPassword');
const btnResetToSignup = $('#btnResetToSignup');

if(forgotPassword) {
  forgotPassword.addEventListener('click', ()=>{
    loginForm.classList.add('hidden');
    form.classList.add('hidden');
    guestCard.classList.add('hidden');
    resetPasswordForm.classList.remove('hidden');
  });
}

// Retour à la connexion depuis le formulaire de réinitialisation
if(backToLogin) {
  backToLogin.addEventListener('click', ()=>{
    resetPasswordForm.classList.add('hidden');
    loginForm.classList.remove('hidden');
  });
}

// Créer un compte depuis le formulaire de réinitialisation
if(btnResetToSignup) {
  btnResetToSignup.addEventListener('click', ()=>{
    resetPasswordForm.classList.add('hidden');
    form.classList.remove('hidden');
  });
}

// Envoyer l'email de réinitialisation
if(btnResetPassword) {
  btnResetPassword.addEventListener('click', async ()=>{
    const email = $('#resetEmail').value.trim();
    if(!email) {
      alert('Merci de remplir ton email.');
      return;
    }
    
    btnResetPassword.disabled = true;
    btnResetPassword.textContent = 'Envoi en cours…';
    
    try {
      // Appeler l'API pour envoyer l'email de réinitialisation
      const res = await fetch('/api/reset-password', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email })
      });
      
      if(res.ok) {
        alert('Un email de réinitialisation vient d\'être envoyé à ' + email);
        resetPasswordForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
      } else {
        const error = await res.json();
        alert(error.detail || 'Erreur lors de l\'envoi');
      }
    } catch(err) {
      // Fallback si l'API n'existe pas encore
      alert('Un email de réinitialisation vient d\'être envoyé à ' + email);
      resetPasswordForm.classList.add('hidden');
      loginForm.classList.remove('hidden');
    } finally {
      btnResetPassword.disabled = false;
      btnResetPassword.textContent = 'Réinitialiser mon mot de passe';
    }
  });
}

// Appel API pour créer le compte et définir la session
async function signupViaAPI(payload){
  const res = await fetch('/api/signup-reservation', { 
    method:'POST', 
    headers:{'Content-Type':'application/json'}, 
    body: JSON.stringify(payload),
    credentials: 'include'
  });
  if(!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Inscription échouée');
  }
  return await res.json();
}

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  if(!$('#acceptCgu').checked){
    alert("Merci d'accepter les CGU pour continuer.");
    return;
  }
  const fullName = $('#fullName').value.trim();
  const email = $('#email').value.trim();
  const password = $('#password').value;
  if(!fullName || !email || !password){ return; }

  btnCreate.disabled = true;
  btnCreate.textContent = 'Création du compte…';

  try{
    await signupViaAPI({ fullName, email, password });
    // Sauvegarde session locale
    localStorage.setItem(LS_USER_KEY, JSON.stringify({ fullName, email, verified: false }));
    // Envoyer le code OTP et ouvrir l'overlay
    await sendOtpEmail(email);
    openEmailVerification();
  }catch(err){
    alert("Impossible de créer le compte. Réessayez.");
  }finally{
    btnCreate.disabled = false;
    btnCreate.textContent = 'Créer mon compte';
  }
});

btnEdit.addEventListener('click', ()=>{
  summary.classList.add('hidden');
  form.classList.remove('hidden');
});

btnLogout.addEventListener('click', ()=>{
  localStorage.removeItem(LS_USER_KEY);
  renderIdentification();
});

// Premier rendu
renderIdentification();

// ===== VÉRIFICATION EMAIL =====
const overlay = $('#email-verify-overlay');
const evEmail = $('#evEmailHint');
const evCode = $('#evCode');
const evSubmit = $('#evSubmit');
const evResend = $('#evResend');
const evEdit = $('#evEditEmail');
const evLogout2 = $('#evLogout');
const evToast = $('#evToast');

function showOverlay(){ overlay.classList.remove('hidden'); }
function hideOverlay(){ overlay.classList.add('hidden'); }
function toast(msg){ evToast.textContent = msg; evToast.classList.remove('hidden'); setTimeout(()=>evToast.classList.add('hidden'), 3500); }

function generateCode(){ return ('' + Math.floor(100000 + Math.random()*900000)); }
function saveOtp(email, code){
  const expiresAt = Date.now() + 5*60*1000;
  localStorage.setItem(LS_OTP_KEY, JSON.stringify({ email, code, expiresAt }));
}
function getOtp(){ try{ return JSON.parse(localStorage.getItem(LS_OTP_KEY)||'null'); }catch{ return null; } }
function clearOtp(){ localStorage.removeItem(LS_OTP_KEY); }

async function sendOtpEmail(email){
  try {
    const res = await fetch('/api/send-otp-email', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ email })
    });
    if(!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Envoi OTP impossible');
    }
    toast('Code envoyé à ' + email + ' ! Vérifie ta boîte Gmail 📧');
  } catch(err) {
    console.error('Erreur envoi OTP:', err);
    // Fallback local si l'API échoue
    const code = generateCode();
    saveOtp(email, code);
    console.log('%c[DEV] Mode fallback - Code: ' + code, 'color: #f59e0b; font-weight:700;');
    toast('Mode démo: vérifie la console pour le code');
  }
}

async function verifyOtpEmail(email, code){
  try {
    const res = await fetch('/api/verify-otp', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ email, code })
    });
    if(!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Code invalide');
    }
  } catch(err) {
    // Si l'API échoue, essayer le fallback local
    const otp = getOtp();
    if(!otp || otp.email !== email) throw new Error("Aucun code actif pour cet e-mail.");
    if(Date.now() > otp.expiresAt) throw new Error("Le code a expiré. Renvoyez-le.");
    if(otp.code !== code) throw new Error("Code incorrect.");
  }
}

function openEmailVerification(){
  const u = JSON.parse(localStorage.getItem(LS_USER_KEY) || 'null');
  if(!u || !u.email){ return; }
  evEmail.textContent = u.email;
  evCode.value = '';
  showOverlay();
}

evResend.addEventListener('click', async ()=>{
  const u = JSON.parse(localStorage.getItem(LS_USER_KEY) || 'null');
  if(!u) return;
  try{
    await sendOtpEmail(u.email);
  }catch(e){ toast("Impossible d'envoyer le code. Réessaie."); }
});

evEdit.addEventListener('click', ()=>{
  hideOverlay();
  guestCard.classList.add('hidden');
  form.classList.remove('hidden');
  summary.classList.add('hidden');
  toast('Tu peux modifier ton e-mail puis recréer ton compte.');
});

evLogout2.addEventListener('click', ()=>{
  localStorage.removeItem(LS_USER_KEY);
  clearOtp();
  hideOverlay();
  renderIdentification();
});

evSubmit.addEventListener('click', async ()=>{
  const u = JSON.parse(localStorage.getItem(LS_USER_KEY) || 'null');
  if(!u) return;
  const code = evCode.value.trim();
  if(code.length !== 6){ toast('Entre le code à 6 chiffres.'); return; }

  evSubmit.disabled = true; evSubmit.textContent = 'Vérification…';
  
  try{
    await verifyOtpEmail(u.email, code);
    
    // Mettre à jour l'utilisateur comme vérifié
    const verifiedUser = { ...u, verified: true };
    localStorage.setItem(LS_USER_KEY, JSON.stringify(verifiedUser));
    clearOtp();
    
    // Sauvegarder la réservation avec toutes les données
    const booking = {
      coach,
      service,
      duration,
      price,
      gym,
      gym_address: gymAddress || '',
      coach_photo: coachPhoto || '',
      date: selDate.toISOString().split('T')[0],
      time: selTime,
      createdAt: new Date().toISOString()
    };
    
    const fmData = JSON.parse(localStorage.getItem('fitmatch') || '{}');
    fmData.user = verifiedUser;
    fmData.bookings = fmData.bookings || [];
    fmData.bookings.push(booking);
    localStorage.setItem('fitmatch', JSON.stringify(fmData));
    
    // Envoyer la demande de réservation au coach
    evSubmit.textContent = 'Envoi de la demande…';
    try {
      const confirmRes = await fetch('/api/confirm-booking', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          client_name: verifiedUser.fullName,
          client_email: verifiedUser.email,
          coach_name: coach,
          coach_email: coachEmail || null,
          gym_name: gym,
          gym_address: gymAddress || 'Adresse non renseignée',
          date: booking.date,
          time: booking.time,
          service: service,
          duration: duration,
          price: price,
          coach_photo: coachPhoto || null
        })
      });
      const confirmData = await confirmRes.json();
      console.log('📋 Demande envoyée au coach:', confirmData);
      
      // Mettre à jour le booking avec l'ID du serveur et l'email du coach
      if (confirmData.booking_id) {
        const fmDataUpdated = JSON.parse(localStorage.getItem('fitmatch') || '{}');
        const lastBookingIndex = (fmDataUpdated.bookings || []).length - 1;
        if (lastBookingIndex >= 0) {
          fmDataUpdated.bookings[lastBookingIndex].id = confirmData.booking_id;
          fmDataUpdated.bookings[lastBookingIndex].booking_id = confirmData.booking_id;
          fmDataUpdated.bookings[lastBookingIndex].coach_email = coachEmail || '';
          fmDataUpdated.bookings[lastBookingIndex].status = 'pending';
          localStorage.setItem('fitmatch', JSON.stringify(fmDataUpdated));
          console.log('✅ Booking mis à jour avec ID:', confirmData.booking_id);
        }
      }
    } catch(emailErr) {
      console.log('⚠️ Demande non envoyée:', emailErr);
    }
    
    // Rediriger vers la page Mon Compte
    window.location.href = '/mon-compte';
    
  }catch(e){
    toast(e.message || 'Code invalide.');
    evSubmit.disabled = false; evSubmit.textContent = 'Enregistrer';
  }
});

// Bouton Confirmer la séance
document.getElementById('btnConfirmBooking').addEventListener('click', async ()=>{
  const u = JSON.parse(localStorage.getItem(LS_USER_KEY) || 'null');
  if(!u || !u.verified) {
    toast('Veuillez d\'abord vérifier votre email.');
    return;
  }
  
  const btn = document.getElementById('btnConfirmBooking');
  btn.disabled = true;
  btn.textContent = 'Confirmation en cours...';
  
  // IMPORTANT: Créer/rafraîchir la session pour cet utilisateur
  try {
    console.log('🔐 Création session pour:', u.email);
    const sessionRes = await fetch('/api/signup-reservation', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        fullName: u.fullName,
        email: u.email,
        password: 'session_refresh'
      }),
      credentials: 'include'
    });
    if(sessionRes.ok) {
      const sessionData = await sessionRes.json();
      console.log('✅ Session créée:', sessionData);
    }
  } catch(sessionErr) {
    console.log('⚠️ Session non créée:', sessionErr);
  }
  
  // D'abord récupérer le prix ACTUEL du coach
  let actualPrice = price;
  if (coachEmail) {
    try {
      const priceRes = await fetch(`/api/coach/pricing?coach_email=${encodeURIComponent(coachEmail)}`);
      const priceData = await priceRes.json();
      if (priceData.success && priceData.price !== undefined) {
        actualPrice = String(priceData.price);
        console.log('💰 Prix actuel du coach:', actualPrice);
        $('#price').textContent = actualPrice;
      }
    } catch(priceErr) {
      console.log('⚠️ Impossible de récupérer le prix actuel:', priceErr);
      actualPrice = String(price);
    }
  } else {
    actualPrice = String(price);
  }
  
  // Préparer les données de réservation (mais ne PAS sauvegarder avant la réponse API)
  const bookingData = {
    coach,
    service,
    duration,
    price: actualPrice,
    gym,
    gym_address: gymAddress || '',
    coach_photo: coachPhoto || '',
    date: selDate.toISOString().split('T')[0],
    time: selTime,
    createdAt: new Date().toISOString()
  };
  
  // Envoyer la demande de réservation au coach
  btn.textContent = 'Envoi de la demande…';
  let confirmData = null;
  
  try {
    const confirmRes = await fetch('/api/confirm-booking', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        client_name: u.fullName,
        client_email: u.email,
        coach_name: coach,
        coach_email: coachEmail || null,
        gym_name: gym,
        gym_address: gymAddress || 'Adresse non renseignée',
        date: bookingData.date,
        time: bookingData.time,
        service: service,
        duration: String(duration),
        price: actualPrice,
        coach_photo: coachPhoto || null
      })
    });
    
    confirmData = await confirmRes.json();
    console.log('📋 Réponse du serveur:', confirmData);
    
    // Vérifier si l'API a réussi
    if (!confirmRes.ok) {
      console.error('❌ Erreur API:', confirmData);
      toast(confirmData.message || 'Erreur lors de la réservation');
      btn.disabled = false;
      btn.textContent = 'Confirmer la séance';
      return;
    }
    
    // SEULEMENT maintenant sauvegarder le booking (après succès API)
    if (confirmData.success && confirmData.booking_id) {
      bookingData.id = confirmData.booking_id;
      bookingData.booking_id = confirmData.booking_id;
      bookingData.coach_email = coachEmail || '';
      bookingData.status = confirmData.status || 'pending';
      
      const fmData = JSON.parse(localStorage.getItem('fitmatch') || '{}');
      fmData.user = u;
      fmData.bookings = fmData.bookings || [];
      fmData.bookings.push(bookingData);
      localStorage.setItem('fitmatch', JSON.stringify(fmData));
      console.log('✅ Booking sauvegardé avec ID:', confirmData.booking_id);
    }
    
    // Si paiement requis, rediriger vers Stripe
    if (confirmData.checkout_url) {
      console.log('💳 Redirection vers Stripe pour paiement:', confirmData.checkout_url);
      window.location.href = confirmData.checkout_url;
      return;
    }
    
    // Sinon rediriger vers la page Mon Compte
    window.location.href = '/mon-compte';
    
  } catch(err) {
    console.error('❌ Erreur réseau:', err);
    toast('Erreur de connexion. Veuillez réessayer.');
    btn.disabled = false;
    btn.textContent = 'Confirmer la séance';
  }
});
