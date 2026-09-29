const PersonsModule = (() => {
  let cache = [];
  const load = async () => {
    const grid = document.getElementById('personsGrid');
    if (!grid) return;
    try {
      if (BioAPI.getSettings().demoMode) {
        cache = RegisterModule.demoPersons();
        try { const api = await BioAPI.persons(); cache = api.persons || api || cache; } catch {}
      } else { const api = await BioAPI.persons(); cache = api.persons || api || []; }
      render(cache);
    } catch { render(RegisterModule.demoPersons()); }
  };
  const render = list => {
    const grid = document.getElementById('personsGrid');
    if (!list.length) { grid.innerHTML = '<div class="empty-state">Aucun profil enregistré.</div>'; return; }
    grid.innerHTML = list.map(p => `
      <article class="person-card">
        <div class="person-avatar">${(p.first_name || '?')[0]}${(p.last_name || '')[0] || ''}</div>
        <h3>${p.first_name || ''} ${p.last_name || ''}</h3>
        <p class="muted">${p.matricule || 'Sans matricule'} · ${p.department || '—'}</p>
        <span class="badge neutral">${p.status || 'Actif'}</span>
        <div class="profile-grid">
          <div class="profile-item"><span>Fonction</span><strong>${p.role || '—'}</strong></div>
          <div class="profile-item"><span>Créé le</span><strong>${p.created_at || '—'}</strong></div>
        </div>
      </article>`).join('');
  };
  const init = () => {
    const search = document.getElementById('personSearch');
    document.getElementById('refreshPersons')?.addEventListener('click', load);
    search?.addEventListener('input', () => {
      const q = search.value.toLowerCase();
      render(cache.filter(p => JSON.stringify(p).toLowerCase().includes(q)));
    });
  };
  return { init, load };
})();
