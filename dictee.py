#!/usr/bin/env python3
"""
Dictee vocale systeme - Faster-Whisper + PyAutoGUI
Maintenez F9 pour dicter, relacher pour transcrire et coller automatiquement.
Icone systray : verte (pret) / rouge (enregistrement).
Clic gauche : historique des 10 dernières dictées.
Clic droit > Quitter.
"""

import sys
import os
import time
import threading
import tkinter as tk
import numpy as np

# Compatibilité pythonw (pas de console)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
import sounddevice as sd
import keyboard
import pyperclip
import pyautogui
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw
import pystray

# --- Configuration (modifiable) ---
MODELE           = "base"   # tiny | base | small | medium | large-v3
LANGUE           = "fr"     # fr | en | auto | ...
TOUCHE           = "F9"     # Touche a maintenir pour dicter
TAUX_ECHANTILLON = 16000
DUREE_MIN_SEC    = 0.5
MAX_HISTORIQUE   = 10
# ----------------------------------

print("Chargement du modele Whisper, patientez...")
modele = WhisperModel(MODELE, device="cpu", compute_type="int8")
print(f"  Modele '{MODELE}' charge.")
print(f"  Icone systray active - clic droit pour quitter.\n")

en_enregistrement = False
donnees_audio     = []
tray_icon         = None
historique        = []  # dernières phrases dictées


def creer_icone(enregistrement=False):
    """Cree une icone ronde : rouge si enregistrement, verte sinon."""
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    couleur = (220, 50, 50) if enregistrement else (50, 200, 80)
    draw.ellipse([4, 4, 60, 60], fill=couleur)
    draw.ellipse([20, 20, 44, 44], fill=(255, 255, 255, 180))
    return img


def ajouter_historique(texte):
    """Ajoute une phrase en tête de l'historique (max MAX_HISTORIQUE)."""
    historique.insert(0, texte)
    if len(historique) > MAX_HISTORIQUE:
        historique.pop()


