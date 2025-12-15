import cv2
import numpy as np
import mss
import pyautogui
import time
from PIL import Image

class GPOFishingBot:
    def __init__(self):
        self.sct = mss.mss()
        self.running = False
        
        # Zone de capture calibrée
        # Format: {"top": y, "left": x, "width": w, "height": h}
        self.capture_region = {
            "top": 414,    # Position Y du haut de la zone
            "left": 1118,  # Position X du début de la zone
            "width": 125,  # Largeur de la zone à capturer
            "height": 429  # Hauteur de la zone à capturer
        }
        
        self.is_clicking = False
        
    def find_white_bar_position(self, frame):
        """Trouve la position Y de la barre blanche (cible)"""
        # Convertir en HSV pour mieux détecter le blanc
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Masque pour détecter le blanc/couleur claire
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Trouver les contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Prendre le plus grand contour (probablement la barre)
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            return y + h // 2  # Retourne le centre Y de la barre
        
        return None
    
    def find_gray_bar_position(self, frame):
        """Trouve la position Y de la barre grise (contrôlée)"""
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Détecter les zones grises (ta barre de contrôle)
        lower_gray = 80
        upper_gray = 150
        mask = cv2.inRange(gray, lower_gray, upper_gray)
        
        # Trouver les contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            return y + h // 2
        
        return None
    
    def check_green_bar(self, frame):
        """Vérifie le niveau de la barre verte (progression)"""
        # Isoler la partie droite où se trouve la barre verte
        right_section = frame[:, -50:]
        
        # Détecter le vert
        hsv = cv2.cvtColor(right_section, cv2.COLOR_BGR2HSV)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Calculer le pourcentage de pixels verts
        green_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        percentage = (green_pixels / total_pixels) * 100
        
        return percentage
    
    def should_hold_click(self, gray_pos, white_pos):
        """Détermine si on doit maintenir le clic"""
        if gray_pos is None or white_pos is None:
            return False
        
        # Si la barre grise est en dessous de la blanche, on clique
        # Offset de 20 pixels pour anticiper
        return gray_pos > (white_pos - 20)
    
    def calibrate(self):
        """Aide à calibrer la zone de capture"""
        print("=== CALIBRATION ===")
        print("Positionne-toi devant le mini-jeu de pêche")
        print("\nValeurs actuelles:")
        print(f"Top: {self.capture_region['top']}")
        print(f"Left: {self.capture_region['left']}")
        print(f"Width: {self.capture_region['width']}")
        print(f"Height: {self.capture_region['height']}")
        print("\nUtilise ce script pour trouver les bonnes coordonnées:")
        print("--------------------")
        print("import pyautogui")
        print("import time")
        print("try:")
        print("    while True:")
        print("        x, y = pyautogui.position()")
        print("        print(f'X: {x} Y: {y}', end='\\r')")
        print("        time.sleep(0.1)")
        print("except KeyboardInterrupt:")
        print("    pass")
        print("--------------------")
        print("\nNote les coordonnées coin haut-gauche et bas-droite de la zone de pêche")
    
    def run(self, debug=True):
        """Lance le bot"""
        print("=== BOT DE PÊCHE GPO ===")
        print("Appuie sur 'q' pour arrêter")
        print("Démarrage dans 3 secondes...")
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        start_time = time.time()
        
        # Créer la fenêtre AVANT la boucle pour éviter l'effet miroir
        if debug:
            cv2.namedWindow("GPO Fishing Bot", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("GPO Fishing Bot", 600, 600)
            time.sleep(0.5)  # Laisser le temps à la fenêtre de s'initialiser
        
        try:
            while self.running:
                # Capture d'écran
                screenshot = self.sct.grab(self.capture_region)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Détection des positions
                white_pos = self.find_white_bar_position(frame)
                gray_pos = self.find_gray_bar_position(frame)
                green_level = self.check_green_bar(frame)
                
                # Décision de cliquer
                should_click = self.should_hold_click(gray_pos, white_pos)
                
                if should_click and not self.is_clicking:
                    pyautogui.mouseDown()
                    self.is_clicking = True
                elif not should_click and self.is_clicking:
                    pyautogui.mouseUp()
                    self.is_clicking = False
                
                # Mode debug : affichage visuel
                if debug:
                    debug_frame = frame.copy()
                    
                    # Dessiner les positions détectées
                    if white_pos:
                        cv2.line(debug_frame, (0, white_pos), 
                                (debug_frame.shape[1], white_pos), (255, 255, 255), 2)
                        cv2.putText(debug_frame, "Cible", (10, white_pos - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    
                    if gray_pos:
                        cv2.line(debug_frame, (0, gray_pos), 
                                (debug_frame.shape[1], gray_pos), (128, 128, 128), 2)
                        cv2.putText(debug_frame, "Controle", (10, gray_pos + 20),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                    
                    # Afficher les infos
                    cv2.putText(debug_frame, f"Vert: {green_level:.1f}%", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(debug_frame, f"Click: {self.is_clicking}", (10, 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    cv2.imshow("GPO Fishing Bot", debug_frame)
                
                # FPS counter
                fps_counter += 1
                if time.time() - start_time >= 1.0:
                    print(f"FPS: {fps_counter} | Vert: {green_level:.1f}% | Click: {self.is_clicking}")
                    fps_counter = 0
                    start_time = time.time()
                
                # Check for quit
                if debug and cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                # Vérifier si on a fini (100%)
                if green_level > 95:
                    print("Poisson attrapé ! 🎣")
                    time.sleep(2)  # Attendre avant de recommencer
        
        except KeyboardInterrupt:
            print("\nArrêt du bot...")
        
        finally:
            if self.is_clicking:
                pyautogui.mouseUp()
            cv2.destroyAllWindows()

# Utilisation
if __name__ == "__main__":
    bot = GPOFishingBot()
    
    # Étape 1: Calibrer la zone (optionnel mais recommandé)
    print("Veux-tu calibrer la zone de capture ? (o/n)")
    if input().lower() == 'o':
        bot.calibrate()
    
    # Étape 2: Lancer le bot
    bot.run(debug=True)