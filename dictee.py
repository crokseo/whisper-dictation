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
import atexit

# Ajout des DLLs CUDA 12 installées via pip au PATH Windows
_cuda_bins = [
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cuda_runtime", "bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cuda_nvrtc", "bin"),
]
for _p in _cuda_bins:
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(_p)

# Compatibilité pythonw (pas de console)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Verrou instance unique : empêche plusieurs instances simultanées
_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictee.lock")

def _verifier_instance_unique():
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE) as f:
                pid = int(f.read().strip())
            # Vérifie si le PID est encore actif
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                print(f"Une instance tourne déjà (PID {pid}). Arrêt.")
                sys.exit(0)
        except Exception:
            pass  # PID invalide ou processus mort — on continue
    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(_LOCK_FILE) and os.remove(_LOCK_FILE))

_verifier_instance_unique()
import sounddevice as sd
import keyboard
import pyperclip
import pyautogui
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw
import pystray

# --- Configuration (modifiable) ---
MODELE           = "large-v3-turbo"  # tiny | base | small | medium | large-v3 | large-v3-turbo
LANGUE           = "fr"     # fr | en | auto | ...
TOUCHE           = "F9"     # Touche a maintenir pour dicter
TAUX_ECHANTILLON = 16000
DUREE_MIN_SEC    = 0.5
MAX_HISTORIQUE   = 10
PROMPT_INITIAL   = (
    "Google Ads, ROAS, CPA, CTR, PMax, Quality Score, campagne, enchères, "
    "conversion, remarketing, audience, budget, CPC, impression, clics, "
    "annonce, mots-clés, négatifs, extensions, ciblage, reporting, dashboard"
)
# ----------------------------------

print("Chargement du modele Whisper, patientez...")
modele = WhisperModel(MODELE, device="cuda", compute_type="float16")
print(f"  Modele '{MODELE}' charge.")
print(f"  Icone systray active - clic droit pour quitter.\n")

en_enregistrement = False
en_pause          = False
donnees_audio     = []
tray_icon         = None
historique        = []  # dernières phrases dictées


