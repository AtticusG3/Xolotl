import json
import os

import pytest

from raster import rasterize
from shapes import SHAPES

REF = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_rasters.json")))


@pytest.mark.parametrize("name,d,w,h,rule", SHAPES)
def test_shape(name, d, w, h, rule):
    got = rasterize(d, w, h, rule)
    want = REF[name]
    if got != want:
        diff = sum(a != b for ga, wa in zip(got, want) for a, b in zip(ga, wa))
        pytest.fail(f"{name}: {diff} pixels differ\n" + "\n".join(got) + "\n--- want ---\n" + "\n".join(want))


@pytest.mark.parametrize("bad", ["M1 1 Q2 2 3 3", "M1 1 L2", "L1 x", "1 2 3"])
def test_malformed(bad):
    with pytest.raises(ValueError):
        rasterize(bad, 8, 8)
