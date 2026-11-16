"""Build the Aventador LP 700-4 anatomy model in Blender.

Run:  blender -b -P blender/build_aventador.py [-- --render <dir>]
Writes blender/aventador.blend, public/models/aventador.glb and src/aventador-parts.json.

Geometry is authored in app coordinates (metres, x right, y up, z forward, ground y=0,
axle midpoint z=0) and converted to Blender's Z-up / -Y-forward on the way in, so the
glTF export (+Y up) lands back in app coordinates.

Real figures used (Lamborghini press data): length 4780, width 2030, height 1136, wheelbase 2700,
track 1720/1700 mm, tyres 255/35 R19 and 335/30 R20, carbon-ceramic discs 400/380 mm,
60° V12 6498 cc, bore 95 x stroke 76.4 mm, dry sump, 7-speed ISR ahead of the engine,
Haldex front coupling, pushrod suspension with inboard horizontal dampers,
carbon monocoque with aluminium front and rear frames.
Everything else (part shapes, internal packaging, rod length, pipe routes) is a reconstruction.
"""
import bpy, bmesh, math, json, os, sys
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = ARGS[ARGS.index('--render') + 1] if '--render' in ARGS else None

bpy.ops.wm.read_factory_settings(use_empty=True)
TAU = 2 * math.pi
C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # app -> blender (proper rotation)

# ---------------------------------------------------------------- geometry (app coords)
class G:
    def __init__(s, v=None, f=None):
        s.v = list(v or []); s.f = list(f or [])
    def add(s, *others):
        for o in others:
            n = len(s.v); s.v += o.v; s.f += [tuple(i + n for i in f) for f in o.f]
        return s
    def xf(s, M=None, t=(0, 0, 0)):
        M = M or Matrix.Identity(3); T = Vector(t)
        s.v = [tuple(M @ Vector(p) + T) for p in s.v]; return s
    def mv(s, *t): return s.xf(None, t[0] if len(t) == 1 else t)
    def scale(s, sx, sy, sz): s.v = [(x * sx, y * sy, z * sz) for x, y, z in s.v]; return s

def join(*gs): return G().add(*gs)
def rot_y_to(axis):
    return Vector((0, 1, 0)).rotation_difference(Vector(axis).normalized()).to_matrix()
def rot(axis, ang): return Matrix.Rotation(ang, 3, Vector(axis))

def box(sx, sy, sz, c=(0, 0, 0)):
    x, y, z = sx / 2, sy / 2, sz / 2
    v = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return G(v, f).mv(c)

def lathe(prof, n=24, axis=(0, 1, 0), c=(0, 0, 0), closed=False, cap=True):
    """Revolve (radius, height) points around +y, then orient +y to `axis`."""
    v, f = [], []
    for r, t in prof:
        for k in range(n):
            a = TAU * k / n; v.append((r * math.cos(a), t, r * math.sin(a)))
    m = len(prof)
    rows = m if closed else m - 1
    for i in range(rows):
        j = (i + 1) % m
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            f.append((a, b, j * n + (k + 1) % n, j * n + k))
    if cap and not closed:
        f.append(tuple(range(n))[::-1]); f.append(tuple(range((m - 1) * n, m * n)))
    return G(v, f).xf(rot_y_to(axis), c)

def cyl(r, h, axis=(0, 1, 0), c=(0, 0, 0), n=20, r2=None):
    return lathe([(r, -h / 2), (r if r2 is None else r2, h / 2)], n, axis, c)

def ring(r0, r1, h, axis=(0, 1, 0), c=(0, 0, 0), n=24):
    """Annulus (washer / bearing / disc) of thickness h."""
    return lathe([(r0, -h / 2), (r1, -h / 2), (r1, h / 2), (r0, h / 2)], n, axis, c, closed=True)

def sphere(r, c=(0, 0, 0), n=16):
    prof = [(max(1e-4, r * math.sin(math.pi * i / 8)), -r * math.cos(math.pi * i / 8)) for i in range(9)]
    return lathe(prof, n, (0, 1, 0), c)

def prism(poly, d, M=None, c=(0, 0, 0)):
    """Extrude a 2D polygon (local x,y, counter-clockwise) along local z by d (centred)."""
    n = len(poly)
    v = [(x, y, -d / 2) for x, y in poly] + [(x, y, d / 2) for x, y in poly]
    f = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return G(v, f).xf(M, c)

def hull(points):
    bm = bmesh.new()
    for p in points: bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    used = [v for v in bm.verts if v.link_faces]
    idx = {v: i for i, v in enumerate(used)}
    g = G([tuple(v.co) for v in used], [tuple(idx[v] for v in fc.verts) for fc in bm.faces])
    bm.free(); return g

def catmull(P, seg=6):
    if len(P) < 3: return P
    out = []
    Q = [P[0]] + P + [P[-1]]
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for s in range(seg):
            t = s / seg; t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1]); return out

