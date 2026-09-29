from pathlib import Path
import threading

import cv2
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
YOLOV8_MODEL = BASE_DIR / "yolov8n.pt"

# Modèle chargé une seule fois
yolo_model = YOLO(str(YOLOV8_MODEL))

camera_lock = threading.Lock()


def generate_yolo_frames(
    confidence: float = 0.35,
    camera_id: int = 0
):
    """
    Génère un flux MJPEG contenant les images de la webcam
    annotées par YOLOv8.

    YOLO affiche :
    - bounding box
    - nom de l'objet
    - confiance
    """

    with camera_lock:

        camera = cv2.VideoCapture(camera_id)

        if not camera.isOpened():
            print("[YOLO] Impossible d'ouvrir la caméra.")
            return

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        print("[YOLO] Caméra démarrée.")

        try:

            while True:

                success, frame = camera.read()

                if not success:
                    print("[YOLO] Impossible de lire la caméra.")
                    break

                # -------------------------------
                # INFERENCE YOLO
                # -------------------------------

                results = yolo_model.predict(
                    source=frame,
                    conf=confidence,
                    verbose=False
                )

                result = results[0]

                # -------------------------------
                # AFFICHAGE TERMINAL
                # -------------------------------

                if result.boxes is not None:

                    for box in result.boxes:

                        class_id = int(box.cls[0])
                        conf = float(box.conf[0])

                        object_name = result.names[class_id]

                        print(
                            f"[YOLO] {object_name} "
                            f"- {conf * 100:.1f}%"
                        )

                # -------------------------------
                # BOUNDING BOX + NOM + SCORE
                # -------------------------------

                annotated_frame = result.plot()

                # Information système
                cv2.putText(
                    annotated_frame,
                    "BioProof AI | YOLOv8",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA
                )

                # -------------------------------
                # JPEG
                # -------------------------------

                encode_success, buffer = cv2.imencode(
                    ".jpg",
                    annotated_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 85]
                )

                if not encode_success:
                    continue

                frame_bytes = buffer.tobytes()

                # Flux MJPEG pour navigateur
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )

        except GeneratorExit:
            print("[YOLO] Client déconnecté.")

        except Exception as error:
            print(
                "[YOLO] Erreur :",
                str(error)
            )

        finally:

            camera.release()

            print("[YOLO] Caméra arrêtée.")


def detect_image(
    image_path: str,
    confidence: float = 0.35
):
    """
    Détection YOLO sur une image.
    Retourne la liste des objets trouvés.
    """

    results = yolo_model.predict(
        source=image_path,
        conf=confidence,
        verbose=False
    )

    detections = []

    result = results[0]

    if result.boxes is None:
        return detections

    for box in result.boxes:

        class_id = int(box.cls[0])
        conf = float(box.conf[0])

        name = result.names[class_id]

        x1, y1, x2, y2 = map(
            float,
            box.xyxy[0]
        )

        detections.append({
            "name": name,
            "confidence": round(conf, 4),
            "confidence_percent": round(
                conf * 100,
                2
            ),
            "box": {
                "x1": round(x1, 2),
                "y1": round(y1, 2),
                "x2": round(x2, 2),
                "y2": round(y2, 2)
            }
        })

    return detections