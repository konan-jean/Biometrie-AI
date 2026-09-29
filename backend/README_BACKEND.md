# Backend BioProof AI

Backend local Python/Tkinter pour le système intelligent de preuve de présence biométrique anti-fraude.

## Technologies

- Python
- Tkinter
- SQLite
- OpenCV / FaceRecognize
- YOLOv8 via `ultralytics` optionnel
- Pillow

## Rôle du backend

- démarrer l’API locale ;
- gérer les profils ;
- analyser les images ;
- faire la reconnaissance ;
- calculer la fiabilité ;
- enregistrer l’historique.

## Installation

Depuis le dossier `backend` :

```powershell
python -m pip install -r requirements.txt
```

## Lancement

```powershell
python app_tkinter.py
```

Cliquez ensuite sur **Démarrer le backend**.

API locale :

```text
http://localhost:8000
```

## Endpoints

| Méthode | Endpoint | Rôle |
|---|---|---|
| GET | `/api/health` | vérifier l’état du backend |
| POST | `/api/register` | enregistrer une personne |
| POST | `/api/robust-analyze` | analyser une capture webcam |
| GET | `/api/persons` | lister les personnes |
| GET | `/api/history` | consulter l’historique |
| DELETE | `/api/persons/<id>` | supprimer une personne |

## Remarque importante

Le backend fournit une reconnaissance locale exploitable pour un prototype universitaire. Pour un système biométrique de production, il est recommandé d’utiliser des embeddings spécialisés comme ArcFace, FaceNet ou InsightFace, avec une vraie détection de vivacité multi-images.
