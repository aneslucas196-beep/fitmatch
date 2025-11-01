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

// === AUTHENTIFICATION ===
function getUser(){
  try {
    return JSON.parse(localStorage.getItem('fm_user'));
  } catch(e) {
    return null;
  }
}

function renderUser(){
  const user = getUser();
  const userCard = $('#userCard');
  const guestCard = $('#guestCard');
  
  if(user && user.email){
    // Afficher nom + email
    $('#userName').textContent = user.name || 'Utilisateur';
    $('#userEmail').textContent = user.email;
    userCard.classList.remove('hide');
    guestCard.classList.add('hide');
  } else {
    // Afficher boutons signup/login
    userCard.classList.add('hide');
    guestCard.classList.remove('hide');
  }
}

// Bouton signup : sauvegarder l'URL actuelle avant redirection
$('#btnSignup').addEventListener('click', ()=>{
  sessionStorage.setItem('redirect_to', location.pathname + location.search);
  location.href = '/static/signup.html';
});

// Init
renderUser();
