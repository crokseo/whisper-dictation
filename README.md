# Whisper Dictation

Dictée vocale système sous Windows via Faster-Whisper.  
Maintenez **F9** pour dicter n'importe où (terminal, navigateur, Word…), relâchez pour coller le texte automatiquement.

## Installation

```powershell
pip install -r requirements.txt
```

> FFmpeg doit être installé et dans le PATH : https://ffmpeg.org/download.html

## Utilisation

```powershell
python dictee.py
```

Ou double-cliquer sur `lancer.bat`.

## Configuration

Modifier les variables en haut de `dictee.py` :

| Variable        | Défaut  | Description                              |
|----------------|---------|------------------------------------------|
| `MODELE`       | `base`  | Taille du modèle : tiny / base / small / medium / large-v3 |
| `LANGUE`       | `fr`    | Langue de transcription                  |
| `TOUCHE`       | `F9`    | Touche à maintenir pour dicter           |

## Modèles disponibles

| Modèle    | Précision | Vitesse | RAM  |
|-----------|-----------|---------|------|
| tiny      | Faible    | Très rapide | ~400 Mo |
| base      | Correcte  | Rapide  | ~700 Mo |
| small     | Bonne     | Moyenne | ~1.5 Go |
| medium    | Très bonne | Lente  | ~3 Go  |
| large-v3  | Excellente | Très lente | ~6 Go |
