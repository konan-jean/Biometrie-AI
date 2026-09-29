# BioProof AI — Template fullstack renforcé

Application universitaire professionnelle pour un **système intelligent de preuve de présence biométrique anti-fraude**.

## Modules inclus

- Frontend HTML/CSS/JavaScript
- Backend Python/Tkinter
- API locale HTTP sur `http://localhost:8000`
- SQLite
- OpenCV / FaceRecognize léger
- YOLOv8 optionnel
- Pillow pour amélioration d'image
- Scan automatique intelligent
- Précontrôle avant scan
- Score global de fiabilité
- Niveau de risque
- Explication de décision
- Historique avec hash de preuve chaîné

## Corrections de robustesse ajoutées

### 1. Scan automatique conditionnel
Le système ne scanne plus uniquement toutes les 5 secondes. Il vérifie d'abord :

- présence d'un visage ou d'une personne ;
- une seule personne visible ;
- qualité d'image suffisante ;
- absence d'objet suspect comme téléphone ou écran ;
- stabilité minimale avant analyse.

Endpoint :

```text
POST /api/precheck-scan
```

### 2. Correction des failles YOLOv8
YOLOv8 est utilisé pour :

- compter les personnes visibles ;
- détecter la meilleure personne ;
- détecter les objets suspects : téléphone, écran, ordinateur ;
- réduire le score si plusieurs personnes sont présentes ;
- éviter une validation sur une scène ambiguë.

YOLOv8 ne reconnaît pas l'identité. L'identité est traitée par le module facial.

### 3. Recadrage robuste
Ordre de priorité :

```text
visage OpenCV -> haut du corps YOLOv8 -> centre de l'image
```

Cela réduit l'influence de l'arrière-plan et améliore l'analyse faciale.

### 4. Qualité image détaillée
Le système calcule :

- luminosité ;
- contraste ;
- netteté ;
- avertissements : image sombre, floue, surexposée.

### 5. Décision professionnelle
Résultats possibles :

- Présence validée ;
- Présence incertaine ;
- Présence refusée ;
- Tentative suspecte.

### 6. Explication de décision
Chaque scan retourne :

- raisons de la décision ;
- recommandations de correction ;
- niveau de risque ;
- alertes YOLOv8 ;
- hash de preuve chaîné.

## Lancement

### Backend

```powershell
cd "C:\Users\GPC\Desktop\biometric-fullstack-template\backend"
python -m pip install -r requirements.txt
python app_tkinter.py
```

Cliquez sur **Démarrer le backend**.

### Frontend

```powershell
cd "C:\Users\GPC\Desktop\biometric-fullstack-template"
python -m http.server 5500
```

Ouvrir :

```text
http://localhost:5500
```

Puis faire `Ctrl + F5`.

## Endpoints

```text
GET    /api/health
POST   /api/register
POST   /api/precheck-scan
POST   /api/robust-analyze
GET    /api/persons
GET    /api/history
DELETE /api/persons/<id>
```

## Important

Pour un vrai système biométrique de production, il faudra remplacer l'embedding facial léger par ArcFace, FaceNet, DeepFace ou InsightFace.

## Correction AutoScan 5 secondes

Cette version active un scan automatique direct : après le démarrage de la webcam, le frontend lance une capture et une analyse toutes les 5 secondes.

Le précontrôle YOLOv8/qualité reste affiché pour renforcer la décision et produire des avertissements, mais il ne bloque plus le lancement de l'analyse automatique. Ainsi, même si l'image est sombre ou si la qualité est moyenne, l'utilisateur obtient un résultat biométrique avec recommandations.

Pour tester :

1. Démarrer le backend Python.
2. Lancer le frontend.
3. Aller dans Scanner robuste.
4. Cliquer sur Démarrer webcam.
5. Attendre 5 secondes : la capture et l'analyse se lancent automatiquement.

## Espace admin ajouté

Cette version contient un espace administrateur professionnel accessible depuis la sidebar : **Espace admin**.

Identifiants de prototype :

```text
admin / admin123
```

Fonctions disponibles :

- tableau de statistiques des profils enregistrés ;
- recherche et filtrage par statut ;
- modification des informations d’un profil ;
- suppression individuelle ;
- suppression groupée ;
- export CSV des profils ;
- journal administratif des actions ;
- synchronisation avec le backend Python via les endpoints `/api/persons`, `/api/admin/stats`, `/api/admin/audit`.

Important : l’authentification actuelle est une protection locale adaptée au prototype universitaire. Pour une version de production, il faudra ajouter une authentification sécurisée côté backend avec mots de passe hachés, rôles utilisateurs et sessions protégées.

## Mise à jour : Espace admin avancé

L’espace admin inclut maintenant trois sections professionnelles :

1. **Profils biométriques** : recherche, modification, suppression, export CSV et journal administratif.
2. **Historique des scans** : consultation des preuves, filtrage par décision, suppression d’un scan, vidage de l’historique et export CSV.
3. **Paramètres système** : seuil facial, seuil de fiabilité, seuil de vivacité, seuil qualité, intervalle du scan automatique, conservation de l’historique, mode de décision et synchronisation backend.

Endpoints ajoutés :

```text
GET    /api/settings
PUT    /api/settings
DELETE /api/history/<id>
DELETE /api/history
```

Identifiants prototype :

```text
admin / admin123
```

Pour une version réelle, remplacez cette authentification locale par une authentification backend avec mots de passe hachés et rôles.
