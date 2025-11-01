// Utilitaires
const $ = (sel) => document.querySelector(sel);
const fmtDateLong = (d) => {
  return d.toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
};

// Lire paramètres URL ou mettre des valeurs par défaut
const p = new URLSearchParams(location.search);
const coach   = p.get('coach')   || 'Coach Anas';
const service = p.get('service') || 'Séance musculation';
const duration= p.get('duration')|| '60';
const price   = p.get('price')   || '40';
const gym     = p.get('gym')     || 'BasicFit Élancourt';

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
  const start = 9, end = 20; // 9h -> 20h
  for(let h=start; h<=end; h++){
    for(let m of [0,30]){
      const t = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
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

// ===== AUTHENTIFICATION =====
const AUTH_KEY = 'fm_user';

function getUser(){
  try { 
    return JSON.parse(localStorage.getItem(AUTH_KEY)); 
  } catch(e) { 
    return null; 
  }
}

function logout(){
  localStorage.removeItem(AUTH_KEY);
  location.reload();
}

function saveRedirectUrl(){
  sessionStorage.setItem('redirect_to', location.pathname + location.search + location.hash);
}

function goToSignup(){
  saveRedirectUrl();
  location.href = '/signup';
}

function goToLogin(){
  saveRedirectUrl();
  location.href = '/login';
}

function renderIdentification(){
  const user = getUser();
  const idLogged = $('#id-logged');
  const idGuest = $('#id-guest');
  
  if(user && user.email){
    // Affiche Nom + Email, cache les boutons
    $('#id-name').textContent = user.name || 'Compte FitMatch';
    $('#id-email').textContent = user.email;
    
    idLogged.classList.remove('hide');
    idGuest.classList.add('hide');
  } else {
    // Version non connectée
    idLogged.classList.add('hide');
    idGuest.classList.remove('hide');
  }
}

// Event listeners
$('#btn-signup').addEventListener('click', goToSignup);
$('#btn-login').addEventListener('click', goToLogin);
$('#btn-logout').addEventListener('click', logout);

// Init
renderIdentification();
