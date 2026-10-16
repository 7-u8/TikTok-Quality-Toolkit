"""Draw the app icon (icon.png + icon.ico) with Pillow."""

import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 512


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # diagonal gradient pink -> cyan in a rounded square
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    a, b = (255, 45, 110), (20, 205, 230)
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S - 2)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # motion lines (smoothness)
    for i, y in enumerate((170, 256, 342)):
        d.rounded_rectangle((70 + i * 6, y - 13, 190 - i * 18, y + 13), radius=13, fill=(255, 255, 255, 150))
    # play triangle with a soft shadow
    tri = [(205, 140), (205, 372), (405, 256)]
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 8, y + 10) for x, y in tri], fill=(0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    d.polygon(tri, fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    icon = draw()
    icon.save(os.path.join(HERE, "icon.png"))
    icon.save(os.path.join(HERE, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.png / icon.ico written")
