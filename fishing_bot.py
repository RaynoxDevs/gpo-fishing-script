import cv2
import numpy as np
import mss
import pyautogui
import time
import tkinter as tk
from tkinter import ttk
import threading
import keyboard
import json
import os
import ctypes

class ManualCalibrationWindow:
    def __init__(self, on_complete_callback, last_x=None, last_y=None):
        self.on_complete = on_complete_callback
        self.dragging = False
        self.start_x = 0
        self.start_y = 0
        self.rect_x = last_x if last_x is not None else 100
        self.rect_y = last_y if last_y is not None else 100
        self.rect_width = 40
        self.rect_height = 400
        
        self.root = tk.Tk()
        self.root.title("Manual Calibration")
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')
        
        self.canvas = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.rect = self.canvas.create_rectangle(
            self.rect_x, self.rect_y,
            self.rect_x + self.rect_width, self.rect_y + self.rect_height,
            outline='cyan', width=3, fill='blue', stipple='gray50'
        )
        
        self.text = self.canvas.create_text(
            self.rect_x + self.rect_width // 2, self.rect_y - 20,
            text="Drag this box over the blue bar\nPress ENTER to confirm",
            fill='white', font=('Arial', 12, 'bold')
        )
        
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.root.bind('<Return>', self.on_confirm)
        self.root.bind('<Escape>', self.on_cancel)
        
    def on_press(self, event):
        x1, y1, x2, y2 = self.canvas.coords(self.rect)
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            self.dragging = True
            self.start_x = event.x - x1
            self.start_y = event.y - y1
    
    def on_drag(self, event):
        if self.dragging:
            new_x = event.x - self.start_x
            new_y = event.y - self.start_y
            self.canvas.coords(self.rect, new_x, new_y, 
                             new_x + self.rect_width, new_y + self.rect_height)
            self.canvas.coords(self.text, new_x + self.rect_width // 2, new_y - 20)
    
    def on_release(self, event):
        self.dragging = False
    
    def on_confirm(self, event=None):
        x1, y1, x2, y2 = self.canvas.coords(self.rect)
        self.root.destroy()
        self.on_complete(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
    
    def on_cancel(self, event=None):
        self.root.destroy()
        self.on_complete(None, None, None, None)
    
    def show(self):
        self.root.mainloop()

class GPOFishingBot:
    def __init__(self):
        self.sct = None
        self.running = False
        self.is_clicking = False
        
        # Dimensions fixes
        self.blue_bar_width = 40
        self.blue_bar_height = 400
        self.green_offset_x = 64
        self.green_offset_y = 52
        self.green_bar_width = 22
        self.green_bar_height = 319
        
        self.blue_bar = None
        self.green_bar = None
        self.calibrated = False
        
        # === PARAMÈTRES V4 - CONTRÔLE PROPORTIONNEL ===
        self.target_offset = 40  # Zone grise doit être 40px AU-DESSUS du marqueur blanc
        self.tolerance = 5       # Tolérance en pixels
        self.click_interval = 0.1  # Intervalle entre micro-clics (10 CPS max)
        
        # Timers
        self.last_action_time = 0
        self.last_click_time = 0
        
        # Gestion des états
        self.bar_lost_time = None
        self.click_sent_for_restart = False
        self.just_caught_fish = False
        self.fish_caught_time = None
        self.fish_count = 0
        self.first_cast = True  # Pour ne pas compter le premier lancer
    
    def get_sct(self):
        if self.sct is None:
            self.sct = mss.mss()
        return self.sct
    
    def save_calibration(self):
        if self.blue_bar:
            data = {'x': self.blue_bar['left'], 'y': self.blue_bar['top']}
            with open('calibration.json', 'w') as f:
                json.dump(data, f)
            print("💾 Calibration saved")
    
    def load_calibration(self):
        if os.path.exists('calibration.json'):
            try:
                with open('calibration.json', 'r') as f:
                    data = json.load(f)
                self.blue_bar = {"top": data['y'], "left": data['x'], "width": self.blue_bar_width, "height": self.blue_bar_height}
                self.green_bar = {"top": data['y'] + self.green_offset_y, "left": data['x'] + self.green_offset_x, "width": self.green_bar_width, "height": self.green_bar_height}
                self.calibrated = True
                print(f"✅ Calibration loaded: X={data['x']}, Y={data['y']}")
                return True
            except Exception as e:
                print(f"⚠️ Failed to load: {e}")
        return False
    
    def save_fish_count(self):
        """Sauvegarde le nombre de poissons capturés"""
        try:
            with open('fish_count.json', 'w') as f:
                json.dump({'count': self.fish_count}, f)
        except Exception as e:
            print(f"⚠️ Failed to save fish count: {e}")
    
    def load_fish_count(self):
        """Charge le nombre de poissons capturés depuis la dernière session"""
        if os.path.exists('fish_count.json'):
            try:
                with open('fish_count.json', 'r') as f:
                    data = json.load(f)
                    self.fish_count = data.get('count', 0)
                    print(f"✅ Fish count loaded: {self.fish_count}")
                    return True
            except Exception as e:
                print(f"⚠️ Failed to load fish count: {e}")
        return False
    
    def manual_calibrate(self):
        self.sct = mss.mss()
        
        print("\n🎯 Manual Calibration Mode")
        print("🔍 Applying zoom preset...")
        time.sleep(0.5)
        
        MOUSEEVENTF_WHEEL = 0x0800
        
        print("1. Zooming in (20x)...")
        for i in range(20):
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
            time.sleep(0.02)
        
        time.sleep(0.3)
        
        print("2. Zooming out (9x)...")
        for i in range(9):
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -120, 0)
            time.sleep(0.03)
        
        time.sleep(0.3)
        print("✅ Zoom applied!")
        time.sleep(0.5)
        print("✅ Zoom preset applied!")
        print("\nMove the blue rectangle over the blue bar")
        print("Press ENTER to confirm")
        
        result = {'x': None, 'y': None, 'w': None, 'h': None}
        
        def on_calibration_complete(x, y, w, h):
            result['x'] = x
            result['y'] = y
            result['w'] = w
            result['h'] = h
        
        last_x = self.blue_bar['left'] if self.blue_bar else None
        last_y = self.blue_bar['top'] if self.blue_bar else None
        cal_window = ManualCalibrationWindow(on_calibration_complete, last_x, last_y)
        cal_window.show()
        
        if result['x'] is not None:
            self.blue_bar = {
                "top": result['y'],
                "left": result['x'],
                "width": self.blue_bar_width,
                "height": self.blue_bar_height
            }
            
            self.green_bar = {
                "top": result['y'] + self.green_offset_y,
                "left": result['x'] + self.green_offset_x,
                "width": self.green_bar_width,
                "height": self.green_bar_height
            }
            
            self.calibrated = True
            print(f"✅ Calibration complete: X={result['x']}, Y={result['y']}")
            self.save_calibration()
            return True
        else:
            print("❌ Calibration cancelled")
            return False
    
    def capture_blue_bar(self):
        if self.sct is None:
            self.sct = mss.mss()
        screenshot = self.sct.grab(self.blue_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def capture_green_bar(self):
        if self.sct is None:
            self.sct = mss.mss()
        screenshot = self.sct.grab(self.green_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def find_white_marker_y(self, blue_frame):
        gray = cv2.cvtColor(blue_frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        moments = cv2.moments(thresh)
        if moments["m00"] > 50:
            return int(moments["m01"] / moments["m00"])
        return None
    
    def find_gray_zone_y(self, blue_frame):
        lower_bound = np.array([15, 15, 15])
        upper_bound = np.array([35, 35, 35])
        mask = cv2.inRange(blue_frame, lower_bound, upper_bound)
        height = mask.shape[0]
        max_width = 0
        best_y = None
        for y in range(height):
            white_pixels = np.sum(mask[y, :] > 0)
            if white_pixels > max_width:
                max_width = white_pixels
                best_y = y
        if best_y is not None and max_width >= 15:
            return best_y
        return None
    
    def get_green_bar_progress(self, green_frame):
        hsv = cv2.cvtColor(green_frame, cv2.COLOR_BGR2HSV)
        lower_green = np.array([25, 20, 20])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        green_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        if total_pixels > 0:
            return (green_pixels / total_pixels) * 100
        return 0.0
    
    def should_click_v4(self, gray_y, white_y):
        """
        🚁 CONTRÔLE PROPORTIONNEL V4 - Système de duty cycle OPTIMISÉ
        
        Retourne: (should_click, click_type, duty_cycle)
        - should_click: booléen
        - click_type: "long", "fast", "hover", "stable", None
        - duty_cycle: 0-100 (% du temps où on clique)
        """
        if gray_y is None or white_y is None:
            return False, None, 0
        
        # Position cible : zone grise doit être 40px AU-DESSUS du marqueur blanc
        target_gray_y = white_y - self.target_offset
        distance = gray_y - target_gray_y
        
        # CONTRÔLE OPTIMISÉ - Correction immédiate si trop haut
        if distance > 150:
            return True, "long", 300   # Très très loin : monter vite
        elif distance > 100:
            return True, "fast", 200   # Loin : monter contrôlé
        elif distance > 80:
            return True, "fast", 170 # Loin : monter contrôlé
        elif distance > 50:
            return True, "hover", 105  # Moyennement loin : ralentir progressivement
        elif distance > 30:
            return True, "hover", 105  # Moyennement loin : ralentir progressivement
        elif distance > 1:
            return True, "stable", 30 # Approche finale : stabilisation anticipée
        else:
            # distance <= 0 : TROP HAUT - Relâcher immédiatement !
            return False, None, 0
                    
    
    def run(self, debug=False):
        self.sct = mss.mss()
        
        print("\n" + "="*50)
        print("STARTING BOT V14 - OPTIMIZED CONTROL")
        print("="*50)
        
        if not self.calibrated:
            print("❌ Not calibrated! Use calibration button first.")
            return
        
        print("\n🚁 Algorithm: V14 Optimized Control (No Prediction)")
        print("   - Gray zone maintained 40px ABOVE white marker")
        print("   - Adaptive duty cycle (immediate correction):")
        print("     • 90% = Rise fast (very far +60px)")
        print("     • 55% = Rise controlled (far +40px)")
        print("     • 30% = HOVER smooth (medium +25px)")
        print("     • 18% = APPROACH (anticipate, +8 to +25px)")
        print("     • 20% = STABLE (target zone: 0 to +8px)")
        print("     • 0%  = RELEASE (below 0px - immediate correction!)")
        print("\nPress F6 to stop")
        print("Starting in 3 seconds...\n")
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        fps_start = time.time()
        
        try:
            while self.running:
                blue_frame = self.capture_blue_bar()
                green_frame = self.capture_green_bar()
                
                white_y = self.find_white_marker_y(blue_frame)
                gray_y = self.find_gray_zone_y(blue_frame)
                
                # Reset restart variables when detection works
                if white_y is not None and gray_y is not None:
                    self.bar_lost_time = None
                    self.click_sent_for_restart = False
                progress = self.get_green_bar_progress(green_frame)
                
                if white_y is None or gray_y is None:
                    current_time = time.time()
                    
                    # After catching fish, wait a bit
                    if self.just_caught_fish:
                        if self.fish_caught_time and (current_time - self.fish_caught_time) < 3:
                            time.sleep(0.5)
                            continue
                        else:
                            self.just_caught_fish = False
                    
                    # Detection failed - rod not cast, restart fishing
                    if self.bar_lost_time is None:
                        self.bar_lost_time = current_time
                        print("\n⚠️  No detection - Restarting fishing...")
                    
                    # Wait 1 second before clicking to cast rod
                    elapsed = current_time - self.bar_lost_time
                    if not self.click_sent_for_restart and elapsed >= 1.0:
                        # Incrémenter le compteur si ce n'est pas le premier lancer
                        if not self.first_cast:
                            self.fish_count += 1
                            print(f"\n🎣 FISH CAUGHT! Total: {self.fish_count} 🎣")
                            self.save_fish_count()  # Sauvegarde
                        else:
                            self.first_cast = False
                            print("\n🎣 First cast - starting fishing...")
                        
                        pyautogui.click()
                        print("🖱️  Click sent to cast rod")
                        self.click_sent_for_restart = True
                        time.sleep(0.5)
                    
                    # Wait for bar to appear (max 15s after click)
                    if elapsed < 15:
                        if elapsed % 3 < 0.5:  # Print every 3 seconds
                            print(f"⏳ Waiting for bar... ({elapsed:.1f}s/15s)")
                        time.sleep(0.5)
                        continue
                    else:
                        # Reset after 15s timeout
                        print("⚠️  15s timeout - Resetting...")
                        self.bar_lost_time = None
                        self.click_sent_for_restart = False
                        time.sleep(1)
                        continue
                
                # === DÉCISION V4 AVEC DUTY CYCLE ===
                should_click, click_type, duty_cycle = self.should_click_v4(gray_y, white_y)
                current_time = time.time()
                
                if should_click:
                    if click_type == "long":
                        # 100% duty cycle : clic maintenu
                        if not self.is_clicking:
                            pyautogui.mouseDown()
                            self.is_clicking = True
                            self.last_click_time = current_time
                    else:
                        # Clics proportionnels basés sur le duty cycle
                        click_duration = self.click_interval * (duty_cycle / 100.0)
                        release_duration = self.click_interval - click_duration
                        
                        time_since_action = current_time - self.last_action_time
                        
                        if not self.is_clicking:
                            if time_since_action >= release_duration:
                                pyautogui.mouseDown()
                                self.is_clicking = True
                                self.last_action_time = current_time
                        else:
                            if time_since_action >= click_duration:
                                pyautogui.mouseUp()
                                self.is_clicking = False
                                self.last_action_time = current_time
                else:
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                        self.last_action_time = current_time
                
                # Affichage console simplifié (sans debug visuel)
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    mode_str = f"{click_type}({duty_cycle}%)" if click_type else "NONE"
                    dist_str = f"{gray_y - (white_y - self.target_offset):+.0f}px" if (white_y and gray_y) else "N/A"
                    print(f"FPS: {fps_counter:2d} | Progress: {progress:5.1f}% | Click: {'YES' if self.is_clicking else 'NO '} | Mode: {mode_str:>14} | Dist: {dist_str:>6}")
                    fps_counter = 0
                    fps_start = time.time()
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Stop requested by user")
        finally:
            if self.is_clicking:
                pyautogui.mouseUp()
            print("\n✅ Bot stopped")

class BotGUI:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.bot_thread = None
        
        self.root = tk.Tk()
        self.root.title("GPO Fishing Bot V14")
        self.root.geometry("320x300")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 12, 'bold'))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="GPO Auto Fishing Bot", font=('Arial', 16, 'bold'))
        title_label.pack(pady=5)
        
        version_label = ttk.Label(main_frame, text="V14 - Optimized Control", font=('Arial', 9, 'italic'))
        version_label.pack(pady=2)
        
        self.status_label = ttk.Label(main_frame, text="Status: Stopped", font=('Arial', 10))
        self.status_label.pack(pady=5)
        
        self.fish_label = ttk.Label(main_frame, text="Fish Caught: 0", font=('Arial', 12, 'bold'), foreground='green')
        self.fish_label.pack(pady=5)
        
        self.cal_button = ttk.Button(main_frame, text="CALIBRATION (F7)", style='Big.TButton', state='disabled')
        self.cal_button.pack(pady=5, fill=tk.X)
        
        self.start_button = ttk.Button(main_frame, text="START (F6)", style='Big.TButton', state='disabled')
        self.start_button.pack(pady=5, fill=tk.X)
        
        self.exit_button = ttk.Button(main_frame, text="EXIT (Q)", command=self.exit_app, style='Big.TButton')
        self.exit_button.pack(pady=5, fill=tk.X)
        
        if self.bot.load_calibration():
            self.status_label.config(text="Status: Calibrated")
        
        # Charger le compteur de poissons
        self.bot.load_fish_count()
        self.fish_label.config(text=f"Fish Caught: {self.bot.fish_count}")
        
        self.root.bind('q', lambda e: self.exit_app())
        self.root.bind('Q', lambda e: self.exit_app())
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        try:
            keyboard.add_hotkey('f6', self.start_bot, suppress=False)
            keyboard.add_hotkey('f7', self.calibrate, suppress=False)
            print("✅ Global hotkeys active: F6=Start/Stop, F7=Calibration")
        except:
            print("⚠️ Global hotkeys unavailable")
        
        # Démarre la mise à jour automatique du compteur de poissons
        self.update_fish_count()
    
    def calibrate(self):
        print("\n▶️ Starting calibration...")
        self.status_label.config(text="Status: Calibrating...")
        
        def do_calibration():
            if self.bot.manual_calibrate():
                self.root.after(100, lambda: self.status_label.config(text="Status: Calibrated"))
            else:
                self.root.after(100, lambda: self.status_label.config(text="Status: Stopped"))
        
        threading.Thread(target=do_calibration, daemon=True).start()
    

    def update_fish_count(self):
        if self.fish_label.winfo_exists():
            self.fish_label.config(text=f"Fish Caught: {self.bot.fish_count}")
        self.root.after(1000, self.update_fish_count)

    def start_bot(self):
        if not self.bot.calibrated:
            print("⚠️ Please calibrate first!")
            return
        
        if self.running:
            print("\n⏸️ Stopping bot...")
            self.bot.running = False
            self.running = False
            self.status_label.config(text="Status: Stopped")
            self.start_button.config(text="START (F6)")
        else:
            print("\n▶️ Starting bot...")
            
            self.running = True
            self.bot.running = True
            self.status_label.config(text="Status: Fishing...")
            self.start_button.config(text="STOP (F6)")
            self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            self.bot_thread.start()
    
    def run_bot_thread(self):
        try:
            self.bot.run(debug=False)
        except Exception as e:
            print(f"❌ Error: {e}")
            if self.status_label.winfo_exists():
                self.status_label.config(text="Status: Error")
        finally:
            self.running = False
            if self.start_button.winfo_exists():
                self.start_button.config(text="START (F6)")
            if self.status_label.winfo_exists() and self.status_label.cget("text") != "Status: Error":
                self.status_label.config(text="Status: Stopped")
    
    def exit_app(self):
        print("\n👋 Closing...")
        self.bot.running = False
        if self.bot.is_clicking:
            pyautogui.mouseUp()
        try:
            keyboard.remove_hotkey('f6')
            keyboard.remove_hotkey('f7')
        except:
            pass
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("GPO AUTO FISHING BOT V14 - OPTIMIZED VERSION")
    print("="*50)
    print("\n🔥 Features:")
    print("  • No Prediction (More Stable)")
    print("  • Enhanced STABLE Mode (±15px)")
    print("  • Fish Count Saving")
    print("  • Reduced Duty Cycles (Better Control)")
    print("  • No Debug Window (Lighter)")
    
    bot = GPOFishingBot()
    gui = BotGUI(bot)
    gui.run()