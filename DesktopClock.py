import datetime
import math
import os
import random
import threading
import queue
import tempfile
import pygame
from pygame import gfxdraw
import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw
import argparse


def create_tray_icon_file():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Simple round clock face with minute/hour hands for tray usage.
    margin = 5
    face_color = (245, 235, 200, 255)
    fill_color = (35, 35, 35, 220)
    center = size // 2
    draw.ellipse((margin, margin, size - margin - 1, size - margin - 1), outline=face_color, fill=fill_color, width=5)

    # Minute hand: straight up. Hour hand: around 2 o'clock.
    draw.line((center, center, center, 14), fill=face_color, width=5)
    draw.line((center, center, center + 14, center - 8), fill=face_color, width=6)
    draw.ellipse((center - 3, center - 3, center + 3, center + 3), fill=face_color)

    icon_path = os.path.join(tempfile.gettempdir(), "desktop_clock_tray.ico")
    img.save(icon_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)])
    return icon_path


class TrayIcon:
    WM_TRAYICON = win32con.WM_APP + 1
    ID_SHOW = 1023
    ID_HIDE = 1024
    ID_EXIT = 1025

    def __init__(self, title, action_queue):
        self.title = title
        self.action_queue = action_queue
        self.hwnd = None
        self.hicon = None
        self.icon_path = None
        self._class_name = "DesktopClockTrayWindow"
        self._thread = None
        self._ready = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def stop(self):
        if self.hwnd:
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)

    def _run(self):
        message_map = {
            win32con.WM_DESTROY: self._on_destroy,
            win32con.WM_COMMAND: self._on_command,
            self.WM_TRAYICON: self._on_tray,
        }

        window_class = win32gui.WNDCLASS()
        hinstance = win32api.GetModuleHandle(None)
        window_class.hInstance = hinstance
        window_class.lpszClassName = self._class_name
        window_class.lpfnWndProc = message_map

        try:
            win32gui.RegisterClass(window_class)
        except win32gui.error:
            pass

        self.hwnd = win32gui.CreateWindow(
            self._class_name,
            self._class_name,
            0,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            hinstance,
            None,
        )

        self.icon_path = create_tray_icon_file()
        self.hicon = win32gui.LoadImage(
            0,
            self.icon_path,
            win32con.IMAGE_ICON,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
        )
        if not self.hicon:
            self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        notify_id = (
            self.hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            self.WM_TRAYICON,
            self.hicon,
            self.title,
        )
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, notify_id)
        self._ready.set()

        win32gui.PumpMessages()

    def _on_tray(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP:
            self.action_queue.put("show")
        elif lparam == win32con.WM_RBUTTONUP:
            self._show_menu()
        return 0

    def _show_menu(self):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.ID_SHOW, "Show")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.ID_HIDE, "Hide")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.ID_EXIT, "Exit")

        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON,
            pos[0],
            pos[1],
            0,
            self.hwnd,
            None,
        )
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def _on_command(self, hwnd, msg, wparam, lparam):
        command_id = win32api.LOWORD(wparam)
        if command_id == self.ID_SHOW:
            self.action_queue.put("show")
        elif command_id == self.ID_HIDE:
            self.action_queue.put("hide")
        elif command_id == self.ID_EXIT:
            self.action_queue.put("exit")
        return 0

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
        if self.hicon:
            win32gui.DestroyIcon(self.hicon)
            self.hicon = None
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                os.remove(self.icon_path)
            except OSError:
                pass
        win32gui.PostQuitMessage(0)
        return 0


def set_tool_window(hwnd):
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style |= win32con.WS_EX_TOOLWINDOW
    ex_style &= ~win32con.WS_EX_APPWINDOW
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE
        | win32con.SWP_NOSIZE
        | win32con.SWP_NOZORDER
        | win32con.SWP_FRAMECHANGED,
    )


def get_desktop_host_window():
    progman = win32gui.FindWindow("Progman", None)
    if progman:
        try:
            # Ensure WorkerW/SHELLDLL_DefView hierarchy is initialized.
            win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
        except win32gui.error:
            pass

    found = {
        "defview": None,
        "workerw": None,
    }

    def enum_windows_callback(hwnd, _):
        defview = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
        if defview:
            found["defview"] = defview
            found["workerw"] = hwnd
        return True

    win32gui.EnumWindows(enum_windows_callback, None)

    if found["defview"]:
        return found["defview"]
    if found["workerw"]:
        return found["workerw"]
    if progman:
        return progman
    return win32gui.GetDesktopWindow()


def attach_to_desktop_layer(hwnd):
    host = get_desktop_host_window()

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style |= win32con.WS_CHILD
    style &= ~win32con.WS_POPUP
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

    win32gui.SetParent(hwnd, host)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOP,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE
        | win32con.SWP_NOSIZE
        | win32con.SWP_NOACTIVATE
        | win32con.SWP_SHOWWINDOW
        | win32con.SWP_FRAMECHANGED,
    )
    return host


