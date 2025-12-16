import cv2
import numpy as np
import mss
import pyautogui
import time
import tkinter as tk
from tkinter import ttk
import threading
import keyboard  # Pour hotkeys globaux

class GPOFishingBotV4:
    def __init__(self):
        self.sct = None  # Sera cree dans get_sct()
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
        self.target_offset = 20  # 🎯 Zone grise doit être 20px AU-DESSUS du marqueur blanc
        self.tolerance = 3       # Tolérance en pixels (zone "OK")
        self.calibrated = False
        
        # Systeme de suivi precis avec prediction
        self.last_action_time = 0
        self.last_white_y = None
        self.white_y_velocity = 0  # Vitesse de deplacement de la cible (px/frame)
        self.prediction_frames = 3  # Predire 3 frames a l'avance
        
        # Variables pour gestion poisson attrape
        self.bar_lost_time = None
        self.click_sent_for_restart = False
        self.just_caught_fish = False
        self.fish_caught_time = None
    
    def get_sct(self):
        """Cree l'objet mss dans le thread actuel si pas deja fait"""
        if self.sct is None:
            self.sct = mss.mss()
        return self.sct
    
    def auto_calibrate(self):
        """
        Détecte automatiquement la position de la barre bleue,
        puis calcule la position de la barre verte par rapport à celle-ci
        """
        print("\n🔍 CALIBRATION AUTOMATIQUE EN COURS...")
        print("Place-toi devant le mini-jeu de pêche !")
        print("Recherche de la barre bleue...\n")
        
        # Créer une fenêtre de preview
        # Pas de fenetre preview
        
        attempts = 0
        max_attempts = 200  # 100 frames max pour détecter
        
        while attempts < max_attempts:
            attempts += 1
            
            # Capturer l'écran complet
            sct = self.get_sct()
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
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
                
                # Debug removed  # Afficher 2 secondes
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
                # Debug removed
            
            time.sleep(0.1)
        
        # ❌ Échec
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
        screenshot = self.get_sct().grab(self.blue_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def capture_green_bar(self):
        """Capture uniquement la barre verte"""
        screenshot = self.get_sct().grab(self.green_bar)
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
        # Convertir en HSV
        hsv = cv2.cvtColor(green_frame, cv2.COLOR_BGR2HSV)
        
        # Seuils tres permissifs pour capturer TOUT le vert (meme les teintes foncees)
        lower_green = np.array([25, 20, 20])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Compter les pixels verts
        green_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        
        if total_pixels > 0:
            percentage = (green_pixels / total_pixels) * 100
            # Debug: afficher les valeurs brutes
            # print(f"Debug: {green_pixels}/{total_pixels} = {percentage:.1f}%")
            return percentage
        
        return 0.0
    
    def should_click(self, gray_y, white_y):
        """
        Systeme de tracking precis avec prediction de mouvement
        
        Calcule la duree optimale du clic selon:
        1. Distance actuelle
        2. Vitesse de deplacement de la cible
        3. Prediction du prochain mouvement
        
        Retourne (should_click, click_duration_ms)
        """
        if gray_y is None or white_y is None:
            self.last_white_y = None
            self.white_y_velocity = 0
            return False, 0
        
        # Calculer la vitesse de la cible (prediction)
        if self.last_white_y is not None:
            self.white_y_velocity = white_y - self.last_white_y
        self.last_white_y = white_y
        
        # Position cible: 20px au-dessus du marqueur blanc
        target_gray_y = white_y - self.target_offset
        
        # Predire la prochaine position de la cible
        predicted_white_y = white_y + (self.white_y_velocity * self.prediction_frames)
        predicted_target_y = predicted_white_y - self.target_offset
        
        # Distance actuelle + prediction
        current_distance = gray_y - target_gray_y
        predicted_distance = gray_y - predicted_target_y
        
        # Utiliser la moyenne pour lisser
        distance = (current_distance + predicted_distance) / 2.0
        
        # CALCUL DE LA DUREE DU CLIC selon la distance
        # Plus on est loin, plus le clic est long
        
        if distance > 50:
            # Tres loin: clic long (300ms)
            self.last_click_duration = 300
            return True, 300
        elif distance > 30:
            # Loin: clic moyen-long (200ms)
            self.last_click_duration = 200
            return True, 200
        elif distance > 15:
            # Moyennement loin: clic moyen (120ms)
            self.last_click_duration = 120
            return True, 120
        elif distance > 8:
            # Proche: clic court (80ms)
            self.last_click_duration = 80
            return True, 80
        elif distance > 3:
            # Tres proche: micro-clic (50ms)
            self.last_click_duration = 50
            return True, 50
        elif distance > -3:
            # Zone parfaite: micro-clic ultra-court (30ms)
            self.last_click_duration = 30
            return True, 30
        elif distance > -8:
            # Legerement haut: pause courte (pas de clic)
            self.last_click_duration = 0
            return False, 0
        elif distance > -15:
            # Moyennement haut: pause moyenne
            self.last_click_duration = 0
            return False, 0
        else:
            # Tres haut: pause longue (chute libre)
            self.last_click_duration = 0
            return False, 0
    

    def check_and_recalibrate(self):
        """Cherche la barre bleue et met a jour si trouvee"""
        sct = self.get_sct()
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        blue_region = self.find_blue_bar(frame)
        
        if blue_region:
            new_x = blue_region['x']
            new_y = blue_region['y']
            
            if self.blue_bar:
                old_x = self.blue_bar['left']
                old_y = self.blue_bar['top']
                
                if abs(new_x - old_x) > 3 or abs(new_y - old_y) > 3:
                    print(f"\n🔄 Barre deplacee: ({old_x},{old_y}) -> ({new_x},{new_y})")
                    
                    self.blue_bar = {
                        "top": new_y,
                        "left": new_x,
                        "width": self.blue_bar_width,
                        "height": self.blue_bar_height
                    }
                    
                    self.green_bar = {
                        "top": new_y + self.green_offset_y,
                        "left": new_x + self.green_offset_x,
                        "width": self.green_bar_width,
                        "height": self.green_bar_height
                    }
            
            self.bar_lost_time = None
            self.click_sent_for_restart = False
            return True
        
        return False
    
    def run(self, debug=True):
        """Lance le bot avec calibration automatique"""
        print("=" * 50)
        print("GPO AUTO FISHING BOT V4 - CONTRÔLE PROPORTIONNEL")
        print("=" * 50)
        
        # 🔧 PHASE 1 : CALIBRATION
        if not self.auto_calibrate():
            print("\n⚠️ Impossible de lancer le bot sans calibration.")
            return
        
        # 🎮 PHASE 2 : LANCEMENT DU BOT
        print("\n" + "=" * 50)
        print("🎣 DÉMARRAGE DU BOT")
        print("=" * 50)
        print("\n🎯 Logique : Contrôle proportionnel (comme un hélicoptère)")
        print("   - Zone grise maintenue à 20px AU-DESSUS du marqueur blanc")
        print("   - Duty cycle adaptatif selon la distance :")
        print("     • 100% = Monter vite (clic maintenu)")
        print("     • 80%  = Monter doucement")
        print("     • 50%  = MAINTENIR position (hover mode)")
        print("     • 30%  = Stabiliser")
        print("     • 0%   = Descendre")
        print("\n📊 Tolérance : ±5px | Fréquence : 10 CPS max")
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
            cv2.setWindowProperty("Bot Debug", cv2.WND_PROP_TOPMOST, 1)  # Always on top
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
                
                # Recalibration si detection echoue
                if white_y is None or gray_y is None:
                    current_time = time.time()
                    
                    # Attendre 5s apres poisson
                    if self.just_caught_fish:
                        if self.fish_caught_time and (current_time - self.fish_caught_time) < 5:
                            print("⏳ Attente du prochain poisson...")
                            time.sleep(0.5)
                            continue
                        else:
                            self.just_caught_fish = False
                    
                    print("\n⚠️  Detection echouee ! Recherche...")
                    
                    if self.check_and_recalibrate():
                        blue_frame = self.capture_blue_bar()
                        green_frame = self.capture_green_bar()
                        white_y = self.find_white_marker_y(blue_frame)
                        gray_y = self.find_gray_zone_y(blue_frame)
                        progress = self.get_green_bar_progress(green_frame)
                        print("✅ Barre retrouvee !")
                    else:
                        if self.bar_lost_time is None:
                            self.bar_lost_time = current_time
                            print("⚠️  Barre perdue ! Relance...")
                        
                        if not self.click_sent_for_restart:
                            pyautogui.click()
                            print("🖱️  Clic envoye")
                            self.click_sent_for_restart = True
                            time.sleep(0.5)
                        
                        elapsed = current_time - self.bar_lost_time
                        if elapsed < 15:
                            print(f"⏳ Attente... ({elapsed:.1f}s/15s)")
                            time.sleep(0.5)
                            continue
                        else:
                            print("⚠️  Timeout 15s. Reset...")
                            self.bar_lost_time = None
                            self.click_sent_for_restart = False
                            time.sleep(1)
                            continue
                
                # Décision avec contrôle proportionnel (duty cycle)
                should_click, click_duration_ms = self.should_click(gray_y, white_y)
                current_time = time.time()
                
                # SYSTEME DE CLICS ADAPTATIFS
                # Clic de duree variable selon la distance
                
                if should_click:
                    time_since_last = current_time - self.last_action_time
                    click_duration_s = click_duration_ms / 1000.0
                    
                    if not self.is_clicking:
                        # Commencer un nouveau clic
                        pyautogui.mouseDown()
                        self.is_clicking = True
                        self.last_action_time = current_time
                    elif time_since_last >= click_duration_s:
                        # Terminer le clic et attendre un peu avant le prochain
                        pyautogui.mouseUp()
                        self.is_clicking = False
                        self.last_action_time = current_time
                        time.sleep(0.03)  # Petite pause entre les clics
                else:
                    # Pas de clic necessaire (descendre)
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                
                # Debug visuel Debug visuel
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
                        
                        # Dessiner la position cible (20px au-dessus) en pointillés
                        target_y_scaled = int(((white_y - self.target_offset) / self.blue_bar["height"]) * 400) + 50
                        # Ligne en pointillés (dessinée manuellement)
                        for x in range(50, 250, 10):
                            cv2.line(debug_view, (x, target_y_scaled), (min(x+5, 250), target_y_scaled), 
                                    (0, 255, 0), 2)
                        cv2.putText(debug_view, "TARGET", (260, target_y_scaled), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
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
                        # Calculer la distance réelle
                        target_gray_y = white_y - self.target_offset
                        distance = gray_y - target_gray_y
                        dist_color = (0, 255, 0) if abs(distance) <= self.tolerance else (255, 255, 0) if abs(distance) < 20 else (0, 165, 255)
                        cv2.putText(debug_view, f"Distance: {distance:+.0f}px", (450, info_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, dist_color, 2)
                    
                    info_y += 40
                    # Afficher le type de clic et duty cycle
                    # Afficher la duree du dernier clic
                    if hasattr(self, 'last_click_duration'):
                        color = (0, 255, 0) if self.last_click_duration < 100 else (255, 255, 0) if self.last_click_duration < 200 else (0, 165, 255)
                        cv2.putText(debug_view, f"Click: {self.last_click_duration}ms", (450, info_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    info_y += 40
                    # Afficher la configuration
                    cv2.putText(debug_view, f"Target: -{self.target_offset}px | Tol: {self.tolerance}px", (450, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                    
                    info_y += 60
                    cv2.putText(debug_view, "BARRE BLEUE", (100, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(debug_view, "BARRE VERTE", (310, 470),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    cv2.imshow("Bot Debug", debug_view)
                
                # FPS Counter
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    mode_str = f"Click:{getattr(self, 'last_click_duration', 0)}ms"
                    dist_str = f"{gray_y - (white_y - self.target_offset):+.0f}px" if (white_y and gray_y) else "N/A"
                    print(f"FPS: {fps_counter:2d} | Progress: {progress:5.1f}% | " +
                          f"Click: {'YES' if self.is_clicking else 'NO '} | Mode: {mode_str:>14} | " +
                          f"Dist: {dist_str:>6} | White: {white_y or 'N/A':>4} | Gray: {gray_y or 'N/A':>4}")
                    fps_counter = 0
                    fps_start = time.time()
                
                # Check completion
                if progress >= 95.0:
                    print("\n🎣 POISSON ATTRAPÉ! 🎣")
                    print("Attente que la barre disparaisse...\n")
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                    self.just_caught_fish = True
                    self.fish_caught_time = time.time()
                    time.sleep(2)
                
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



class FishingBotGUI:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.bot_thread = None
        
        self.root = tk.Tk()
        self.root.title("Fishing Script GPO")
        self.root.geometry("300x200")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)  # Always on top
        
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 14, 'bold'))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="GPO Auto Fishing Bot", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        self.status_label = ttk.Label(main_frame, text="Status: Arrete", font=('Arial', 10))
        self.status_label.pack(pady=10)
        
        self.start_button = ttk.Button(main_frame, text="START (F6)", command=self.start_bot, style='Big.TButton')
        self.start_button.pack(pady=10, fill=tk.X)
        
        self.exit_button = ttk.Button(main_frame, text="EXIT (Q)", command=self.exit_app, style='Big.TButton')
        self.exit_button.pack(pady=10, fill=tk.X)
        
        # Hotkeys locaux (quand fenetre focus)
        self.root.bind('<F6>', lambda e: self.start_bot())
        self.root.bind('q', lambda e: self.exit_app())
        self.root.bind('Q', lambda e: self.exit_app())
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        # Hotkey GLOBAL F6 (marche meme si jeu au premier plan)
        try:
            keyboard.add_hotkey('f6', self.start_bot, suppress=False)
            print("✅ Hotkey global F6 active (marche dans le jeu)")
        except:
            print("⚠️  Hotkey global F6 non disponible (lance en admin si besoin)")
    
    def start_bot(self):
        if not self.running:
            print("\n▶️  Demarrage du bot...")
            self.running = True
            self.status_label.config(text="Status: Calibration...")
            self.start_button.config(state='disabled', text="EN COURS...")
            self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            self.bot_thread.start()
    
    def run_bot_thread(self):
        try:
            print("\n🔍 === DEBUT CALIBRATION ===")
            if self.bot.auto_calibrate():
                self.status_label.config(text="Status: Peche en cours...")
                print("✅ Calibration OK! Demarrage...")
                self.bot.run(debug=True)
            else:
                self.status_label.config(text="Status: Echec")
                print("❌ Echec calibration")
                self.running = False
                self.start_button.config(state='normal')
        except Exception as e:
            print(f"❌ Erreur: {e}")
            self.status_label.config(text="Status: Erreur")
            self.running = False
            self.start_button.config(state='normal')
    
    def exit_app(self):
        print("\n👋 Fermeture...")
        self.bot.running = False
        if self.bot.is_clicking:
            pyautogui.mouseUp()
        
        # Nettoyer le hotkey global
        try:
            keyboard.remove_hotkey('f6')
        except:
            pass
        
        cv2.destroyAllWindows()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

# === POINT D'ENTREE ===
if __name__ == "__main__":
    print("\n" + "="*50)
    print("GPO AUTO FISHING BOT - INTERFACE GUI")
    print("="*50)
    
    bot = GPOFishingBotV4()
    gui = FishingBotGUI(bot)
    gui.run()