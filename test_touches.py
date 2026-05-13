from pynput import keyboard as kb
import sys

print("Test detection touches - appuyez sur des touches (Echap pour quitter)")
sys.stdout.flush()

def on_press(key):
    print(f"Touche appuyee : {key}")
    sys.stdout.flush()
    if key == kb.Key.esc:
        return False  # arrete le listener

with kb.Listener(on_press=on_press) as listener:
    listener.join()

print("Termine.")
