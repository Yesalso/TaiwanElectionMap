from PIL import Image

src = Image.open("Colorful.png").convert("RGBA")
for x in range(src.width):
    for y in range(src.height):
        r, g, b, a = src.getpixel((x, y))
        if (r, g, b) == (0, 255, 255):
            src.putpixel((x, y), (0, 0, 0, a))
src.convert("RGB").save("Colorful_black.png")
print("done")