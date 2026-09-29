const BioWebcam = (() => {
  let stream = null;
  const video = () => document.getElementById('webcam');
  const canvas = () => document.getElementById('captureCanvas');
  const start = async () => {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, facingMode: 'user' }, audio: false });
    video().srcObject = stream;
    return stream;
  };
  const stop = () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    if (video()) video().srcObject = null;
  };
  const captureBlob = () => new Promise((resolve, reject) => {
    const v = video();
    if (!v || !v.videoWidth) return reject(new Error('Webcam non active'));
    const c = canvas();
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
    c.toBlob(blob => blob ? resolve(blob) : reject(new Error('Capture impossible')), 'image/jpeg', 0.92);
  });
  return { start, stop, captureBlob };
})();