"""
Set the desktop wallpaper to a BMP image. This function modifies the Windows registry to set the wallpaper style 
and tile options, and then uses the SystemParametersInfo function to apply the new wallpaper. The BMP image is 
specified by the bmp_path parameter.
"""
def set_wallpaper_from_bmp(bmp_path):
    reg_key = win32api.RegOpenKeyEx(win32con.HKEY_CURRENT_USER, "Control Panel\\Desktop", 2, win32con.KEY_SET_VALUE)
    # 2: Stretch, 0: Center, 6: Fit, 10: Fill, 0: Tile
    win32api.RegSetValueEx(reg_key, "WallpaperStyle", 10, win32con.REG_SZ, "10")
    # 1: Tile, 0: No Tile
    win32api.RegSetValueEx(reg_key, "TileWallpaper", 0, win32con.REG_SZ, "0")
    new_bmp_path = os.path.abspath(bmp_path)
    win32gui.SystemParametersInfo(win32con.SPI_SETDESKWALLPAPER, new_bmp_path, win32con.SPIF_SENDWININICHANGE)


"""
Set the desktop wallpaper to a randomly chosen image from the specified directory. If no directory is provided, 
it defaults to 'D:\\desktop_bg'. The chosen image is converted to BMP format and saved in a 'wallpaper' 
subdirectory before being set as the desktop wallpaper.
"""
def set_wallpaper(img_path):
    img_dir = os.path.dirname(img_path)
    bmp_image = Image.open(img_path)
    if not os.path.exists(os.path.join(img_dir, 'wallpaper')):
        os.makedirs(os.path.join(img_dir, 'wallpaper'))
    new_bmp_path = os.path.join(img_dir, 'wallpaper\\wallpaper.bmp')
    bmp_image.save(new_bmp_path, "BMP")
    set_wallpaper_from_bmp(new_bmp_path)


"""
Choose a random wallpaper from the list of JPG files in the specified directory. The function takes a list of 
JPG or PNG filenames and returns one randomly selected filename.
"""
def choose_wallpaper(jpgs):
    return random.choice(jpgs)


"""
Set the desktop wallpaper to a randomly chosen image from the specified directory. If no directory is provided,
it defaults to 'D:\\desktop_bg'. The function lists all JPG and PNG files in the directory, randomly selects one, 
and sets it as the desktop wallpaper using the set_wallpaper function.
"""
def wallpaper(path=None):
    if path is None:
        p = 'D:\\desktop_bg'
    else:
        p = path
    jpgs = os.listdir(p)
    for f in jpgs:
        if '.jpg' not in f and '.png' not in f or not os.path.isfile(os.path.join(p, f)):
            jpgs.remove(f)
    f = choose_wallpaper(jpgs)
    path = os.path.join(p, f)
    set_wallpaper(path)
    return p, jpgs, path


"""
Fix the position of the clock window to be near the bottom-right corner of the screen. The function checks if the
currently active window has the title 'clock', and if so, it moves the clock window to a position calculated based 
on the screen dimensions (xx, yy) with specific offsets to place it near the bottom-right corner.
"""
def fix_window(xx, yy):
    hwnd = pygame.display.get_wm_info()['window']
    target_x = xx - 380
    target_y = yy - 430

    parent = win32gui.GetParent(hwnd)
    if parent:
        try:
            target_x, target_y = win32gui.ScreenToClient(parent, (target_x, target_y))
        except win32gui.error:
            pass

    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOP,
        target_x,
        target_y,
        0,
        0,
        win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
    )


"""
Draw the clock face on the given surface. The function draws a central circle and 12 smaller circles around it to
represent the hours on the clock face. The circles are drawn in a lemon yellow color, and their positions are 
calculated using trigonometric functions to evenly space them around the center of the clock.
"""
def draw_clock_face(surface):
    lemon_yellow = 255, 250, 205
    origin = 175, 175

    ox, oy = int(origin[0]), int(origin[1])
    gfxdraw.filled_circle(surface, ox, oy, 8, lemon_yellow)
    gfxdraw.aacircle(surface, ox, oy, 8, lemon_yellow)

    for i in range(1, 13):
        sita = math.pi * i / 6
        pos = origin[0] + 150 * math.sin(sita), origin[1] - 150 * math.cos(sita)
        px, py = int(round(pos[0])), int(round(pos[1]))
        gfxdraw.filled_circle(surface, px, py, 12, lemon_yellow)
        gfxdraw.aacircle(surface, px, py, 12, lemon_yellow)