def ouvrir_historique(icon=None, item=None):
    """Ouvre le widget historique dans un thread dédié."""
    def _construire_fenetre():
        root = tk.Tk()
        root.title("Historique des dictées")
        root.configure(bg="#1e1e1e")
        root.resizable(False, False)
        root.wm_attributes("-topmost", True)
        # Pas d'entrée dans la barre des tâches
        root.wm_attributes("-toolwindow", True)

        # Position : coin bas-droit, au-dessus de la barre des tâches
        largeur, hauteur = 480, min(80 + len(historique) * 58, 680)
        x = root.winfo_screenwidth() - largeur - 20
        y = root.winfo_screenheight() - hauteur - 60
        root.geometry(f"{largeur}x{hauteur}+{x}+{y}")

        # En-tête
        en_tete = tk.Frame(root, bg="#2d2d2d", pady=10)
        en_tete.pack(fill="x")
        tk.Label(
            en_tete,
            text="  Historique des dictées",
            bg="#2d2d2d",
            fg="#cccccc",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(side="left", padx=10)
        tk.Label(
            en_tete,
            text=f"{len(historique)}/{MAX_HISTORIQUE}",
            bg="#2d2d2d",
            fg="#666666",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=10)

        # Zone scrollable
        canvas    = tk.Canvas(root, bg="#1e1e1e", highlightthickness=0)
        scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
        frame_interieur = tk.Frame(canvas, bg="#1e1e1e")

        frame_interieur.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=frame_interieur, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        if not historique:
            tk.Label(
                frame_interieur,
                text="Aucune dictée pour l'instant.\nMaintenez F9 pour dicter.",
                bg="#1e1e1e",
                fg="#666666",
                font=("Segoe UI", 10),
                pady=30,
            ).pack()
        else:
            for i, phrase in enumerate(historique):
                ligne = tk.Frame(frame_interieur, bg="#2a2a2a", pady=8, padx=10)
                ligne.pack(fill="x", padx=8, pady=3)

                # Numéro
                tk.Label(
                    ligne,
                    text=f"#{i + 1}",
                    bg="#2a2a2a",
                    fg="#555555",
                    font=("Segoe UI", 8),
                    width=3,
                    anchor="n",
                ).pack(side="left", padx=(0, 6), anchor="n")

                # Texte (avec retour à la ligne automatique)
                tk.Label(
                    ligne,
                    text=phrase,
                    bg="#2a2a2a",
                    fg="#e0e0e0",
                    font=("Segoe UI", 9),
                    anchor="w",
                    justify="left",
                    wraplength=340,
                ).pack(side="left", fill="x", expand=True, anchor="n")

                # Bouton copier
                def _copier(p=phrase, r=root):
                    pyperclip.copy(p)
                    r.destroy()

                btn = tk.Button(
                    ligne,
                    text="📋",
                    command=_copier,
                    bg="#3a3a3a",
                    fg="white",
                    activebackground="#505050",
                    relief="flat",
                    font=("Segoe UI", 11),
                    cursor="hand2",
                    padx=6,
                    pady=2,
                )
                btn.pack(side="right", anchor="n")

        canvas.pack(side="left", fill="both", expand=True)
        if historique:
            scrollbar.pack(side="right", fill="y")

        # Pied : bouton Fermer
        pied = tk.Frame(root, bg="#2d2d2d", pady=8)
        pied.pack(fill="x", side="bottom")
        tk.Button(
            pied,
            text="Fermer",
            command=root.destroy,
            bg="#3a3a3a",
            fg="#cccccc",
            activebackground="#505050",
            relief="flat",
            font=("Segoe UI", 9),
            padx=16,
            pady=4,
            cursor="hand2",
        ).pack()

        # Fermer avec Échap
        root.bind("<Escape>", lambda e: root.destroy())

        root.mainloop()

    threading.Thread(target=_construire_fenetre, daemon=True).start()


def callback_audio(indata, frames, time_info, status):
    if en_enregistrement:
        donnees_audio.append(indata.copy())


# Retry au démarrage : attend que le driver MME soit prêt (jusqu'à 60s)
flux = None
for _tentative in range(12):
    try:
        flux = sd.InputStream(
            samplerate=TAUX_ECHANTILLON,
            channels=1,
            dtype="float32",
            callback=callback_audio,
        )
        flux.start()
        break
    except Exception as _e:
        print(f"  Micro indisponible, nouvel essai dans 5s... ({_e})")
        time.sleep(5)

if flux is None:
    print("Erreur : impossible d'ouvrir le micro après 60s. Vérifiez le micro par défaut Windows.")
    sys.exit(1)

nom_micro = sd.query_devices(kind="input")["name"]
print(f"  Micro utilisé : {nom_micro}")


def debut_enregistrement(event):
    global en_enregistrement, donnees_audio
    if en_enregistrement:
        return
    en_enregistrement = True
    donnees_audio     = []
    print("  Enregistrement...", end="\r")
    if tray_icon:
        tray_icon.icon  = creer_icone(enregistrement=True)
        tray_icon.title = "🔴 Whisper — Enregistrement..."


def fin_et_transcription(event):
    global en_enregistrement
    if not en_enregistrement:
        return
    en_enregistrement = False

    if tray_icon:
        tray_icon.icon  = creer_icone(enregistrement=False)
        tray_icon.title = "🟢 Whisper Dictée (F9)"

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
        ajouter_historique(texte)
        pyperclip.copy(texte)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
    else:
        print("  Aucun texte detecte.")


def quitter(icon, item):
    """Arret propre depuis le menu systray."""
    icon.stop()
    flux.stop()
    flux.close()
    sys.exit(0)


def lancer_clavier():
    keyboard.on_press_key(TOUCHE,   debut_enregistrement)
    keyboard.on_release_key(TOUCHE, fin_et_transcription)
    keyboard.wait()


# Thread clavier en arriere-plan
t = threading.Thread(target=lancer_clavier, daemon=True)
t.start()

# Icone systray dans le thread principal
menu = pystray.Menu(
    pystray.MenuItem(
        "📋 Historique des dictées",
        ouvrir_historique,
        default=True,   # clic gauche sur l'icone
    ),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem("Maintenez F9 pour dicter", None, enabled=False),
    pystray.MenuItem(f"🎙 {nom_micro}", None, enabled=False),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem("Quitter", quitter),
)

tray_icon = pystray.Icon(
    name="whisper-dictee",
    icon=creer_icone(enregistrement=False),
    title="🟢 Whisper Dictée (F9)",
    menu=menu,
)

print("  Pret ! Icone dans le systray. Clic gauche = historique. Clic droit > Quitter.\n")
tray_icon.run()