def tube(pts, r, n=12, seg=6, smooth=True):
    P = [Vector(p) for p in pts]
    if smooth: P = catmull(P, seg)
    P = [p for i, p in enumerate(P) if i == 0 or (p - P[i - 1]).length > 1e-6]
    T = [(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized() for i in range(len(P))]
    up = Vector((0, 1, 0)) if abs(T[0].y) < .9 else Vector((1, 0, 0))
    N = T[0].cross(up).normalized()
    v, f = [], []
    for i, p in enumerate(P):
        if i:
            ax = T[i - 1].cross(T[i])
            if ax.length > 1e-9: N = Matrix.Rotation(T[i - 1].angle(T[i]), 3, ax.normalized()) @ N
        B = T[i].cross(N)
        for k in range(n):
            a = TAU * k / n; v.append(tuple(p + N * (r * math.cos(a)) + B * (r * math.sin(a))))
    m = len(P)
    for i in range(m - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            f.append((a, b, b + n, a + n))
    f.append(tuple(range(n))[::-1]); f.append(tuple(range((m - 1) * n, m * n)))
    return G(v, f)

def helix(r, wire, length, turns, axis=(1, 0, 0), c=(0, 0, 0)):
    pts = [(r * math.cos(TAU * turns * i / (turns * 16)), length * i / (turns * 16) - length / 2, r * math.sin(TAU * turns * i / (turns * 16))) for i in range(int(turns * 16) + 1)]
    return tube(pts, wire, 8, smooth=False).xf(rot_y_to(axis), c)

def sector(r0, r1, a0, a1, h, n=10):
    """Annular sector around +y (angles in the x-z plane), thickness h along y."""
    pts = [(r0 * math.cos(a0 + (a1 - a0) * i / n), r0 * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    pts += [(r1 * math.cos(a1 - (a1 - a0) * i / n), r1 * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
    g = prism(pts[::-1], h)  # local xy plane, extruded along local z
    return g.xf(Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))))  # local z -> y

def bellows(r0, r1, length, folds, axis, c):
    prof = []
    for i in range(folds * 2 + 1):
        t = i / (folds * 2); r = r0 + (r1 - r0) * t
        prof.append((r * (1.18 if i % 2 else 1), length * t - length / 2))
    return lathe(prof, 16, axis, c)

# ---------------------------------------------------------------- materials
MATS = {
    'paint':   ((((212 / 255 + .055) / 1.055) ** 2.4, 0, 0, 1), 0.2, 0.25, 'paint'),  # Rosso Mars #D40000 (sRGB -> linear)
    'carbon':  ((0.03, 0.03, 0.035, 1), 0.1, 0.35, 'dark'),
    'plastic': ((0.05, 0.05, 0.05, 1), 0.0, 0.6, 'dark'),
    'glass':   ((0.55, 0.65, 0.68, 0.3), 0.0, 0.05, 'glass'),
    'lens':    ((0.9, 0.92, 0.95, 0.5), 0.0, 0.05, 'glass'),
    'redlens': ((0.6, 0.02, 0.02, 0.7), 0.0, 0.1, 'dark'),
    'alu':     ((0.75, 0.76, 0.78, 1), 0.9, 0.35, 'metal'),
    'cast':    ((0.55, 0.56, 0.57, 1), 0.8, 0.55, 'metal'),
    'steel':   ((0.45, 0.46, 0.48, 1), 0.95, 0.3, 'metal'),
    'chrome':  ((0.9, 0.9, 0.9, 1), 1.0, 0.08, 'metal'),
    'titanium':((0.5, 0.48, 0.45, 1), 0.9, 0.4, 'metal'),
    'ceramic': ((0.22, 0.22, 0.23, 1), 0.3, 0.6, 'dark'),
    'caliper': ((0.95, 0.75, 0.05, 1), 0.3, 0.3, 'accent'),
    'rubber':  ((0.03, 0.03, 0.03, 1), 0.0, 0.9, 'rubber'),
    'leather': ((0.08, 0.07, 0.07, 1), 0.0, 0.55, 'dark'),
    'copper':  ((0.75, 0.45, 0.25, 1), 1.0, 0.35, 'metal'),
    'red':     ((0.7, 0.05, 0.03, 1), 0.2, 0.4, 'accent'),
}
_mat = {}
def material(key):
    if key in _mat: return _mat[key]
    col, metal, rough, _ = MATS[key]
    m = bpy.data.materials.new(key); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = col
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if col[3] < 1:
        b.inputs['Alpha'].default_value = col[3]
        try: m.surface_render_method = 'BLENDED'
        except Exception: pass
    m.diffuse_color = col; m.use_backface_culling = False
    _mat[key] = m; return m

# ---------------------------------------------------------------- scene hierarchy and part registry
SYSTEMS = {
    '01_Exterior_Body': 'Body panels, glass, lamps and the hinged covers.',
    '02_Chassis_Monocoque': 'Carbon-fibre passenger cell with bolted aluminium front and rear frames.',
    '03_Powertrain': 'L539 V12, its ancillaries, the ISR transmission and the all-wheel-drive driveline.',
    '04_Suspension_Brakes': 'Pushrod double wishbones, inboard dampers, steering, brakes and wheels.',
    '05_Aero_Underbody': 'Splitter, flat floor, diffuser, arch liners and heat shields.',
    '06_Interior': 'Cockpit: seats, steering wheel, dashboard and controls.',
    '07_Electrical': 'Battery, control units and main cabling.',
}
ROOT_EMPTY = bpy.data.objects.new('Aventador_LP700_4', None); bpy.context.scene.collection.objects.link(ROOT_EMPTY)
_coll, _empty = {}, {}
def group(system, assembly):
    key = f'{system}/{assembly}'
    if key in _coll: return _coll[key], _empty[key]
    if system not in _coll:
        c = bpy.data.collections.new(system); bpy.context.scene.collection.children.link(c)
        e = bpy.data.objects.new(system, None); c.objects.link(e); e.parent = ROOT_EMPTY
        _coll[system], _empty[system] = c, e
    c = bpy.data.collections.new(assembly); _coll[system].children.link(c)
    e = bpy.data.objects.new(assembly, None); c.objects.link(e); e.parent = _empty[system]
    _coll[key], _empty[key] = c, e
    return c, e

PARTS, IDS = [], set()
CTX = {}  # current system / assembly / zone defaults
def ctx(system, assembly, zone, **defaults):
    CTX.clear(); CTX.update(system=system, assembly=assembly, zone=zone, **defaults)

def part(pid, name, g, mat, summary, *, pivot=(0, 0, 0), local=False, q=None, zone=None, vector=None,
         blocked=None, kin=None, spec=None, open_surface=False):
    """Create one object. g is in world app coords (or local to pivot when local=True, rotated by q)."""
    assert pid not in IDS, pid
    assert pid.replace('_', '').isalnum(), pid
    IDS.add(pid)
    coll, empty = group(CTX['system'], CTX['assembly'])
    piv = Vector(pivot)
    verts = [tuple(C @ (Vector(p) if local else Vector(p) - piv)) for p in g.v]
    me = bpy.data.meshes.new(pid); me.from_pydata(verts, [], g.f); me.validate(clean_customdata=False)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    if not open_surface: bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    me.shade_smooth(); me.set_sharp_from_angle(angle=math.radians(32))
    me.materials.append(material(mat))
    ob = bpy.data.objects.new(pid, me); coll.objects.link(ob); ob.parent = empty
    R = (C @ (q.to_matrix() if q else Matrix.Identity(3)) @ C.inverted())
    ob.matrix_world = Matrix.Translation(C @ piv) @ R.to_4x4()
    ob['part_id'] = pid
    centre = sum((Vector(p) if not local else (q.to_matrix() if q else Matrix.Identity(3)) @ Vector(p) + piv for p in g.v), Vector()) / max(1, len(g.v))
    v = vector if vector is not None else CTX.get('vector') or [round(centre.x * .6, 3), 0.8, round(centre.z * .3, 3)]
    PARTS.append({
        'id': pid, 'name': name, 'zone': zone or CTX['zone'], 'system': CTX['system'], 'assembly': CTX['assembly'],
        'summary': summary, 'material': CTX.get('matname', {}).get(mat, MAT_NAMES.get(mat, mat)),
        'tone': MATS[mat][3], 'blockedBy': list(blocked if blocked is not None else CTX.get('blocked', [])),
        'vector': [round(x, 3) for x in v], **({'kin': kin} if kin else {}), **({'spec': spec} if spec else {}),
    })
    return ob

MAT_NAMES = {'paint': 'Painted composite / aluminium panel', 'carbon': 'Carbon-fibre reinforced polymer', 'plastic': 'Engineering polymer',
             'glass': 'Laminated / tempered glass', 'lens': 'Polycarbonate lens', 'redlens': 'Tinted polycarbonate lens', 'alu': 'Aluminium alloy',
             'cast': 'Cast aluminium alloy', 'steel': 'Steel', 'chrome': 'Polished steel', 'titanium': 'Heat-resistant alloy',
             'ceramic': 'Carbon-ceramic (CCB)', 'caliper': 'Aluminium monobloc, painted', 'rubber': 'Rubber compound', 'leather': 'Leather / Alcantara',
             'copper': 'Copper alloy', 'red': 'Painted alloy'}

# ---------------------------------------------------------------- key dimensions
FA, RA = 1.35, -1.35                         # axle z (wheelbase 2.70 m)
FT, RT = 1.72 / 2, 1.70 / 2                  # half tracks
FR, RR = 0.0254 * 19 / 2 + .255 * .35, 0.0254 * 20 / 2 + .335 * .30   # tyre radii .331 / .355
FW, RW = .255, .335                          # tyre widths
CY = 0.32                                    # crank axis height
BANK = math.radians(30)                      # each bank 30° from vertical (60° V)
BORE, STROKE, ROD = .095, .0764, .145
CR = STROKE / 2
DECK = CR + ROD + .032                       # crank axis to deck face along the bank
PIN_Z = [-.66 - .1 * i for i in range(6)]    # crank throws (gearbox side first)
THROW = [0, 240, 120, 120, 240, 0]           # throw angles, degrees
CYL_OFF = .013                               # bank A rods sit ahead of bank B on each pin
ENG_Z0, ENG_Z1 = -.59, -1.22                 # block faces

def bank_axes(s):
    """Unit bank axis b (cylinder axis, outward-up) and p (across the bank, outward) for side s=+1 (A) / -1 (B)."""
    b = Vector((s * math.sin(BANK), math.cos(BANK), 0)); p = Vector((s * math.cos(BANK), -math.sin(BANK), 0))
    return b, p
def on_bank(s, along, across, z):
    b, p = bank_axes(s); return Vector((0, CY, z)) + b * along + p * across
def bank_frame(s):
    """Rotation mapping local (x across, y along bank, z along crank) to world."""
    b, p = bank_axes(s); return Matrix((p, b, (0, 0, 1))).transposed()

# ================================================================= 01 EXTERIOR BODY
# Lofted shell: faceted cross-sections keyed along z (see src geometry notes in README).
# z, roofY, roofHalfW, beltHalfW, beltY, shoulderHalfW, shoulderY, sideHalfW, sideY, sillHalfW, sillY
K = [
    [-2.34, .86, .45, .70, .84, .92, .80, .96, .52, .92, .22],
    [-2.10, .90, .50, .78, .87, .98, .84, 1.00, .55, .97, .16],
    [-1.85, .97, .55, .80, .90, 1.00, .88, 1.015, .56, .99, .13],
    [-1.35, 1.04, .55, .80, .92, 1.00, .91, 1.015, .56, 1.0, .13],
    [-1.00, 1.08, .55, .82, .91, 1.00, .90, 1.015, .56, .99, .12],
    [-0.53, 1.115, .56, .86, .89, .99, .88, 1.01, .56, .99, .12],
    [-0.20, 1.136, .58, .84, .87, .97, .86, 1.00, .54, .97, .12],
    [0.10, 1.12, .58, .82, .85, .95, .85, .98, .54, .96, .12],
    [0.55, .97, .58, .74, .81, .93, .83, .97, .54, .96, .12],
    [0.95, .80, .55, .60, .78, .94, .80, .99, .52, .97, .13],
    [1.35, .72, .30, .52, .71, .96, .77, 1.0, .50, .98, .14],
    [1.80, .64, .20, .50, .63, .96, .70, .99, .44, .97, .14],
    [2.10, .55, .15, .45, .54, .92, .58, .96, .36, .93, .13],
    [2.30, .45, .10, .35, .44, .70, .42, .78, .28, .76, .12],
    [2.44, .36, .05, .20, .35, .30, .32, .34, .22, .32, .14],
]
ARCHES = [(FA, FR, FR + .04), (RA, RR, RR + .045)]   # z, centre y, radius
ARCH_X, STEP = .66, .025

def station(z):
    n = len(K); i = 0
    while i < n - 2 and z > K[i + 1][0]: i += 1
    a, b = K[i], K[i + 1]; h = b[0] - a[0]; t = min(1, max(0, (z - a[0]) / h)); t2, t3 = t * t, t * t * t
    def m(j, f):
        p, q = K[max(0, j - 1)], K[min(n - 1, j + 1)]; return (q[f] - p[f]) / (q[0] - p[0])
    return [(2 * t3 - 3 * t2 + 1) * a[f] + (t3 - 2 * t2 + t) * h * m(i, f) + (3 * t2 - 2 * t3) * b[f] + (t3 - t2) * h * m(i + 1, f) for f in range(len(a))]

def point(u, z):
    _, ry, rw, bw, by, sw, sy, mw, my, lw, ly = station(z)
    c = [(0, ry), (rw, ry - .02), (bw, by), (sw, sy), (mw, my), (lw, ly)]
    i = min(4, int(math.floor(u))); f = u - i
    x = c[i][0] + (c[i + 1][0] - c[i][0]) * f; y = c[i][1] + (c[i + 1][1] - c[i][1]) * f
    for w, cy, R in ARCHES:
        d = z - w
        if x > ARCH_X and abs(d) < R: y = max(y, cy + math.sqrt(R * R - d * d))
    return x, y

def surf(u, z, side, lift=0.0):
    x, y = point(u, z)
    if lift:
        a, b = point(max(0, u - .01), z), point(min(5, u + .01), z)
        tx, ty = b[0] - a[0], b[1] - a[1]; l = math.hypot(tx, ty) or 1
        x, y = x - ty / l * lift, y + tx / l * lift
    return (x * side, y, z)

def zs(z0, z1):
    s = {z0, z1}; z = math.ceil(z0 / STEP) * STEP
    while z < z1: s.add(round(z, 4)); z += STEP
    for w, _, R in ARCHES:
        for e in (w - R, w - R + .002, w + R - .002, w + R):
            if z0 < e < z1: s.add(round(e, 4))
    return sorted(s)

def grid(z0, z1, u0, u1, side=1, both=False, lift=0.0):
    n = max(1, round((u1 - u0) * 4)); us = [u0 + (u1 - u0) * i / n for i in range(n + 1)]
    cols = ([(u, -1) for u in us[1:][::-1]] + [(u, 1) for u in us]) if both else [(u, side) for u in (us if side > 0 else us[::-1])]
    Z = zs(z0, z1); w = len(cols); v, f = [], []
    for z in Z:
        for u, s in cols: v.append(surf(u, z, s, lift))
    for j in range(len(Z) - 1):
        for i in range(w - 1):
            a = j * w + i; b = a + w
            f.append((a, b, b + 1, a + 1))
    return G(v, f)

def cap(z, outward):
    ring_ = [surf(u / 4, z, 1) for u in range(21)] + [(0, station(z)[10], z)] + [surf(u / 4, z, -1) for u in range(20, -1, -1)]
    c = (0, sum(p[1] for p in ring_) / len(ring_), z)
    v = [c] + ring_; f = []
    for i in range(1, len(ring_)):
        f.append((0, i, i + 1) if outward > 0 else (0, i + 1, i))
    return G(v, f)

ILL = ' Surface reconstructed from published dimensions; contours are illustrative.'
def outward(c, k=1.0):
    return [round(c[0] * .9 * k, 3), round((.45 + max(0, c[1] - .5)) * k, 3), round(c[2] * .35 * k, 3)]
def panel(pid, name, desc, z0, z1, u0, u1, mat='paint', both=False, lift=0.0, **kw):
    sides = [0] if both else [-1, 1]
    for s in sides:
        g = grid(z0, z1, u0, u1, s or 1, both, lift)
        cx = sum(p[0] for p in g.v) / len(g.v); cy = sum(p[1] for p in g.v) / len(g.v); cz = sum(p[2] for p in g.v) / len(g.v)
        part(pid + ('' if both else ('L' if s < 0 else 'R')), name + ('' if both else (' · left' if s < 0 else ' · right')), g, mat,
             desc + ILL, open_surface=True, vector=kw.get('vector') or outward((cx, cy, cz)), **{k: v for k, v in kw.items() if k != 'vector'})

ctx('01_Exterior_Body', 'Front_End', 'Body')
panel('bumper', 'Front bumper', 'Arrow-shaped nose of the wedge profile; aluminium crash structure sits behind it.', 2.05, 2.44, 0, 3, both=True)
panel('frontIntake', 'Front air intake', 'Large lower opening at each front corner, flanking the nose.', 2.05, 2.44, 3, 5, 'carbon')
part('frontGrille', 'Lower front grille', cap(2.44, 1), 'plastic', 'Mesh closing the front fascia.' + ILL, open_surface=True, vector=[0, .1, .9])
panel('frontLid', 'Front luggage compartment lid', 'Lid over the front luggage bay, hinged at the windscreen base.', .95, 2.05, 0, 2, both=True,
      kin={'type': 'hinge', 'axis': [1, 0, 0], 'angle': -0.9, 'trigger': 'frontLid'}, pivot=(0, point(0, .97)[1], .97))
panel('fender', 'Front fender', 'Wraps the front wheel; its crease runs from headlamp to door.', .95, 2.05, 2, 5)
panel('headlamp', 'Bi-xenon headlamp', 'Headlamp unit at the front corner with LED daytime running lights.', 1.78, 2.15, 2.15, 2.85, 'carbon', lift=.012)
for s, L in ((-1, 'L'), (1, 'R')):
    drl = tube([surf(2.25, 2.1, s, .017), surf(2.5, 1.95, s, .017), surf(2.75, 1.84, s, .017)], .005, 8)
    drl.add(tube([surf(2.5, 1.95, s, .017), surf(2.45, 1.82, s, .017)], .005, 8))
    part('drl' + L, 'LED daytime running light' + (' · left' if s < 0 else ' · right'), drl, 'chrome', 'Y-shaped LED light signature inside the headlamp.', vector=[s * .9, .5, .7])
part('splitter', 'Front splitter', hull([(x * sg, y, z) for sg in (-1, 1) for x, z in ((0, 2.47), (.38, 2.45), (.85, 2.30), (.98, 2.05), (.98, 1.95)) for y in (.10, .118)]),
     'carbon', 'Carbon blade under the nose that manages air flowing beneath the car.', vector=[0, -.3, .8])

ctx('01_Exterior_Body', 'Cabin', 'Body')
panel('windshield', 'Windscreen', 'Steeply raked screen continuing the line of the front lid.', .10, .95, 0, 1, 'glass', both=True)
panel('roof', 'Roof panel', 'Low roof over the carbon-fibre passenger cell.', -.53, .10, 0, 1, both=True)
for s, L in ((-1, 'L'), (1, 'R')):
    piv = (s * .80, .86, .95)
    trig = {'type': 'hinge', 'axis': [1, 0, 0], 'angle': 1.2, 'trigger': 'doors'}
    for pid, name, desc, z0, z1, u0, u1, mat in (
        ('doorGlass', 'Door window', 'Door glass; drops slightly when the door opens.', -.53, .95, 1, 2, 'glass'),
        ('door', 'Scissor door', 'Door hinged at the front that swings upward rather than outward.', -.53, .95, 2, 4.6, 'paint')):
        part(pid + L, name + (' · left' if s < 0 else ' · right'), grid(z0, z1, u0, u1, s), mat, desc + ILL, pivot=piv, kin=trig, open_surface=True, vector=[s * .9, .6, .1])
    mirror = hull([(s * x, y, z) for x, y, z in ((.80, .90, .76), (.97, .93, .72), (.99, 1.0, .64), (.83, .98, .60), (.97, .92, .60), (.87, .88, .66))])
    mirror.add(tube([(s * .72, .84, .74), (s * .82, .91, .69)], .012, 8))
    part('mirror' + L, 'Door mirror' + (' · left' if s < 0 else ' · right'), mirror, 'carbon', 'Exterior mirror on a slim stalk at the front of the door.', pivot=piv, kin=trig, vector=[s * 1.1, .6, .2])
panel('sill', 'Carbon side sill', 'Lower sill along the passenger cell between the wheels.', -1.0, .95, 4.6, 5, 'carbon')
wiper = tube([(-.5, .82, .9), (0, .80, .93), (.35, .80, .92)], .006, 8)
part('wiper', 'Windscreen wiper', wiper, 'plastic', 'Single wiper arm parked at the base of the windscreen.', vector=[0, .5, .6])

ctx('01_Exterior_Body', 'Rear_End', 'Body')
hinge_y = point(0, -.53)[1]
part('glassCover', 'Hinged glass engine cover', grid(-1.85, -.53, 0, 1, 1, True), 'glass',
     'Click to open. The glass cover with hexagonal louvres shows the V12 beneath it.' + ILL, pivot=(0, hinge_y, -.53),
     kin={'type': 'hinge', 'axis': [1, 0, 0], 'angle': 1.15, 'trigger': 'cover'}, open_surface=True, vector=[0, 1.2, -.3])
for s, L in ((-1, 'L'), (1, 'R')):
    part('coverStrut' + L, 'Engine cover gas strut' + (' · left' if s < 0 else ' · right'),
         tube([(s * .52, .80, -.75), (s * .52, hinge_y - .05, -1.05)], .009, 10, smooth=False), 'steel',
         'Gas strut that holds the glass engine cover open.', vector=[s * .4, 1.0, -.3], blocked=[])
panel('louvers', 'Engine bay cooling louvres', 'Louvred panel beside the glass cover lets heat escape from the engine bay.', -1.85, -.53, 1, 2, 'carbon')
for s, L in ((-1, 'L'), (1, 'R')):
    for i in range(5):
        z = -.75 - i * .22
        part(f'slat{L}{i}', 'Cooling louvre blade', hull([surf(1.1, z, s, .015), surf(1.9, z, s, .015), surf(1.9, z - .05, s, .015), surf(1.1, z - .05, s, .015),
             surf(1.1, z, s, .0), surf(1.9, z, s, .0)]), 'paint', 'Individual blade over the engine bay vent.', vector=[s * .5, 1.0, -.2])
panel('activeIntake', 'Active shoulder air intake', 'Upper intake that opens with temperature and speed to feed the engine airboxes.', -1.0, -.53, 2, 3, 'carbon')
panel('sideIntake', 'Side radiator intake', 'Large scoop behind the door that feeds the side-mounted radiators.', -1.0, -.53, 3, 4, 'carbon')
panel('rearSkirt', 'Rear side skirt', 'Lower panel between the side intake and the rear wheel.', -1.0, -.53, 4, 4.6)
panel('haunch', 'Rear haunch', 'Wide rear wing over the driven rear wheel.', -2.10, -1.0, 2, 5)
panel('tail', 'Rear bumper', 'Rear corner of the body wrapping toward the open rear fascia.', -2.34, -2.10, 2, 5)
panel('deck', 'Rear deck', 'Deck behind the engine cover that carries the active wing.', -2.34, -1.85, 0, 2, both=True)
part('rearFascia', 'Rear grille', cap(-2.34, -1), 'plastic', 'Open mesh rear fascia that lets hot air out of the engine bay.' + ILL, open_surface=True, vector=[0, .1, -.9])
part('wing', 'Active rear wing', hull([(x, y, z) for x in (-.72, .72) for y, z in ((.965, -2.06), (.965, -2.30), (.94, -2.30), (.94, -2.06))]), 'carbon',
     'Three-position rear wing; it rises with speed to add downforce.', vector=[0, .8, -.4])
for s, L in ((-1, 'L'), (1, 'R')):
    part('wingStrut' + L, 'Wing actuator' + (' · left' if s < 0 else ' · right'), box(.03, .07, .08, (s * .45, .905, -2.18)), 'alu',
         'Electric actuator that raises and tilts the wing.', vector=[s * .2, .7, -.4])
    part('taillamp' + L, 'LED rear lamp' + (' · left' if s < 0 else ' · right'),
         hull([(s * x, y, z) for x, y, z in ((.48, .72, -2.335), (.88, .68, -2.32), (.86, .78, -2.32), (.50, .80, -2.335), (.48, .72, -2.36), (.88, .68, -2.35), (.86, .78, -2.35), (.50, .80, -2.36))]),
         'redlens', 'Y-shaped LED rear lamp set into the rear fascia.', vector=[s * .4, .2, -.9])
part('brakeLight', 'Third brake light', box(.5, .012, .02, (0, .88, -2.31)), 'redlens', 'High-mounted LED brake light below the wing.', vector=[0, .6, -.8])

# ================================================================= 02 CHASSIS
ctx('02_Chassis_Monocoque', 'Carbon_Monocoque', 'Chassis', vector=[0, -.6, 0])
part('tubFloor', 'Monocoque floor', box(1.84, .03, 1.52, (0, .125, .23)), 'carbon', 'Floor of the one-piece carbon-fibre tub, cured as a single structure.')
for s, L in ((-1, 'L'), (1, 'R')):
    part('tubSill' + L, 'Monocoque sill box' + (' · left' if s < 0 else ' · right'), box(.28, .30, 1.52, (s * .78, .29, .23)), 'carbon',
         'Deep structural sill that carries side-impact and torsional loads.', vector=[s * .5, -.4, 0])
    part('aPillar' + L, 'A-pillar' + (' · left' if s < 0 else ' · right'), tube([(s * .66, .74, .97), (s * .62, .95, .55), (s * .58, 1.10, .12), (s * .56, 1.12, -.3), (s * .58, 1.09, -.52)], .03, 10),
         'carbon', 'Windscreen pillar and roof rail moulded into the tub.', vector=[s * .4, .3, 0])
part('tunnel', 'Transmission tunnel', join(box(.34, .02, 1.50, (0, .44, .24)), box(.02, .30, 1.50, (-.17, .29, .24)), box(.02, .30, 1.50, (.17, .29, .24))), 'carbon',
     'Central spine of the tub; houses the gearbox and the front propeller shaft.')
part('frontBulkhead', 'Front bulkhead', box(1.28, .55, .04, (0, .42, .99)), 'carbon', 'Forward wall of the tub; the front frame bolts here.')
part('firewall', 'Rear bulkhead / firewall', join(box(1.28, .55, .03, (0, .77, -.48)), box(.45, .32, .03, (-.42, .30, -.48)), box(.45, .32, .03, (.42, .30, -.48))), 'carbon',
     'Separates cabin from engine bay; the bellhousing passes through its lower centre.')
part('roofFrame', 'Roof cross-member', tube([(-.56, 1.10, -.45), (0, 1.12, -.47), (.56, 1.10, -.45)], .03, 10), 'carbon', 'Roll-over hoop at the rear of the roof.')
ctx('02_Chassis_Monocoque', 'Front_Frame', 'Chassis', vector=[0, 0, .9])
for s, L in ((-1, 'L'), (1, 'R')):
    part('frontRail' + L, 'Front frame rail' + (' · left' if s < 0 else ' · right'), box(.07, .10, 1.20, (s * .34, .30, 1.62)), 'alu', 'Aluminium rail carrying the front suspension and crash structure.')
    part('crashBox' + L, 'Front crash box' + (' · left' if s < 0 else ' · right'), box(.12, .12, .20, (s * .34, .30, 2.30)), 'alu', 'Deformable aluminium box that absorbs frontal impact energy.')
for z, nm in ((1.12, 'rear'), (1.62, 'middle'), (2.20, 'front')):
    part('frontCross' + nm.capitalize(), f'Front frame cross-member · {nm}', box(.62, .07, .06, (0, .30, z)), 'alu', 'Ties the front rails together.')
part('frontTower', 'Front damper mount beam', box(1.20, .06, .08, (0, .54, 1.41)), 'alu', 'Upper beam on which the horizontal front dampers and rockers are mounted.')
ctx('02_Chassis_Monocoque', 'Rear_Frame', 'Chassis', vector=[0, 0, -.9])
for s, L in ((-1, 'L'), (1, 'R')):
    part('rearRail' + L, 'Rear frame rail' + (' · left' if s < 0 else ' · right'), tube([(s * .52, .24, -.52), (s * .52, .24, -1.6), (s * .52, .36, -2.30)], .035, 12), 'alu', 'Aluminium rail carrying the engine, rear suspension and crash structure.')
    part('rearUpperRail' + L, 'Rear upper frame rail' + (' · left' if s < 0 else ' · right'), tube([(s * .60, .78, -.50), (s * .62, .72, -1.10), (s * .60, .66, -1.75), (s * .55, .55, -2.20)], .03, 10), 'alu',
         'Upper rail joining the firewall to the rear crash structure.')
    part('engineMount' + L, 'Engine mount' + (' · left' if s < 0 else ' · right'), join(box(.10, .06, .10, (s * .40, .26, -.90)), cyl(.03, .05, (0, 1, 0), (s * .40, .30, -.90))), 'rubber',
         'Elastomer mount isolating the V12 from the rear frame.', vector=[s * .5, -.3, 0])
for z, y, nm in ((-.70, .22, 'front'), (-1.55, .24, 'middle'), (-2.25, .31, 'rear')):
    part('rearCross' + nm.capitalize(), f'Rear frame cross-member · {nm}', box(1.04, .06, .06, (0, y, z)), 'alu', 'Ties the rear rails together.')
part('rearTower', 'Rear damper mount beam', box(1.30, .06, .08, (0, .60, -1.49)), 'alu', 'Upper beam carrying the horizontal rear dampers above the gearbox output.')

# ================================================================= 03 POWERTRAIN — ENGINE
ENG_BLOCK = ['glassCover']
def eng(assembly, zone='Engine', **kw): ctx('03_Powertrain', assembly, zone, blocked=kw.pop('blocked', ENG_BLOCK), **kw)

eng('Engine_Block')
LEN = ENG_Z0 - ENG_Z1
mid = (ENG_Z0 + ENG_Z1) / 2
for s, L in ((1, 'A'), (-1, 'B')):
    b, p = bank_axes(s)
    deck_o = on_bank(s, DECK, .085, 0); deck_i = on_bank(s, DECK, -.075, 0)
    poly = [(0, CY - .07), (s * .26, CY - .07), (s * .26, CY + .06), (deck_o.x, deck_o.y), (deck_i.x, deck_i.y), (0, deck_i.y - .02)]
    if s < 0: poly = poly[::-1]
    g = prism(poly, LEN, None, (0, 0, mid))
    part('block' + L, f'Cylinder block · bank {L}', g, 'cast',
         'Half of the aluminium crankcase and cylinder bank. The L539 has a 60° V, 95 mm bores and an open-deck crankcase with steel liners.',
         vector=[s * .8, .25, 0], spec='Bank angle 60°, 6 cylinders per bank')
part('bedplate', 'Bedplate / main bearing girdle', box(.50, .04, LEN, (0, CY - .085, mid)), 'cast', 'Stiff lower crankcase that carries the seven main bearing caps.', vector=[0, -.4, 0])
part('sump', 'Dry-sump pan', join(box(.46, .05, LEN - .04, (0, CY - .145, mid)), *[box(.46, .008, .006, (0, CY - .174, z)) for z in [ENG_Z0 - .06 - .1 * i for i in range(6)]]),
     'cast', 'Shallow dry-sump pan lets the crank sit low; scavenge pumps return oil to a separate tank.', vector=[0, -.8, 0], blocked=['floorPan'])
for i in range(7):
    z = PIN_Z[0] + .05 - .1 * i
    part(f'mainCap{i + 1}', f'Main bearing cap {i + 1}', box(.16, .035, .03, (0, CY - .055, z)), 'steel', 'Clamps the crankshaft main journal into the block.',
         zone='Internals', vector=[0, -.55, 0], blocked=['bedplate'])
for s, L in ((1, 'A'), (-1, 'B')):
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        c = on_bank(s, DECK - .07, 0, z)
        part(f'liner{L}{i + 1}', f'Cylinder liner {n}', ring(BORE / 2, BORE / 2 + .005, .14, tuple(bank_axes(s)[0]), tuple(c), 24), 'steel',
             'Bore surface the piston rings seal against; 95 mm diameter.', zone='Internals', vector=list(bank_axes(s)[0] * .5), blocked=['block' + L])

eng('Cylinder_Heads')
for s, L in ((1, 'A'), (-1, 'B')):
    M = bank_frame(s); b, p = bank_axes(s)
    head = prism([(-.085, 0), (.095, 0), (.10, .12), (-.09, .12)], LEN, M, tuple(Vector((0, CY, mid)) + b * DECK))
    part('head' + L, f'Cylinder head · bank {L}', head, 'cast', 'Four-valve aluminium head with twin overhead camshafts; intake ports face the V, exhaust ports face out.',
         vector=list(b * 1.0 + Vector((0, .2, 0))), blocked=['camCover' + L, 'plenum' + L])
    cover = prism([(-.09, 0), (.10, 0), (.085, .05), (-.075, .05)], LEN - .02, M, tuple(Vector((0, CY, mid)) + b * (DECK + .12)))
    for i in range(7):
        cover.add(prism([(-.075, .05), (.085, .05), (.085, .056), (-.075, .056)], .006, M, tuple(Vector((0, CY, ENG_Z0 - .02 - .1 * i)) + b * (DECK + .12))))
    part('camCover' + L, f'Camshaft cover · bank {L}', cover, 'red', 'Ribbed cam cover closing the valvetrain; coil packs pass through it.',
         vector=list(b * 1.4 + Vector((0, .3, 0))))
    for k, (nm, off) in enumerate((('intake', -.045), ('exhaust', .045))):
        axis_c = on_bank(s, DECK + .10, off, mid)
        cam = cyl(.012, LEN - .01, (0, 0, 1), (0, 0, 0), 12)
        for i in range(6):
            for j in (-1, 1):
                z = PIN_Z[i] + s * CYL_OFF + j * .02 - mid
                a = math.radians(THROW[i] + 90 * k)
                cam.add(hull([(math.cos(t) * .017, math.sin(t) * .017, z + dz) for t in [TAU * q / 16 for q in range(16)] for dz in (-.006, .006)] +
                             [(math.cos(a) * .026, math.sin(a) * .026, z + dz) for dz in (-.006, .006)]))
        part(f'cam{L}{nm.capitalize()}', f'{nm.capitalize()} camshaft · bank {L}', cam, 'steel',
             f'Opens the {nm} valves; turns at half crank speed via the timing chain.', pivot=tuple(axis_c), local=True, zone='Internals',
             kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': .5}, vector=list(b * 1.2), blocked=['camCover' + L])
        part(f'camSprocket{L}{nm.capitalize()}', f'Cam sprocket · bank {L} {nm}', ring(.012, .045, .012, (0, 0, 1), (0, 0, 0), 24), 'steel',
             'Chain sprocket on the gearbox-side end of the camshaft.', pivot=tuple(on_bank(s, DECK + .10, off, ENG_Z0 - .015)), local=True, zone='Internals',
             kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': .5}, vector=list(b * 1.0 + Vector((0, 0, .3))), blocked=['timingCover'])
    chain = tube([tuple(on_bank(s, DECK + .10, -.045, ENG_Z0 - .015)), tuple(Vector((0, CY, ENG_Z0 - .015))), tuple(on_bank(s, DECK + .10, .045, ENG_Z0 - .015))], .006, 6)
    part('timingChain' + L, f'Timing chain · bank {L}', chain, 'steel', 'Drives the two camshafts of this bank from the crankshaft.', zone='Internals', vector=[s * .4, .4, .5], blocked=['timingCover'])
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        for k in range(4):
            off = -.026 if k < 2 else .026; dz = -.02 if k % 2 == 0 else .02
            kind = 'intake' if k < 2 else 'exhaust'
            valve = join(cyl(.004, .11, (0, 1, 0), (0, .055, 0), 8), cyl(.016 if k < 2 else .014, .004, (0, 1, 0), (0, 0, 0), 16, .006))
            part(f'valve{L}{i + 1}{k + 1}', f'Cylinder {n} · {kind} valve {k % 2 + 1}', valve.xf(M), 'steel',
                 'One of four valves per cylinder. Intake valves admit air from the V; exhaust valves release gas outward.',
                 pivot=tuple(on_bank(s, DECK + .005, off, z + dz)), local=True, zone='Internals', vector=list(b * .9), blocked=[f'cam{L}{"Intake" if k < 2 else "Exhaust"}'])
        springs = G()
        for k in range(4):
            off = -.026 if k < 2 else .026; dz = -.02 if k % 2 == 0 else .02
            springs.add(helix(.009, .0015, .035, 5, tuple(b), tuple(on_bank(s, DECK + .082, off, z + dz))))
        part(f'valveSprings{L}{i + 1}', f'Valve springs · cylinder {n}', springs, 'steel', 'Close the four valves of this cylinder after each cam lobe passes.',
             zone='Internals', vector=list(b * 1.0), blocked=['camCover' + L])
part('timingCover', 'Timing chain cover', prism([(-.30, CY - .10), (.30, CY - .10), (.34, CY + .25), (.12, CY + .40), (-.12, CY + .40), (-.34, CY + .25)], .02, None, (0, 0, ENG_Z0 + .01)),
     'cast', 'Encloses the cam drive chains at the gearbox end of the engine.', vector=[0, .3, .6])

eng('Ignition_Fuel')
for s, L in ((1, 'A'), (-1, 'B')):
    b, p = bank_axes(s); M = bank_frame(s)
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        part(f'plug{L}{i + 1}', f'Spark plug {n}', join(cyl(.007, .05, (0, 1, 0), (0, .025, 0), 12), cyl(.010, .015, (0, 1, 0), (0, .055, 0), 6)).xf(M), 'chrome',
             'Ignites the mixture at the centre of the four-valve combustion chamber.', pivot=tuple(on_bank(s, DECK + .01, 0, z)), local=True, zone='Internals',
             vector=list(b * 1.3), blocked=['coil' + L + str(i + 1)])
        part(f'coil{L}{i + 1}', f'Ignition coil {n}', join(cyl(.012, .09, (0, 1, 0), (0, 0, 0), 14), box(.04, .03, .05, (0, .055, 0))).xf(M), 'plastic',
             'Coil-on-plug unit; raises battery voltage to fire the spark plug below it.', pivot=tuple(on_bank(s, DECK + .14, 0, z)), local=True,
             vector=list(b * 1.6 + Vector((0, .2, 0))))
        inj_c = on_bank(s, DECK + .07, -.11, z)
        part(f'injector{L}{i + 1}', f'Fuel injector {n}', cyl(.007, .06, tuple(b * .5 + Vector((0, .5, 0)) - p * .5), tuple(inj_c), 10), 'steel',
             'Port injector spraying fuel into the intake runner just ahead of the valves.', zone='Engine', vector=list(b * 1.2 + Vector((0, .4, 0))), blocked=['fuelRail' + L])
    a = on_bank(s, DECK + .09, -.13, ENG_Z0 - .02); e = on_bank(s, DECK + .09, -.13, ENG_Z1 + .02)
    part('fuelRail' + L, f'Fuel rail · bank {L}', tube([tuple(a), tuple(e)], .009, 10, smooth=False), 'steel', 'Feeds pressurised fuel to the six injectors of this bank.',
         vector=list(b * 1.4 + Vector((0, .4, 0))))

eng('Intake')
for s, L in ((1, 'A'), (-1, 'B')):
    b, p = bank_axes(s)
    px = s * .065
    part('plenum' + L, f'Intake plenum · bank {L}', cyl(.058, LEN + .02, (0, 0, 1), (px, .80, mid), 20), 'cast', 'Collector feeding six runners; the two plenums sit side by side in the V.',
         vector=[s * .35, 1.75, 0], blocked=ENG_BLOCK)
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        port = on_bank(s, DECK + .07, -.10, z)
        part(f'runner{L}{i + 1}', f'Intake runner {n}', tube([tuple(port), tuple(port + Vector((0, .05, 0)) - p * .02), (px, .76, z)], .02, 12), 'cast',
             'Individual intake passage from the plenum to the cylinder head; its length tunes cylinder filling.', vector=[s * .45, 1.4, 0])
    part('throttle' + L, f'Throttle body · bank {L}', join(cyl(.045, .06, (0, 0, 1), (px, .80, ENG_Z1 - .04), 20), cyl(.004, .1, (1, 0, 0), (px, .80, ENG_Z1 - .04), 8)), 'alu',
         'Electronically controlled throttle at the rear of the plenum.', vector=[s * .4, 1.5, -.3])
    duct = tube([(px, .80, ENG_Z1 - .07), (px + s * .05, .82, ENG_Z1 - .18), (s * .42, .82, -1.55)], .05, 16)
    part('intakeDuct' + L, f'Intake duct · bank {L}', duct, 'carbon', 'Carbon duct from the airbox to the throttle body.', vector=[s * .5, 1.3, -.3])
    part('airbox' + L, f'Airbox and filter · bank {L}', join(box(.26, .16, .26, (s * .46, .80, -1.70)), box(.27, .015, .27, (s * .46, .885, -1.70))), 'carbon',
         'Filter housing fed from the active shoulder intake above it.', vector=[s * .6, 1.2, -.4])

eng('Exhaust')
for s, L in ((1, 'A'), (-1, 'B')):
    b, p = bank_axes(s)
    col = Vector((s * .36, .46, -1.27))
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        port = on_bank(s, DECK + .06, .11, z)
        off = Vector((s * .012 * math.cos(i), .012 * math.sin(i), 0))
        pts = [tuple(port), tuple(port + p * .07), (s * (.37 + .012 * (i % 2)), .44 + .008 * i, z - .03), tuple(col + off + Vector((0, 0, .05)))]
        part(f'header{L}{i + 1}', f'Exhaust header {n}', tube(pts, .019, 12), 'titanium', 'Primary pipe from the exhaust port; equal lengths keep pulses evenly spaced.',
             vector=[s * 1.0, .3, 0])
    part('collector' + L, f'Exhaust collector · bank {L}', cyl(.05, .1, (0, 0, 1), tuple(col), 20, .045), 'titanium', 'Merges the six headers of this bank.', vector=[s * .9, .2, -.3])
    part('catalyst' + L, f'Catalytic converter · bank {L}', join(cyl(.06, .22, (0, 0, 1), (col.x, col.y, -1.43), 20), cyl(.04, .04, (0, 0, 1), (col.x, col.y, -1.30), 16, .06)),
         'titanium', 'Cleans exhaust gas before the silencer.', vector=[s * .9, .1, -.5])
    part('exhaustPipe' + L, f'Exhaust pipe · bank {L}', tube([(col.x, col.y, -1.54), (col.x, col.y, -1.62), (s * .30, .43, -1.80)], .035, 12), 'titanium',
         'Links the catalyst to the silencer.', vector=[s * .7, .1, -.7])
part('silencer', 'Exhaust silencer', join(box(.80, .26, .32, (0, .43, -1.98)), *[box(.81, .27, .01, (0, .43, z)) for z in (-1.84, -2.12)]), 'titanium',
     'Transverse silencer with valve-controlled bypass behind the engine.', vector=[0, -.2, -1.0], blocked=['diffuser'])
hexp = [(math.cos(i * math.pi / 3) * .085, math.sin(i * math.pi / 3) * .065) for i in range(6)]
part('tailpipe', 'Hexagonal exhaust outlet', prism(hexp, .22, None, (0, .43, -2.24)), 'titanium', 'Single centre-mounted hexagonal outlet.', vector=[0, 0, -1.2])
part('heatShield', 'Exhaust heat shield', box(.9, .006, .40, (0, .60, -1.98)), 'alu', 'Protects the rear deck and airboxes from silencer heat.', zone='Aero', vector=[0, .6, -.8])

eng('Cooling_Lubrication')
for s, L in ((-1, 'L'), (1, 'R')):
    rad = box(.04, .40, .38).xf(rot((0, 1, 0), s * .35), (s * .80, .50, -.78))
    part('radiator' + L, 'Coolant radiator' + (' · left' if s < 0 else ' · right'), rad, 'alu', 'Side-mounted radiator behind the side intake.', vector=[s * 1.0, .2, 0], blocked=['sideIntake' + L])
    part('fan' + L, 'Radiator fan' + (' · left' if s < 0 else ' · right'), join(ring(.03, .16, .02, (s, 0, 0), (0, 0, 0), 24), *[box(.012, .13, .04, (0, .09, 0)).xf(rot((1, 0, 0), k * TAU / 7)) for k in range(7)]).xf(rot((0, 1, 0), s * .35)),
         'plastic', 'Electric fan pulling air through the radiator at low speed.', pivot=(s * .74, .50, -.80), local=True, kin={'type': 'spin', 'axis': [s * math.cos(.35), 0, -math.sin(.35)], 'rate': .2},
         vector=[s * .8, .2, 0], blocked=['radiator' + L])
    part('coolantHose' + L, 'Coolant hose' + (' · left' if s < 0 else ' · right'), tube([(s * .76, .62, -.62), (s * .55, .60, -.58), (s * .20, .58, ENG_Z0 + .01)], .02, 12), 'rubber',
         'Carries hot coolant from the engine to the radiator.', vector=[s * .6, .5, .2])
part('waterPump', 'Water pump', join(cyl(.05, .05, (0, 0, 1), (0, .47, ENG_Z1 - .03), 20), ring(.02, .045, .012, (0, 0, 1), (0, .47, ENG_Z1 - .062))), 'cast',
     'Circulates coolant through both banks and the radiators.', vector=[0, .6, .7])
part('expansionTank', 'Coolant expansion tank', join(cyl(.07, .20, (0, 0, 1), (.38, .88, -.62), 20), cyl(.025, .02, (0, 1, 0), (.38, .96, -.62), 16)), 'plastic',
     'Header tank that absorbs coolant expansion.', vector=[.5, 1.0, .2])
part('oilTank', 'Dry-sump oil tank', join(cyl(.06, .34, (0, 1, 0), (-.45, .55, -.55), 20), cyl(.025, .03, (0, 1, 0), (-.45, .735, -.55), 16)), 'alu',
     'Separate oil reservoir of the dry-sump system.', vector=[-.6, .8, .3])
part('scavengePump', 'Oil scavenge pump', cyl(.035, .30, (0, 0, 1), (.22, CY - .12, -.80), 16), 'cast', 'Multi-stage pump pulling oil from the sump back to the tank.', vector=[.5, -.5, 0], blocked=['floorPan'])
part('oilCooler', 'Oil cooler', box(.04, .20, .26).xf(rot((0, 1, 0), -.35), (-.80, .52, -1.05)), 'alu', 'Cools engine oil using air from the left side intake.', vector=[-1.0, .2, 0], blocked=['sideIntakeL'])

eng('Accessory_Drive')
AZ = ENG_Z1 - .02  # belt plane just behind the block
acc = {'alternator': ((.22, .62), .055, 'Alternator', 'Charges the battery and powers the electrical system.'),
       'acCompressor': ((-.22, .62), .055, 'A/C compressor', 'Compresses refrigerant for the cabin air conditioning.')}
for pid, ((x, y), r, nm, desc) in acc.items():
    part(pid, nm, cyl(r, .12, (0, 0, 1), (x, y, AZ - .08), 20), 'cast', desc, vector=[math.copysign(.6, x), .6, -.5])
    part(pid + 'Pulley', nm + ' pulley', ring(.01, .035, .02, (0, 0, 1), (0, 0, 0), 20), 'steel', 'Belt-driven pulley.', pivot=(x, y, AZ), local=True,
         kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 2.2}, vector=[math.copysign(.6, x), .6, -.7])
part('drivePulley', 'Accessory drive pulley', ring(.02, .05, .02, (0, 0, 1), (0, 0, 0), 24), 'steel', 'Gear-driven from the crank; turns the accessory belt.', pivot=(0, .56, AZ),
     local=True, kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 1.4}, vector=[0, .4, -.7])
belt_pts = [(-.05, .56, AZ), (-.20, .66, AZ), (-.26, .62, AZ), (-.20, .57, AZ), (0, .51, AZ), (.20, .57, AZ), (.26, .62, AZ), (.20, .66, AZ), (.05, .56, AZ)]
part('accBelt', 'Accessory drive belt', tube(belt_pts, .006, 6, seg=3), 'rubber', 'Ribbed belt linking the drive, alternator and compressor pulleys.', vector=[0, .5, -.8])
part('starter', 'Starter motor', join(cyl(.04, .14, (0, 0, 1), (-.32, CY - .03, -.62), 16), cyl(.02, .07, (0, 0, 1), (-.32, CY + .03, -.62), 12)), 'steel',
     'Turns the engine over through the flywheel ring gear.', vector=[-.6, .2, .5])

# Rotating assembly
eng('Rotating_Assembly', zone='Internals')
crank_pivot = (0, CY, mid)
crank = G()
for i in range(7):
    crank.add(cyl(.032, .035, (0, 0, 1), (0, 0, PIN_Z[0] + .05 - .1 * i - mid), 20))
for i, a in enumerate(THROW):
    a = math.radians(a); px, py = CR * math.sin(a), CR * math.cos(a); z = PIN_Z[i] - mid
    crank.add(cyl(.026, .05, (0, 0, 1), (px, py, z), 20))
    for dz in (-.035, .035):
        lobe = [(px + .028 * math.cos(t), py + .028 * math.sin(t)) for t in [TAU * q / 12 for q in range(12)]]
        lobe += [(-.075 * math.sin(a + d), -.075 * math.cos(a + d)) for d in [math.radians(x) for x in range(-55, 56, 11)]]
        crank.add(hull([(x, y, z + dz + e) for x, y in lobe for e in (-.007, .007)]))
crank.add(cyl(.022, .08, (0, 0, 1), (0, 0, ENG_Z0 + .07 - mid), 16))
part('crank', 'Crankshaft', crank, 'steel', 'Six-throw forged crank shared by both banks; each pin carries two side-by-side rods.', pivot=crank_pivot, local=True,
     kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 1}, vector=[0, -.25, 0], blocked=['sump', 'bedplate', 'blockA', 'blockB'] + [f'mainCap{i + 1}' for i in range(7)],
     spec='Stroke 76.4 mm, throws at 120° intervals')
part('flywheel', 'Flywheel', join(ring(.025, .14, .025, (0, 0, 1), (0, 0, 0), 32), *[box(.008, .012, .02, (math.cos(TAU * k / 48) * .142, math.sin(TAU * k / 48) * .142, 0)) for k in range(48)]),
     'steel', 'Smooths crank rotation; its ring gear is turned by the starter.', pivot=(0, CY, -.55), local=True, kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 1},
     vector=[0, 0, .9], blocked=['bellhousing'], zone='Transmission')
for s, L in ((1, 'A'), (-1, 'B')):
    b, p = bank_axes(s); beta = s * 30
    for i in range(6):
        n = i + 1 if s > 0 else i + 7
        z = PIN_Z[i] + s * CYL_OFF
        a = math.radians(THROW[i]); phi = a - math.radians(beta)
        pin = Vector((CR * math.sin(a), CY + CR * math.cos(a), z))
        dist = CR * math.cos(phi) + math.sqrt(ROD ** 2 - (CR * math.sin(phi)) ** 2)
        wrist = Vector((0, CY, z)) + b * dist
        kin = {'type': 'piston', 'bank': beta, 'throw': THROW[i], 'centre': [0, CY, round(z, 4)], 'stroke': STROKE, 'rod': ROD}
        pist = lathe([(.0476, -.035), (.0476, -.006), (.046, -.004), (.046, .000), (.0476, .002), (.0476, .006), (.046, .008), (.046, .012), (.0476, .014), (.0476, .028), (.042, .032), (.01, .033)], 28)
        pist.add(cyl(.011, .07, (0, 0, 1), (0, 0, 0), 12))
        part(f'piston{L}{i + 1}', f'Piston {n}', pist, 'alu', 'Forged piston with two compression rings and an oil ring; 95 mm diameter.',
             pivot=tuple(wrist), local=True, q=Vector((0, 1, 0)).rotation_difference(b), kin=kin, vector=list(b * .9 + Vector((0, .3, 0))), blocked=['head' + L, 'block' + L])
        rod = join(ring(.028 * 0 + .0265, .036, .022, (0, 0, 1), (0, 0, 0), 20), box(.018, ROD - .06, .012, (0, ROD / 2, 0)), ring(.011, .019, .022, (0, 0, 1), (0, ROD, 0), 16))
        part(f'rod{L}{i + 1}', f'Connecting rod {n}', rod, 'steel', 'Links the piston to its crank pin; length here is illustrative (145 mm).',
             pivot=tuple(pin), local=True, q=Vector((0, 1, 0)).rotation_difference((wrist - pin).normalized()), kin={**kin, 'type': 'rod'},
             vector=list(b * .7 + Vector((0, .1, 0))), blocked=['head' + L, 'block' + L])

# ================================================================= 03 POWERTRAIN — DRIVELINE
ctx('03_Powertrain', 'Transmission', 'Transmission', blocked=['tunnel'], vector=[0, -.4, .7])
GB_Z0, GB_Z1 = -.49, .04
part('bellhousing', 'Clutch bellhousing', lathe([(.13, -.58), (.155, -.55), (.13, -.49)], 28, (0, 0, 1), (0, CY, 0)), 'cast', 'Joins engine and gearbox and encloses the clutch.', blocked=[], vector=[0, -.2, .5])
part('clutch', 'Twin-plate clutch', join(ring(.03, .12, .012, (0, 0, 1), (0, 0, -.012)), ring(.03, .12, .012, (0, 0, 1), (0, 0, .012))), 'ceramic',
     'Dry twin-plate clutch actuated by the ISR system.', pivot=(0, CY, -.515), local=True, kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 1}, blocked=['bellhousing'], vector=[0, .1, .8])
