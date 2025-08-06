from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import os

# Параметры колеса
W, H = 600, 600
CENTER = (W // 2, H // 2)
RADIUS = 250
SECTORS = [
    "2 дня PRO аккаунта",
    "10 Мутов",
    "3 дня Армора",
    "7 дней Армора",
    "3 дня Бонуса",
    "7 дней Бонуса",
    "Бесплатный CS",
    "10 голды",
    "100 голды",
    "1000 голды",
    "1-месячный титул чемпиона"  # редкий сектор
]
COLORS = [
    "#FFB300", "#FF7043", "#AB47BC", "#29B6F6", "#66BB6A",
    "#EC407A", "#FFA726", "#8D6E63", "#789262", "#D4E157", "#FFD700"
]
FONT_PATH = "arial.ttf"  # путь к вашему шрифту
FONT_SIZE = 22


def draw_glassmorphism_bg():
    # Фон с градиентом и размытием
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for y in range(H):
        r = int(40 + 80 * (y / H))
        g = int(60 + 100 * (y / H))
        b = int(120 + 100 * (y / H))
        grad_draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
    bg = Image.alpha_composite(bg, grad)
    # Круглый размытый светлый эллипс
    ellipse = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ell_draw = ImageDraw.Draw(ellipse)
    ell_draw.ellipse([CENTER[0]-180, CENTER[1]-180, CENTER[0]+180, CENTER[1]+180], fill=(255,255,255,60))
    from PIL import ImageFilter
    ellipse = ellipse.filter(ImageFilter.GaussianBlur(30))
    bg = Image.alpha_composite(bg, ellipse)
    return bg

def draw_wheel(angle, highlight_index=None):
    # Фон glassmorphism
    img = draw_glassmorphism_bg()
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        font_bold = ImageFont.truetype(FONT_PATH, FONT_SIZE+4)
    except:
        font = ImageFont.load_default()
        font_bold = font
    n = len(SECTORS)
    # Стеклянная подложка
    glass = Image.new("RGBA", (W, H), (255,255,255,0))
    glass_draw = ImageDraw.Draw(glass)
    glass_draw.ellipse([CENTER[0]-RADIUS-18, CENTER[1]-RADIUS-18, CENTER[0]+RADIUS+18, CENTER[1]+RADIUS+18], fill=(255,255,255,60))
    glass = glass.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, glass)
    # Колесо
    wheel = Image.new("RGBA", (W, H), (0,0,0,0))
    wheel_draw = ImageDraw.Draw(wheel)
    start_angle = angle
    for i, label in enumerate(SECTORS):
        end_angle = start_angle + 360 / n
        color = COLORS[i % len(COLORS)]
        if i == 10:
            color = "#FFD700"
        # Сектор с прозрачностью
        wheel_draw.pieslice(
            [CENTER[0] - RADIUS, CENTER[1] - RADIUS, CENTER[0] + RADIUS, CENTER[1] + RADIUS],
            start=start_angle, end=end_angle, fill=color+"80", outline="#FFFFFF80", width=4
        )
        # Текст БЕЗ glow
        theta = math.radians((start_angle + end_angle) / 2)
        tx = CENTER[0] + int(math.cos(theta) * (RADIUS * 0.7))
        ty = CENTER[1] + int(math.sin(theta) * (RADIUS * 0.7))
        text = label
        wheel_draw.text((tx, ty), text, font=font_bold, fill=(255,255,255,220), anchor="mm")
        start_angle = end_angle
    img = Image.alpha_composite(img, wheel)
    # Блик
    highlight = Image.new("RGBA", (W, H), (0,0,0,0))
    hdraw = ImageDraw.Draw(highlight)
    hdraw.ellipse([CENTER[0]-RADIUS+40, CENTER[1]-RADIUS+40, CENTER[0]+RADIUS-40, CENTER[1]-RADIUS+80], fill=(255,255,255,40))
    highlight = highlight.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, highlight)
    # Указатель (стеклянный)
    pointer = Image.new("RGBA", (W, H), (0,0,0,0))
    pdraw = ImageDraw.Draw(pointer)
    pdraw.polygon([(CENTER[0], CENTER[1]-RADIUS-28), (CENTER[0]-22, CENTER[1]-RADIUS+18), (CENTER[0]+22, CENTER[1]-RADIUS+18)], fill=(255,255,255,180), outline=(0,0,0,60))
    pointer = pointer.filter(ImageFilter.GaussianBlur(1))
    img = Image.alpha_composite(img, pointer)
    # Обводка выбранного сектора
    if highlight_index is not None:
        a0 = angle + 360 / n * highlight_index
        a1 = a0 + 360 / n
        sel = Image.new("RGBA", (W, H), (0,0,0,0))
        seldraw = ImageDraw.Draw(sel)
        seldraw.pieslice(
            [CENTER[0] - RADIUS-8, CENTER[1] - RADIUS-8, CENTER[0] + RADIUS+8, CENTER[1] + RADIUS+8],
            start=a0, end=a1, fill=None, outline=(255,255,255,200), width=10
        )
        sel = sel.filter(ImageFilter.GaussianBlur(2))
        img = Image.alpha_composite(img, sel)
    return img


def make_glassmorphism_spin_gif(stop_index=0, frames=60, out_path="wheel_spin.gif"):
    """
    out_path: может быть либо str (путь к файлу), либо BytesIO
    """
    from PIL import ImageSequence
    imgs = []
    n = len(SECTORS)
    # Количество кадров и длительность кадра для 6 секунд
    frames = 60
    duration = 100  # мс на кадр (60*100=6000мс=6сек)
    # Чтобы приз был под верхней стрелкой (270°), считаем нужный угол
    # Сектор 0 должен совпасть с 270° (верх)
    # Т.е. в конце анимации угол = 270 - (360/n)*stop_index
    final_angle = 270 - (360 / n) * stop_index
    # Анимация: крутим несколько оборотов и плавно останавливаемся на final_angle
    total_rot = 5  # оборотов
    for i in range(frames):
        t = i / (frames-1)
        ease = 1 - (1-t)**3
        angle = 360 * total_rot * ease + final_angle
        angle = angle % 360
        img = draw_wheel(angle, highlight_index=stop_index if i == frames-1 else None)
        imgs.append(img)
    save_kwargs = dict(save_all=True, append_images=imgs[1:], duration=duration, loop=1, disposal=2)
    if hasattr(out_path, 'write'):
        imgs[0].save(out_path, format="GIF", **save_kwargs)
        out_path.seek(0)
        print(f"GIF saved to BytesIO")
    else:
        imgs[0].save(out_path, **save_kwargs)
        print(f"GIF saved to {out_path}")

# Пример: создать анимацию, где колесо останавливается на 1-м секторе
if __name__ == "__main__":
    make_glassmorphism_spin_gif(stop_index=0, frames=60, out_path="wheel_spin.gif")
    # Для других призов: stop_index=1,2,...,10
