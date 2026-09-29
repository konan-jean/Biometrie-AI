const HistoryModule = (() => {
  const key = 'bioproof_history';
  let cache = [];
  const getDemo = () => JSON.parse(localStorage.getItem(key) || '[]');
  const setDemo = data => localStorage.setItem(key, JSON.stringify(data));
  const addDemo = r => {
    const p = r.profile || r.person || {};
    const item = { id: crypto.randomUUID(), date: r.scanDate || BioUtils.nowParts().date, time: r.scanTime || BioUtils.nowParts().time,
      name: `${p.first_name || ''} ${p.last_name || 'Inconnu'}`.trim(), matricule: p.matricule || '—', decision: r.decision || 'Présence incertaine',
      faceScore: r.faceScore || r.similarity || 0, reliabilityScore: r.reliabilityScore || 0, proof: 'SHA-256' };
    const list = [item, ...getDemo()].slice(0, 100); setDemo(list); load();
  };
  const load = async () => {
    try {
      if (BioAPI.getSettings().demoMode) {
        cache = getDemo();
        try { const api = await BioAPI.history(); cache = api.history || api || cache; } catch {}
      } else { const api = await BioAPI.history(); cache = api.history || api || []; }
    } catch { cache = getDemo(); }
    render(cache);
  };
  const render = list => {
    const table = document.getElementById('historyTable');
    if (!table) return;
    table.innerHTML = list.length ? list.map(h => `<tr><td>${h.date || h.scan_date || '—'}</td><td>${h.time || h.scan_time || '—'}</td><td>${h.name || h.identity || 'Inconnu'}</td><td><span class="badge ${BioUtils.decisionClass(h.decision)}">${h.decision || '—'}</span></td><td>${BioUtils.pct(h.faceScore || h.face_score)}</td><td>${BioUtils.pct(h.reliabilityScore || h.reliability_score)}</td><td>${h.proof || '—'}</td></tr>`).join('') : '<tr><td colspan="7" class="muted">Aucun scan enregistré.</td></tr>';
  };
  const init = () => {
    const search = document.getElementById('historySearch');
    const filter = document.getElementById('decisionFilter');
    const apply = () => {
      const q = (search?.value || '').toLowerCase(); const f = filter?.value || 'all';
      render(cache.filter(h => (f === 'all' || String(h.decision).toLowerCase().includes(f)) && JSON.stringify(h).toLowerCase().includes(q)));
    };
    search?.addEventListener('input', apply); filter?.addEventListener('change', apply);
    document.getElementById('exportCsv')?.addEventListener('click', exportCsv);
  };
  const exportCsv = () => {
    const rows = [['Date','Heure','Identité','Décision','Score facial','Fiabilité'], ...cache.map(h => [h.date,h.time,h.name,h.decision,h.faceScore,h.reliabilityScore])];
    const csv = rows.map(r => r.map(v => `"${String(v ?? '').replaceAll('"','""')}"`).join(',')).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = 'historique-bioproof.csv'; a.click();
  };
  const all = () => cache.length ? cache : getDemo();
  return { init, load, addDemo, all };
})();
