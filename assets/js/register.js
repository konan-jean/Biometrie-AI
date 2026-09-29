const RegisterModule = (() => {
  const demoPersons = () => JSON.parse(localStorage.getItem('bioproof_persons') || '[]');
  const saveDemoPersons = list => localStorage.setItem('bioproof_persons', JSON.stringify(list));

  const init = () => {
    const input = document.getElementById('photoInput');
    const preview = document.getElementById('photoPreview');
    const form = document.getElementById('registerForm');
    if (!input || !form) return;

    input.addEventListener('change', () => {
      const file = input.files?.[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        BioUtils.toast('Format invalide. Utilisez JPG, PNG ou WebP.', 'error');
        input.value = '';
        return;
      }
      const url = URL.createObjectURL(file);
      preview.innerHTML = `<img src="${url}" alt="Photo de référence" />`;
    });

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const data = new FormData(form);
      if (!data.get('photo') || !data.get('photo').name) return BioUtils.toast('Veuillez ajouter une photo du visage.', 'warning');
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true; submit.textContent = 'Enregistrement...';
      try {
        let result;
        if (BioAPI.getSettings().demoMode) {
          result = await demoRegister(data);
          try { result = await BioAPI.registerPerson(data); } catch { /* mode démonstration */ }
        } else {
          result = await BioAPI.registerPerson(data);
        }
        renderResult(result);
        BioUtils.toast('Profil biométrique enregistré.', 'success');
        PersonsModule.load();
        HistoryModule.load();
        DashboardModule.refresh();
      } catch (err) {
        BioUtils.toast('Échec de l’enregistrement. Vérifiez le backend Python.', 'error');
      } finally {
        submit.disabled = false; submit.textContent = 'Enregistrer le profil';
      }
    });
  };

  const demoRegister = async data => {
    const { date, time } = BioUtils.nowParts();
    const person = {
      id: crypto.randomUUID(),
      first_name: data.get('first_name'), last_name: data.get('last_name'), matricule: data.get('matricule'),
      role: data.get('role'), department: data.get('department'), contact: data.get('contact'), status: data.get('status'),
      created_at: `${date} ${time}`, quality: 86 + Math.round(Math.random()*9)
    };
    const list = demoPersons(); list.unshift(person); saveDemoPersons(list);
    return { person, registeredAt: person.created_at, biometricProfile: { quality: person.quality, faceEmbedding: true, subjectCrop: true } };
  };

  const renderResult = result => {
    const el = document.getElementById('registerResult');
    const p = result.person || result;
    el.className = 'result-box';
    el.innerHTML = `
      <span class="badge success">Profil créé</span>
      <div class="profile-grid">
        <div class="profile-item"><span>Nom complet</span><strong>${p.first_name || ''} ${p.last_name || ''}</strong></div>
        <div class="profile-item"><span>Matricule</span><strong>${p.matricule || '—'}</strong></div>
        <div class="profile-item"><span>Statut</span><strong>${p.status || 'Actif'}</strong></div>
        <div class="profile-item"><span>Enregistré le</span><strong>${result.registeredAt || p.created_at || 'Maintenant'}</strong></div>
      </div>
      ${BioUtils.scoreBar('Qualité photo', result.biometricProfile?.quality || p.quality || 85)}
      <p class="hint">Empreinte faciale générée et profil prêt pour le Scanner robuste.</p>`;
  };

  return { init, demoPersons };
})();