part('gearboxCase', '7-speed ISR gearbox casing', join(box(.30, .26, GB_Z1 - GB_Z0, (0, .25, (GB_Z0 + GB_Z1) / 2)), *[box(.31, .27, .008, (0, .25, z)) for z in (-.40, -.25, -.10)]), 'cast',
     'Independent Shifting Rods gearbox, mounted ahead of the engine in the tunnel; shifts in about 50 ms.', blocked=['tunnel'], spec='7 forward gears, single clutch')
RATIOS = [3.91, 2.44, 1.81, 1.46, 1.19, .97, .84]
for i, r in enumerate(RATIOS):
    z = GB_Z0 + .05 + i * .065; t = .022
    rin = .03 + .05 / (1 + r); rout = .03 + .05 * r / (1 + r)
    part(f'gearIn{i + 1}', f'Gear {i + 1} · input', ring(.012, min(.075, rin + .01), t, (0, 0, 1), (0, 0, 0), 24), 'steel', f'Input-shaft gear for {["1st", "2nd", "3rd", "4th", "5th", "6th", "7th"][i]}.',
         pivot=(0, .32, z), local=True, kin={'type': 'spin', 'axis': [0, 0, 1], 'rate': 1}, zone='Transmission', blocked=['gearboxCase'], vector=[.3, .3, .5])
    part(f'gearOut{i + 1}', f'Gear {i + 1} · output', ring(.012, min(.075, rout), t, (0, 0, 1), (0, 0, 0), 24), 'steel', 'Output-shaft gear; the ISR selects one pair at a time.',
         pivot=(0, .19, z), local=True, kin={'type': 'shaft', 'axis': [0, 0, 1]}, zone='Transmission', blocked=['gearboxCase'], vector=[-.3, -.1, .5])
