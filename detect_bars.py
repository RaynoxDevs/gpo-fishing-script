import cv2
import numpy as np
import mss
import time

class BarDetector:
    def __init__(self):
        self.sct = mss.mss()
        
    def capture_full_screen(self):
        """Capture tout l'écran"""
        monitor = self.sct.monitors[1]  # Écran principal
        screenshot = self.sct.grab(monitor)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def find_bars(self, frame, debug=True):
        """
        Détecte les deux barres (bleue et verte) en cherchant les contours noirs verticaux
        
        Retourne:
        - blue_bar: dict avec {x, y, width, height} ou None
        - green_bar: dict avec {x, y, width, height} ou None
        """
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Détecter les zones très sombres/noires (contours des barres)
        # Les contours sont vraiment noirs (#000000 ou proche)
        _, binary = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)
        
        # Trouver les contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtrer pour trouver des rectangles verticaux
        candidates = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Critères pour être une barre :
            # 1. Hauteur > largeur (vertical)
            # 2. Hauteur minimum (au moins 200px)
            # 3. Largeur raisonnable (entre 15 et 50px)
            # 4. Ratio hauteur/largeur élevé (au moins 8:1)
            
            if h > 200 and 15 < w < 50 and h > w * 8:
                candidates.append({
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h,
                    'area': w * h,
                    'ratio': h / w
                })
        
        # Trier les candidats par position X (gauche à droite)
        candidates.sort(key=lambda c: c['x'])
        
        # Les deux barres devraient être côte à côte
        blue_bar = None
        green_bar = None
        
        # Chercher deux rectangles proches l'un de l'autre
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                bar1 = candidates[i]
                bar2 = candidates[j]
                
                # Vérifier qu'ils sont à peu près à la même hauteur Y
                y_diff = abs(bar1['y'] - bar2['y'])
                
                # Vérifier qu'ils sont proches horizontalement
                x_distance = bar2['x'] - (bar1['x'] + bar1['width'])
                
                # Si les barres sont alignées verticalement et proches horizontalement
                if y_diff < 100 and 10 < x_distance < 200:
                    # La barre la plus large est probablement la bleue
                    if bar1['width'] > bar2['width']:
                        blue_bar = bar1
                        green_bar = bar2
                    else:
                        blue_bar = bar2
                        green_bar = bar1
                    break
            
            if blue_bar and green_bar:
                break
        
        # Debug visuel
        if debug:
            debug_frame = frame.copy()
            
            if blue_bar:
                cv2.rectangle(debug_frame, 
                            (blue_bar['x'], blue_bar['y']),
                            (blue_bar['x'] + blue_bar['width'], blue_bar['y'] + blue_bar['height']),
                            (255, 0, 0), 3)
                cv2.putText(debug_frame, "BARRE BLEUE", 
                           (blue_bar['x'], blue_bar['y'] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            if green_bar:
                cv2.rectangle(debug_frame, 
                            (green_bar['x'], green_bar['y']),
                            (green_bar['x'] + green_bar['width'], green_bar['y'] + green_bar['height']),
                            (0, 255, 0), 3)
                cv2.putText(debug_frame, "BARRE VERTE", 
                           (green_bar['x'], green_bar['y'] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            return blue_bar, green_bar, debug_frame
        
        return blue_bar, green_bar, None
    
    def run_detection_test(self):
        """Lance un test en temps réel de la détection"""
        print("=" * 60)
        print("DÉTECTION AUTOMATIQUE DES BARRES - TEST")
        print("=" * 60)
        print("\nPlace-toi devant le mini-jeu de pêche!")
        print("La détection va commencer dans 3 secondes...\n")
        print("Commandes:")
        print("  'q' = Quitter")
        print("  's' = Sauvegarder les coordonnées détectées\n")
        
        time.sleep(3)
        
        cv2.namedWindow("Detection Test", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Detection Test", 1280, 720)
        
        last_blue = None
        last_green = None
        
        try:
            while True:
                # Capturer l'écran
                frame = self.capture_full_screen()
                
                # Détecter les barres
                blue_bar, green_bar, debug_frame = self.find_bars(frame, debug=True)
                
                # Mettre à jour les dernières détections valides
                if blue_bar:
                    last_blue = blue_bar
                if green_bar:
                    last_green = green_bar
                
                # Afficher les infos dans la console
                if blue_bar and green_bar:
                    print(f"\r✅ BARRES DÉTECTÉES | Bleue: {blue_bar['width']}x{blue_bar['height']} @ ({blue_bar['x']},{blue_bar['y']}) | "
                          f"Verte: {green_bar['width']}x{green_bar['height']} @ ({green_bar['x']},{green_bar['y']})    ", end='')
                else:
                    print(f"\r⚠️  RECHERCHE EN COURS... (Assure-toi d'être devant le mini-jeu)    ", end='')
                
                # Afficher le debug
                if debug_frame is not None:
                    # Redimensionner pour l'affichage
                    scale = 0.7
                    width = int(debug_frame.shape[1] * scale)
                    height = int(debug_frame.shape[0] * scale)
                    resized = cv2.resize(debug_frame, (width, height))
                    cv2.imshow("Detection Test", resized)
                
                # Gestion des touches
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                
                elif key == ord('s'):
                    if last_blue and last_green:
                        print("\n\n" + "=" * 60)
                        print("📋 COORDONNÉES DÉTECTÉES - COPIE ÇA DANS TON BOT:")
                        print("=" * 60)
                        print(f"""
# Barre bleue (zone de contrôle)
self.blue_bar = {{
    "top": {last_blue['y']},
    "left": {last_blue['x']},
    "width": {last_blue['width']},
    "height": {last_blue['height']}
}}

# Barre verte (progression)
self.green_bar = {{
    "top": {last_green['y']},
    "left": {last_green['x']},
    "width": {last_green['width']},
    "height": {last_green['height']}
}}
""")
                        print("=" * 60)
                        print("✅ Coordonnées sauvegardées! Tu peux maintenant les copier.")
                        print("   Appuie sur 'q' pour quitter.\n")
                    else:
                        print("\n⚠️  Aucune barre détectée pour l'instant!\n")
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Arrêt demandé par l'utilisateur")
        
        finally:
            cv2.destroyAllWindows()
            print("\n✅ Détection terminée")

# === POINT D'ENTRÉE ===
if __name__ == "__main__":
    detector = BarDetector()
    detector.run_detection_test()