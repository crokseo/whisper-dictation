"""Script de diagnostic micro — liste les appareils et teste l'enregistrement."""
import sounddevice as sd
import numpy as np

print("=== Appareils audio disponibles ===\n")
print(sd.query_devices())

print(f"\n=== Appareil par défaut : {sd.default.device} ===\n")

print("Test enregistrement 3 secondes... parlez !")
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32")
sd.wait()

niveau = np.abs(audio).mean()
print(f"Niveau moyen capté : {niveau:.6f}")

if niveau < 0.001:
    print("  PROBLEME : niveau trop bas, le micro ne capte rien.")
    print("  => Essayez de spécifier le device manuellement (voir index ci-dessus).")
else:
    print("  OK : le micro capte du son.")