part('isrActuator', 'ISR shift actuator', join(box(.18, .04, .22, (0, .405, -.20)), *[cyl(.006, .2, (0, 0, 1), (x, .43, -.20), 8) for x in (-.06, -.02, .02, .06)]), 'alu',
     'Hydraulic unit moving four independent shift rods.', blocked=['tunnel'], vector=[0, .6, .4])
part('outputShaft', 'Rear output shaft', tube([(0, .19, GB_Z0), (0, .19, -1.08), (0, .27, -1.24)], .02, 12), 'steel',
     'Runs back from the gearbox through the sump to the rear differential.', blocked=['sump'], vector=[0, -.7, 0])

ctx('03_Powertrain', 'Driveline', 'Transmission', blocked=['floorPan'])
part('rearDiff', 'Rear differential', join(sphere(.11, (0, 0, 0), 20).scale(1.1, 1, 1), cyl(.05, .08, (0, 0, 1), (0, -.085, .12), 16)), 'cast',
     'Mechanical limited-slip rear differential.', pivot=(0, RR, -1.35), local=True, vector=[0, -.3, -.8])
part('propShaft', 'Front propeller shaft', join(cyl(.025, 1.0, (0, 0, 1), (0, 0, 0), 12), ring(.025, .045, .02, (0, 0, 1), (0, 0, -.5)), ring(.025, .045, .02, (0, 0, 1), (0, 0, .5))), 'carbon',
     'Carries drive forward from the gearbox to the Haldex coupling.', pivot=(0, .25, .60), local=True, kin={'type': 'shaft', 'axis': [0, 0, 1]}, vector=[0, -.6, .3])
