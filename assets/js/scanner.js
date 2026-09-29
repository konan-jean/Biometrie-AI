const ScannerModule = (() => {
  let lastBlob = null;
  let autoEnabled = true;
  let autoCountdown = 5;
  let autoTimer = null;
  let isAnalyzing = false;

  const els = () => ({
    start: document.getElementById('startCamera'),
    stop: document.getElementById('stopCamera'),
    capture: document.getElementById('captureBtn'),
    analyze: document.getElementById('analyzeBtn'),
    auto: document.getElementById('autoScanBtn'),
    autoStatus: document.getElementById('autoScanStatus'),
    badge: document.getElementById('decisionBadge'),
    box: document.getElementById('scanResult'),
  });

  const init = () => {
    const { start, stop, capture, analyze, auto } = els();
    if (!start) return;

    start.addEventListener('click', async () => {
      try {
        await BioWebcam.start();
        BioUtils.toast('Webcam démarrée. Scan automatique activé.', 'success');
        startAutoScan();
      } catch {
        BioUtils.toast('Accès webcam refusé ou indisponible.', 'error');
      }
    });

    stop.addEventListener('click', () => {
      stopAutoScan();
      BioWebcam.stop();
      BioUtils.toast('Webcam arrêtée.');
    });

    capture.addEventListener('click', async () => {
      try {
        await captureFrame(false);
        BioUtils.toast('Image capturée. Lancez l’analyse ou attendez le scan automatique.', 'success');
      } catch {
        BioUtils.toast('Démarrez la webcam avant de capturer.', 'warning');
      }
    });

    analyze.addEventListener('click', () => analyzeScan(false));

    if (auto) {
      auto.addEventListener('click', () => {
        autoEnabled = !autoEnabled;
        if (autoEnabled) {
          auto.textContent = 'Scan auto ON';
          auto.classList.add('active');
          BioUtils.toast('Scan automatique activé : analyse toutes les 5 secondes.', 'success');
          startAutoScan();
        } else {
          auto.textContent = 'Scan auto OFF';
          auto.classList.remove('active');
          stopAutoScan(false);
          setAutoStatus('Scan automatique désactivé. Utilisez Capturer puis Analyser robuste.');
        }
      });
    }

    setAutoStatus('Démarrez la webcam : le système scannera automatiquement après 5 secondes.');
  };

  const setAutoStatus = text => {
    const { autoStatus } = els();
    if (autoStatus) autoStatus.textContent = text;
  };

  const startAutoScan = () => {
    if (!autoEnabled) return;
    stopAutoScan(false);
    autoCountdown = 5;
    setAutoStatus('AutoScan actif : première analyse automatique dans 5 s.');
    renderAutoWaiting(5, 'Placez votre visage au centre du cadre.');

    autoTimer = setInterval(async () => {
      if (!autoEnabled) return;
      if (isAnalyzing) {
        setAutoStatus('Analyse en cours : le prochain scan attend la fin du traitement.');
        return;
      }

      autoCountdown -= 1;
      setAutoStatus(`Scan automatique dans ${autoCountdown} s. Gardez le visage centré.`);
      renderAutoWaiting(autoCountdown, 'Préparation du scan automatique.');

      if (autoCountdown > 0) return;

      try {
        const blob = await captureFrame(true);

        // Précontrôle YOLO/qualité : il sert à informer et à renforcer la décision,
        // mais il ne bloque plus le scan automatique. Ainsi l'utilisateur obtient
        // toujours une analyse toutes les 5 secondes comme demandé.
        let precheck = null;
        try {
          precheck = await precheckScan(blob);
          renderPrecheck(precheck);
          if (precheck && precheck.reasons && precheck.reasons.length) {
            setAutoStatus(`Analyse lancée malgré avertissement : ${precheck.reasons.join(' • ')}.`);
          } else {
            setAutoStatus('Conditions correctes : analyse automatique lancée.');
          }
        } catch {
          setAutoStatus('Précontrôle indisponible : analyse automatique lancée directement.');
        }

        await analyzeScan(true);
      } catch (err) {
        setAutoStatus('Scan automatique impossible : vérifiez que la webcam est active.');
      } finally {
        autoCountdown = 5;
        if (autoEnabled) renderAutoWaiting(5, 'Prochaine analyse automatique dans 5 s.');
      }
    }, 1000);
  };

  const renderAutoWaiting = (seconds, message) => {
    const { box, badge } = els();
    if (!box) return;
    // Ne remplace pas un résultat déjà affiché, sauf avant le premier scan.
    if (!box.classList.contains('empty-state') && !box.classList.contains('auto-waiting')) return;
    if (badge) { badge.className = 'badge neutral'; badge.textContent = `AUTO ${Math.max(seconds, 0)}s`; }
    box.className = 'auto-waiting';
    box.innerHTML = `
      <div class="auto-countdown">
        <strong>${Math.max(seconds, 0)}</strong>
        <span>secondes</span>
      </div>
      <h4>Scan automatique actif</h4>
      <p>${message}</p>
      <p class="muted-small">Le système capturera l’image et lancera l’analyse biométrique automatiquement.</p>`;
  };

  const precheckScan = async blob => {
    if (!blob) return null;
    const data = new FormData();
    data.append('image', blob, 'precheck.jpg');
    try {
      if (BioAPI.getSettings().demoMode) {
        try { return await BioAPI.precheckScan(data); } catch { return demoPrecheck(); }
      }
      return await BioAPI.precheckScan(data);
    } catch (err) {
      throw err;
    }
  };

  const demoPrecheck = () => ({
    ok: true,
    ready: true,
    status: 'Prêt pour scan automatique',
    reasons: [],
    qualityScore: 82,
    yoloScore: 90,
    peopleCount: 1,
    faceDetected: true,
    faceConfidence: 88,
    qualityDetails: { warnings: [] },
    yolo: { warnings: [] },
  });

  const renderPrecheck = precheck => {
    const box = document.getElementById('precheckPanel');
    if (!box || !precheck) return;
    const readyClass = precheck.ready ? 'ready' : 'blocked';
    const reasons = precheck.reasons && precheck.reasons.length ? precheck.reasons.join(' • ') : 'Conditions de scan correctes';
    box.className = `precheck-panel ${readyClass}`;
    box.innerHTML = `
      <div><strong>${precheck.ready ? 'Précontrôle validé' : 'Précontrôle bloqué'}</strong><span>${reasons}</span></div>
      <div class="precheck-grid">
        <span>Visage: <b>${precheck.faceDetected ? 'oui' : 'non'}</b></span>
        <span>Personnes: <b>${precheck.peopleCount ?? '—'}</b></span>
        <span>Qualité: <b>${precheck.qualityScore ?? 0}%</b></span>
        <span>YOLOv8: <b>${precheck.yoloScore ?? 0}%</b></span>
      </div>`;
  };

  const stopAutoScan = (clearText = true) => {
    if (autoTimer) clearInterval(autoTimer);
    autoTimer = null;
    if (clearText) setAutoStatus('Scan automatique arrêté.');
  };

  const captureFrame = async (silent = false) => {
    lastBlob = await BioWebcam.captureBlob();
    if (!silent) setAutoStatus('Image capturée. Analyse prête.');
    return lastBlob;
  };

  const normalizeResult = r => {
    // Harmonise plusieurs formats possibles venant du backend.
    const scanDate = r.scanDate || r.scan_date || r.date || (r.scanTime ? '' : BioUtils.nowParts().date);
    const scanTime = r.scanTime || r.scan_time || r.time || BioUtils.nowParts().time;
    const faceScore = Number(r.faceScore ?? r.face_score ?? r.similarity ?? r.similarityScore ?? 0);
    const qualityScore = Number(r.qualityScore ?? r.quality_score ?? r.quality ?? 0);
    const livenessScore = Number(r.livenessScore ?? r.liveness_score ?? r.liveness ?? 0);
    const yoloScore = Number(r.yoloScore ?? r.yolo_score ?? r.yolo ?? 0);
    const reliabilityScore = Number(r.reliabilityScore ?? r.reliability_score ?? r.reliability ?? 0);
    return { ...r, scanDate, scanTime, faceScore, qualityScore, livenessScore, yoloScore, reliabilityScore };
  };

  const analyzeScan = async (automatic = false) => {
    if (!lastBlob) {
      if (!automatic) BioUtils.toast('Aucune capture disponible.', 'warning');
      return null;
    }
    if (isAnalyzing) return null;
    isAnalyzing = true;
    const { analyze } = els();
    if (analyze) { analyze.disabled = true; analyze.textContent = automatic ? 'Auto-analyse...' : 'Analyse...'; }
    setAutoStatus(automatic ? 'Analyse automatique en cours...' : 'Analyse manuelle en cours...');

    const data = new FormData();
    data.append('image', lastBlob, 'scan.jpg');
    try {
      let result;
      if (BioAPI.getSettings().demoMode) {
        result = await demoAnalyze();
        try { result = await BioAPI.analyzeScan(data); } catch { /* mode démonstration */ }
      } else {
        result = await BioAPI.analyzeScan(data);
      }
      result = normalizeResult(result);
      await renderResult(result);
      HistoryModule.addDemo(result);
      DashboardModule.refresh();
      setAutoStatus(automatic ? 'Scan analysé. Prochaine analyse automatique dans 5 s.' : 'Analyse terminée.');
      return result;
    } catch (err) {
      BioUtils.toast('Analyse impossible. Vérifiez le backend.', 'error');
      setAutoStatus('Analyse impossible. Vérifiez que le backend Python est démarré.');
      return null;
    } finally {
      isAnalyzing = false;
      if (analyze) { analyze.disabled = false; analyze.textContent = 'Analyser robuste'; }
    }
  };

  const demoAnalyze = async () => {
    const people = RegisterModule.demoPersons();
    const p = people[0];
    const { date, time } = BioUtils.nowParts();
    const face = p ? 84 + Math.round(Math.random()*12) : 18;
    const quality = 70 + Math.round(Math.random()*22);
    const liveness = 64 + Math.round(Math.random()*28);
    const yolo = 82 + Math.round(Math.random()*14);
    const reliability = Math.round(.4*face + .2*quality + .2*liveness + .2*yolo);
    const decision = !p ? 'Présence refusée' : reliability >= 85 ? 'Présence validée' : reliability >= 60 ? 'Présence incertaine' : 'Présence refusée';
    return { profile: p, decision, faceScore: face, qualityScore: quality, livenessScore: liveness, yoloScore: yolo, reliabilityScore: reliability, scanDate: date, scanTime: time };
  };

  const renderResult = async r => {
    const { badge, box } = els();
    if (!badge || !box) return;
    const decision = r.decision || r.status || 'Présence incertaine';
    const cls = BioUtils.decisionClass(decision);
    badge.className = `badge ${cls}`; badge.textContent = decision;
    const p = r.profile || r.person || {};
    const proof = await BioUtils.proofHash(`${p.matricule || p.id || 'unknown'}-${r.scanDate}-${r.scanTime}-${r.reliabilityScore}`);
    box.className = '';
    box.innerHTML = `
      <h4 class="decision-title">${decision}</h4>
      <div class="profile-grid">
        <div class="profile-item"><span>Identité</span><strong>${p.first_name || p.firstName || ''} ${p.last_name || p.lastName || 'Personne inconnue'}</strong></div>
        <div class="profile-item"><span>Matricule</span><strong>${p.matricule || '—'}</strong></div>
        <div class="profile-item"><span>Département</span><strong>${p.department || p.departement || '—'}</strong></div>
        <div class="profile-item"><span>Statut</span><strong>${p.status || p.statut || '—'}</strong></div>
        <div class="profile-item"><span>Date du scan</span><strong>${r.scanDate || BioUtils.nowParts().date}</strong></div>
        <div class="profile-item"><span>Heure du scan</span><strong>${r.scanTime || BioUtils.nowParts().time}</strong></div>
      </div>
      ${BioUtils.scoreBar('Score facial', r.faceScore || 0)}
      ${BioUtils.scoreBar('Qualité image', r.qualityScore || 0)}
      ${BioUtils.scoreBar('Vivacité', r.livenessScore || 0)}
      ${BioUtils.scoreBar('YOLOv8', r.yoloScore || 0)}
      ${BioUtils.scoreBar('Fiabilité globale', r.reliabilityScore || 0)}
      <div class="risk-box ${BioUtils.decisionClass(decision)}">
        <strong>Niveau de risque : ${r.riskLevel || 'moyen'}</strong>
        <p>${r.explanation || 'Décision calculée selon les scores biométriques.'}</p>
      </div>
      ${Array.isArray(r.recommendations) ? `<div class="recommendations"><strong>Corrections recommandées</strong><ul>${r.recommendations.map(x => `<li>${x}</li>`).join('')}</ul></div>` : ''}
      ${r.yolo && r.yolo.warnings && r.yolo.warnings.length ? `<div class="recommendations warning"><strong>Alertes YOLOv8</strong><ul>${r.yolo.warnings.map(x => `<li>${x}</li>`).join('')}</ul></div>` : ''}
      <p class="eyebrow">Hash de preuve chaîné</p><div class="proof-code">${r.proofHash || proof}</div>`;
  };
  return { init, demoAnalyze, startAutoScan, stopAutoScan };
})();
