(() => {

  const API_BASE = "http://127.0.0.1:8000";

  const startBtn = document.getElementById("startYoloBtn");
  const stopBtn = document.getElementById("stopYoloBtn");

  const stream = document.getElementById("yoloStream");
  const placeholder = document.getElementById("yoloPlaceholder");

  const status = document.getElementById("yoloStatus");
  const badge = document.getElementById("yoloBadge");

  const backendState =
    document.getElementById("yoloBackendState");


  // ============================================
  // Vérification du backend YOLO
  // ============================================

  async function checkYoloBackend() {

    if (!backendState) return;

    try {

      const response = await fetch(
        `${API_BASE}/api/yolo/status`
      );

      if (!response.ok) {
        throw new Error("Backend indisponible");
      }

      const data = await response.json();

      if (data.available) {

        backendState.textContent = "YOLOv8 disponible";

        if (status) {
          status.textContent =
            "YOLOv8 est prêt. Démarrez la détection.";
        }

      } else {

        backendState.textContent =
          "YOLOv8 non disponible";

        if (status) {
          status.textContent =
            "Le backend fonctionne mais YOLOv8 n'est pas disponible.";
        }

      }

    } catch (error) {

      console.error("YOLO status error:", error);

      backendState.textContent =
        "Backend hors ligne";

      if (status) {
        status.textContent =
          "Impossible de contacter le backend YOLOv8.";
      }

    }
  }


  // ============================================
  // Démarrer YOLO
  // ============================================

  function startYolo() {

    if (!stream) return;

    // Ajout d'un timestamp pour éviter le cache navigateur
    stream.src =
      `${API_BASE}/api/yolo/stream?t=${Date.now()}`;

    stream.style.display = "block";

    if (placeholder) {
      placeholder.style.display = "none";
    }

    if (startBtn) {
      startBtn.disabled = true;
    }

    if (stopBtn) {
      stopBtn.disabled = false;
    }

    if (badge) {
      badge.textContent = "En direct";
      badge.className = "badge success";
    }

    if (status) {
      status.textContent =
        "Détection YOLOv8 en cours...";
    }
  }


  // ============================================
  // Arrêter YOLO
  // ============================================

  function stopYolo() {

    if (!stream) return;

    // Coupe la connexion HTTP avec le stream
    stream.src = "";

    stream.style.display = "none";

    if (placeholder) {
      placeholder.style.display = "flex";
    }

    if (startBtn) {
      startBtn.disabled = false;
    }

    if (stopBtn) {
      stopBtn.disabled = true;
    }

    if (badge) {
      badge.textContent = "Arrêté";
      badge.className = "badge neutral";
    }

    if (status) {
      status.textContent =
        "Détection YOLOv8 arrêtée.";
    }
  }


  // ============================================
  // Événements
  // ============================================

  if (startBtn) {
    startBtn.addEventListener(
      "click",
      startYolo
    );
  }

  if (stopBtn) {
    stopBtn.addEventListener(
      "click",
      stopYolo
    );
  }


  // ============================================
  // Erreur du flux
  // ============================================

  if (stream) {

    stream.addEventListener("error", () => {

      if (status) {
        status.textContent =
          "Erreur : impossible de recevoir le flux YOLOv8.";
      }

      if (badge) {
        badge.textContent = "Erreur";
        badge.className = "badge danger";
      }

      if (startBtn) {
        startBtn.disabled = false;
      }

      if (stopBtn) {
        stopBtn.disabled = true;
      }

    });

  }


  // Vérification au chargement
  checkYoloBackend();

})();