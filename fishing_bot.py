import cv2
import numpy as np
import mss
import pyautogui
import time

class GPOFishingBotV3:
    def __init__(self):
        self.sct = mss.mss()
        self.running = False
        self.is_clicking = False
        
        # DIMENSIONS FIXES (qui marchent bien)
        self.blue_bar_width = 27
        self.blue_bar_height = 423
        self.green_bar_width = 22
        self.green_bar_height = 319
        
        # OFFSET RELATIF entre barre bleue et verte (depuis ton config originale)
        # Barre verte est à droite de la bleue
        self.green_offset_x = 64  # 1200 - 1136 = 64 pixels à droite
        self.green_offset_y = 52  # 468 - 416 = 52 pixels plus bas
        
        # ZONES (seront calibrées automatiquement)
        self.blue_bar = None
        self.green_bar = None
        
        # Paramètres de détection
        self.offset_anticipation = 15
        self.calibrated = False
        
        # 🆕 Système de clics proportionnels
        self.last_click_time = 0
        self.click_cooldown = 0.05  # Temps minimum entre changements (50ms)
        
    def auto_calibrate(self):
        """
        Détecte automatiquement la position de la barre bleue,
        puis calcule la position de la barre verte par rapport à celle-ci
        """
        print("\n🔍 CALIBRATION AUTOMATIQUE EN COURS...")
        print("Place-toi devant le mini-jeu de pêche !")
        print("Recherche de la barre bleue...\n")
        
        # Créer une fenêtre de preview
        cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Calibration", 800, 600)
        cv2.moveWindow("Calibration", 50, 50)
        
        attempts = 0
        max_attempts = 100  # 100 frames max pour détecter
        
        while attempts < max_attempts:
            attempts += 1
            
            # Capturer l'écran complet
            monitor = self.sct.monitors[1]
            screenshot = self.sct.grab(monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Détecter la barre bleue
            blue_region = self.find_blue_bar(frame)
            
            if blue_region:
                # ✅ BARRE BLEUE TROUVÉE !
                blue_x = blue_region['x']
                blue_y = blue_region['y']
                
                # Utiliser les dimensions fixes qui marchent bien
                self.blue_bar = {
                    "top": blue_y,
                    "left": blue_x,
                    "width": self.blue_bar_width,
                    "height": self.blue_bar_height
                }
                
                # Calculer la position de la barre verte par offset relatif
                self.green_bar = {
                    "top": blue_y + self.green_offset_y,
                    "left": blue_x + self.green_offset_x,
                    "width": self.green_bar_width,
                    "height": self.green_bar_height
                }
                
                # Afficher le résultat
                scale = 0.5
                debug_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                
                # Dessiner les zones détectées
                cv2.rectangle(debug_frame, 
                            (int(blue_x * scale), int(blue_y * scale)),
                            (int((blue_x + self.blue_bar_width) * scale), 
                             int((blue_y + self.blue_bar_height) * scale)),
                            (255, 0, 0), 2)
                
                cv2.rectangle(debug_frame,
                            (int(self.green_bar['left'] * scale), int(self.green_bar['top'] * scale)),
                            (int((self.green_bar['left'] + self.green_bar_width) * scale),
                             int((self.green_bar['top'] + self.green_bar_height) * scale)),
                            (0, 255, 0), 2)
                
                cv2.putText(debug_frame, "CALIBRATION OK!", (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                cv2.imshow("Calibration", debug_frame)
                cv2.waitKey(2000)  # Afficher 2 secondes
                cv2.destroyAllWindows()
                
                print("✅ CALIBRATION RÉUSSIE !")
                print(f"\n📍 Barre bleue détectée à : X={blue_x}, Y={blue_y}")
                print(f"📍 Barre verte calculée à : X={self.green_bar['left']}, Y={self.green_bar['top']}")
                print(f"\n✅ Zones configurées avec succès !")
                
                self.calibrated = True
                return True
            
            # Preview pendant la recherche
            if attempts % 3 == 0:
                scale = 0.5
                debug_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                cv2.putText(debug_frame, f"Recherche... ({attempts}/{max_attempts})", (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)
                cv2.imshow("Calibration", debug_frame)
                cv2.waitKey(1)
            
            time.sleep(0.1)
        
        # ❌ Échec
        cv2.destroyAllWindows()
        print("\n❌ CALIBRATION ÉCHOUÉE")
        print("Assure-toi d'être devant le mini-jeu de pêche avec la barre bleue visible !")
        return False
    
    def find_blue_bar(self, frame):
        """
        Trouve la barre bleue dans l'écran (copié de detect_bars.py)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Détecter le bleu clair de la barre
        lower_blue = np.array([90, 80, 120])
        upper_blue = np.array([130, 255, 255])
        
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Nettoyer le masque
        kernel = np.ones((5, 5), np.uint8)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)
        
        # Trouver les contours
        contours, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Chercher un contour vertical (barre)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Critères : hauteur > largeur, taille minimale, ratio vertical
            if h > 150 and w > 10 and h > w * 5:
                return {'x': x, 'y': y, 'width': w, 'height': h}
        
        return None
    
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
        """Trouve la position Y du marqueur blanc (poisson)"""
        hsv = cv2.cvtColor(blue_frame, cv2.COLOR_BGR2HSV)
        
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        moments = cv2.moments(mask)
        if moments["m00"] > 0:
            cy = int(moments["m01"] / moments["m00"])
            return cy
        
        return None
    
    def find_gray_zone_y(self, blue_frame):
        """Trouve la position Y de la zone grise mobile"""
        target_color_bgr = np.array([25, 25, 25])
        
        lower_bound = np.array([15, 15, 15])
        upper_bound = np.array([35, 35, 35])
        mask = cv2.inRange(blue_frame, lower_bound, upper_bound)
        
        height = mask.shape[0]
        max_width = 0
        best_y = None
        
        for y in range(height):
            row = mask[y, :]
            white_pixels = np.sum(row > 0)
            
            if white_pixels > max_width:
                max_width = white_pixels
                best_y = y
        
        if best_y is not None and max_width >= 15:
            return best_y
        
        return None
    
    def get_green_bar_progress(self, green_frame):
        """Calcule le pourcentage de remplissage de la barre verte"""
        hsv = cv2.cvtColor(green_frame, cv2.COLOR_BGR2HSV)
        
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        green_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        
        if total_pixels > 0:
            percentage = (green_pixels / total_pixels) * 100
            return percentage
        
        return 0.0
    
    def should_click(self, gray_y, white_y):
        """
        🆕 Décide si on doit cliquer avec ajustement proportionnel
        
        Logique :
        - Distance grande (>50px) : maintenir le clic
        - Distance moyenne (20-50px) : clics modérés
        - Distance petite (<20px) : micro-ajustements
        """
        if gray_y is None or white_y is None:
            return False, None
        
        # Calculer la distance (positif = gris en dessous, négatif = gris au-dessus)
        distance = gray_y - white_y
        
        # Si la zone grise est EN DESSOUS de la cible (distance > 0)
        if distance > self.offset_anticipation:
            # Plus la distance est grande, plus on maintient longtemps
            if distance > 50:
                return True, "long"  # Maintenir le clic longtemps
            elif distance > 20:
                return True, "medium"  # Clic moyen
            else:
                return True, "short"  # Micro-clic
        
        # Si la zone grise est AU-DESSUS ou alignée
        return False, None
    
    def run(self, debug=True):
        """Lance le bot avec calibration automatique"""
        print("=" * 50)
        print("GPO AUTO FISHING BOT V3 - AUTO-CALIBRATION")
        print("=" * 50)
        
        # 🔧 PHASE 1 : CALIBRATION
        if not self.auto_calibrate():
            print("\n⚠️ Impossible de lancer le bot sans calibration.")
            return
        
        # 🎮 PHASE 2 : LANCEMENT DU BOT
        print("\n" + "=" * 50)
        print("🎣 DÉMARRAGE DU BOT")
        print("=" * 50)
        print("\nCommandes:")
        print("  'q' = Arrêter le bot")
        print("\nDémarrage dans 3 secondes...\n")
        
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        fps_start = time.time()
        
        if debug:
            cv2.namedWindow("Bot Debug", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Bot Debug", 800, 500)
            time.sleep(0.3)
        
        try:
            while self.running:
                # Capture
                blue_frame = self.capture_blue_bar()
                green_frame = self.capture_green_bar()
                
                # Détection
                white_y = self.find_white_marker_y(blue_frame)
                gray_y = self.find_gray_zone_y(blue_frame)
                progress = self.get_green_bar_progress(green_frame)
                
                # 🆕 Décision avec ajustement proportionnel
                should_hold, click_type = self.should_click(gray_y, white_y)
                current_time = time.time()
                
                # Système de clics proportionnels
                if should_hold:
                    if click_type == "long":
                        # Distance grande : maintenir le clic
                        if not self.is_clicking:
                            pyautogui.mouseDown()
                            self.is_clicking = True
                            self.last_click_time = current_time
                    
                    elif click_type == "medium":
                        # Distance moyenne : clics de 0.1-0.15s
                        if not self.is_clicking and (current_time - self.last_click_time) > 0.15:
                            pyautogui.mouseDown()
                            self.is_clicking = True
                            self.last_click_time = current_time
                        elif self.is_clicking and (current_time - self.last_click_time) > 0.1:
                            pyautogui.mouseUp()
                            self.is_clicking = False
                    
                    elif click_type == "short":
                        # Distance petite : micro-clics de 0.05s
                        if not self.is_clicking and (current_time - self.last_click_time) > 0.1:
                            pyautogui.mouseDown()
                            self.is_clicking = True
                            self.last_click_time = current_time
                        elif self.is_clicking and (current_time - self.last_click_time) > 0.05:
                            pyautogui.mouseUp()
                            self.is_clicking = False
                else:
                    # Relâcher complètement quand pas besoin de monter
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                
                # Debug visuel
                if debug:
                    debug_view = np.zeros((500, 800, 3), dtype=np.uint8)
                    
                    blue_scaled = cv2.resize(blue_frame, (200, 400))
                    debug_view[50:450, 50:250] = blue_scaled
                    
                    green_scaled = cv2.resize(green_frame, (100, 400))
                    debug_view[50:450, 300:400] = green_scaled
                    
                    if white_y is not None:
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
                        dist_color = (0, 255, 0) if abs(distance) < 20 else (255, 255, 0) if abs(distance) < 50 else (0, 165, 255)
                        cv2.putText(debug_view, f"Distance: {distance}px", (450, info_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, dist_color, 2)
                    
                    info_y += 40
                    # Afficher le type de clic
                    if click_type:
                        type_text = {"long": "LONG", "medium": "MEDIUM", "short": "SHORT"}.get(click_type, "NONE")
                        type_color = {"long": (0, 165, 255), "medium": (255, 255, 0), "short": (0, 255, 0)}.get(click_type, (128, 128, 128))
                        cv2.putText(debug_view, f"Mode: {type_text}", (450, info_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, type_color, 2)
                    
                    info_y += 60
                    cv2.putText(debug_view, "BARRE BLEUE", (100, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(debug_view, "BARRE VERTE", (310, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    cv2.imshow("Bot Debug", debug_view)
                
                # FPS Counter
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    mode_str = click_type if click_type else "NONE"
                    print(f"FPS: {fps_counter:2d} | Progress: {progress:5.1f}% | " +
                          f"Click: {'YES' if self.is_clicking else 'NO '} | Mode: {mode_str:>6} | " +
                          f"White: {white_y or 'N/A':>4} | Gray: {gray_y or 'N/A':>4}")
                    fps_counter = 0
                    fps_start = time.time()
                
                # Check completion
                if progress >= 95.0:
                    print("\n🎣 POISSON ATTRAPÉ! 🎣")
                    print("Attente de 3 secondes avant de continuer...\n")
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                    time.sleep(3)
                
                # Check quit
                if debug and cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Arrêt demandé par l'utilisateur")
        
        finally:
            if self.is_clicking:
                pyautogui.mouseUp()
            if debug:
                cv2.destroyAllWindows()
            print("\n✅ Bot arrêté proprement")

# === POINT D'ENTRÉE ===
if __name__ == "__main__":
    bot = GPOFishingBotV3()
    
    print("\n" + "="*50)
    print("LANCEMENT DU BOT - VERSION CLICS PROPORTIONNELS")
    print("="*50)
    
    bot.run(debug=True)