part('haldex', 'Haldex IV coupling', join(cyl(.07, .14, (0, 0, 1), (0, 0, 0), 20), box(.08, .06, .08, (.07, .02, 0))), 'cast',
     'Electro-hydraulic multi-plate clutch that sends torque to the front axle when the rear slips.', pivot=(0, .27, 1.16), local=True, vector=[0, -.4, .7], blocked=['undertray'])
part('frontDiff', 'Front differential', join(sphere(.09, (0, 0, 0), 20).scale(1.1, 1, 1), cyl(.05, .07, (0, 0, 1), (0, -.04, -.08), 16)), 'cast',
     'Open front differential driven through the Haldex coupling.', pivot=(0, FR, FA), local=True, vector=[0, -.3, .9], blocked=['undertray'])
for (axle, hx, R, front) in ((FA, FT, FR, True), (RA, RT, RR, False)):
    for s, L in ((-1, 'L'), (1, 'R')):
        tag = ('front' if front else 'rear') + (' left' if s < 0 else ' right')
        P = 'F' if front else 'R'
        a0, a1 = .13, hx - .13
        shaft = join(cyl(.016, a1 - a0 - .12, (1, 0, 0), (0, 0, 0), 12),
                     bellows(.022, .03, .08, 4, (1, 0, 0), (-(a1 - a0) / 2 + .06, 0, 0)), bellows(.03, .022, .08, 4, (1, 0, 0), ((a1 - a0) / 2 - .06, 0, 0)),
                     sphere(.04, (-(a1 - a0) / 2, 0, 0), 14), sphere(.04, ((a1 - a0) / 2, 0, 0), 14))
        part(f'halfShaft{P}{L}', f'Half-shaft · {tag}', shaft, 'steel', 'Drive shaft with constant-velocity joints and boots at each end.',
             pivot=(s * (a0 + a1) / 2, R, axle), local=True, kin={'type': 'wheel', 'axis': [1, 0, 0]}, vector=[s * .6, -.2, 0], blocked=['wheel' + P + L])

