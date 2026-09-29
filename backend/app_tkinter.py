"""
BioProof AI - Backend local Python/Tkinter
Système intelligent de preuve de présence biométrique anti-fraude.

Endpoints principaux :
- GET  /api/health
- POST /api/register
- POST /api/precheck-scan
- POST /api/robust-analyze
- GET  /api/persons
- GET  /api/history
- DELETE /api/persons/<id>

Le backend fonctionne avec des dépendances progressives :
- Obligatoire : Python standard + Pillow recommandé
- Recommandé : OpenCV pour la détection faciale
- Optionnel : ultralytics pour YOLOv8
- Optionnel : face_recognition si disponible pour des embeddings plus sérieux
"""
from __future__ import annotations

import base64
import hashlib
import io
from email.parser import BytesParser
from email.policy import default as email_default_policy
import json
import math
import os
import sqlite3
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from yolo_detector import generate_yolo_frames
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:  # pragma: no cover
    tk = None
    ttk = None
    messagebox = None

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageStat
except Exception:  # pragma: no cover
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageStat = None

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover
    cv2 = None
    np = None

try:
    import face_recognition  # type: ignore
except Exception:  # pragma: no cover
    face_recognition = None

try:
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover
    YOLO = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bioproof.db"
UPLOAD_DIR = BASE_DIR / "uploads"
PROOF_DIR = BASE_DIR / "proofs"
RESTORED_DIR = BASE_DIR / "restored"
MODEL_DIR = BASE_DIR / "models"
for folder in (UPLOAD_DIR, PROOF_DIR, RESTORED_DIR, MODEL_DIR):
    folder.mkdir(parents=True, exist_ok=True)

HOST = "127.0.0.1"
PORT = 8000

@dataclass
class UploadedFile:
    filename: str
    file: io.BytesIO


class MultipartForm:
    def __init__(self) -> None:
        self.fields: Dict[str, Any] = {}

    def add(self, name: str, value: Any) -> None:
        self.fields[name] = value

    def __contains__(self, name: str) -> bool:
        return name in self.fields

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    def getfirst(self, name: str, default_value: str = "") -> str:
        value = self.fields.get(name, default_value)
        if isinstance(value, UploadedFile):
            return default_value
        return str(value)

_server: Optional[ThreadingHTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_yolo_model = None


def now_parts() -> Tuple[str, str, str]:
    dt = datetime.now()
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), dt.strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def pct(value: float) -> int:
    return max(0, min(100, int(round(value))))


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    # Convertit [-1, 1] vers [0, 100]
    return pct(((dot / (na * nb)) + 1.0) * 50.0)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                matricule TEXT UNIQUE,
                role TEXT,
                department TEXT,
                contact TEXT,
                status TEXT,
                photo_path TEXT,
                restored_path TEXT,
                face_embedding TEXT,
                quality_score REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER,
                name TEXT,
                matricule TEXT,
                decision TEXT,
                face_score REAL,
                quality_score REAL,
                liveness_score REAL,
                yolo_score REAL,
                reliability_score REAL,
                scan_date TEXT,
                scan_time TEXT,
                proof_image TEXT,
                proof_hash TEXT,
                explanation TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(person_id) REFERENCES persons(id)
            )
            """
        )
        # Colonnes ajoutées pour renforcer la preuve et l'analyse anti-fraude.
        existing = {row[1] for row in cur.execute("PRAGMA table_info(scan_history)").fetchall()}
        extra_columns = {
            "risk_level": "TEXT",
            "recommendations": "TEXT",
            "previous_hash": "TEXT",
            "quality_details": "TEXT",
            "yolo_details": "TEXT",
        }
        for col, typ in extra_columns.items():
            if col not in existing:
                cur.execute(f"ALTER TABLE scan_history ADD COLUMN {col} {typ}")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _, _, created_at = now_parts()
        default_settings = {
            "apiBase": "http://localhost:8000",
            "demoMode": True,
            "autoScanInterval": 5,
            "faceThreshold": 85,
            "reliabilityThreshold": 85,
            "livenessThreshold": 40,
            "qualityThreshold": 55,
            "retentionDays": 180,
            "maxImageMb": 8,
            "decisionMode": "hybride",
            "autoScanEnabled": True,
            "storeProofImages": True,
        }
        for key, value in default_settings.items():
            cur.execute("INSERT OR IGNORE INTO system_settings(key,value,updated_at) VALUES(?,?,?)", (key, json_dumps(value), created_at))
        con.commit()


def rows_to_dicts(cur: sqlite3.Cursor, rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def get_persons() -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, first_name, last_name, matricule, role, department, contact, status,
                   photo_path, quality_score, created_at
            FROM persons
            ORDER BY id DESC
            """
        )
        return rows_to_dicts(cur, cur.fetchall())


def get_history(limit: int = 200) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, person_id, name, matricule, decision, face_score AS faceScore,
                   quality_score AS qualityScore, liveness_score AS livenessScore,
                   yolo_score AS yoloScore, reliability_score AS reliabilityScore,
                   scan_date AS date, scan_time AS time, proof_hash AS proof,
                   explanation, created_at
            FROM scan_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return rows_to_dicts(cur, cur.fetchall())


