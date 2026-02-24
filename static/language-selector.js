/**
 * Sélecteur de langue - script externalisé pour CSP (éviter unsafe-inline).
 * Compatible base.html (classList hidden) et language_selector.html (style.display).
 */
function toggleLanguageMenu() {
    const menu = document.getElementById('langMenu');
    if (!menu) return;
    if (menu.classList && typeof menu.classList.toggle === 'function') {
        menu.classList.toggle('hidden');
    } else {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

document.addEventListener('click', function(e) {
    const menu = document.getElementById('langMenu');
    const btn = e.target.closest('.language-selector');
    if (!btn && menu) {
        if (menu.classList && typeof menu.classList.add === 'function') {
            menu.classList.add('hidden');
        }
        if (menu.style) menu.style.display = 'none';
    }
});
