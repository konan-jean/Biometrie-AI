const DashboardModule = (() => {
  const refresh = async () => {
    let persons = RegisterModule.demoPersons();
    let history = HistoryModule.all();
    if (!BioAPI.getSettings().demoMode) {
      try { const p = await BioAPI.persons(); persons = p.persons || p || persons; } catch {}
      try { const h = await BioAPI.history(); history = h.history || h || history; } catch {}
    } else {
      try { const p = await BioAPI.persons(); persons = p.persons || p || persons; } catch {}
      try { const h = await BioAPI.history(); history = h.history || h || history; } catch {}
    }
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set('statPersons', persons.length); set('statScans', history.length);
    const valid = history.filter(h => BioUtils.decisionClass(h.decision) === 'validée').length;
    const uncertain = history.filter(h => BioUtils.decisionClass(h.decision) === 'incertaine').length;
    const suspect = history.filter(h => BioUtils.decisionClass(h.decision) === 'suspecte').length;
    const refused = history.filter(h => BioUtils.decisionClass(h.decision) === 'refusée').length;
    set('statValid', valid); set('statUncertain', uncertain); set('statSuspect', suspect);
    const avg = history.length ? Math.round(history.reduce((s,h)=>s+Number(h.reliabilityScore||h.reliability_score||0),0)/history.length) : 0; set('statReliability', `${avg}%`);
    const recent = document.getElementById('recentScans');
    if (recent) recent.innerHTML = history.slice(0,5).map(h => `<tr><td>${h.time || h.scan_time || '—'}</td><td>${h.name || h.identity || 'Inconnu'}</td><td><span class="badge ${BioUtils.decisionClass(h.decision)}">${h.decision || '—'}</span></td><td>${BioUtils.pct(h.reliabilityScore || h.reliability_score)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Aucun scan récent.</td></tr>';
    const stack = document.getElementById('decisionStack');
    if (stack) stack.innerHTML = [['Validées',valid,'success'],['Incertaines',uncertain,'warning'],['Suspectes',suspect,'danger'],['Refusées',refused,'danger']].map(x=>`<div class="decision-item"><span>${x[0]}</span><span class="badge ${x[2]}">${x[1]}</span></div>`).join('');
  };
  return { refresh };
})();

const App = (() => {
  const titles = { dashboard: ['Système intelligent','Tableau de bord'], register: ['Création profil','Enregistrement'], scanner: ['Scan temps réel','Scanner robuste'], persons: ['Base locale','Personnes enregistrées'], history: ['Traçabilité','Historique'], admin: ['Administration sécurisée','Espace admin'], settings: ['Configuration','Paramètres'] };
  const navigate = page => {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${page}`)?.classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
    document.getElementById('pageEyebrow').textContent = titles[page]?.[0] || '';
    document.getElementById('pageTitle').textContent = titles[page]?.[1] || '';
    document.getElementById('appShell').classList.remove('sidebar-open');
  };
  const checkBackend = async () => {
    const dot = document.getElementById('backendDot'); const label = document.getElementById('backendStatus');
    try { await BioAPI.health(); dot.className='status-dot online'; label.textContent='Backend en ligne'; }
    catch { dot.className='status-dot offline'; label.textContent=BioAPI.getSettings().demoMode ? 'Mode démonstration' : 'Backend hors ligne'; }
  };
  const init = () => {
    document.querySelectorAll('[data-page]').forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.page)));
    document.querySelectorAll('[data-go]').forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.go)));
    document.getElementById('menuToggle')?.addEventListener('click', () => document.getElementById('appShell').classList.toggle('sidebar-open'));
    document.getElementById('themeToggle')?.addEventListener('click', () => document.body.classList.toggle('dark'));
    setInterval(() => { const c = document.getElementById('clock'); if (c) c.textContent = BioUtils.nowParts().time; }, 1000);
    document.getElementById('settingsForm')?.addEventListener('submit', e => { e.preventDefault(); const fd = new FormData(e.target); BioAPI.saveSettings({ apiBase: fd.get('apiBase'), faceThreshold: fd.get('faceThreshold'), reliabilityThreshold: fd.get('reliabilityThreshold'), livenessThreshold: fd.get('livenessThreshold'), demoMode: Boolean(fd.get('demoMode')) }); BioUtils.toast('Paramètres sauvegardés.', 'success'); checkBackend(); });
    RegisterModule.init(); ScannerModule.init(); PersonsModule.init(); HistoryModule.init(); AdminModule.init(); PersonsModule.load(); HistoryModule.load(); setTimeout(DashboardModule.refresh, 200); checkBackend(); setInterval(checkBackend, 15000);
  };
  return { init, navigate };
})();
document.addEventListener('DOMContentLoaded', App.init);