def get_admin_stats() -> Dict[str, Any]:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        total = cur.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        active = cur.execute("SELECT COUNT(*) FROM persons WHERE LOWER(COALESCE(status,'')) LIKE '%actif%'").fetchone()[0]
        visitors = cur.execute("SELECT COUNT(*) FROM persons WHERE LOWER(COALESCE(status,'')) LIKE '%visiteur%'").fetchone()[0]
        scans = cur.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        avg_quality = cur.execute("SELECT AVG(COALESCE(quality_score,0)) FROM persons").fetchone()[0] or 0
        suspect = cur.execute("SELECT COUNT(*) FROM scan_history WHERE LOWER(COALESCE(decision,'')) LIKE '%suspect%'").fetchone()[0]
        return {
            "totalPersons": total,
            "activePersons": active,
            "visitors": visitors,
            "totalScans": scans,
            "averageQuality": pct(float(avg_quality)),
            "suspectScans": suspect,
        }


def get_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT id, action, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
        return rows_to_dicts(cur, cur.fetchall())


def get_system_settings() -> Dict[str, Any]:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        rows = cur.execute("SELECT key, value FROM system_settings").fetchall()
    settings: Dict[str, Any] = {}
    for key, raw in rows:
        try:
            settings[key] = json.loads(raw)
        except Exception:
            settings[key] = raw
    return settings


def save_system_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "apiBase", "demoMode", "autoScanInterval", "faceThreshold", "reliabilityThreshold",
        "livenessThreshold", "qualityThreshold", "retentionDays", "maxImageMb",
        "decisionMode", "autoScanEnabled", "storeProofImages",
    }
    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key in {"autoScanInterval", "faceThreshold", "reliabilityThreshold", "livenessThreshold", "qualityThreshold", "retentionDays", "maxImageMb"}:
            cleaned[key] = int(max(0, safe_float(value, 0)))
        elif key in {"demoMode", "autoScanEnabled", "storeProofImages"}:
            cleaned[key] = bool(value)
        else:
            cleaned[key] = str(value).strip()
    _, _, created_at = now_parts()
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        for key, value in cleaned.items():
            cur.execute("INSERT OR REPLACE INTO system_settings(key,value,updated_at) VALUES(?,?,?)", (key, json_dumps(value), created_at))
        cur.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)", ("UPDATE_SETTINGS", json_dumps(cleaned), created_at))
        con.commit()
    return get_system_settings()


def delete_history_item(scan_id: int) -> bool:
    _, _, created_at = now_parts()
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        row = cur.execute("SELECT id,name,decision,scan_date,scan_time FROM scan_history WHERE id=?", (scan_id,)).fetchone()
        if not row:
            return False
        cur.execute("DELETE FROM scan_history WHERE id=?", (scan_id,))
        cur.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)", ("DELETE_SCAN", json_dumps({"scan": row}), created_at))
        con.commit()
    return True


def clear_history_items() -> int:
    _, _, created_at = now_parts()
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        count = cur.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        cur.execute("DELETE FROM scan_history")
        cur.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)", ("CLEAR_HISTORY", json_dumps({"deleted": count}), created_at))
        con.commit()
    return int(count)


def load_image_pil(path: Path) -> Optional[Any]:
    if Image is None:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def save_uploaded_file(field: Any, folder: Path, prefix: str = "upload") -> Path:
    filename = getattr(field, "filename", None) or "image.jpg"
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        ext = ".jpg"
    target = folder / f"{prefix}_{int(time.time() * 1000)}{ext}"
    raw = field.file.read()
    target.write_bytes(raw)
    return target


def detect_faces_cv(path: Path) -> List[Tuple[int, int, int, int, float]]:
    if cv2 is None:
        return []
    img = cv2.imread(str(path))
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    h, w = gray.shape[:2]
    out: List[Tuple[int, int, int, int, float]] = []
    for (x, y, fw, fh) in faces:
        area_ratio = (fw * fh) / max(1, w * h)
        conf = min(98.0, 45.0 + area_ratio * 250.0)
        out.append((int(x), int(y), int(fw), int(fh), conf))
    out.sort(key=lambda r: r[2] * r[3], reverse=True)
    return out


def crop_face_or_center(path: Path, prefix: str = "face") -> Tuple[Path, bool, float]:
    img = load_image_pil(path)
    if img is None:
        return path, False, 0.0
    faces = detect_faces_cv(path)
    if faces:
        x, y, w, h, conf = faces[0]
        margin_x = int(w * 0.30)
        margin_y = int(h * 0.35)
        left = max(0, x - margin_x)
        top = max(0, y - margin_y)
        right = min(img.width, x + w + margin_x)
        bottom = min(img.height, y + h + margin_y)
        crop = img.crop((left, top, right, bottom))
        target = RESTORED_DIR / f"{prefix}_{int(time.time() * 1000)}.jpg"
        crop.save(target, quality=92)
        return target, True, conf
    # Fallback : crop central si aucun visage n'est détecté.
    side = int(min(img.width, img.height) * 0.82)
    left = max(0, (img.width - side) // 2)
    top = max(0, (img.height - side) // 2)
    crop = img.crop((left, top, left + side, top + side))
    target = RESTORED_DIR / f"{prefix}_center_{int(time.time() * 1000)}.jpg"
    crop.save(target, quality=92)
    return target, False, 35.0


def restore_image(path: Path, prefix: str = "restored") -> Path:
    img = load_image_pil(path)
    if img is None:
        return path
    # Amélioration légère : contraste, luminosité, netteté.
    img = ImageEnhance.Contrast(img).enhance(1.10)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    img = ImageEnhance.Sharpness(img).enhance(1.35)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=105, threshold=3))
    target = RESTORED_DIR / f"{prefix}_{int(time.time() * 1000)}.jpg"
    img.save(target, quality=92)
    return target


