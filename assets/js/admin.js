const AdminModule = (() => {
  let cache = [];
  let filtered = [];
  let historyCache = [];
  let historyFiltered = [];
  const selected = new Set();
  const SESSION_KEY = 'bioproof_admin_session';

  const isLogged = () => sessionStorage.getItem(SESSION_KEY) === 'active';
  const demoFallback = () => RegisterModule.demoPersons ? RegisterModule.demoPersons() : [];
  const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  const setSessionView = () => {
    const login = document.getElementById('adminLoginPanel');
    const workspace = document.getElementById('adminWorkspace');
    if (!login || !workspace) return;
    const active = isLogged();
    login.hidden = active;
    workspace.hidden = !active;
    if (active) load();
  };

  const init = () => {
    document.getElementById('adminLoginForm')?.addEventListener('submit', e => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const user = String(fd.get('username') || '').trim();
      const pass = String(fd.get('password') || '').trim();
      if (user === 'admin' && pass === 'admin123') {
        sessionStorage.setItem(SESSION_KEY, 'active');
        BioUtils.toast('Session administrateur ouverte.', 'success');
        setSessionView();
      } else {
        BioUtils.toast('Identifiant ou mot de passe administrateur incorrect.', 'error');
      }
    });

    document.querySelectorAll('[data-admin-tab]').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.adminTab)));
    document.getElementById('adminLogout')?.addEventListener('click', () => {
      sessionStorage.removeItem(SESSION_KEY);
      selected.clear();
      setSessionView();
      BioUtils.toast('Session administrateur fermée.','info');
    });

    document.getElementById('adminRefresh')?.addEventListener('click', load);
    document.getElementById('adminExportCsv')?.addEventListener('click', exportCsv);
    document.getElementById('adminSearch')?.addEventListener('input', applyFilters);
    document.getElementById('adminStatusFilter')?.addEventListener('change', applyFilters);
    document.getElementById('adminSelectAll')?.addEventListener('change', e => {
      selected.clear();
      if (e.target.checked) filtered.forEach(p => selected.add(String(p.id)));
      renderTable(filtered);
    });
    document.getElementById('adminDeleteSelected')?.addEventListener('click', deleteSelected);
    document.getElementById('adminLoadAudit')?.addEventListener('click', loadAudit);
    document.getElementById('adminCloseModal')?.addEventListener('click', closeModal);
    document.getElementById('adminCancelEdit')?.addEventListener('click', closeModal);
    document.getElementById('adminEditModal')?.addEventListener('click', e => { if (e.target.id === 'adminEditModal') closeModal(); });
    document.getElementById('adminEditForm')?.addEventListener('submit', saveEdit);

    document.getElementById('adminHistorySearch')?.addEventListener('input', applyHistoryFilters);
    document.getElementById('adminHistoryDecisionFilter')?.addEventListener('change', applyHistoryFilters);
    document.getElementById('adminHistoryRefresh')?.addEventListener('click', loadHistoryAdmin);
    document.getElementById('adminHistoryExport')?.addEventListener('click', exportHistoryCsv);
    document.getElementById('adminHistoryClear')?.addEventListener('click', clearHistory);

    document.getElementById('adminSettingsForm')?.addEventListener('submit', saveSettingsAdmin);
    document.getElementById('adminSettingsReset')?.addEventListener('click', resetSettingsAdmin);
    document.getElementById('adminSettingsSync')?.addEventListener('click', loadSettingsAdmin);

    setSessionView();
  };

  const switchTab = tab => {
    document.querySelectorAll('[data-admin-tab]').forEach(btn => btn.classList.toggle('active', btn.dataset.adminTab === tab));
    document.querySelectorAll('.admin-tab-page').forEach(page => page.classList.toggle('active', page.id === `adminTab-${tab}`));
    if (tab === 'history') loadHistoryAdmin();
    if (tab === 'settings') loadSettingsAdmin();
    if (tab === 'profiles') load();
  };

  const load = async () => {
    if (!isLogged()) return;
    try {
      const api = await BioAPI.persons();
      cache = api.persons || api || [];
    } catch {
      cache = demoFallback();
      BioUtils.toast('Backend indisponible : affichage local de démonstration.', 'warning');
    }
    selected.clear();
    applyFilters();
    renderStats(cache);
  };

  const applyFilters = () => {
    const q = String(document.getElementById('adminSearch')?.value || '').toLowerCase();
    const status = document.getElementById('adminStatusFilter')?.value || 'all';
    filtered = cache.filter(p => {
      const hitText = JSON.stringify(p).toLowerCase().includes(q);
      const hitStatus = status === 'all' || String(p.status || '').toLowerCase() === status.toLowerCase();
      return hitText && hitStatus;
    });
    renderTable(filtered);
    renderStats(cache);
  };

  const renderStats = list => {
    const active = list.filter(p => String(p.status || '').toLowerCase().includes('actif')).length;
    const visitors = list.filter(p => String(p.status || '').toLowerCase().includes('visiteur')).length;
    const avg = list.length ? Math.round(list.reduce((s,p)=>s+Number(p.quality_score || p.quality || 0),0)/list.length) : 0;
    setText('adminTotalPersons', list.length);
    setText('adminActivePersons', active);
    setText('adminVisitors', visitors);
    setText('adminAvgQuality', `${avg}%`);
    setText('adminCountBadge', `${filtered.length || list.length} profils`);
  };

  const renderTable = list => {
    const tbody = document.getElementById('adminPersonsTable');
    if (!tbody) return;
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="muted">Aucun profil correspondant.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(p => {
      const id = String(p.id);
      const full = `${p.first_name || ''} ${p.last_name || ''}`.trim() || 'Profil sans nom';
      const initials = `${(p.first_name || '?')[0]}${(p.last_name || '')[0] || ''}`.toUpperCase();
      const statusClass = String(p.status || '').toLowerCase().includes('inactif') ? 'danger' : 'neutral';
      return `<tr data-person-id="${id}">
        <td><input type="checkbox" class="admin-row-check" data-id="${id}" ${selected.has(id) ? 'checked' : ''} /></td>
        <td><div class="admin-identity"><span class="mini-avatar">${initials}</span><div><strong>${full}</strong><small>${p.role || '—'}</small></div></div></td>
        <td>${p.matricule || '—'}</td>
        <td>${p.department || '—'}</td>
        <td><span class="badge ${statusClass}">${p.status || 'Actif'}</span></td>
        <td>${BioUtils.pct(p.quality_score || p.quality || 0)}</td>
        <td>${p.created_at || '—'}</td>
        <td><div class="row-actions"><button class="btn btn-small btn-ghost" data-admin-edit="${id}" type="button">Modifier</button><button class="btn btn-small btn-danger" data-admin-delete="${id}" type="button">Supprimer</button></div></td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('.admin-row-check').forEach(ch => ch.addEventListener('change', e => {
      const id = String(e.target.dataset.id);
      e.target.checked ? selected.add(id) : selected.delete(id);
    }));
    tbody.querySelectorAll('[data-admin-edit]').forEach(btn => btn.addEventListener('click', () => openEdit(btn.dataset.adminEdit)));
    tbody.querySelectorAll('[data-admin-delete]').forEach(btn => btn.addEventListener('click', () => deleteOne(btn.dataset.adminDelete)));
  };

  const openEdit = id => {
    const p = cache.find(x => String(x.id) === String(id));
    if (!p) return BioUtils.toast('Profil introuvable.', 'error');
    const form = document.getElementById('adminEditForm');
    form.id.value = p.id || '';
    form.last_name.value = p.last_name || '';
    form.first_name.value = p.first_name || '';
    form.matricule.value = p.matricule || '';
    form.role.value = p.role || '';
    form.department.value = p.department || '';
    form.contact.value = p.contact || '';
    form.status.value = p.status || 'Actif';
    document.getElementById('adminEditModal').hidden = false;
  };

  const closeModal = () => { const m = document.getElementById('adminEditModal'); if (m) m.hidden = true; };

  const saveEdit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const id = fd.get('id');
    const payload = Object.fromEntries(fd.entries());
    delete payload.id;
    try {
      await BioAPI.updatePerson(id, payload);
      BioUtils.toast('Profil mis à jour.', 'success');
      closeModal();
      await load();
      PersonsModule.load();
      DashboardModule.refresh();
    } catch {
      BioUtils.toast('Modification impossible. Vérifiez le backend.', 'error');
    }
  };

  const deleteOne = async id => {
    const p = cache.find(x => String(x.id) === String(id));
    const label = p ? `${p.first_name || ''} ${p.last_name || ''}`.trim() : `#${id}`;
    if (!confirm(`Supprimer définitivement le profil ${label} ?`)) return;
    try {
      await BioAPI.deletePerson(id);
      BioUtils.toast('Profil supprimé.', 'success');
      await load();
      PersonsModule.load();
      DashboardModule.refresh();
    } catch {
      BioUtils.toast('Suppression impossible. Vérifiez le backend.', 'error');
    }
  };

  const deleteSelected = async () => {
    if (!selected.size) return BioUtils.toast('Aucun profil sélectionné.', 'warning');
    if (!confirm(`Supprimer ${selected.size} profil(s) sélectionné(s) ?`)) return;
    try {
      await Promise.all([...selected].map(id => BioAPI.deletePerson(id)));
      BioUtils.toast('Profils sélectionnés supprimés.', 'success');
      selected.clear();
      await load();
      PersonsModule.load();
      DashboardModule.refresh();
    } catch {
      BioUtils.toast('Suppression groupée impossible.', 'error');
    }
  };

  const exportCsv = () => {
    const rows = [['id','prenom','nom','matricule','fonction','departement','contact','statut','qualite','cree_le'], ...filtered.map(p => [p.id,p.first_name,p.last_name,p.matricule,p.role,p.department,p.contact,p.status,p.quality_score || p.quality || '',p.created_at])];
    downloadCsv(rows, `profils-biometriques-${Date.now()}.csv`);
  };

  const loadAudit = async () => {
    const box = document.getElementById('adminAuditList');
    if (!box) return;
    try {
      const res = await BioAPI.auditLogs();
      const logs = res.logs || [];
      if (!logs.length) { box.className = 'audit-list empty-state'; box.textContent = 'Aucune action administrative enregistrée.'; return; }
      box.className = 'audit-list';
      box.innerHTML = logs.map(l => `<div class="audit-item"><strong>${l.action}</strong><span>${l.created_at || '—'}</span><small>${l.details || ''}</small></div>`).join('');
    } catch {
      box.className = 'audit-list empty-state';
      box.textContent = 'Impossible de charger le journal administratif.';
    }
  };

  const loadHistoryAdmin = async () => {
    if (!isLogged()) return;
    try {
      const res = await BioAPI.history();
      historyCache = res.history || res || [];
    } catch {
      historyCache = HistoryModule.all ? HistoryModule.all() : [];
      BioUtils.toast('Backend indisponible : historique local affiché.', 'warning');
    }
    applyHistoryFilters();
  };

  const applyHistoryFilters = () => {
    const q = String(document.getElementById('adminHistorySearch')?.value || '').toLowerCase();
    const f = document.getElementById('adminHistoryDecisionFilter')?.value || 'all';
    historyFiltered = historyCache.filter(h => {
      const dec = String(h.decision || '').toLowerCase();
      const okDecision = f === 'all' || dec.includes(f);
      const okText = JSON.stringify(h).toLowerCase().includes(q);
      return okDecision && okText;
    });
    renderHistoryTable(historyFiltered);
    renderHistoryStats(historyCache);
  };

  const renderHistoryStats = list => {
    const valid = list.filter(h => BioUtils.decisionClass(h.decision) === 'validée').length;
    const uncertain = list.filter(h => BioUtils.decisionClass(h.decision) === 'incertaine').length;
    const suspect = list.filter(h => BioUtils.decisionClass(h.decision) === 'suspecte').length;
    const avg = list.length ? Math.round(list.reduce((s,h)=>s+Number(h.reliabilityScore || h.reliability_score || 0),0)/list.length) : 0;
    setText('adminHistoryCount', `${historyFiltered.length || list.length} scans`);
    setText('adminHistValid', valid);
    setText('adminHistUncertain', uncertain);
    setText('adminHistSuspect', suspect);
    setText('adminHistAvgReliability', `${avg}%`);
  };

  const renderHistoryTable = list => {
    const tbody = document.getElementById('adminHistoryTable');
    if (!tbody) return;
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="muted">Aucun scan correspondant.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(h => {
      const id = h.id || '';
      return `<tr>
        <td>${h.date || h.scan_date || '—'}</td>
        <td>${h.time || h.scan_time || '—'}</td>
        <td>${h.name || h.identity || 'Inconnu'}</td>
        <td>${h.matricule || '—'}</td>
        <td><span class="badge ${BioUtils.decisionClass(h.decision)}">${h.decision || '—'}</span></td>
        <td>${BioUtils.pct(h.faceScore || h.face_score)}</td>
        <td>${BioUtils.pct(h.reliabilityScore || h.reliability_score)}</td>
        <td><code>${String(h.proof || h.proof_hash || '—').slice(0, 16)}</code></td>
        <td>${id ? `<button class="btn btn-small btn-danger" data-admin-history-delete="${id}" type="button">Supprimer</button>` : '—'}</td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('[data-admin-history-delete]').forEach(btn => btn.addEventListener('click', () => deleteHistoryItem(btn.dataset.adminHistoryDelete)));
  };

  const deleteHistoryItem = async id => {
    if (!confirm(`Supprimer définitivement le scan #${id} de l’historique ?`)) return;
    try {
      await BioAPI.deleteHistoryItem(id);
      BioUtils.toast('Scan supprimé de l’historique.', 'success');
      await loadHistoryAdmin();
      HistoryModule.load();
      DashboardModule.refresh();
    } catch {
      BioUtils.toast('Suppression de l’historique impossible. Vérifiez le backend.', 'error');
    }
  };

  const clearHistory = async () => {
    if (!confirm('Vider définitivement tout l’historique des scans ? Cette action est irréversible.')) return;
    try {
      await BioAPI.clearHistory();
      BioUtils.toast('Historique vidé.', 'success');
      await loadHistoryAdmin();
      HistoryModule.load();
      DashboardModule.refresh();
    } catch {
      BioUtils.toast('Impossible de vider l’historique. Vérifiez le backend.', 'error');
    }
  };

  const exportHistoryCsv = () => {
    const rows = [['id','date','heure','identite','matricule','decision','score_facial','qualite','vivacite','yolo','fiabilite','preuve'], ...historyFiltered.map(h => [h.id,h.date || h.scan_date,h.time || h.scan_time,h.name || h.identity,h.matricule,h.decision,h.faceScore || h.face_score,h.qualityScore || h.quality_score,h.livenessScore || h.liveness_score,h.yoloScore || h.yolo_score,h.reliabilityScore || h.reliability_score,h.proof || h.proof_hash])];
    downloadCsv(rows, `historique-scans-${Date.now()}.csv`);
  };

  const loadSettingsAdmin = async () => {
    const form = document.getElementById('adminSettingsForm');
    if (!form) return;
    let settings = BioAPI.getSettings();
    try {
      const res = await BioAPI.backendSettings();
      settings = { ...settings, ...(res.settings || {}) };
      BioAPI.saveSettings(settings);
    } catch {}
    Object.entries(settings).forEach(([k,v]) => {
      const field = form.elements[k];
      if (!field) return;
      if (field.type === 'checkbox') field.checked = Boolean(v);
      else field.value = v;
    });
  };

  const formSettingsPayload = form => {
    const fd = new FormData(form);
    return {
      apiBase: String(fd.get('apiBase') || 'http://localhost:8000').trim(),
      autoScanInterval: Number(fd.get('autoScanInterval') || 5),
      faceThreshold: Number(fd.get('faceThreshold') || 85),
      reliabilityThreshold: Number(fd.get('reliabilityThreshold') || 85),
      livenessThreshold: Number(fd.get('livenessThreshold') || 40),
      qualityThreshold: Number(fd.get('qualityThreshold') || 55),
      retentionDays: Number(fd.get('retentionDays') || 180),
      maxImageMb: Number(fd.get('maxImageMb') || 8),
      decisionMode: String(fd.get('decisionMode') || 'hybride'),
      demoMode: Boolean(fd.get('demoMode')),
      autoScanEnabled: Boolean(fd.get('autoScanEnabled')),
      storeProofImages: Boolean(fd.get('storeProofImages')),
    };
  };

  const saveSettingsAdmin = async e => {
    e.preventDefault();
    const payload = formSettingsPayload(e.target);
    BioAPI.saveSettings(payload);
    try {
      await BioAPI.saveBackendSettings(payload);
      BioUtils.toast('Paramètres sauvegardés localement et dans le backend.', 'success');
    } catch {
      BioUtils.toast('Paramètres sauvegardés localement. Backend indisponible pour la synchronisation.', 'warning');
    }
  };

  const resetSettingsAdmin = () => {
    if (!confirm('Réinitialiser les paramètres professionnels par défaut ?')) return;
    const defaults = { apiBase:'http://localhost:8000', demoMode:true, autoScanInterval:5, faceThreshold:85, reliabilityThreshold:85, livenessThreshold:40, qualityThreshold:55, retentionDays:180, maxImageMb:8, decisionMode:'hybride', autoScanEnabled:true, storeProofImages:true };
    BioAPI.saveSettings(defaults);
    loadSettingsAdmin();
    BioUtils.toast('Paramètres réinitialisés.', 'success');
  };

  const downloadCsv = (rows, filename) => {
    const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(';')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return { init, load, isLogged, loadHistoryAdmin, loadSettingsAdmin };
})();
