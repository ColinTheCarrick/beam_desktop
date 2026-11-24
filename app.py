"""Beam Designer desktop prototype. Section properties are synthetic."""

SECTIONS = {
    "W12x26": dict(weight=26, depth=12.22, bf=6.49, tw=.23, tf=.38, Ix=204, Sx=33.4),
    "W8x18": dict(weight=18, depth=8.14, bf=5.25, tw=.23, tf=.33, Ix=61.9, Sx=15.2),
    "W16x31": dict(weight=31, depth=15.88, bf=5.53, tw=.275, tf=.44, Ix=375, Sx=47.2),
}
THEMES = {
    "Light": ("#f4f6fa", "#fff", "#172338", "#1d5ca8", "#2471bd", "#bd4d35"),
    "Dark mode": ("#101725", "#182337", "#e8eef8", "#8ab8ff", "#8ab8ff", "#ff9a82"),
    "Night mode": ("#080d20", "#111a35", "#e9eaff", "#9ba8ff", "#a1b4ff", "#ff76c7"),
    "Ocean": ("#eaf5f6", "#fbffff", "#17333a", "#087f8c", "#098a9a", "#d96445"),
    "Sunset": ("#fff4e9", "#fffdf9", "#3b2b35", "#b54d69", "#b44f76", "#dd6b3f"),
    "Forest": ("#edf4eb", "#fbfef9", "#25352a", "#34734a", "#37845d", "#bd5b43"),
}


def calculate(span, support, points, uniforms, section, allowable, divisor):
    """Compute reactions, diagrams, and elastic deflection on a fine grid."""
    if span <= 0:
        raise ValueError("Span must be greater than zero for analysis.")
    n = 600
    dx = span / n
    xs = [i * dx for i in range(n + 1)]
    total = sum(p for p, _ in points) + sum(w * (b-a) for w, a, b in uniforms)
    first = sum(p*x for p, x in points) + sum(w*(b-a)*(a+b)/2 for w, a, b in uniforms)
    right = first / span if support == "Simply supported" else 0.0
    left = total - right
    fixed = -first if support == "Cantilever" else 0.0
    shear, moment = [], []
    for x in xs:
        v = left - sum(p for p, at in points if at < x)
        m = fixed + left*x - sum(p*(x-at) for p, at in points if at < x)
        for w, a, b in uniforms:
            length = max(0.0, min(x, b)-a)
            if length:
                v -= w*length
                m -= w*length*(x-(a+min(x,b))/2)
        shear.append(v); moment.append(m)
    # EI in kip-in^2; M is converted from kip-ft to kip-in.
    curvature = [m*12/(29000*section["Ix"]) for m in moment]
    slope = [0.0]; disp = [0.0]
    for i in range(1, n+1):
        slope.append(slope[-1] + (curvature[i-1]+curvature[i])*0.5*dx*12)
        disp.append(disp[-1] + (slope[i-1]+slope[i])*0.5*dx*12)
    if support == "Simply supported":
        correction = disp[-1]/(span*12)
        disp = [d-correction*x*12 for d, x in zip(disp, xs)]
    # Sagging curvature gives negative displacement in an upward-positive axis;
    # the interface and spec use positive-downward deflection.
    disp = [-d for d in disp]
    def peak(values):
        i = max(range(len(values)), key=lambda j: abs(values[j]))
        return abs(values[i]), xs[i], values[i]
    vmax, vx, _ = peak(shear); mmax, mx, msigned = peak(moment); dmax, ddx, _ = peak(disp)
    return dict(xs=xs, shear=shear, moment=moment, deflection=disp, left=left, right=right,
                fixed=fixed, vmax=vmax, vx=vx, mmax=mmax, mx=mx, msigned=msigned,
                dmax=dmax, dx=ddx, stress=mmax*12/section["Sx"], allowable=allowable,
                limit=span*12/divisor)


from beam_ui import BeamUI


class App(BeamUI):
    def __init__(self):
        super().__init__(calculate, SECTIONS, THEMES)


if __name__ == "__main__":
    App().mainloop()
