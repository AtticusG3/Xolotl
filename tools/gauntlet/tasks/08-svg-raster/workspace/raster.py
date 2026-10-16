"""Rasterize a filled SVG path.  Implement rasterize(d, width, height, fill_rule) -> list[str].

d: an SVG path string using only these commands (absolute UPPER case, relative lower case):
   M/m x y   move to (starts a new subpath; extra coordinate pairs after it are implicit L/l)
   L/l x y   line to (several pairs allowed)
   H/h x     horizontal line;   V/v y   vertical line
   Z/z       close the subpath (back to its start point; the current point becomes that start point)
   Numbers: ints or decimals, optional sign, separated by spaces and/or commas; a command letter may be followed
   directly by a number ("M10,10L20 10").  Every subpath is closed for filling even without Z.
   Relative commands are relative to the current point (after Z: the subpath's start point).
Coordinates are pixels: x right, y DOWN; pixel (col, row) covers [col, col+1) x [row, row+1).
A pixel is filled iff its CENTRE (col + 0.5, row + 0.5) is inside the shape:
   cast a ray from the centre toward +x; for every edge (x0,y0)->(x1,y1) with (y0 <= cy < y1) or (y1 <= cy < y0)
   compute the crossing x; count it if crossing_x > cx.  Its winding contribution is +1 if y1 > y0 else -1.
   fill_rule "nonzero": inside iff the sum of contributions != 0;  "evenodd": inside iff the crossing count is odd.
Return height strings of width characters: '#' filled, '.' empty.  Unknown commands / bad numbers -> ValueError.
"""


def rasterize(d, width, height, fill_rule="nonzero"):
    raise NotImplementedError