def image_quality(path: Path) -> int:
    return int(image_quality_report(path).get("score", 50))


def face_embedding(path: Path) -> List[float]:
    """Retourne une empreinte faciale locale.

    Priorité : bibliothèque face_recognition si installée.
    Fallback robuste pour prototype : patch grayscale 64x64 normalisé avec OpenCV/Pillow.
    """
    if face_recognition is not None:
        try:
            image = face_recognition.load_image_file(str(path))
            locations = face_recognition.face_locations(image)
            encodings = face_recognition.face_encodings(image, locations)
            if encodings:
                return [float(x) for x in encodings[0].tolist()]
        except Exception:
            pass
    img = load_image_pil(path)
    if img is None:
        return []
    crop_path, _, _ = crop_face_or_center(path, prefix="emb")
    img = load_image_pil(crop_path) or img
    img = img.convert("L").resize((64, 64))
    values = list(img.getdata())
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(var) or 1.0
    # Sous-échantillonnage pour garder une empreinte légère.
    return [round((v - mean) / std, 5) for i, v in enumerate(values) if i % 2 == 0]


def load_yolo():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    if YOLO is None:
        return None
    try:
        # ultralytics téléchargera yolov8n.pt au premier usage si Internet est disponible.
        # Sinon, placer un modèle dans backend/models/yolov8n.pt.
        local = MODEL_DIR / "yolov8n.pt"
        _yolo_model = YOLO(str(local) if local.exists() else "yolov8n.pt")
        return _yolo_model
    except Exception:
        return None



def yolo_analyze(path: Path) -> Dict[str, Any]:
    """Analyse YOLOv8 renforcée.

    Rôle : détecter la personne, compter les personnes visibles et repérer les objets
    pouvant indiquer une fraude par écran/téléphone. YOLOv8 ne remplace pas le
    module de reconnaissance faciale ; il sécurise la qualité du scan.
    """
    meta: Dict[str, Any] = {
        "available": False,
        "persons": 0,
        "bestConfidence": 0,
        "score": 45,
        "bestPersonBox": None,
        "suspiciousObjects": [],
        "objects": [],
        "warnings": [],
    }
    model = load_yolo()
    if model is None:
        faces = detect_faces_cv(path)
        meta.update({
            "available": False,
            "message": "YOLOv8 non chargé, fallback OpenCV utilisé",
            "persons": 1 if faces else 0,
            "bestConfidence": pct(faces[0][4]) if faces else 0,
            "score": pct(faces[0][4]) if faces else 35,
        })
        if not faces:
            meta["warnings"].append("Aucun visage détecté par OpenCV")
        return meta
    try:
        results = model(str(path), verbose=False)
        suspicious_labels = {"cell phone", "tv", "laptop", "tablet", "monitor", "remote"}
        best_person_conf = 0.0
        best_box = None
        persons = 0
        objects = []
        suspicious = []
        for r in results:
            names = getattr(r, "names", {}) or {}
            for box in getattr(r, "boxes", []) or []:
                cls = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
                conf = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
                label = names.get(cls, str(cls))
                xyxy = [int(v) for v in box.xyxy[0].tolist()] if getattr(box, "xyxy", None) is not None else None
                obj = {"label": label, "confidence": pct(conf * 100), "box": xyxy}
                objects.append(obj)
                if label == "person":
                    persons += 1
                    if conf > best_person_conf:
                        best_person_conf = conf
                        best_box = xyxy
                if label in suspicious_labels and conf >= 0.35:
                    suspicious.append(obj)
        score = pct((best_person_conf * 100.0) if best_person_conf else 35)
        warnings = []
        if persons == 0:
            warnings.append("Aucune personne détectée par YOLOv8")
            score = min(score, 35)
        if persons > 1:
            warnings.append("Plusieurs personnes détectées : scan ambigu")
            score = min(score, 55)
        if suspicious:
            warnings.append("Objet écran/téléphone détecté : risque de présentation frauduleuse")
            score = min(score, 65)
        meta.update({
            "available": True,
            "persons": persons,
            "bestConfidence": pct(best_person_conf * 100.0),
            "score": score,
            "bestPersonBox": best_box,
            "suspiciousObjects": suspicious,
            "objects": objects[:12],
            "warnings": warnings,
        })
        return meta
    except Exception as exc:
        meta.update({"available": False, "message": f"Erreur YOLOv8: {exc}", "score": 45})
        return meta


def yolo_detection_score(path: Path) -> Tuple[int, Dict[str, Any]]:
    meta = yolo_analyze(path)
    return pct(safe_float(meta.get("score"), 45)), meta


