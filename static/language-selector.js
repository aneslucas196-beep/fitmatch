/**
 * Sélecteur de langue - compatible tous templates (index, base, login, etc.).
 * Utilise style.display pour garantir le toggle sur tous les navigateurs.
 */
function toggleLanguageMenu() {
    const menu = document.getElementById('langMenu');
    if (!menu) return;
    var isHidden = menu.style.display === 'none' || (menu.classList && menu.classList.contains('hidden'));
    menu.style.display = isHidden ? 'block' : 'none';
    if (menu.classList) {
        if (isHidden) menu.classList.remove('hidden'); else menu.classList.add('hidden');
    }
}

document.addEventListener('click', function(e) {
    const menu = document.getElementById('langMenu');
    const btn = e.target.closest('.language-selector');
    if (!btn && menu) {
        menu.style.display = 'none';
        if (menu.classList) menu.classList.add('hidden');
    }
});