"""
Draw a single clock hand on the given surface. The function calculates the end position of the hand based on the
origin, angle, and length parameters. It then creates a polygon representing the hand with the specified width and 
color, and draws it using anti-aliasing for smoother edges. The function also draws circles at the base and tip of 
the hand to create a rounded appearance.
"""
def draw_hand(surface, origin, angle, length, width, color):
    ox, oy = origin
    dx = math.sin(angle)
    dy = -math.cos(angle)

    ex = ox + length * dx
    ey = oy + length * dy

    nx = -dy
    ny = dx
    half_w = width / 2

    points = [
        (ox + nx * half_w, oy + ny * half_w),
        (ox - nx * half_w, oy - ny * half_w),
        (ex - nx * half_w, ey - ny * half_w),
        (ex + nx * half_w, ey + ny * half_w),
    ]
    polygon = [(int(round(x)), int(round(y))) for x, y in points]

    gfxdraw.filled_polygon(surface, polygon, color)
    gfxdraw.aapolygon(surface, polygon, color)

    cap_r = max(1, int(round(half_w)))
    iox, ioy = int(round(ox)), int(round(oy))
    iex, iey = int(round(ex)), int(round(ey))
    gfxdraw.filled_circle(surface, iox, ioy, cap_r, color)
    gfxdraw.aacircle(surface, iox, ioy, cap_r, color)
    gfxdraw.filled_circle(surface, iex, iey, cap_r, color)
    gfxdraw.aacircle(surface, iex, iey, cap_r, color)


"""
Draw the clock hands on the given surface based on the current time. The function calculates the angles for the
second, minute, and hour hands using the current time, and then draws lines representing each hand in a lemon yellow
color. The lengths and widths of the hands are different to visually distinguish them, with the second hand being 
the longest and thinnest, and the hour hand being the shortest and thickest.
"""
def draw_hands(surface, now):
    lemon_yellow = 255, 250, 205
    origin = 175, 175

    second = now.second + now.microsecond / 1_000_000
    minute = now.minute + second / 60
    hour_12 = (now.hour % 12) + minute / 60

    s = math.pi * second / 30
    m = math.pi * minute / 30
    h = math.pi * hour_12 / 6

    draw_hand(surface, origin, s, 125, 8, lemon_yellow)
    draw_hand(surface, origin, m, 105, 10, lemon_yellow)
    draw_hand(surface, origin, h, 75, 12, lemon_yellow)

    return now.hour



    

def main():
    parser = argparse.ArgumentParser(description='Desktop Clock')
    parser.add_argument('-d', '--wallpaper-dir', type=str, default='D:\\desktop_bg', help='Directory containing wallpaper images')
    parser.add_argument('--no-tray', action='store_true', help='Disable system tray icon and background mode')
    args = parser.parse_args()

    p, jpgs, path = wallpaper(path=args.wallpaper_dir)

    pygame.init()
    screen = pygame.display.set_mode((350, 350), pygame.NOFRAME)
    pygame.display.set_caption('clock')
    hwnd = pygame.display.get_wm_info()['window']
    set_tool_window(hwnd)
    attach_to_desktop_layer(hwnd)

    background = pygame.image.load(path).convert()
    xx = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    yy = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    now = datetime.datetime.now()
    h_cpy = now.hour

    redraw_event = pygame.USEREVENT + 1
    window_change_events = {
        pygame.WINDOWEXPOSED,
        pygame.WINDOWMOVED,
        pygame.WINDOWSIZECHANGED,
        pygame.WINDOWSHOWN,
        pygame.WINDOWDISPLAYCHANGED,
    }
    pygame.time.set_timer(redraw_event, 50)
    running = True
    needs_fix_window = True
    action_queue = queue.Queue()
    tray = None

    if not args.no_tray:
        tray = TrayIcon('Desktop Clock', action_queue)
        tray.start()

    screen.fill((0, 0, 0, 0))
    draw_hands(screen, now)
    pygame.display.update()

    while running:
        first_event = pygame.event.wait()
        events = [first_event]
        events.extend(pygame.event.get())
        should_redraw = False

        while not action_queue.empty():
            action = action_queue.get_nowait()
            if action == 'show':
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                needs_fix_window = True
            elif action == 'hide':
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            elif action == 'exit':
                running = False
                break

        for event in events:
            if event.type == pygame.QUIT:
                if tray is not None:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                else:
                    running = False
            elif event.type == redraw_event:
                should_redraw = True
            elif event.type in window_change_events:
                should_redraw = True
                needs_fix_window = True

        if not running:
            break

        if not should_redraw:
            continue

        if needs_fix_window:
            current_xx = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            current_yy = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            if current_xx != xx or current_yy != yy:
                xx, yy = current_xx, current_yy
            fix_window(xx, yy)
            needs_fix_window = False

        now = datetime.datetime.now()

        screen.fill((0, 0, 0, 0))
        draw_clock_face(screen)
        hour = draw_hands(screen, now)

        if h_cpy != hour:
            f = choose_wallpaper(jpgs)
            path = os.path.join(p, f)
            set_wallpaper(path)
        h_cpy = hour

        pygame.display.update()

    pygame.time.set_timer(redraw_event, 0)

    if tray is not None:
        tray.stop()

    pygame.quit()


if __name__ == '__main__':
    main()
