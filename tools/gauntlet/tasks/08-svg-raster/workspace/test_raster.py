from raster import rasterize


def test_square():
    img = rasterize("M1 1 H4 V3 H1 Z", 5, 4)
    assert img == [".....", ".###.", ".###.", "....."]
