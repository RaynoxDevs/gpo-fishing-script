import cv2
import numpy as np
import mss
import time

class BarDetector:
    def __init__(self):
        self.sct = mss.mss()
        
    def capture_screen_without_window(self):
        """Capture l'écran en excluant une zone pour éviter l'effet miroir"""
        monitor = self.sct.monitors[1]
        screenshot = self.sct.grab(monitor)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def find_blue_bar_region(self, frame):
        """
        Trouve la région de la barre bleue en détectant sa couleur bleue claire distinctive
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Détecter le bleu clair de la barre (ajusté pour le bleu clair qu'on voit sur ton screen)
        # Bleu clair : HSV environ [100-120, 100-255, 150-255]
        lower_blue = np.array([90, 80, 120])
        upper_blue = np.array([130, 255, 255])
        
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Nettoyer le masque avec morphologie
        kernel = np.ones((5, 5), np.uint8)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)
        
        # Trouver les contours des zones bleues
        contours, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Chercher un contour vertical (barre)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Critères : hauteur > largeur, taille minimale, ratio vertical
            if h > 150 and w > 10 and h > w * 5:
                # Agrandir légèrement la bbox pour inclure les contours noirs
                padding = 5
                return {
                    'x': max(0, x - padding),
                    'y': max(0, y - padding),
                    'width': w + padding * 2,
                    'height': h + padding * 2
                }
        
        return None
    
    def find_green_bar_near_blue(self, frame, blue_bar):
        """
        Cherche la barre verte à droite de la barre bleue
        """
        if not blue_bar:
            return None
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Détecter le vert de la barre de progression
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        
        # Chercher seulement à droite de la barre bleue
        search_x_start = blue_bar['x'] + blue_bar['width']
        search_x_end = min(search_x_start + 200, frame.shape[1])
        
        # Extraire la région de recherche
        search_region = hsv[blue_bar['y']:blue_bar['y'] + blue_bar['height'], 
                           search_x_start:search_x_end]
        
        mask_green = cv2.inRange(search_region, lower_green, upper_green)
        
        # Nettoyer
        kernel = np.ones((3, 3), np.uint8)
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
        
        # Trouver les contours verts
        contours, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Chercher un contour vertical
        best_contour = None
        max_height = 0
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Critères : vertical, hauteur raisonnable
            if h > 100 and h > max_height:
                max_height = h
                best_contour = {
                    'x': search_x_start + x,
                    'y': blue_bar['y'] + y,
                    'width': w,
                    'height': h
                }
        
        # Si on ne trouve pas de vert (barre vide), chercher la structure noire
        if not best_contour:
            # Chercher un rectangle noir vertical à droite de la barre bleue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            search_gray = gray[blue_bar['y']:blue_bar['y'] + blue_bar['height'],
                              search_x_start:search_x_end]
            
            _, binary = cv2.threshold(search_gray, 40, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                if h > 150 and 10 < w < 40 and h > w * 5:
                    best_contour = {
                        'x': search_x_start + x,
                        'y': blue_bar['y'] + y,
                        'width': w,
                        'height': h
                    }
                    break
        
        return best_contour
    
    def find_bars(self, frame):
        """
        Pipeline complet : trouve d'abord la bleue, puis la verte à côté
        """
        blue_bar = self.find_blue_bar_region(frame)
        green_bar = None
        
        if blue_bar:
            green_bar = self.find_green_bar_near_blue(frame, blue_bar)
        
        return blue_bar, green_bar
    
    def run_detection_test(self):
        """Lance le test de détection en temps réel"""
        print("=" * 60)
        print("DÉTECTION AUTOMATIQUE DES BARRES - VERSION 2")
        print("=" * 60)
        print("\n📌 Instructions:")
        print("  1. Lance le jeu Roblox GPO")
        print("  2. Place-toi devant le mini-jeu de pêche")
        print("  3. Les barres vont être détectées automatiquement\n")
        print("🎮 Commandes:")
        print("  'q' = Quitter")
        print("  's' = Sauvegarder les coordonnées\n")
        print("Démarrage dans 3 secondes...\n")
        
        time.sleep(3)
        
        # Créer une petite fenêtre pour éviter l'effet miroir
        window_name = "Detection"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)
        cv2.moveWindow(window_name, 50, 50)
        
        last_blue = None
        last_green = None
        frame_count = 0
        
        try:
            while True:
                frame_count += 1
                
                # Capturer l'écran
                frame = self.capture_screen_without_window()
                
                # Détecter les barres (pas besoin à chaque frame pour l'affichage)
                if frame_count % 3 == 0:  # Toutes les 3 frames pour la détection
                    blue_bar, green_bar = self.find_bars(frame)
                    
                    if blue_bar:
                        last_blue = blue_bar
                    if green_bar:
                        last_green = green_bar
                
                # Créer une vue debug réduite
                scale = 0.5
                debug_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                
                # Dessiner les détections (ajuster pour le scale)
                if last_blue:
                    x, y, w, h = (int(last_blue['x'] * scale), int(last_blue['y'] * scale),
                                 int(last_blue['width'] * scale), int(last_blue['height'] * scale))
                    cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(debug_frame, "BLEUE", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                if last_green:
                    x, y, w, h = (int(last_green['x'] * scale), int(last_green['y'] * scale),
                                 int(last_green['width'] * scale), int(last_green['height'] * scale))
                    cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(debug_frame, "VERTE", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Afficher le statut
                status = "✅ DÉTECTÉ" if (last_blue and last_green) else "⏳ RECHERCHE..."
                color = (0, 255, 0) if (last_blue and last_green) else (0, 165, 255)
                cv2.putText(debug_frame, status, (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                cv2.imshow(window_name, debug_frame)
                
                # Console output
                if last_blue and last_green:
                    print(f"\r✅ DÉTECTION OK | Bleue: {last_blue['width']}x{last_blue['height']} @ ({last_blue['x']},{last_blue['y']}) | "
                          f"Verte: {last_green['width']}x{last_green['height']} @ ({last_green['x']},{last_green['y']})    ", end='')
                else:
                    print(f"\r⏳ Recherche des barres... (Assure-toi d'être devant le mini-jeu!)    ", end='')
                
                # Touches
                key = cv2.waitKey(30) & 0xFF
                
                if key == ord('q'):
                    break
                
                elif key == ord('s'):
                    if last_blue and last_green:
                        print("\n\n" + "=" * 70)
                        print("📋 COORDONNÉES DÉTECTÉES - COPIE ÇA DANS fishing_bot.py")
                        print("=" * 70)
                        print(f"""
# Zones calibrées automatiquement
self.blue_bar = {{
    "top": {last_blue['y']},
    "left": {last_blue['x']},
    "width": {last_blue['width']},
    "height": {last_blue['height']}
}}

self.green_bar = {{
    "top": {last_green['y']},
    "left": {last_green['x']},
    "width": {last_green['width']},
    "height": {last_green['height']}
}}
""")
                        print("=" * 70)
                        print("✅ Coordonnées prêtes! Copie-les dans ton bot.")
                        print("   Appuie sur 'q' pour quitter.\n")
                    else:
                        print("\n⚠️  Aucune barre détectée! Place-toi devant le mini-jeu.\n")
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Arrêt manuel")
        
        finally:
            cv2.destroyAllWindows()
            print("\n✅ Test terminé")

if __name__ == "__main__":
    detector = BarDetector()
    detector.run_detection_test()