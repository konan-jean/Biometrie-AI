const BioAPI = (() => {
  const defaults = { apiBase: 'http://localhost:8000', demoMode: true, autoScanInterval: 5, faceThreshold: 85, reliabilityThreshold: 85, livenessThreshold: 40, qualityThreshold: 55, retentionDays: 180, maxImageMb: 8, decisionMode: 'hybride', autoScanEnabled: true, storeProofImages: true };
  const getSettings = () => ({ ...defaults, ...JSON.parse(localStorage.getItem('bioproof_settings') || '{}') });
  const saveSettings = data => localStorage.setItem('bioproof_settings', JSON.stringify({ ...getSettings(), ...data }));
  const request = async (path, options = {}) => {
    const { apiBase } = getSettings();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch(`${apiBase}${path}`, { ...options, signal: controller.signal });
      clearTimeout(timeout);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      clearTimeout(timeout);
      throw err;
    }
  };
  const health = () => request('/api/health');
  const registerPerson = formData => request('/api/register', { method: 'POST', body: formData });
  const precheckScan = formData => request('/api/precheck-scan', { method: 'POST', body: formData });
  const analyzeScan = formData => request('/api/robust-analyze', { method: 'POST', body: formData });
  const persons = () => request('/api/persons');
  const history = () => request('/api/history');
  const deleteHistoryItem = id => request(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE' });
  const clearHistory = () => request('/api/history', { method: 'DELETE' });
  const backendSettings = () => request('/api/settings');
  const saveBackendSettings = payload => request('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const deletePerson = id => request(`/api/persons/${encodeURIComponent(id)}`, { method: 'DELETE' });
  const updatePerson = (id, payload) => request(`/api/persons/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const auditLogs = () => request('/api/admin/audit');
  const adminStats = () => request('/api/admin/stats');
  return { getSettings, saveSettings, health, registerPerson, precheckScan, analyzeScan, persons, history, deleteHistoryItem, clearHistory, backendSettings, saveBackendSettings, deletePerson, updatePerson, auditLogs, adminStats };
})();