# ================================================================= 04 SUSPENSION, BRAKES, WHEELS
def corner(front, s):
    axle, hx, R, W = (FA, FT, FR, FW) if front else (RA, RT, RR, RW)
    P, L = ('F' if front else 'R'), ('L' if s < 0 else 'R')
    tag = ('front' if front else 'rear') + (' left' if s < 0 else ' right')
    hub = (s * hx, R, axle)
    spin = {'type': 'wheel', 'axis': [1, 0, 0], **({'steer': True} if front else {})}
    steer = {'type': 'steer'} if front else None
    ox = lambda x: s * x  # mirror local x for left side
    # Wheels
    ctx('04_Suspension_Brakes', 'Wheels', 'Wheels', vector=[s * 1.3, 0, 0])
    rim_r = .0254 * (19 if front else 20) / 2
    tread = []
    for t in [i / 20 for i in range(21)]:
        x = -W / 2 + W * t; groove = any(abs(t - g) < .03 for g in (.3, .5, .7))
        tread.append((R - (.006 if groove else 0) - .01 * (2 * t - 1) ** 6, x))
    tyre = lathe([(rim_r + .005, W / 2 - .01), (R - .045, W / 2 + .002), (R - .015, W / 2 - .004)] + tread[::-1] + [(R - .015, -W / 2 + .004), (R - .045, -W / 2 - .002), (rim_r + .005, -W / 2 + .01)],
                 48, (1, 0, 0), closed=True)
    part(f'tyre{P}{L}', f'Tyre · {tag}', tyre, 'rubber', f'{"255/35 ZR19" if front else "335/30 ZR20"} high-performance tyre.', pivot=hub, local=True, kin=spin, blocked=[])
    rim = lathe([(rim_r - .025, -W / 2 + .01), (rim_r + .012, -W / 2 + .005), (rim_r + .012, -W / 2 + .02), (rim_r - .008, -W / 2 + .03), (rim_r - .008, W / 2 - .03),
                 (rim_r + .012, W / 2 - .02), (rim_r + .012, W / 2 - .005), (rim_r - .025, W / 2 - .01)], 48, (1, 0, 0), closed=True)
    for k in range(5):
        for d in (-.13, .13):
            a = TAU * k / 5 + d
            sp = box(.026, rim_r - .07, .022, (0, .035 + (rim_r - .07) / 2, 0)).xf(rot((1, 0, 0), a))
            rim.add(sp.mv(W / 2 - .045, 0, 0))
    rim.add(cyl(.065, .05, (1, 0, 0), (W / 2 - .05, 0, 0), 24))
    part(f'wheel{P}{L}', f'Forged wheel · {tag}', rim.scale(s, 1, 1), 'alu', f'{"19-inch" if front else "20-inch"} forged aluminium wheel with five twin spokes.',
         pivot=hub, local=True, kin=spin, blocked=['tyre' + P + L])
    nuts = G()
    for k in range(5):
        a = TAU * k / 5 + TAU / 10
        nuts.add(cyl(.01, .03, (1, 0, 0), (s * (W / 2 - .015), math.cos(a) * .056, math.sin(a) * .056), 6))
    part(f'wheelBolts{P}{L}', f'Wheel bolts · {tag}', nuts, 'chrome', 'Five bolts clamping the wheel to the hub.', pivot=hub, local=True, kin=spin, blocked=[], vector=[s * 1.5, 0, 0])
    # Brakes
    ctx('04_Suspension_Brakes', 'Brakes', 'Brakes', vector=[s * .9, 0, 0], blocked=['wheel' + P + L, 'tyre' + P + L])
    dr = .20 if front else .19; dt = .038 if front else .032; dx = s * -(.0)
    disc = join(ring(dr - .075, dr, dt, (1, 0, 0), (0, 0, 0), 48))
    for k in range(24):
        a = TAU * k / 24
        disc.add(cyl(.004, dt + .002, (1, 0, 0), (0, math.cos(a) * (dr - .03), math.sin(a) * (dr - .03)), 6))
    disc.add(lathe([(dr - .075, 0), (dr - .08, s * .045), (.07, s * .055), (.07, s * .065)], 32, (1, 0, 0)))
    part(f'disc{P}{L}', f'Carbon-ceramic brake disc · {tag}', disc.mv(-s * .035, 0, 0), 'ceramic', f'{"400" if front else "380"} mm ventilated carbon-ceramic disc.',
         pivot=hub, local=True, kin=spin)
    ca = math.radians(-50 if front else 50)
    cal = sector(dr - .055, dr + .028, ca - .55, ca + .55, .11, 12).xf(Matrix(((0, 1, 0), (1, 0, 0), (0, 0, 1))))  # y-thickness -> x
    part(f'caliper{P}{L}', f'Brake caliper · {tag}', cal.mv(-s * .035, 0, 0), 'caliper', f'{"Six" if front else "Four"}-piston monobloc caliper.', pivot=hub, local=True, kin=steer)
    pad = G()
    for e in (-1, 1):
        pad.add(sector(dr - .05, dr - .005, ca - .4, ca + .4, .012, 8).xf(Matrix(((0, 1, 0), (1, 0, 0), (0, 0, 1)))).mv(-s * .035 + e * (dt / 2 + .008), 0, 0))
    part(f'pads{P}{L}', f'Brake pads · {tag}', pad, 'ceramic', 'Pair of friction pads squeezed against the disc by the caliper pistons.', pivot=hub, local=True, kin=steer,
         blocked=['caliper' + P + L])
    # Suspension
    ctx('04_Suspension_Brakes', 'Suspension', 'Suspension', vector=[s * .6, .1, 0], blocked=['wheel' + P + L, 'tyre' + P + L])
    ux = hx - .11
    upright = join(hull([(ox(ux), R - .17, axle - .04), (ox(ux), R - .17, axle + .04), (ox(ux - .03), R + .19, axle - .03), (ox(ux - .03), R + .19, axle + .03),
                         (ox(ux + .03), R, axle - .07), (ox(ux + .03), R, axle + .07), (ox(ux - .02), R, axle - .07), (ox(ux - .02), R, axle + .07)]),
                   box(.03, .03, .10, (ox(ux - .01), R + .02, axle + (.08 if front else -.08))))
    part(f'upright{P}{L}', f'Upright / hub carrier · {tag}', upright.mv(-s * hx, -R, -axle), 'cast', 'Aluminium upright carrying the wheel bearing, caliper and ball joints.',
         pivot=hub, local=True, kin=steer, blocked=['disc' + P + L, 'caliper' + P + L])
    part(f'hub{P}{L}', f'Wheel hub · {tag}', join(cyl(.06, .05, (1, 0, 0), (s * .05, 0, 0), 24), cyl(.035, .06, (1, 0, 0), (0, 0, 0), 16)), 'steel',
         'Bearing hub; the wheel and disc bolt to its flange.', pivot=hub, local=True, kin=spin, blocked=['disc' + P + L])
    lo_in, lo_out = s * .30, s * (ux - .01)
    lower = tube([(lo_in, .16, axle + .22), (lo_out, R - .16, axle), (lo_in, .16, axle - .22)], .016, 10, smooth=False)
    lower.add(sphere(.022, (lo_out, R - .16, axle)))
    part(f'lowerArm{P}{L}', f'Lower wishbone · {tag}', lower, 'alu', 'Lower control arm; the pushrod rises from its outer end.')
    up_in = s * .38
    upper = tube([(up_in, R + .18, axle + .18), (s * (ux - .04), R + .18, axle), (up_in, R + .18, axle - .18)], .014, 10, smooth=False)
    upper.add(sphere(.02, (s * (ux - .04), R + .18, axle)))
    part(f'upperArm{P}{L}', f'Upper wishbone · {tag}', upper, 'alu', 'Upper control arm locating the top of the upright.')
    rk = (s * .56, .56 if front else .62, axle + (.05 if front else -.15))
    part(f'pushrod{P}{L}', f'Pushrod · {tag}', tube([(s * (ux - .06), R - .14, axle), rk], .012, 10, smooth=False), 'steel',
         'Transfers wheel movement up to the inboard rocker; this is what makes it a pushrod suspension.', vector=[s * .5, .5, 0])
    part(f'rocker{P}{L}', f'Rocker (bellcrank) · {tag}', hull([(rk[0], rk[1] - .03, rk[2]), (rk[0] - s * .09, rk[1] + .02, rk[2]), (rk[0] - s * .02, rk[1] + .06, rk[2]),
                                                               (rk[0], rk[1] - .03, rk[2] + .02), (rk[0] - s * .09, rk[1] + .02, rk[2] + .02), (rk[0] - s * .02, rk[1] + .06, rk[2] + .02)]),
         'alu', 'Pivots on the frame and turns pushrod travel into horizontal damper travel.', vector=[s * .4, .6, 0])
    d0 = (s * .14, rk[1] + .03, rk[2] + .01); dlen = abs(rk[0] - s * .09 - d0[0])
    damp = join(cyl(.026, dlen * .6, (1, 0, 0), (s * dlen * .3, 0, 0), 16), cyl(.009, dlen * .5, (1, 0, 0), (s * dlen * .72, 0, 0), 10),
                ring(.008, .02, .02, (0, 0, 1), (0, 0, 0)), ring(.008, .02, .02, (0, 0, 1), (s * dlen, 0, 0)))
    part(f'damper{P}{L}', f'Horizontal damper · {tag}', damp, 'steel', 'Inboard, horizontally mounted damper (Öhlins-supplied per press reports).',
         pivot=d0, local=True, kin={'type': 'spring', 'axis': [1, 0, 0]}, vector=[s * .3, .7, 0])
    part(f'spring{P}{L}', f'Coil spring · {tag}', helix(.04, .006, dlen * .55, 6, (1, 0, 0), (s * dlen * .55, 0, 0)), 'red', 'Steel coil spring around the damper body.',
         pivot=d0, local=True, kin={'type': 'spring', 'axis': [1, 0, 0]}, vector=[s * .3, .8, 0])
    if not front:
        part(f'toeLink{P}{L}', f'Toe link · {tag}', tube([(s * .30, .24, axle - .16), (s * (ux - .02), R - .08, axle - .12)], .011, 10, smooth=False), 'steel',
             'Rear toe-control link that keeps the wheel tracking straight under load.')
    else:
        part(f'tieRod{P}{L}', f'Steering tie rod · {tag}', tube([(s * .40, .21, axle + .13), (s * (ux - .01), R + .02, axle + .08)], .011, 10, smooth=False), 'steel',
             'Connects the steering rack to the upright steering arm.')
    part(f'brakeLine{P}{L}', f'Brake line · {tag}', tube([(s * .45, .55, axle + .2), (s * (ux - .06), R + .25, axle + .05), (s * (ux - .02), R + .10, axle + (.06 if front else -.06))], .004, 6),
         'rubber', 'Braided hose feeding brake fluid to the caliper.', zone='Brakes', vector=[s * .6, .2, 0])

