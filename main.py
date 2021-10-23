import datetime
import math
import os
import random

import pygame
import win32api
import win32con
import win32gui
from PIL import Image
from pygame.locals import *


def set_wallpaper_from_bmp(bmp_path):
    reg_key = win32api.RegOpenKeyEx(win32con.HKEY_CURRENT_USER, "Control Panel\\Desktop", 2, win32con.KEY_SET_VALUE)
    # 2拉伸,0居中,6适应,10填充,0平铺
    win32api.RegSetValueEx(reg_key, "WallpaperStyle", 2, win32con.REG_SZ, "2")
    # 1表示平铺,拉伸居中等都是0
    win32api.RegSetValueEx(reg_key, "TileWallpaper", 0, win32con.REG_SZ, "0")
    win32gui.SystemParametersInfo(win32con.SPI_SETDESKWALLPAPER, bmp_path, win32con.SPIF_SENDWININICHANGE)


def set_wallpaper(img_path):
    # 把图片格式统一转换成bmp格式,并放在源图片的同一目录
    img_dir = os.path.dirname(img_path)
    bmp_image = Image.open(img_path)
    new_bmp_path = os.path.join(img_dir, 'wallpaper\\wallpaper.bmp')
    bmp_image.save(new_bmp_path, "BMP")
    set_wallpaper_from_bmp(new_bmp_path)


def wallpaper():
    p = 'D:\\desktop_bg'
    jpgs = os.listdir(p)
    for f in jpgs:
        if '.jpg' not in f or not os.path.isfile(os.path.join(p, f)):
            jpgs.remove(f)
    f = random.choice(jpgs)
    path = os.path.join(p, f)
    set_wallpaper(path)
    return p, jpgs, path


def fix_window(xx, yy, ing):
    title1 = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    title = win32gui.GetWindowText(win32gui.GetActiveWindow())
    if (title == 'clock' or title1 == 'clock') and ing == 0:
        win32gui.SetWindowPos(pygame.display.get_wm_info()['window'], 1, xx - 380, yy - 430, 0, 0, 0x0001)
        ing += 1
    elif title != 'clock':
        ing = 0
    return ing


def draw(surface):
    now = datetime.datetime.now()
    white = 255, 255, 255
    origin = 175, 175
    pygame.draw.circle(surface, white, origin, 8, 8)
    for i in range(1, 13):
        sita = math.pi * i / 6
        pos = origin[0] + 150 * math.sin(sita), origin[1] - 150 * math.cos(sita)
        pygame.draw.circle(surface, white, pos, 12, 12)

    hour = now.hour
    minute = now.minute
    second = now.second // 1

    s = math.pi * second / 30
    m = math.pi * (minute / 30 + second // 10 / 180)
    h = math.pi * (hour / 6 + minute // 2 / 180)

    terminal_sec = origin[0] + 125 * math.sin(s), origin[1] - 125 * math.cos(s)
    pygame.draw.line(surface, white, origin, terminal_sec, 8)
    terminal_min = origin[0] + 105 * math.sin(m), origin[1] - 105 * math.cos(m)
    pygame.draw.line(surface, white, origin, terminal_min, 10)
    terminal_hour = origin[0] + 75 * math.sin(h), origin[1] - 75 * math.cos(h)
    pygame.draw.line(surface, white, origin, terminal_hour, 12)

    return hour


def main():
    p, jpgs, path = wallpaper()

    pygame.init()
    screen = pygame.display.set_mode((350, 350), NOFRAME)
    pygame.display.set_caption('clock')
    surface = screen.convert_alpha()
    background = pygame.image.load(path)
    xx = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    yy = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    new_png = pygame.transform.scale(background, (xx, yy))
    ing = 0
    now = datetime.datetime.now()
    h_cpy = now.hour

    icon = pygame.transform.scale(surface, (32, 32))
    icon.fill((255, 255, 255, 0))
    pygame.draw.circle(icon, (255, 255, 255), (16, 16), 15, 2)
    pygame.display.set_icon(icon)

    while True:
        for event in pygame.event.get():
            if event.type in (QUIT,):
                break

        ing = fix_window(xx, yy, ing)

        screen.blit(new_png, (380 - xx, 429 - yy))
        surface.fill((255, 255, 255, 0))

        hour = draw(surface)

        if h_cpy != hour:
            f = random.choice(jpgs)
            path = os.path.join(p, f)
            background = pygame.image.load(path)
            new_png = pygame.transform.scale(background, (xx, yy))
            set_wallpaper(path)
        h_cpy = hour

        surface.set_alpha(180)

        screen.blit(surface, (0, 0))
        pygame.display.update()


if __name__ == '__main__':
    main()
