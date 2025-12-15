import cv2
import numpy as np
import mss
import pyautogui
import time

class GPOFishingBotV2:
    def __init__(self):
        self.sct = mss.mss()
        self.running = False
        self.is_clicking = False
        
        # ZONES FIXES CALIBRÉES
        # Barre bleue (zone de contrôle)
        self.blue_bar = {
            "top": 416,
            "left": 1136,
            "width": 27,    # 1163 - 1136
            "height": 423   # 839 - 416
        }
        
        # Barre verte (progression)
        self.green_bar = {
            "top": 468,
            "left": 1200,
            "width": 22,    # 1222 - 1200
            "height": 319   # 787 - 468
        }
        
        # Paramètres de détection
        self.offset_anticipation = 15  # Pixels d'anticipation pour le clic
        
    def capture_blue_bar(self):
        """Capture uniquement la barre bleue"""
        screenshot = self.sct.grab(self.blue_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def capture_green_bar(self):
        """Capture uniquement la barre verte"""
        screenshot = self.sct.grab(self.green_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def find_white_marker_y(self, blue_frame):
        """
        Trouve la position Y du marqueur blanc (poisson) dans la barre bleue.
        Retourne la position relative (0 = haut de la barre, height = bas)
        """
        # Convertir en HSV pour mieux détecter le blanc
        hsv = cv2.cvtColor(blue_frame, cv2.COLOR_BGR2HSV)
        
        # Masque pour le blanc (marqueur poisson)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Trouver le centre de masse des pixels blancs
        moments = cv2.moments(mask)
        if moments["m00"] > 0:
            cy = int(moments["m01"] / moments["m00"])
            return cy
        
        return None
    
    def find_gray_zone_y(self, blue_frame):
        """
        Trouve la position Y de la zone grise (que tu contrôles).
        Retourne la position relative du centre de la zone grise.
        """
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(blue_frame, cv2.COLOR_BGR2GRAY)
        
        # Masque pour la zone grise/foncée de contrôle
        # Ajuster ces valeurs si la détection ne marche pas
        lower_gray = 60
        upper_gray = 140
        mask = cv2.inRange(gray, lower_gray, upper_gray)
        
        # Trouver le centre de masse
        moments = cv2.moments(mask)
        if moments["m00"] > 0:
            cy = int(moments["m01"] / moments["m00"])
            return cy
        
        return None
    
    def get_green_bar_progress(self, green_frame):
        """
        Calcule le pourcentage de remplissage de la barre verte.
        Retourne un float entre 0.0 et 100.0
        """
        # Convertir en HSV
        hsv = cv2.cvtColor(green_frame, cv2.COLOR_BGR2HSV)
        
        # Masque pour le vert
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Compter les pixels verts par rapport au total
        green_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        
        if total_pixels > 0:
            percentage = (green_pixels / total_pixels) * 100
            return percentage
        
        return 0.0
    
    def should_click(self, gray_y, white_y):
        """
        Décide si on doit cliquer ou non.
        
        LOGIQUE:
        - Si la zone grise est EN DESSOUS du marqueur blanc → Cliquer (pour la faire monter)
        - Si la zone grise est AU-DESSUS ou alignée → Ne pas cliquer (elle redescend naturellement)
        
        On ajoute un offset d'anticipation pour réagir plus vite.
        """
        if gray_y is None or white_y is None:
            return False
        
        # Si gris EN DESSOUS du blanc (plus grand Y) → cliquer pour monter
        return gray_y > (white_y - self.offset_anticipation)
    
    def run(self, debug=True):
        """Lance le bot avec affichage debug optionnel"""
        print("=" * 50)
        print("GPO AUTO FISHING BOT V2")
        print("=" * 50)
        print("\nZones calibrées:")
        print(f"  Barre bleue: {self.blue_bar}")
        print(f"  Barre verte: {self.green_bar}")
        print("\nCommandes:")
        print("  'q' = Arrêter le bot")
        print("\nDémarrage dans 3 secondes...")
        print("Place-toi devant le mini-jeu de pêche!\n")
        
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        fps_start = time.time()
        
        # Créer la fenêtre debug si activé
        if debug:
            cv2.namedWindow("Bot Debug", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Bot Debug", 800, 500)
            time.sleep(0.3)
        
        try:
            while self.running:
                # === CAPTURE ===
                blue_frame = self.capture_blue_bar()
                green_frame = self.capture_green_bar()
                
                # === DÉTECTION ===
                white_y = self.find_white_marker_y(blue_frame)
                gray_y = self.find_gray_zone_y(blue_frame)
                progress = self.get_green_bar_progress(green_frame)
                
                # === DÉCISION ===
                should_hold = self.should_click(gray_y, white_y)
                
                # === ACTION ===
                if should_hold and not self.is_clicking:
                    pyautogui.mouseDown()
                    self.is_clicking = True
                elif not should_hold and self.is_clicking:
                    pyautogui.mouseUp()
                    self.is_clicking = False
                
                # === DEBUG VISUEL ===
                if debug:
                    # Créer une vue combinée
                    debug_view = np.zeros((500, 800, 3), dtype=np.uint8)
                    
                    # Agrandir la barre bleue pour mieux voir
                    blue_scaled = cv2.resize(blue_frame, (200, 400))
                    debug_view[50:450, 50:250] = blue_scaled
                    
                    # Agrandir la barre verte
                    green_scaled = cv2.resize(green_frame, (100, 400))
                    debug_view[50:450, 300:400] = green_scaled
                    
                    # Dessiner les détections sur la barre bleue agrandie
                    if white_y is not None:
                        # Scale la position Y
                        white_y_scaled = int((white_y / self.blue_bar["height"]) * 400) + 50
                        cv2.line(debug_view, (50, white_y_scaled), (250, white_y_scaled), 
                                (255, 255, 255), 3)
                        cv2.putText(debug_view, "CIBLE", (260, white_y_scaled), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    if gray_y is not None:
                        gray_y_scaled = int((gray_y / self.blue_bar["height"]) * 400) + 50
                        cv2.line(debug_view, (50, gray_y_scaled), (250, gray_y_scaled), 
                                (128, 128, 128), 3)
                        cv2.putText(debug_view, "CONTROLE", (260, gray_y_scaled), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                    
                    # Afficher les infos
                    info_y = 50
                    cv2.putText(debug_view, f"Progress: {progress:.1f}%", (450, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                    info_y += 40
                    click_color = (0, 255, 0) if self.is_clicking else (0, 0, 255)
                    cv2.putText(debug_view, f"Clicking: {self.is_clicking}", (450, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, click_color, 2)
                    
                    info_y += 40
                    if white_y and gray_y:
                        distance = gray_y - white_y
                        cv2.putText(debug_view, f"Distance: {distance}px", (450, info_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    
                    info_y += 60
                    cv2.putText(debug_view, "BARRE BLEUE", (100, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(debug_view, "BARRE VERTE", (310, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    cv2.imshow("Bot Debug", debug_view)
                
                # === FPS COUNTER ===
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    print(f"FPS: {fps_counter:2d} | Progress: {progress:5.1f}% | " +
                          f"Click: {'YES' if self.is_clicking else 'NO '} | " +
                          f"White: {white_y or 'N/A':>4} | Gray: {gray_y or 'N/A':>4}")
                    fps_counter = 0
                    fps_start = time.time()
                
                # === CHECK COMPLETION ===
                if progress >= 95.0:
                    print("\n🎣 POISSON ATTRAPÉ! 🎣")
                    print("Attente de 3 secondes avant de continuer...\n")
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                    time.sleep(3)
                
                # === CHECK QUIT ===
                if debug and cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Arrêt demandé par l'utilisateur")
        
        finally:
            # Cleanup
            if self.is_clicking:
                pyautogui.mouseUp()
            if debug:
                cv2.destroyAllWindows()
            print("\n✅ Bot arrêté proprement")

# === POINT D'ENTRÉE ===
if __name__ == "__main__":
    bot = GPOFishingBotV2()
    
    print("\n" + "="*50)
    print("LANCEMENT DU BOT")
    print("="*50)
    
    # Lancer avec debug activé (fenêtre visuelle)
    bot.run(debug=True)