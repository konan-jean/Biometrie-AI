const BioUtils = (() => {
  const pct = value => `${Math.round(Number(value || 0))}%`;
  const pad = n => String(n).padStart(2, '0');
  const nowParts = () => {
    const d = new Date();
    return { date: `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` };
  };
  const decisionClass = decision => {
    const v = String(decision || '').toLowerCase();
    if (v.includes('valid') || v.includes('reconn')) return 'validée';
    if (v.includes('incertain')) return 'incertaine';
    if (v.includes('suspect')) return 'suspecte';
    if (v.includes('refus') || v.includes('inconnu')) return 'refusée';
    return 'neutral';
  };
  const toast = (message, type = 'info') => {
    const area = document.getElementById('toastArea');
    if (!area) return alert(message);
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    area.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  };
  const scoreBar = (label, value) => {
    const v = Math.max(0, Math.min(100, Number(value || 0)));
    const level = v >= 85 ? 'high' : v >= 60 ? 'mid' : 'low';
    return `<div class="score-row"><div class="score-label"><span>${label}</span><strong>${pct(v)}</strong></div><div class="score-bar"><div class="score-fill ${level}" style="width:${v}%"></div></div></div>`;
  };
  const proofHash = async text => {
    try {
      const data = new TextEncoder().encode(text);
      const hash = await crypto.subtle.digest('SHA-256', data);
      return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
    } catch { return `DEMO-${Date.now()}`; }
  };
  return { pct, nowParts, decisionClass, toast, scoreBar, proofHash };
})();
