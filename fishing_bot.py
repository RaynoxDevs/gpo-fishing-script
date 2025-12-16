import cv2
import numpy as np
import mss
import pyautogui
import time
import tkinter as tk
from tkinter import ttk
import threading
import keyboard

class ManualCalibrationWindow:
    def __init__(self, on_complete_callback):
        self.on_complete = on_complete_callback
        self.dragging = False
        self.start_x = 0
        self.start_y = 0
        self.rect_x = 100
        self.rect_y = 100
        self.rect_width = 35
        self.rect_height = 350
        
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
        
        self.blue_bar_width = 27
        self.blue_bar_height = 423
        self.green_offset_x = 64
        self.green_offset_y = 52
        self.green_bar_width = 22
        self.green_bar_height = 319
        
        self.blue_bar = None
        self.green_bar = None
        self.calibrated = False
        
        self.target_offset = 20
        self.tolerance = 3
        
        self.last_action_time = 0
        self.last_white_y = None
        self.white_y_velocity = 0
        self.prediction_frames = 3
        self.last_click_duration = 0
        
        self.bar_lost_time = None
        self.click_sent_for_restart = False
        self.just_caught_fish = False
        self.fish_caught_time = None
    
    def get_sct(self):
        if self.sct is None:
            self.sct = mss.mss()
        return self.sct
    
    def manual_calibrate(self):
        print("\n🎯 Manual Calibration Mode")
        print("Move the blue rectangle over the blue bar")
        print("Press ENTER to confirm")
        
        result = {'x': None, 'y': None, 'w': None, 'h': None}
        
        def on_calibration_complete(x, y, w, h):
            result['x'] = x
            result['y'] = y
            result['w'] = w
            result['h'] = h
        
        cal_window = ManualCalibrationWindow(on_calibration_complete)
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
            return True
        else:
            print("❌ Calibration cancelled")
            return False
    
    def capture_blue_bar(self):
        screenshot = self.get_sct().grab(self.blue_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def capture_green_bar(self):
        screenshot = self.get_sct().grab(self.green_bar)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def find_white_marker_y(self, blue_frame):
        hsv = cv2.cvtColor(blue_frame, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        moments = cv2.moments(mask)
        if moments["m00"] > 0:
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
    
    def should_click(self, gray_y, white_y):
        if gray_y is None or white_y is None:
            self.last_white_y = None
            self.white_y_velocity = 0
            return False, 0
        
        if self.last_white_y is not None:
            self.white_y_velocity = white_y - self.last_white_y
        self.last_white_y = white_y
        
        target_gray_y = white_y - self.target_offset
        predicted_white_y = white_y + (self.white_y_velocity * self.prediction_frames)
        predicted_target_y = predicted_white_y - self.target_offset
        
        current_distance = gray_y - target_gray_y
        predicted_distance = gray_y - predicted_target_y
        distance = (current_distance + predicted_distance) / 2.0
        
        if distance > 50:
            self.last_click_duration = 300
            return True, 300
        elif distance > 30:
            self.last_click_duration = 200
            return True, 200
        elif distance > 15:
            self.last_click_duration = 120
            return True, 120
        elif distance > 8:
            self.last_click_duration = 80
            return True, 80
        elif distance > 3:
            self.last_click_duration = 50
            return True, 50
        elif distance > -3:
            self.last_click_duration = 30
            return True, 30
        else:
            self.last_click_duration = 0
            return False, 0
    
    def check_and_recalibrate(self):
        sct = self.get_sct()
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([90, 80, 120])
        upper_blue = np.array([130, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        kernel = np.ones((5, 5), np.uint8)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if h > 150 and w > 10 and h > w * 5:
                if self.blue_bar:
                    old_x = self.blue_bar['left']
                    old_y = self.blue_bar['top']
                    if abs(x - old_x) > 3 or abs(y - old_y) > 3:
                        print(f"🔄 Bar moved: ({old_x},{old_y}) -> ({x},{y})")
                        self.blue_bar = {"top": y, "left": x, "width": self.blue_bar_width, "height": self.blue_bar_height}
                        self.green_bar = {"top": y + self.green_offset_y, "left": x + self.green_offset_x, "width": self.green_bar_width, "height": self.green_bar_height}
                self.bar_lost_time = None
                self.click_sent_for_restart = False
                return True
        return False
    
    def run(self, debug=True):
        print("\n" + "="*50)
        print("STARTING BOT")
        print("="*50)
        
        if not self.calibrated:
            print("❌ Not calibrated! Use calibration button first.")
            return
        
        print("\nPress 'Q' in debug window to stop")
        print("Starting in 3 seconds...\n")
        time.sleep(3)
        
        self.running = True
        fps_counter = 0
        fps_start = time.time()
        
        if debug:
            cv2.namedWindow("Bot Debug", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Bot Debug", 800, 500)
            cv2.setWindowProperty("Bot Debug", cv2.WND_PROP_TOPMOST, 1)
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
                            print("⏳ Waiting for next fish...")
                            time.sleep(0.5)
                            continue
                        else:
                            self.just_caught_fish = False
                    
                    print("\n⚠️  Detection failed! Searching...")
                    if self.check_and_recalibrate():
                        blue_frame = self.capture_blue_bar()
                        green_frame = self.capture_green_bar()
                        white_y = self.find_white_marker_y(blue_frame)
                        gray_y = self.find_gray_zone_y(blue_frame)
                        progress = self.get_green_bar_progress(green_frame)
                        print("✅ Bar found!")
                    else:
                        if self.bar_lost_time is None:
                            self.bar_lost_time = current_time
                            print("⚠️  Bar lost! Attempting restart...")
                        if not self.click_sent_for_restart:
                            pyautogui.click()
                            print("🖱️  Click sent")
                            self.click_sent_for_restart = True
                            time.sleep(0.5)
                        elapsed = current_time - self.bar_lost_time
                        if elapsed < 15:
                            print(f"⏳ Waiting... ({elapsed:.1f}s/15s)")
                            time.sleep(0.5)
                            continue
                        else:
                            print("⚠️  15s timeout. Resetting...")
                            self.bar_lost_time = None
                            self.click_sent_for_restart = False
                            time.sleep(1)
                            continue
                
                should_click, click_duration_ms = self.should_click(gray_y, white_y)
                current_time = time.time()
                
                if should_click:
                    time_since_last = current_time - self.last_action_time
                    click_duration_s = click_duration_ms / 1000.0
                    if not self.is_clicking:
                        pyautogui.mouseDown()
                        self.is_clicking = True
                        self.last_action_time = current_time
                    elif time_since_last >= click_duration_s:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                        self.last_action_time = current_time
                        time.sleep(0.03)
                else:
                    if self.is_clicking:
                        pyautogui.mouseUp()
                        self.is_clicking = False
                
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
                    release_ms = self.last_click_duration
                    color = (0, 255, 0) if release_ms < 100 else (255, 255, 0) if release_ms < 200 else (0, 165, 255)
                    cv2.putText(debug_view, f"Click: {release_ms}ms", (450, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    info_y += 60
                    cv2.putText(debug_view, "BLUE BAR", (100, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(debug_view, "GREEN BAR", (310, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.imshow("Bot Debug", debug_view)
                
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    mode_str = f"Click:{self.last_click_duration}ms"
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
            print("\n\n⚠️  Stop requested by user")
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
        self.root.title("GPO Fishing Bot")
        self.root.geometry("300x250")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 12, 'bold'))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="GPO Auto Fishing Bot", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        self.status_label = ttk.Label(main_frame, text="Status: Stopped", font=('Arial', 10))
        self.status_label.pack(pady=10)
        
        self.cal_button = ttk.Button(main_frame, text="CALIBRATION", command=self.calibrate, style='Big.TButton')
        self.cal_button.pack(pady=5, fill=tk.X)
        
        self.start_button = ttk.Button(main_frame, text="START (F6)", command=self.start_bot, style='Big.TButton', state='disabled')
        self.start_button.pack(pady=5, fill=tk.X)
        
        self.exit_button = ttk.Button(main_frame, text="EXIT (Q)", command=self.exit_app, style='Big.TButton')
        self.exit_button.pack(pady=5, fill=tk.X)
        
        self.root.bind('q', lambda e: self.exit_app())
        self.root.bind('Q', lambda e: self.exit_app())
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        try:
            keyboard.add_hotkey('f6', self.start_bot, suppress=False)
            print("✅ Global hotkey F6 active")
        except:
            print("⚠️  Global hotkey F6 unavailable")
    
    def calibrate(self):
        print("\n▶️  Starting calibration...")
        self.status_label.config(text="Status: Calibrating...")
        self.cal_button.config(state='disabled')
        
        def do_calibration():
            if self.bot.manual_calibrate():
                self.root.after(100, lambda: self.status_label.config(text="Status: Calibrated"))
                self.root.after(100, lambda: self.start_button.config(state='normal'))
            else:
                self.root.after(100, lambda: self.status_label.config(text="Status: Stopped"))
            self.root.after(100, lambda: self.cal_button.config(state='normal'))
        
        threading.Thread(target=do_calibration, daemon=True).start()
    
    def start_bot(self):
        if not self.running and self.bot.calibrated:
            print("\n▶️  Starting bot...")
            self.running = True
            self.status_label.config(text="Status: Fishing...")
            self.start_button.config(state='disabled', text="RUNNING...")
            self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            self.bot_thread.start()
    
    def run_bot_thread(self):
        try:
            self.bot.run(debug=True)
        except Exception as e:
            print(f"❌ Error: {e}")
            self.status_label.config(text="Status: Error")
        finally:
            self.running = False
            self.start_button.config(state='normal', text="START (F6)")
    
    def exit_app(self):
        print("\n👋 Closing...")
        self.bot.running = False
        if self.bot.is_clicking:
            pyautogui.mouseUp()
        try:
            keyboard.remove_hotkey('f6')
        except:
            pass
        cv2.destroyAllWindows()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("GPO AUTO FISHING BOT - MANUAL CALIBRATION")
    print("="*50)
    
    bot = GPOFishingBot()
    gui = BotGUI(bot)
    gui.run()