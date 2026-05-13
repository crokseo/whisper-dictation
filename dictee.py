#!/usr/bin/env python3
"""
Dictee vocale systeme - Faster-Whisper + PyAutoGUI
Maintenez F9 pour dicter, relacher pour transcrire et coller automatiquement.
"""

import sys
import time
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import pyautogui
from faster_whisper import WhisperModel

# --- Configuration (modifiable) ---
MODELE           = "base"   # tiny | base | small | medium | large-v3
LANGUE           = "fr"     # fr | en | auto | ...
TOUCHE           = "F9"     # Touche a maintenir pour dicter
TAUX_ECHANTILLON = 16000
DUREE_MIN_SEC    = 0.5
# ----------------------------------

print("Chargement du modele Whisper, patientez...")
modele = WhisperModel(MODELE, device="cpu", compute_type="int8")
print(f"  Modele '{MODELE}' charge.")
print(f"  Maintenez [F9] pour dicter - relacher pour transcrire.")
print(f"  Ctrl+C pour quitter.\n")

en_enregistrement = False
donnees_audio     = []


def callback_audio(indata, frames, time_info, status):
    if en_enregistrement:
        donnees_audio.append(indata.copy())


flux = sd.InputStream(
    samplerate=TAUX_ECHANTILLON,
    channels=1,
    dtype="float32",
    callback=callback_audio,
)
flux.start()


def debut_enregistrement(event):
    global en_enregistrement, donnees_audio
    if en_enregistrement:
        return
    en_enregistrement = True
    donnees_audio     = []
    print("  Enregistrement...", end="\r")


def fin_et_transcription(event):
    global en_enregistrement
    if not en_enregistrement:
        return
    en_enregistrement = False

    if not donnees_audio:
        return

    audio = np.concatenate(donnees_audio).flatten()

    if len(audio) < TAUX_ECHANTILLON * DUREE_MIN_SEC:
        print("  Trop court, ignore.                    ")
        return

    duree  = len(audio) / TAUX_ECHANTILLON
    niveau = float(np.abs(audio).mean())
    print(f"  Transcription... ({duree:.1f}s, niveau={niveau:.4f})")

    segments, _ = modele.transcribe(audio, language=LANGUE, beam_size=5)
    texte = " ".join(seg.text for seg in segments).strip()

    if texte:
        print(f"  OK : {texte}")
        pyperclip.copy(texte)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
    else:
        print("  Aucun texte detecte.")


keyboard.on_press_key(TOUCHE,   debut_enregistrement)
keyboard.on_release_key(TOUCHE, fin_et_transcription)

print(f"  Pret ! Maintenez F9 pour dicter.\n")

try:
    keyboard.wait()
except KeyboardInterrupt:
    print("\n  Arret.")
    flux.stop()
    flux.close()
    sys.exit(0)
