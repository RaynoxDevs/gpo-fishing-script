import pyautogui
import time

print("Bouge ta souris pour voir les coordonnées")
print("Ctrl+C pour arrêter\n")

try:
    while True:
        x, y = pyautogui.position()
        print(f"X: {x:4d} Y: {y:4d}", end='\r')
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\nArrêté")