for front in (True, False):
    for s in (-1, 1): corner(front, s)
ctx('04_Suspension_Brakes', 'Suspension', 'Suspension')
for front, z, y in ((True, 1.47, .63), (False, -1.58, .70)):
    P = 'F' if front else 'R'
    part(f'antiRoll{P}', f'Anti-roll bar · {"front" if front else "rear"}', tube([(-.55, y - .06, z - .12), (-.50, y, z), (.50, y, z), (.55, y - .06, z - .12)], .012, 10), 'steel',
         'Torsion bar linking left and right rockers to limit body roll.', vector=[0, .9, .3 if front else -.3])
ctx('04_Suspension_Brakes', 'Steering', 'Suspension', vector=[0, .3, .6])
part('steeringRack', 'Steering rack', join(cyl(.03, .62, (1, 0, 0), (0, .21, FA + .13), 16), bellows(.02, .02, .08, 4, (1, 0, 0), (-.35, .21, FA + .13)), bellows(.02, .02, .08, 4, (1, 0, 0), (.35, .21, FA + .13)),
                                                cyl(.04, .10, (0, 1, 0), (-.14, .25, FA + .13), 16)), 'alu', 'Rack-and-pinion steering with hydraulic assistance.')
part('steeringColumn', 'Steering column', tube([(-.14, .30, FA + .13), (-.20, .45, 1.05), (-.36, .62, .62), (-.39, .69, .49)], .015, 10), 'steel',
     'Column with universal joints from the steering wheel to the rack pinion.', vector=[0, .5, .4], blocked=['dashboard'])

# ================================================================= 05 AERO / UNDERBODY
ctx('05_Aero_Underbody', 'Underbody', 'Aero', vector=[0, -.8, 0])
part('undertray', 'Front undertray', box(1.5, .012, 1.0, (0, .115, 1.65)), 'carbon', 'Flat panel beneath the front frame.')
part('floorPan', 'Centre floor', box(1.6, .01, 1.0, (0, .105, -.9)), 'carbon', 'Flat floor under the engine bay that feeds the diffuser.', blocked=[])
part('diffuser', 'Rear diffuser', hull([(x, y, z) for x in (-.8, .8) for y, z in ((.105, -1.42), (.28, -2.34), (.29, -2.34), (.115, -1.42))]), 'carbon',
     'Upswept rear floor that accelerates air under the car to create downforce.', vector=[0, -.6, -.6])
