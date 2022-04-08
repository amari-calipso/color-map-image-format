import pygame, sys, math
from bitarray import bitarray

MAX_INDEX_BITS = 7

def limitToRange(variable, min_, max_):
    if variable < min_: return min_
    if variable > max_: return max_
    return variable

def __setpx(surf : pygame.Surface, at, error, q):
    px = surf.get_at(at)

    surf.set_at(at, (
        limitToRange(int(px[0] + q * error[0]), 0, 255),
        limitToRange(int(px[1] + q * error[1]), 0, 255),
        limitToRange(int(px[2] + q * error[2]), 0, 255)
    ))

def __indexToXY(index, sizeX):
    y = index // sizeX
    return (index - y * sizeX, y)

def grayScale(surf : pygame.Surface):
    print("Applying grayscale...")
    size = surf.get_size()

    for y in range(size[1] - 1):
        for x in range(1, size[0] - 1):
            px = surf.get_at((x, y))
            c = round(0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2])
            surf.set_at((x, y), (c, c, c))

def dither(surf : pygame.Surface, variety = 4):
    print(f"Applying dithering ({variety} levels)...")

    variety -= 1

    n = variety / 255
    m = 255 / variety

    size = surf.get_size()

    for y in range(size[1] - 1):
        for x in range(1, size[0] - 1):
            px = surf.get_at((x, y))

            c = (
                round(px[0] * n) * m,
                round(px[1] * n) * m,
                round(px[2] * n) * m
            )

            error = (
                px[0] - c[0],
                px[1] - c[1],
                px[2] - c[2]
            )

            surf.set_at((x, y), c)

            __setpx(surf, (x + 1,     y), error, 0.4375)
            __setpx(surf, (x - 1, y + 1), error, 0.1875)
            __setpx(surf, (    x, y + 1), error, 0.3125)
            __setpx(surf, (x + 1, y + 1), error, 0.0625)

class CMIFRange:
    def __init__(self, a):
        self.a = a
        self.b = None

class CMIFImage:
    def __init__(self, resolution, image, bg):
        self.resolution = resolution
        self.image      = image
        self.bg         = bg

def convert(surf : pygame.Surface):
    print("Mapping colors...")

    size  = surf.get_size()
    sizeX = size[0]
    size  = sizeX * size[1]
    image = {}

    i = 0
    while i < size:
        px = surf.get_at(__indexToXY(i, sizeX))
        tPx = (px[0], px[1], px[2])

        if i + 1 == size: pxRight = None
        else: pxRight = surf.get_at(__indexToXY(i + 1, sizeX))

        if tPx in image:
            if px == pxRight:
                image[tPx].append(CMIFRange(i))
            else:
                image[tPx].append(i)
                i += 1
                continue
        else:
            if px == pxRight:
                image[tPx] = [CMIFRange(i)]
            else:
                image[tPx] = [i]
                i += 1
                continue

        while True:
            i += 1
            if i == size: break

            pxRight = surf.get_at(__indexToXY(i, sizeX))

            if pxRight != px: break

        image[tPx][-1].b = i
        continue

    print("Optimizing...")
    max_ = 0
    c = (0, 0, 0)
    for color in image:
        if len(image[color]) > max_:
            max_ = len(image[color])
            c = color

    del image[c]

    return image, c

def decimalToBinary(n, bits):
    return bin(n)[2:].zfill(bits)

def encode(image : CMIFImage):
    print("Encoding...")

    data = decimalToBinary(image.bg[0], 8)
    data += decimalToBinary(image.bg[1], 8)
    data += decimalToBinary(image.bg[2], 8)

    size = math.ceil(math.log2(image.resolution[0] * image.resolution[1]))
    data += decimalToBinary(size, MAX_INDEX_BITS)

    data += decimalToBinary(image.resolution[0], size)
    data += decimalToBinary(image.resolution[1], size)

    for color in image.image:
        data += decimalToBinary(color[0], 8)
        data += decimalToBinary(color[1], 8)
        data += decimalToBinary(color[2], 8)

        idx = len(image.image[color]) - 1

        for i in range(idx):
            tmp = image.image[color][i]

            if isinstance(tmp, CMIFRange):
                data += "01" # 01 -> not end of color group | next data is a range

                data += decimalToBinary(tmp.a, size)
                data += decimalToBinary(tmp.b, size)
            else:
                data += "00" # 00 -> not end of color group | next data is not a range

                data += decimalToBinary(tmp, size)

        tmp = image.image[color][idx]
        if isinstance(tmp, CMIFRange):
            data += "11" # 11 -> end of color group | next data is a range

            data += decimalToBinary(tmp.a, size)
            data += decimalToBinary(tmp.b, size)
        else:
            data += "10" # 10 -> end of color group | next data is not a range

            data += decimalToBinary(tmp, size)

    return bitarray(data)

