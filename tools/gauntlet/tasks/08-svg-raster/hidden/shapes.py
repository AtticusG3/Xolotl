SHAPES = [
    ("star_nonzero", "M16 2 L25 30 L2 12 L30 12 L7 30 Z", 32, 32, "nonzero"),
    ("star_evenodd", "M16 2 L25 30 L2 12 L30 12 L7 30 Z", 32, 32, "evenodd"),
    ("donut_same_dir_nonzero", "M2 2 H30 V30 H2 Z M10 10 H22 V22 H10 Z", 32, 32, "nonzero"),
    ("donut_opposite_nonzero", "M2 2 H30 V30 H2 Z M10 10 V22 H22 V10 Z", 32, 32, "nonzero"),
    ("donut_same_dir_evenodd", "M2 2 H30 V30 H2 Z M10 10 H22 V22 H10 Z", 32, 32, "evenodd"),
    ("relative_arrow", "m4,14 l12,-10 v6 h12 v8 h-12 v6 z", 32, 32, "nonzero"),
    ("implicit_lineto_unclosed", "M3.5 3.5 28.25 6 20 28.75", 32, 32, "nonzero"),
    ("two_subpaths_relative_after_z", "M2 2 h6 v6 h-6 z m10 10 h8 v8 h-8 z", 32, 32, "nonzero"),
    ("self_overlap_twice", "M4 4 H28 V28 H4 Z M4 4 H28 V28 H4 Z", 32, 32, "evenodd"),
    ("compact_numbers", "M1,1L31,1L16,31Z M16,8L23-0.5", 32, 32, "nonzero"),
]