def crop_subject_robust(path: Path, yolo_meta: Optional[Dict[str, Any]] = None, prefix: str = "subject") -> Tuple[Path, bool, float, Dict[str, Any]]:
    """Recadrage robuste : visage OpenCV d'abord, puis haut du corps YOLO, puis centre.

    Cette correction évite d'envoyer au module facial une image complète avec beaucoup
    d'arrière-plan. Elle corrige une faiblesse fréquente des prototypes YOLOv8.
    """
    img = load_image_pil(path)
    info = {"method": "original", "warnings": []}
    if img is None:
        return path, False, 0.0, info
    faces = detect_faces_cv(path)
    if faces:
        x, y, w, h, conf = faces[0]
        margin_x = int(w * 0.32)
        margin_y = int(h * 0.40)
        left = max(0, x - margin_x)
        top = max(0, y - margin_y)
        right = min(img.width, x + w + margin_x)
        bottom = min(img.height, y + h + margin_y)
        crop = img.crop((left, top, right, bottom))
        target = RESTORED_DIR / f"{prefix}_face_{int(time.time() * 1000)}.jpg"
        crop.save(target, quality=94)
        info.update({"method": "opencv_face", "faceCount": len(faces), "box": [left, top, right, bottom]})
        if len(faces) > 1:
            info["warnings"].append("Plusieurs visages détectés")
        return target, True, conf, info
    box = (yolo_meta or {}).get("bestPersonBox")
    if box and len(box) == 4:
        x1, y1, x2, y2 = [int(v) for v in box]
        # Pour une personne entière, le visage est généralement dans la partie haute.
        width = x2 - x1
        height = y2 - y1
        left = max(0, x1 - int(width * 0.08))
        right = min(img.width, x2 + int(width * 0.08))
        top = max(0, y1)
        bottom = min(img.height, y1 + int(height * 0.58))
        crop = img.crop((left, top, right, bottom))
        target = RESTORED_DIR / f"{prefix}_yolo_upper_{int(time.time() * 1000)}.jpg"
        crop.save(target, quality=94)
        info.update({"method": "yolo_upper_body", "box": [left, top, right, bottom], "warnings": ["Visage non détecté précisément : recadrage haut du corps utilisé"]})
        return target, False, safe_float((yolo_meta or {}).get("bestConfidence"), 45), info
    # Fallback central contrôlé, mais le scan doit rester incertain/refusé.
    side = int(min(img.width, img.height) * 0.78)
    left = max(0, (img.width - side) // 2)
    top = max(0, (img.height - side) // 2)
    crop = img.crop((left, top, left + side, top + side))
    target = RESTORED_DIR / f"{prefix}_center_{int(time.time() * 1000)}.jpg"
    crop.save(target, quality=92)
    info.update({"method": "center_fallback", "box": [left, top, left + side, top + side], "warnings": ["Aucun visage détecté : analyse dégradée"]})
    return target, False, 30.0, info


def image_quality_report(path: Path) -> Dict[str, Any]:
    img = load_image_pil(path)
    if img is None:
        return {"score": 30, "brightness": 0, "contrast": 0, "sharpness": 0, "warnings": ["Image illisible"]}
    stat = ImageStat.Stat(img.convert("L"))
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    brightness_score = 100 - min(100, abs(brightness - 128) / 1.28)
    contrast_score = min(100, contrast * 2.4)
    sharpness_score = 60.0
    if cv2 is not None:
        cv_img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if cv_img is not None:
            lap = cv2.Laplacian(cv_img, cv2.CV_64F).var()
            sharpness_score = min(100, lap / 5.0)
    score = pct(0.45 * sharpness_score + 0.30 * brightness_score + 0.25 * contrast_score)
    warnings = []
    if brightness < 65:
        warnings.append("Image trop sombre")
    if brightness > 205:
        warnings.append("Image surexposée")
    if contrast < 18:
        warnings.append("Contraste faible")
    if sharpness_score < 45:
        warnings.append("Image floue")
    return {
        "score": score,
        "brightness": pct(brightness / 255 * 100),
        "contrast": pct(min(100, contrast * 1.5)),
        "sharpness": pct(sharpness_score),
        "warnings": warnings,
    }


def get_previous_proof_hash() -> str:
    try:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT proof_hash FROM scan_history WHERE proof_hash IS NOT NULL ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else "GENESIS"
    except Exception:
        return "GENESIS"


def risk_level(decision: str, face: int, quality: int, liveness: int, yolo_meta: Dict[str, Any]) -> str:
    if "suspect" in decision.lower() or liveness < 40 or yolo_meta.get("suspiciousObjects"):
        return "élevé"
    if "incertaine" in decision.lower() or quality < 60 or face < 75 or yolo_meta.get("persons", 1) != 1:
        return "moyen"
    return "faible"


def build_recommendations(face: int, quality_report: Dict[str, Any], liveness: int, yolo_meta: Dict[str, Any], face_detected: bool) -> List[str]:
    recs = []
    if not face_detected:
        recs.append("Positionner le visage plus proche et bien au centre du cadre")
    if face < 70:
        recs.append("Réenregistrer la personne avec plusieurs photos nettes de face")
    for warning in quality_report.get("warnings", []):
        if "sombre" in warning.lower():
            recs.append("Ajouter une lumière devant le visage")
        elif "floue" in warning.lower():
            recs.append("Stabiliser la caméra et éviter les mouvements pendant le scan")
        elif "surexpos" in warning.lower():
            recs.append("Réduire la lumière directe derrière ou devant le visage")
        else:
            recs.append(warning)
    if liveness < 55:
        recs.append("Refaire le scan avec un challenge de vivacité : cligner des yeux ou tourner légèrement la tête")
    if yolo_meta.get("persons", 1) > 1:
        recs.append("Garder une seule personne devant la caméra")
    if yolo_meta.get("suspiciousObjects"):
        recs.append("Éloigner les téléphones ou écrans visibles pendant le scan")
    if not recs:
        recs.append("Aucune correction nécessaire : les scores sont cohérents")
    return list(dict.fromkeys(recs))[:5]


def liveness_score(path: Path, quality: int, face_detected: bool) -> int:
    """Score de vivacité logiciel approximatif.

    Une vraie vivacité exige plusieurs frames ou un challenge utilisateur.
    Ici, le score indique seulement la cohérence visuelle du scan.
    """
    img = load_image_pil(path)
    if img is None:
        return 30
    texture = 50.0
    if cv2 is not None:
        cv_img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if cv_img is not None:
            edges = cv2.Canny(cv_img, 80, 160)
            texture = min(100, float(edges.mean()) * 2.8)
    base = 55 + (10 if face_detected else -8)
    return pct(0.45 * quality + 0.25 * texture + 0.30 * base)


def reliability_score(face: int, quality: int, liveness: int, yolo: int) -> int:
    return pct(0.4 * face + 0.2 * quality + 0.2 * liveness + 0.2 * yolo)


def decide(face: int, quality: int, liveness: int, yolo: int, reliability: int, matched: bool) -> str:
    if liveness < 40 and matched:
        return "Tentative suspecte"
    if not matched or face < 60:
        return "Présence refusée"
    if reliability >= 85 and face >= 80 and quality >= 55 and liveness >= 55:
        return "Présence validée"
    if reliability >= 60:
        return "Présence incertaine"
    return "Présence refusée"


def best_match(query_embedding: List[float]) -> Tuple[Optional[Dict[str, Any]], int]:
    if not query_embedding:
        return None, 0
    persons = []
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, first_name, last_name, matricule, role, department, contact, status,
                   photo_path, face_embedding, quality_score, created_at
            FROM persons
            ORDER BY id DESC
            """
        )
        persons = rows_to_dicts(cur, cur.fetchall())
    best_person = None
    best_score = 0
    for p in persons:
        try:
            emb = json.loads(p.get("face_embedding") or "[]")
        except Exception:
            emb = []
        score = cosine_similarity(query_embedding, emb)
        if score > best_score:
            best_person = p
            best_score = score
    if best_person:
        best_person.pop("face_embedding", None)
    return best_person, best_score


def make_proof_hash(image_path: Path, identity: str, date: str, time_str: str, reliability: int) -> str:
    h = hashlib.sha256()
    try:
        h.update(image_path.read_bytes())
    except Exception:
        pass
    h.update(f"{identity}|{date}|{time_str}|{reliability}".encode("utf-8"))
    return h.hexdigest()


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "BioProofAI/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Silence la console HTTP. Les erreurs sont remontées dans JSON.
        return

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json_dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
  
        try:
            path = urlparse(self.path).path

            # ==========================================
            # YOLOv8 - STATUS
            # ==========================================
            if path == "/api/yolo/status":
                self._send_json({
                    "ok": True,
                    "status": "online",
                    "model": "YOLOv8n",
                    "camera": 0,
                    "available": YOLO is not None
                })

            # ==========================================
            # YOLOv8 - WEBCAM TEMPS REEL
            # ==========================================
            elif path == "/api/yolo/stream":

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame"
                )

                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*"
                )

                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )

                self.end_headers()

                try:
                    for frame in generate_yolo_frames(
                        confidence=0.35
                    ):
                        self.wfile.write(frame)
                        self.wfile.flush()

                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ConnectionAbortedError
                ):
                    pass

            # ==========================================
            # ANCIENNES ROUTES DE TON APPLICATION
            # ==========================================
            elif path == "/api/health":
                self._send_json({
                    "ok": True,
                    "service": "BioProof AI Backend",
                    "time": now_parts()[2],
                    "modules": {
                        "python": True,
                        "tkinter": tk is not None,
                        "sqlite": True,
                        "pillow": Image is not None,
                        "opencv": cv2 is not None,
                        "face_recognition": face_recognition is not None,
                        "yolov8": YOLO is not None,
                    },
                })

            elif path == "/api/persons":
                self._send_json({
                    "persons": get_persons()
                })

            elif path == "/api/history":
                self._send_json({
                    "history": get_history()
                })

            elif path == "/api/admin/stats":
                self._send_json({
                    "stats": get_admin_stats()
                })

            elif path == "/api/admin/audit":
                self._send_json({
                    "logs": get_audit_logs()
                })

            elif path == "/api/settings":
                self._send_json({
                    "settings": get_system_settings()
                })

            else:
                self._send_json({
                    "error": "Endpoint introuvable"
                }, 404)

        except Exception as exc:
            try:
                self._send_json({
                    "error": str(exc),
                    "trace": traceback.format_exc()
                }, 500)
            except Exception:
                print(traceback.format_exc())

    def do_DELETE(self) -> None:
        try:
            path = urlparse(self.path).path
            if path.startswith("/api/persons/"):
                pid = int(path.rsplit("/", 1)[-1])
                _, _, created_at = now_parts()
                with sqlite3.connect(DB_PATH) as con:
                    row = con.execute("SELECT first_name,last_name,matricule FROM persons WHERE id=?", (pid,)).fetchone()
                    con.execute("DELETE FROM persons WHERE id=?", (pid,))
                    con.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)",
                                ("DELETE_PERSON", json_dumps({"id": pid, "person": row}), created_at))
                    con.commit()
                self._send_json({"ok": True, "deleted": pid})
            elif path.startswith("/api/history/"):
                sid = int(path.rsplit("/", 1)[-1])
                ok = delete_history_item(sid)
                self._send_json({"ok": ok, "deleted": sid} if ok else {"error": "Scan introuvable"}, 200 if ok else 404)
            elif path == "/api/history":
                deleted = clear_history_items()
                self._send_json({"ok": True, "deleted": deleted})
            else:
                self._send_json({"error": "Endpoint introuvable"}, 404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)

    def _read_form(self) -> MultipartForm:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Requête multipart/form-data attendue")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        raw = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8") + body
        message = BytesParser(policy=email_default_policy).parsebytes(raw)
        form = MultipartForm()
        if not message.is_multipart():
            return form
        for part in message.iter_parts():
            disposition = part.get("Content-Disposition", "")
            if "form-data" not in disposition:
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                form.add(name, UploadedFile(filename=filename, file=io.BytesIO(payload)))
            else:
                charset = part.get_content_charset() or "utf-8"
                form.add(name, payload.decode(charset, errors="replace"))
        return form

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Objet JSON attendu")
        return data

    def do_PUT(self) -> None:
        try:
            path = urlparse(self.path).path
            if path.startswith("/api/persons/"):
                pid = int(path.rsplit("/", 1)[-1])
                data = self._read_json()
                allowed = ["first_name", "last_name", "matricule", "role", "department", "contact", "status"]
                clean = {k: str(data.get(k, "")).strip() for k in allowed if k in data}
                if not clean:
                    self._send_json({"error": "Aucune donnée à modifier"}, 400)
                    return
                if "first_name" in clean and not clean["first_name"]:
                    self._send_json({"error": "Prénom obligatoire"}, 400)
                    return
                if "last_name" in clean and not clean["last_name"]:
                    self._send_json({"error": "Nom obligatoire"}, 400)
                    return
                if "matricule" in clean and not clean["matricule"]:
                    self._send_json({"error": "Matricule obligatoire"}, 400)
                    return
                assignments = ", ".join([f"{k}=?" for k in clean])
                params = list(clean.values()) + [pid]
                _, _, created_at = now_parts()
                with sqlite3.connect(DB_PATH) as con:
                    cur = con.cursor()
                    before = cur.execute("SELECT id FROM persons WHERE id=?", (pid,)).fetchone()
                    if not before:
                        self._send_json({"error": "Profil introuvable"}, 404)
                        return
                    cur.execute(f"UPDATE persons SET {assignments} WHERE id=?", params)
                    con.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)",
                                ("UPDATE_PERSON", json_dumps({"id": pid, "changes": clean}), created_at))
                    con.commit()
                self._send_json({"ok": True, "updated": pid, "changes": clean})
            elif path == "/api/settings":
                data = self._read_json()
                settings = save_system_settings(data)
                self._send_json({"ok": True, "settings": settings})
            else:
                self._send_json({"error": "Endpoint introuvable"}, 404)
        except sqlite3.IntegrityError:
            self._send_json({"error": "Matricule déjà utilisé par un autre profil"}, 409)
        except Exception as exc:
            self._send_json({"error": str(exc), "trace": traceback.format_exc()}, 500)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/register":
                self.handle_register()
            elif path == "/api/precheck-scan":
                self.handle_precheck()
            elif path == "/api/robust-analyze":
                self.handle_analyze()
            else:
                self._send_json({"error": "Endpoint introuvable"}, 404)
        except Exception as exc:
            self._send_json({"error": str(exc), "trace": traceback.format_exc()}, 500)

    def handle_register(self) -> None:
        form = self._read_form()
        photo = form["photo"] if "photo" in form else None
        if not photo or not getattr(photo, "filename", None):
            self._send_json({"error": "Photo obligatoire"}, 400)
            return
        first_name = str(form.getfirst("first_name", "")).strip()
        last_name = str(form.getfirst("last_name", "")).strip()
        matricule = str(form.getfirst("matricule", "")).strip()
        if not first_name or not last_name or not matricule:
            self._send_json({"error": "Nom, prénom et matricule sont obligatoires"}, 400)
            return
        image_path = save_uploaded_file(photo, UPLOAD_DIR, "register")
        restored_path = restore_image(image_path, "register_restored")
        yolo_meta = yolo_analyze(restored_path)
        face_path, face_detected, face_conf, crop_info = crop_subject_robust(restored_path, yolo_meta, "register")
        q_report = image_quality_report(face_path)
        quality = int(q_report.get("score", 50))
        emb = face_embedding(face_path)
        duplicate_person, duplicate_score = best_match(emb)
        _, _, created_at = now_parts()
        person = {
            "first_name": first_name,
            "last_name": last_name,
            "matricule": matricule,
            "role": str(form.getfirst("role", "")).strip(),
            "department": str(form.getfirst("department", "")).strip(),
            "contact": str(form.getfirst("contact", "")).strip(),
            "status": str(form.getfirst("status", "Actif")).strip() or "Actif",
        }
        try:
            with sqlite3.connect(DB_PATH) as con:
                cur = con.cursor()
                cur.execute(
                    """
                    INSERT INTO persons(first_name,last_name,matricule,role,department,contact,status,
                                        photo_path,restored_path,face_embedding,quality_score,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        person["first_name"], person["last_name"], person["matricule"], person["role"],
                        person["department"], person["contact"], person["status"], str(image_path), str(restored_path),
                        json_dumps(emb), quality, created_at,
                    ),
                )
                pid = cur.lastrowid
                con.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)",
                            ("REGISTER_PERSON", json_dumps({"matricule": matricule, "quality": quality}), created_at))
                con.commit()
        except sqlite3.IntegrityError:
            self._send_json({"error": "Matricule déjà enregistré"}, 409)
            return
        person.update({"id": pid, "created_at": created_at, "quality_score": quality})
        warnings = []
        if not face_detected:
            warnings.append("Aucun visage précis détecté : améliorez la photo de référence")
        if duplicate_person and duplicate_score >= 88:
            warnings.append(f"Profil similaire détecté : {duplicate_person.get('first_name','')} {duplicate_person.get('last_name','')} ({duplicate_score} %)")
        warnings.extend(q_report.get("warnings", []))
        self._send_json({
            "ok": True,
            "person": person,
            "registeredAt": created_at,
            "biometricProfile": {
                "faceEmbedding": bool(emb),
                "quality": quality,
                "qualityDetails": q_report,
                "faceDetected": face_detected,
                "faceConfidence": pct(face_conf),
                "crop": crop_info,
                "yolo": yolo_meta,
                "duplicateWarning": duplicate_score if duplicate_person else 0,
                "warnings": warnings,
                "restored": True,
            },
        })

    def handle_precheck(self) -> None:
        """Pré-analyse légère pour le scan automatique conditionnel.

        Le frontend l'utilise avant de lancer une analyse complète. Cela évite les scans
        inutiles lorsque le visage est absent, trop sombre, mal cadré ou si plusieurs
        personnes sont visibles.
        """
        form = self._read_form()
        field = form["image"] if "image" in form else None
        if not field or not getattr(field, "filename", None):
            self._send_json({"error": "Image de précontrôle obligatoire"}, 400)
            return
        image_path = save_uploaded_file(field, PROOF_DIR, "precheck")
        restored_path = restore_image(image_path, "precheck_restored")
        yolo_meta = yolo_analyze(restored_path)
        face_path, face_detected, face_conf, crop_info = crop_subject_robust(restored_path, yolo_meta, "precheck")
        q_report = image_quality_report(face_path)
        quality = int(q_report.get("score", 50))
        people = int(yolo_meta.get("persons") or (1 if face_detected else 0))
        reasons = []
        if not face_detected and yolo_meta.get("bestPersonBox") is None:
            reasons.append("Aucun visage/personne exploitable détecté")
        if people > 1:
            reasons.append("Plusieurs personnes visibles")
        if quality < 55:
            reasons.append("Qualité image insuffisante")
        if yolo_meta.get("suspiciousObjects"):
            reasons.append("Téléphone ou écran détecté")
        ready = not reasons
        self._send_json({
            "ok": True,
            "ready": ready,
            "status": "Prêt pour scan automatique" if ready else "Scan non déclenché",
            "reasons": reasons,
            "qualityScore": quality,
            "qualityDetails": q_report,
            "faceDetected": face_detected,
            "faceConfidence": pct(face_conf),
            "peopleCount": people,
            "yoloScore": yolo_meta.get("score", 45),
            "yolo": yolo_meta,
            "crop": crop_info,
        })

    def handle_analyze(self) -> None:
        form = self._read_form()
        field = form["image"] if "image" in form else None
        if not field or not getattr(field, "filename", None):
            self._send_json({"error": "Image de scan obligatoire"}, 400)
            return
        image_path = save_uploaded_file(field, PROOF_DIR, "scan")
        restored_path = restore_image(image_path, "scan_restored")
        yolo_meta = yolo_analyze(restored_path)
        yolo = int(yolo_meta.get("score", 45))
        face_path, face_detected, face_conf, crop_info = crop_subject_robust(restored_path, yolo_meta, "scan")
        q_report = image_quality_report(face_path)
        quality = int(q_report.get("score", 50))
        liveness = liveness_score(face_path, quality, face_detected)
        emb = face_embedding(face_path)
        person, face_score = best_match(emb)
        # Correction professionnelle : pas de validation si le visage n'est pas fiablement détecté.
        matched = bool(person and face_score >= 65 and face_detected)
        reliability = reliability_score(face_score, quality, liveness, yolo)
        decision = decide(face_score, quality, liveness, yolo, reliability, matched)
        if not face_detected:
            decision = "Présence refusée"
        if int(yolo_meta.get("persons") or 1) > 1:
            decision = "Tentative suspecte"
        if yolo_meta.get("suspiciousObjects") and liveness < 60:
            decision = "Tentative suspecte"
        date, time_str, created_at = now_parts()
        identity = "Personne inconnue"
        matricule = "—"
        person_id = None
        profile = None
        if person and matched and decision not in {"Présence refusée", "Tentative suspecte"}:
            person_id = person.get("id")
            identity = f"{person.get('first_name','')} {person.get('last_name','')}".strip() or "Personne reconnue"
            matricule = person.get("matricule") or "—"
            profile = {k: person.get(k) for k in ["id", "first_name", "last_name", "matricule", "role", "department", "contact", "status", "created_at"]}
        previous_hash = get_previous_proof_hash()
        proof_hash = make_proof_hash(image_path, identity, date, time_str, reliability)
        chained_hash = hashlib.sha256(f"{previous_hash}|{proof_hash}".encode("utf-8")).hexdigest()
        recommendations = build_recommendations(face_score, q_report, liveness, yolo_meta, face_detected)
        risk = risk_level(decision, face_score, quality, liveness, yolo_meta)
        explanation = self._build_explanation(decision, face_score, quality, liveness, yolo, yolo_meta, q_report, recommendations)
        with sqlite3.connect(DB_PATH) as con:
            con.execute(
                """
                INSERT INTO scan_history(person_id,name,matricule,decision,face_score,quality_score,liveness_score,
                                         yolo_score,reliability_score,scan_date,scan_time,proof_image,proof_hash,explanation,created_at,
                                         risk_level,recommendations,previous_hash,quality_details,yolo_details)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (person_id, identity, matricule, decision, face_score, quality, liveness, yolo, reliability,
                 date, time_str, str(image_path), chained_hash, explanation, created_at, risk,
                 json_dumps(recommendations), previous_hash, json_dumps(q_report), json_dumps(yolo_meta)),
            )
            con.execute("INSERT INTO audit_logs(action,details,created_at) VALUES(?,?,?)",
                        ("SCAN_ANALYZED", json_dumps({"decision": decision, "risk": risk, "reliability": reliability}), created_at))
            con.commit()
        self._send_json({
            "ok": True,
            "profile": profile,
            "person": profile,
            "decision": decision,
            "riskLevel": risk,
            "faceScore": face_score,
            "qualityScore": quality,
            "qualityDetails": q_report,
            "livenessScore": liveness,
            "yoloScore": yolo,
            "reliabilityScore": reliability,
            "scanDate": date,
            "scanTime": time_str,
            "proofHash": chained_hash,
            "previousHash": previous_hash,
            "proof": chained_hash[:16] + "…",
            "faceDetected": face_detected,
            "faceConfidence": pct(face_conf),
            "crop": crop_info,
            "yolo": yolo_meta,
            "recommendations": recommendations,
            "explanation": explanation,
        })

    @staticmethod
    def _build_explanation(decision: str, face: int, quality: int, liveness: int, yolo: int,
                           yolo_meta: Optional[Dict[str, Any]] = None,
                           quality_report: Optional[Dict[str, Any]] = None,
                           recommendations: Optional[List[str]] = None) -> str:
        reasons = []
        yolo_meta = yolo_meta or {}
        quality_report = quality_report or {}
        if face < 65:
            reasons.append("similarité faciale insuffisante")
        if quality < 55:
            reasons.append("qualité d'image faible")
        if liveness < 40:
            reasons.append("vivacité insuffisante, risque de photo ou écran")
        if yolo < 50:
            reasons.append("détection YOLOv8 faible")
        if yolo_meta.get("persons", 1) > 1:
            reasons.append("plusieurs personnes détectées")
        if yolo_meta.get("suspiciousObjects"):
            reasons.append("téléphone/écran détecté dans la scène")
        for w in quality_report.get("warnings", []):
            if w not in reasons:
                reasons.append(w)
        if not reasons:
            reasons.append("scores biométriques cohérents")
        rec_txt = " Recommandation : " + "; ".join((recommendations or [])[:3]) + "." if recommendations else ""
        return f"{decision} : " + "; ".join(reasons) + "." + rec_txt


def start_server() -> None:
    global _server, _server_thread
    init_db()
    if _server is not None:
        return
    _server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()


def stop_server() -> None:
    global _server, _server_thread
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
        _server_thread = None


class BackendApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BioProof AI - Backend local")
        self.root.geometry("760x460")
        self.root.minsize(720, 420)
        self.status_var = tk.StringVar(value="Backend arrêté")
        self.modules_var = tk.StringVar(value=self.module_text())
        self.build_ui()

    def module_text(self) -> str:
        return (
            f"SQLite: OK | Pillow: {'OK' if Image else 'manquant'} | "
            f"OpenCV: {'OK' if cv2 else 'manquant'} | "
            f"FaceRecognize: {'face_recognition' if face_recognition else 'fallback local'} | "
            f"YOLOv8: {'OK' if YOLO else 'optionnel/manquant'}"
        )

    def build_ui(self):
        main = ttk.Frame(self.root, padding=22)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="BioProof AI Backend", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="API locale pour reconnaissance faciale, fiabilité, vivacité et historique SQLite.").pack(anchor="w", pady=(4, 18))

        card = ttk.LabelFrame(main, text="État du serveur", padding=16)
        card.pack(fill="x", pady=(0, 14))
        ttk.Label(card, textvariable=self.status_var, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(card, text=f"URL API : http://localhost:{PORT}").pack(anchor="w", pady=(4, 0))
        ttk.Label(card, textvariable=self.modules_var, wraplength=680).pack(anchor="w", pady=(4, 0))

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Démarrer le backend", command=self.on_start).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Arrêter", command=self.on_stop).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Ouvrir le dossier backend", command=self.open_folder).pack(side="left")

        info = ttk.LabelFrame(main, text="Endpoints disponibles", padding=16)
        info.pack(fill="both", expand=True, pady=(12, 0))
        text = (
            "GET  /api/health\n"
            "POST /api/register\n"
            "POST /api/precheck-scan\n"
            "POST /api/robust-analyze\n"
            "GET  /api/persons\n"
            "GET  /api/history\n"
            "DELETE /api/persons/<id>\n\n"
            "Conseil : lancez ensuite le frontend avec : python -m http.server 5500"
        )
        ttk.Label(info, text=text, justify="left").pack(anchor="w")

    def on_start(self):
        try:
            start_server()
            self.status_var.set(f"Backend en ligne sur http://localhost:{PORT}")
        except Exception as exc:
            if messagebox:
                messagebox.showerror("Erreur", str(exc))
            self.status_var.set("Erreur de démarrage")

    def on_stop(self):
        stop_server()
        self.status_var.set("Backend arrêté")

    def open_folder(self):
        try:
            os.startfile(str(BASE_DIR))  # type: ignore[attr-defined]
        except Exception:
            pass


def main():
    init_db()
    if tk is None:
        print(f"Tkinter indisponible. Démarrage direct sur http://localhost:{PORT}")
        start_server()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_server()
        return
    root = tk.Tk()
    app = BackendApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (stop_server(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
