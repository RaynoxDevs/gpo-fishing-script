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
        self.target_offset = 40  # Zone grise doit être 20px AU-DESSUS du marqueur blanc
        self.tolerance = 5       # Tolérance en pixels
        self.click_interval = 0.1  # Intervalle entre micro-clics (10 CPS max)
        
        # Système de prédiction (V11)
        self.last_white_y = None
        self.white_y_velocity = 0
        self.prediction_weight = 0.3  # 30% prédiction, 70% position actuelle
        
        # Timers
        self.last_action_time = 0
        self.last_click_time = 0
        
        # Gestion des états
        self.bar_lost_time = None
        self.click_sent_for_restart = False
        self.just_caught_fish = False
        self.fish_caught_time = None
    
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
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
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
        🚁 CONTRÔLE PROPORTIONNEL V4 - Système de duty cycle
        
        Retourne: (should_click, click_type, duty_cycle)
        - should_click: booléen
        - click_type: "long", "fast", "hover", "stable", None
        - duty_cycle: 0-100 (% du temps où on clique)
        """
        if gray_y is None or white_y is None:
            self.last_white_y = None
            self.white_y_velocity = 0
            return False, None, 0
        
        # Calcul de la vélocité (prédiction)
        if self.last_white_y is not None:
            self.white_y_velocity = white_y - self.last_white_y
        self.last_white_y = white_y
        
        # Position cible avec prédiction
        predicted_white_y = white_y + (self.white_y_velocity * 4)
        target_gray_y = white_y - self.target_offset
        predicted_target_y = predicted_white_y - self.target_offset
        
        # Distance hybride (70% actuel, 30% prédiction)
        current_distance = gray_y - target_gray_y
        predicted_distance = gray_y - predicted_target_y
        distance = (current_distance * 0.7) + (predicted_distance * 0.3)
        
        # CONTRÔLE PROPORTIONNEL basé sur la distance
        if distance > 50:
            return True, "long", 100  # Monter vite (clic maintenu)
        elif distance > 20:
            return True, "fast", 80   # Monter activement
        elif distance > 5:
            return True, "hover", 50  # MAINTENIR position (hover mode)
        elif distance > -5:
            return True, "stable", 30 # Stabiliser
        else:
            return False, None, 0     # Descendre (relâché)
    
    def run(self, debug=True):
        self.sct = mss.mss()
        
        print("\n" + "="*50)
        print("STARTING BOT V12 - HYBRID PROPORTIONAL CONTROL")
        print("="*50)
        
        if not self.calibrated:
            print("❌ Not calibrated! Use calibration button first.")
            return
        
        print("\n🚁 Algorithm: V4 Proportional Control + V11 Prediction")
        print("   - Gray zone maintained 20px ABOVE white marker")
        print("   - Adaptive duty cycle based on distance:")
        print("     • 100% = Rise fast (hold click)")
        print("     • 80%  = Rise actively")
        print("     • 50%  = HOVER (maintain position)")
        print("     • 30%  = Stabilize")
        print("     • 0%   = Descend")
        print("\nPress 'Q' in debug window to stop")
        print("Starting in 3 seconds...\n")
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        fps_start = time.time()
        
        if debug:
            cv2.namedWindow("Bot Debug V12", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Bot Debug V12", 800, 500)
            cv2.setWindowProperty("Bot Debug V12", cv2.WND_PROP_TOPMOST, 1)
            time.sleep(0.3)
        
        try:
            while self.running:
                blue_frame = self.capture_blue_bar()
                green_frame = self.capture_green_bar()
                
                white_y = self.find_white_marker_y(blue_frame)
                gray_y = self.find_gray_zone_y(blue_frame)
                progress = self.get_green_bar_progress(green_frame)
                
                if white_y is None or gray_y is None:
                    current_time = time.time()
                    
                    if self.just_caught_fish:
                        if self.fish_caught_time and (current_time - self.fish_caught_time) < 5:
                            time.sleep(0.5)
                            continue
                        else:
                            self.just_caught_fish = False
                    
                    time.sleep(0.1)
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
                
                if debug:
                    debug_view = np.zeros((500, 800, 3), dtype=np.uint8)
                    blue_scaled = cv2.resize(blue_frame, (200, 400))
                    debug_view[50:450, 50:250] = blue_scaled
                    green_scaled = cv2.resize(green_frame, (100, 400))
                    debug_view[50:450, 300:400] = green_scaled
                    
                    if white_y is not None:
                        white_y_scaled = int((white_y / self.blue_bar["height"]) * 400) + 50
                        cv2.line(debug_view, (50, white_y_scaled), (250, white_y_scaled), (255, 255, 255), 3)
                        cv2.putText(debug_view, "TARGET", (260, white_y_scaled), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        
                        # Ligne cible (20px au-dessus)
                        target_y_scaled = int(((white_y - self.target_offset) / self.blue_bar["height"]) * 400) + 50
                        for x in range(50, 250, 10):
                            cv2.line(debug_view, (x, target_y_scaled), (min(x+5, 250), target_y_scaled), (0, 255, 0), 2)
                        cv2.putText(debug_view, "IDEAL", (260, target_y_scaled), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    if gray_y is not None:
                        gray_y_scaled = int((gray_y / self.blue_bar["height"]) * 400) + 50
                        cv2.line(debug_view, (50, gray_y_scaled), (250, gray_y_scaled), (128, 128, 128), 3)
                        cv2.putText(debug_view, "CONTROL", (260, gray_y_scaled), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                    
                    info_y = 50
                    cv2.putText(debug_view, f"Progress: {progress:.1f}%", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    info_y += 40
                    click_color = (0, 255, 0) if self.is_clicking else (0, 0, 255)
                    cv2.putText(debug_view, f"Clicking: {self.is_clicking}", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, click_color, 2)
                    info_y += 40
                    if white_y and gray_y:
                        target_gray_y = white_y - self.target_offset
                        distance = gray_y - target_gray_y
                        dist_color = (0, 255, 0) if abs(distance) <= self.tolerance else (255, 255, 0) if abs(distance) < 20 else (0, 165, 255)
                        cv2.putText(debug_view, f"Distance: {distance:+.0f}px", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, dist_color, 2)
                    info_y += 40
                    if click_type:
                        type_text = {"long": "LONG", "fast": "FAST", "hover": "HOVER", "stable": "STABLE"}.get(click_type, "NONE")
                        type_color = {"long": (0, 165, 255), "fast": (255, 255, 0), "hover": (0, 255, 0), "stable": (128, 255, 128)}.get(click_type, (128, 128, 128))
                        cv2.putText(debug_view, f"Mode: {type_text} ({duty_cycle}%)", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, type_color, 2)
                    info_y += 40
                    cv2.putText(debug_view, f"Target: -{self.target_offset}px | Tol: ±{self.tolerance}px", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                    info_y += 60
                    cv2.putText(debug_view, "BLUE BAR", (100, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(debug_view, "GREEN BAR", (310, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.imshow("Bot Debug V12", debug_view)
                
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    mode_str = f"{click_type}({duty_cycle}%)" if click_type else "NONE"
                    dist_str = f"{gray_y - (white_y - self.target_offset):+.0f}px" if (white_y and gray_y) else "N/A"
                    print(f"FPS: {fps_counter:2d} | Progress: {progress:5.1f}% | Click: {'YES' if self.is_clicking else 'NO '} | Mode: {mode_str:>14} | Dist: {dist_str:>6}")
                    fps_counter = 0
                    fps_start = time.time()
                
                if progress >= 95.0:
                    print("\n🎣 FISH CAUGHT! 🎣")
                    print("Waiting for bar to disappear...\n")
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                    self.just_caught_fish = True
                    self.fish_caught_time = time.time()
                    time.sleep(2)
                
                if debug and cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Stop requested by user")
        finally:
            if self.is_clicking:
                pyautogui.mouseUp()
            if debug:
                cv2.destroyAllWindows()
            print("\n✅ Bot stopped")

class BotGUI:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.bot_thread = None
        
        self.root = tk.Tk()
        self.root.title("GPO Fishing Bot V12")
        self.root.geometry("320x300")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 12, 'bold'))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="GPO Auto Fishing Bot", font=('Arial', 16, 'bold'))
        title_label.pack(pady=5)
        
        version_label = ttk.Label(main_frame, text="V12 - Proportional Control", font=('Arial', 9, 'italic'))
        version_label.pack(pady=2)
        
        self.status_label = ttk.Label(main_frame, text="Status: Stopped", font=('Arial', 10))
        self.status_label.pack(pady=10)
        
        self.cal_button = ttk.Button(main_frame, text="CALIBRATION (F7)", style='Big.TButton', state='disabled')
        self.cal_button.pack(pady=5, fill=tk.X)
        
        self.start_button = ttk.Button(main_frame, text="START (F6)", style='Big.TButton', state='disabled')
        self.start_button.pack(pady=5, fill=tk.X)
        
        self.exit_button = ttk.Button(main_frame, text="EXIT (Q)", command=self.exit_app, style='Big.TButton')
        self.exit_button.pack(pady=5, fill=tk.X)
        
        if self.bot.load_calibration():
            self.status_label.config(text="Status: Calibrated")
        
        self.root.bind('q', lambda e: self.exit_app())
        self.root.bind('Q', lambda e: self.exit_app())
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        try:
            keyboard.add_hotkey('f6', self.start_bot, suppress=False)
            keyboard.add_hotkey('f7', self.calibrate, suppress=False)
            print("✅ Global hotkeys active: F6=Start/Stop, F7=Calibration")
        except:
            print("⚠️ Global hotkeys unavailable")
    
    def calibrate(self):
        print("\n▶️ Starting calibration...")
        self.status_label.config(text="Status: Calibrating...")
        
        def do_calibration():
            if self.bot.manual_calibrate():
                self.root.after(100, lambda: self.status_label.config(text="Status: Calibrated"))
            else:
                self.root.after(100, lambda: self.status_label.config(text="Status: Stopped"))
        
        threading.Thread(target=do_calibration, daemon=True).start()
    
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
            self.bot.run(debug=True)
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
        cv2.destroyAllWindows()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("GPO AUTO FISHING BOT V12 - HYBRID VERSION")
    print("="*50)
    print("\n🔥 Features:")
    print("  • V4 Proportional Control (Duty Cycle)")
    print("  • V11 Prediction System")
    print("  • V11 GUI & Calibration")
    print("  • Optimized Performance")
    
    bot = GPOFishingBot()
    gui = BotGUI(bot)
    gui.run()