for i, x in enumerate((-.55, -.2, .2, .55)):
    part(f'diffFin{i + 1}', 'Diffuser strake', hull([(x + e, y, z) for e in (-.005, .005) for y, z in ((.11, -1.5), (.29, -2.34), (.20, -2.34))]), 'carbon',
         'Vertical strake that keeps diffuser flow from spilling sideways.', vector=[x * .3, -.6, -.6], blocked=[])
for (axle, hx, R, P) in ((FA, FT, FR, 'F'), (RA, RT, RR, 'R')):
    for s, L in ((-1, 'L'), (1, 'R')):
        Rr = R + .035; n = 18
        pts = [(math.cos(math.pi * (.08 + .84 * i / n)) * Rr, math.sin(math.pi * (.08 + .84 * i / n)) * Rr) for i in range(n + 1)]
        ring_pts = [(px, py) for px, py in pts]
        g = G()
        for i in range(n):
            (z0, y0), (z1, y1) = ring_pts[i], ring_pts[i + 1]
            g.add(G([(s * (hx - .20), R + y0, axle + z0), (s * (hx - .20), R + y1, axle + z1), (s * (hx + .14), R + y1, axle + z1), (s * (hx + .14), R + y0, axle + z0)], [(0, 1, 2, 3)]))
        part(f'archLiner{P}{L}', f'Wheel-arch liner · {"front" if P == "F" else "rear"} {"left" if s < 0 else "right"}', g, 'plastic',
             'Liner shielding the arch from stones and spray.', open_surface=True, vector=[s * .5, .3, 0])

# ================================================================= 06 INTERIOR
ctx('06_Interior', 'Cockpit', 'Interior', vector=[0, 1.2, 0], blocked=['roof'])
for s, L in ((-1, 'L'), (1, 'R')):
    x = s * .38
    seat = join(hull([(x + e * .21, .16, z) for e in (-1, 1) for z in (-.32, .16)] + [(x + e * .23, .26, z) for e in (-1, 1) for z in (-.32, .16)]),
                hull([(x + e * .23, .26, -.30) for e in (-1, 1)] + [(x + e * .21, .86, -.40) for e in (-1, 1)] + [(x + e * .22, .26, -.38) for e in (-1, 1)] + [(x + e * .20, .86, -.47) for e in (-1, 1)]))
    part('seat' + L, 'Sport seat' + (' · passenger' if s > 0 else ' · driver'), seat, 'leather', 'Carbon-shell seat trimmed in leather and Alcantara.')
    part('belt' + L, 'Seat belt' + (' · passenger' if s > 0 else ' · driver'), tube([(x + s * .2, .86, -.40), (x, .55, -.22), (x - s * .2, .28, -.05)], .006, 6), 'plastic',
         'Three-point belt anchored to the tub.')
wheel_c = Vector((-.39, .70, .48)); wq = rot((1, 0, 0), math.radians(-70))
sw = lathe([(.17, -.012), (.185, 0), (.17, .012), (.155, 0)], 32, (0, 1, 0), closed=True, cap=False)
for a in (math.pi / 2, math.pi * 7 / 6, -math.pi / 6):
    sw.add(box(.13, .012, .03, (math.cos(a) * .08, 0, math.sin(a) * .08)).xf(rot((0, 1, 0), -a)))
sw.add(cyl(.05, .04, (0, 1, 0), (0, 0, 0), 20))
part('steeringWheel', 'Steering wheel', sw.xf(wq), 'leather', 'Leather-rimmed wheel; the column runs to the front rack.', pivot=tuple(wheel_c), local=True, vector=[0, .9, .3])
for s in (-1, 1):
    part('paddle' + ('L' if s < 0 else 'R'), 'Shift paddle' + (' · downshift' if s < 0 else ' · upshift'), box(.06, .09, .006, (s * .14, .03, -.06)).xf(wq), 'alu',
         'Column-mounted aluminium paddle for the ISR gearbox.', pivot=tuple(wheel_c), local=True, vector=[s * .2, .9, .3])
part('dashboard', 'Dashboard', hull([(x, y, z) for x in (-.66, .66) for y, z in ((.60, .82), (.78, .82), (.80, .62), (.62, .55))]), 'leather', 'Wraparound dash in front of both seats.')
part('cluster', 'TFT instrument cluster', box(.30, .12, .02).xf(rot((1, 0, 0), .35), (-.39, .82, .62)), 'plastic', 'Configurable TFT display with selectable layouts per drive mode.', vector=[-.2, 1.3, .2])
part('console', 'Centre console', hull([(x, y, z) for x in (-.13, .13) for y, z in ((.62, .56), (.75, .62), (.46, .05), (.40, .05), (.46, .30))]), 'leather',
     'Runs down the tunnel between the seats; holds the switch gear.', vector=[0, 1.0, .2])
part('startCover', 'Start-button flap', box(.04, .008, .05).xf(rot((1, 0, 0), -.5), (0, .66, .50)), 'red', 'Red flip cover over the engine start button, inspired by fighter-jet controls.', vector=[0, 1.4, .2])
for i, (x, nm) in enumerate(((-.43, 'Brake pedal'), (-.33, 'Throttle pedal'))):
    part('pedal' + ('Brake' if i == 0 else 'Throttle'), nm, join(box(.07 if i == 0 else .05, .12, .01, (x, .26, .92)), tube([(x, .32, .92), (x, .50, .98)], .007, 6, smooth=False)), 'alu',
         'Aluminium pedal; there is no clutch pedal with the ISR gearbox.', vector=[0, .8, .4])
part('rearMirror', 'Rear-view mirror', box(.20, .055, .015, (0, 1.05, .30)), 'plastic', 'Interior mirror on the windscreen header.', vector=[0, 1.4, .2])

# ================================================================= 07 ELECTRICAL / FUEL
ctx('07_Electrical', 'Electrical', 'Electrical', vector=[0, .9, .5], blocked=['frontLid'])
part('battery', 'Battery', join(box(.26, .18, .17, (.18, .36, 1.95)), cyl(.01, .02, (0, 1, 0), (.10, .46, 1.92), 10), cyl(.01, .02, (0, 1, 0), (.26, .46, 1.92), 10)), 'plastic',
     '12 V battery in the front luggage bay.')
part('fuelTank', 'Fuel tank', join(box(.62, .16, .18, (0, .52, 1.17)), cyl(.04, .14, (0, 1, 0), (.20, .63, 1.17), 16)), 'plastic',
     'Illustrative fuel-tank placeholder; its shape, capacity, position and filler routing are not verified.', blocked=['frontLid'], vector=[0, .8, .6])
part('fuelPump', 'Fuel pump', cyl(.035, .12, (0, 1, 0), (-.18, .52, 1.17), 16), 'steel', 'In-tank pump delivering fuel to the engine.', blocked=['fuelTank'])
for s, L in ((-1, 'L'), (1, 'R')):
    part('ecu' + L, f'Engine control unit · bank {"B" if s < 0 else "A"}', join(box(.20, .16, .05, (s * .36, .92, -.53)), box(.06, .04, .02, (s * .36, .92, -.56))), 'alu',
         'One of two ECUs; each manages fuel and ignition for one bank.', blocked=[], vector=[s * .4, 1.0, .3])
part('batteryCable', 'Main battery cable', tube([(.26, .46, 1.92), (.30, .32, 1.10), (.20, .17, .60), (.20, .17, -.30), (-.32, CY - .03, -.55)], .008, 8), 'red',
     'Heavy cable from the front battery along the tub to the starter.', blocked=[], vector=[0, -.4, 0])
part('fuseBox', 'Fuse and relay box', box(.18, .10, .12, (-.20, .36, 1.95)), 'plastic', 'Front power distribution centre.')

# ================================================================= output
# Metadata corrections must survive regeneration; rendering materials are illustrative.
for p in PARTS:
    pid = p['id']
    if pid in ('frontLid', 'fenderL', 'fenderR', 'doorL', 'doorR'):
        p['material'] = 'Aluminium panel'
    elif pid in ('haunchL', 'haunchR', 'rearSkirtL', 'rearSkirtR'):
        p['material'] = 'SMC composite panel'
    elif pid == 'roof':
        p['material'] = 'Carbon-fibre reinforced polymer'
    elif pid == 'clutch':
        p['material'] = 'Friction lining / metal plates; exact compound unverified'
        p['spec'] = 'Dry double-plate clutch, factory diameter 235 mm; mesh approximate'
    elif pid.startswith('pads'):
        p['material'] = 'Brake friction compound; exact composition unverified'
    elif pid.startswith('upright'):
        p['material'] = 'Aluminium alloy; manufacturing process unverified'
    elif pid.startswith('spring'):
        p['material'] = 'Steel coil spring, painted'
    elif pid == 'batteryCable':
        p['material'] = 'Insulated conductor; exact construction unverified'

PARTS_BY = {p['id'] for p in PARTS}
for p in PARTS:
    p['blockedBy'] = [b for b in p['blockedBy'] if b in PARTS_BY and b != p['id']]
os.makedirs(os.path.join(ROOT, 'public', 'models'), exist_ok=True)
manifest = {
    'model': 'Lamborghini Aventador LP 700-4 — reconstructed anatomy model',
    'provenance': 'Procedurally modelled in Blender from published dimensions and specifications; not OEM CAD.',
    'units': 'metres, Y up, nose +Z, ground at y=0',
    'zones': ['Body', 'Chassis', 'Engine', 'Internals', 'Transmission', 'Suspension', 'Brakes', 'Wheels', 'Aero', 'Interior', 'Electrical'],
    'systems': SYSTEMS,
    'parts': PARTS,
}
with open(os.path.join(ROOT, 'src', 'aventador-parts.json'), 'w') as f: json.dump(manifest, f, indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'aventador.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(ROOT, 'public', 'models', 'aventador.glb'), export_format='GLB', export_extras=True,
                          export_apply=True, export_yup=True, use_selection=False)
print(f'BUILT {len(PARTS)} parts')

if RENDER:
    os.makedirs(RENDER, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 40
    def shot(name, loc, target, hide=()):
        for o in bpy.data.objects:
            if o.type == 'MESH':
                pid = o.get('part_id'); rec = next((p for p in PARTS if p['id'] == pid), None)
                o.hide_render = bool(rec and (rec['zone'] in hide or rec['id'] in hide))
        cam.location = C @ Vector(loc)
        d = (C @ Vector(target)) - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(RENDER, name + '.png'); bpy.ops.render.render(write_still=True)
    shot('front34', (4.2, 2.2, 5.0), (0, .45, .2))
    shot('rear34', (-4.0, 2.6, -4.6), (0, .5, -.4))
    shot('side', (7.5, .7, 0), (0, .5, 0))
    shot('xray', (3.4, 2.8, -3.6), (0, .45, -.5), hide=('Body', 'Interior', 'Aero'))
    shot('engine', (1.2, 1.6, -2.3), (0, .55, -.9), hide=('Body', 'Interior', 'Aero', 'Chassis'))
    shot('corner', (2.2, .8, 2.6), (.86, .33, 1.35), hide=('Body',))