def creer_icone(enregistrement=False, pause=False, alerte=False):
    """Cree une icone ronde : rouge=enregistrement, grise=pause, orange=alerte, verte=prêt."""
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if enregistrement:
        couleur = (220, 50, 50)
    elif pause:
        couleur = (130, 130, 130)
    elif alerte:
        couleur = (230, 130, 30)
    else:
        couleur = (50, 200, 80)
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
        root.resizable(True, True)
        root.wm_attributes("-topmost", True)
        root.wm_attributes("-toolwindow", True)

        largeur, hauteur = 560, min(100 + len(historique) * 72, 700)
        x = root.winfo_screenwidth() - largeur - 20
        y = root.winfo_screenheight() - hauteur - 60
        root.geometry(f"{largeur}x{hauteur}+{x}+{y}")
        root.minsize(400, 200)

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

        # Pied : bouton Fermer (packé avant le canvas pour rester fixe en bas)
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

        # Zone scrollable
        conteneur = tk.Frame(root, bg="#1e1e1e")
        conteneur.pack(fill="both", expand=True)

        canvas    = tk.Canvas(conteneur, bg="#1e1e1e", highlightthickness=0)
        scrollbar = tk.Scrollbar(conteneur, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame_interieur = tk.Frame(canvas, bg="#1e1e1e")
        fenetre_canvas = canvas.create_window((0, 0), window=frame_interieur, anchor="nw")

        def _on_resize(event):
            canvas.itemconfig(fenetre_canvas, width=event.width)
        canvas.bind("<Configure>", _on_resize)

        frame_interieur.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        # Scroll à la molette
        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

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
                # Carte : grid avec 3 colonnes [numéro | texte | bouton]
                carte = tk.Frame(frame_interieur, bg="#2a2a2a")
                carte.pack(fill="x", padx=8, pady=4)
                carte.columnconfigure(1, weight=1)  # colonne texte s'étire

                # Numéro
                tk.Label(
                    carte,
                    text=f"#{i + 1}",
                    bg="#2a2a2a",
                    fg="#555555",
                    font=("Segoe UI", 8),
                    width=3,
                    anchor="nw",
                ).grid(row=0, column=0, sticky="nw", padx=(10, 4), pady=10)

                # Texte
                lbl_texte = tk.Label(
                    carte,
                    text=phrase,
                    bg="#2a2a2a",
                    fg="#e0e0e0",
                    font=("Segoe UI", 10),
                    anchor="nw",
                    justify="left",
                    wraplength=370,
                )
                lbl_texte.grid(row=0, column=1, sticky="nw", pady=10)

                # Bouton copier — feedback visuel "Copié !"
                def _copier(p=phrase, b=None):
                    pyperclip.copy(p)
                    if b:
                        b.config(text="✓ Copié", fg="#5cb85c")
                        b.after(1200, lambda: b.config(text="📋 Copier", fg="#cccccc"))

                btn = tk.Button(
                    carte,
                    text="📋 Copier",
                    bg="#3a3a3a",
                    fg="#cccccc",
                    activebackground="#505050",
                    activeforeground="white",
                    relief="flat",
                    font=("Segoe UI", 9),
                    cursor="hand2",
                    padx=10,
                    pady=6,
                )
                btn.config(command=lambda p=phrase, b=btn: _copier(p, b))
                btn.grid(row=0, column=2, sticky="ne", padx=10, pady=10)

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


def surveiller_flux():
    """Vérifie toutes les 5s que le flux audio est actif, passe en orange sinon."""
    while True:
        time.sleep(5)
        if tray_icon and not en_enregistrement and not en_pause:
            actif = flux is not None and flux.active
            tray_icon.icon = creer_icone(alerte=not actif)
            tray_icon.title = "🟢 Whisper Dictée (F9)" if actif else "🟠 Whisper — Micro indisponible"


def basculer_pause(icon=None, item=None):
    global en_pause
    en_pause = not en_pause
    if en_pause:
        icon.icon  = creer_icone(pause=True)
        icon.title = "⏸ Whisper Dictée — En pause"
    else:
        icon.icon  = creer_icone()
        icon.title = "🟢 Whisper Dictée (F9)"
    icon.update_menu()


def debut_enregistrement(event):
    global en_enregistrement, donnees_audio
    if en_pause or en_enregistrement:
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

    segments, _ = modele.transcribe(
        audio,
        language=LANGUE,
        beam_size=1,
        temperature=0,
        vad_filter=True,
        initial_prompt=PROMPT_INITIAL,
    )
    texte = " ".join(seg.text for seg in segments).strip()

    # Post-traitement : majuscule initiale + point final si absent
    if texte:
        texte = texte[0].upper() + texte[1:]
        if texte[-1] not in ".!?…":
            texte += "."

    if texte:
        print(f"  OK : {texte}")
        ajouter_historique(texte)
        pyperclip.copy(texte)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
    else:
        print("  Aucun texte detecte.")


def redemarrer(icon, item):
    """Relance le processus complet (utile après une mise en veille)."""
    import subprocess
    subprocess.Popen([sys.executable, os.path.abspath(__file__)])
    flux.stop()
    flux.close()
    # Arrêt dans un thread pour éviter l'erreur SystemExit dans le callback pystray
    threading.Thread(target=icon.stop, daemon=True).start()


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

# Thread surveillance flux audio (icône orange si micro indisponible)
threading.Thread(target=surveiller_flux, daemon=True).start()

# Icone systray dans le thread principal
menu = pystray.Menu(
    pystray.MenuItem(
        "📋 Historique des dictées",
        ouvrir_historique,
        default=True,   # clic gauche sur l'icone
    ),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem(
        lambda item: "▶ Reprendre la dictée" if en_pause else "⏸ Mettre en pause",
        basculer_pause,
    ),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem("Maintenez F9 pour dicter", None, enabled=False),
    pystray.MenuItem(f"🎙 {nom_micro}", None, enabled=False),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem("🔄 Forcer le redémarrage", redemarrer),
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