def decode(data : bitarray):
    print("Decoding...")

    data = data.to01()[:-2]

    bg = (
        int(data[:8], 2),
        int(data[8:16], 2),
        int(data[16:24], 2)
    )

    ptr = 24 + MAX_INDEX_BITS
    size = int(data[24:ptr], 2)

    resX = int(data[ptr:ptr + size], 2)
    ptr += size
    resY = int(data[ptr:ptr + size], 2)
    ptr += size

    image = {}
    while ptr < len(data):
        cr = int(data[ptr:ptr + 8], 2)
        ptr += 8
        cg = int(data[ptr:ptr + 8], 2)
        ptr += 8
        cb = int(data[ptr:ptr + 8], 2)
        ptr += 8

        color = (cr, cg, cb)

        end = data[ptr]
        ptr += 1
        rg  = data[ptr]
        ptr += 1

        if rg == "0":
            image[color] = [int(data[ptr:ptr + size], 2)]
        else:
            r = CMIFRange(int(data[ptr:ptr + size], 2))
            ptr += size
            r.b = int(data[ptr:ptr + size], 2)

            image[color] = [r]

        ptr += size

        if end == "1": continue

        while ptr < len(data):
            end = data[ptr]
            ptr += 1
            rg  = data[ptr]
            ptr += 1

            if rg == "0":
                image[color].append(int(data[ptr:ptr + size], 2))
            else:
                r = CMIFRange(int(data[ptr:ptr + size], 2))
                ptr += size
                r.b = int(data[ptr:ptr + size], 2)

                image[color].append(r)

            ptr += size

            if end == "1": break

    return CMIFImage((resX, resY), image, bg)

screenCounter = 1
def __update(surf, scale, screen, visualize, sTime):
    global screenCounter

    if visualize and screenCounter == sTime:
        screenCounter = 0

        pygame.transform.scale(surf, scale, screen)
        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit()
    screenCounter += 1

def display(screen : pygame.Surface, surf : pygame.Surface, scaleTo, image : CMIFImage, visualize = False, speed = 1):
    print("Writing image to screen buffer...", end = "", flush = True)

    for color in image.image:
        for pos in image.image[color]:
            if isinstance(pos, CMIFRange):
                for i in range(pos.a, pos.b):
                    surf.set_at(__indexToXY(i, image.resolution[0]), color)

                __update(surf, scaleTo, screen, visualize, speed)
            else:
                surf.set_at(__indexToXY(pos, image.resolution[0]), color)

                __update(surf, scaleTo, screen, visualize, speed)

    print("Done")
    pygame.transform.scale(surf, scaleTo, screen)
    pygame.display.update()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Color Map Image Format utility v2022.4.8 - thatsOven")
    elif sys.argv[1] == "convert":
        if "--dither" in sys.argv:
            idx = sys.argv.index("--dither")
            sys.argv.pop(idx)
            dithering = int(sys.argv.pop(idx))

            if dithering < 2 or dithering > 256:
                print("invalid dither factor")
                quit()
        else: dithering = None

        if "--grayscale" in sys.argv:
            bw = True
            sys.argv.remove("--grayscale")
        else: bw = False

        if len(sys.argv) == 2:
            print('input file required for command "convert"')
            sys.exit(1)

        imported = pygame.image.load(sys.argv[2])

        if bw: grayScale(imported)

        if dithering is not None:
            dither(imported, dithering)

        c, bg = convert(imported)
        data = encode(CMIFImage(imported.get_size(), c, bg))

        if len(sys.argv) == 3:
            fileName = "output.cmif"
        else:
            fileName = sys.argv[3].replace("\\", "\\\\")

        print("Writing file...")
        with open(fileName, "wb") as f:
            data.tofile(f)

    elif sys.argv[1] == "display":
        if "--animate" in sys.argv:
            animate = True
            sys.argv.remove("--animate")
        else: animate = False

        if "--scale" in sys.argv:
            idx = sys.argv.index("--scale")
            sys.argv.pop(idx)
            scale = float(sys.argv.pop(idx))
        else: scale = 1

        if "--speed" in sys.argv:
            idx = sys.argv.index("--speed")
            sys.argv.pop(idx)
            speed = int(sys.argv.pop(idx))
        else: speed = 1

        if len(sys.argv) == 2:
            print('input file required for command "display"')
            sys.exit(1)

        print("Loading image...")
        data : bitarray = bitarray()
        with open(sys.argv[2], "rb") as f:
            data.fromfile(f)

        img = decode(data)
        res = (int(img.resolution[0] * scale), int(img.resolution[1] * scale))

        pygame.init()
        screen = pygame.display.set_mode(res)

        surf = pygame.Surface(img.resolution)
        surf.fill(img.bg)
        display(screen, surf, res, img, animate, speed)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit()
