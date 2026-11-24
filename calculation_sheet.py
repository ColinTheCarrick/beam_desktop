"""Create a printable, multi-page PDF of a beam analysis."""
import os
from pathlib import Path
import tempfile
import textwrap


def write_calculation_sheet(path, design, section, result):
    # Import on demand so the rest of the app still opens if the dependency is missing.
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError as exc:
        raise RuntimeError("PDF export requires matplotlib. Install it with: python -m pip install -r requirements.txt") from exc

    if not result["xs"] or any(len(result[k]) != len(result["xs"]) for k in ("shear", "moment", "deflection")):
        raise ValueError("The analysis results are incomplete.")
    span = design["span_ft"]
    points = design["point_loads"]
    uniforms = design["uniform_loads"]
    allowable = design["allowable_stress_ksi"]
    divisor = design["deflection_divisor"]
    checks = [
        f"Peak shear |V|: {result['vmax']:.3f} kip at x = {result['vx']:.3f} ft",
        f"Peak moment |M|: {result['mmax']:.3f} kip-ft at x = {result['mx']:.3f} ft (signed {result['msigned']:.3f} kip-ft)",
        f"Peak elastic bending stress |M|/Sx: {result['stress']:.3f} ksi",
        ("Bending stress comparison: not compared; no allowable stress entered." if allowable is None else
         f"Bending stress comparison: {'within' if result['stress'] <= allowable else 'exceeds'} entered allowable of {allowable:g} ksi."),
        f"Peak |deflection|: {result['dmax']:.4f} in at x = {result['dx']:.3f} ft",
        f"Deflection screen: {'within' if result['dmax'] <= result['limit'] else 'exceeds'} L/{divisor:g} = {result['limit']:.4f} in; appropriate limit depends on the application.",
    ]
    if design["support"] == "Simply supported":
        reactions = [f"Left reaction: {result['left']:.3f} kip; right reaction: {result['right']:.3f} kip (upward positive)."]
    else:
        reactions = [f"Fixed vertical reaction: {result['left']:.3f} kip (upward positive).",
                     f"Fixed reaction moment: {-result['fixed']:.3f} kip-ft (counterclockwise positive)."]
    lines = [
        ("heading", "BEAM INPUTS AND ASSUMPTIONS"),
        ("text", f"Support: {design['support']}; span: {span:g} ft; section: {design['section']} (synthetic)."),
        ("text", f"Synthetic section properties: weight = {section['weight']} lb/ft; d = {section['depth']} in; bf = {section['bf']} in; tw = {section['tw']} in; tf = {section['tf']} in; Ix = {section['Ix']} in^4; Sx = {section['Sx']} in^3."),
        ("text", "Strong-axis bending; demonstration material A992: Fy = 50 ksi, E = 29,000 ksi."),
        ("text", f"Deflection limit: L/{divisor:g}. Allowable bending stress: {'not entered' if allowable is None else f'{allowable:g} ksi'}."),
        ("text", "Loads: positive downward, negative upward. Positions are measured from the left end. Self-weight is excluded."),
        ("heading", "APPLIED LOADS"),
    ]
    if not points and not uniforms:
        lines.append(("text", "No applied loads."))
    for i, load in enumerate(points, 1):
        lines.append(("text", f"P{i}: {load['magnitude_kip']:g} kip at x = {load['position_ft']:g} ft."))
    for i, load in enumerate(uniforms, 1):
        lines.append(("text", f"W{i}: {load['magnitude_kip_per_ft']:g} kip/ft from x = {load['start_ft']:g} to {load['end_ft']:g} ft."))
    lines.extend([("heading", "REACTIONS AND PRELIMINARY CHECKS")])
    lines.extend(("text", line) for line in reactions + checks)
    lines.append(("text", "All entered point and uniform loads are included in both screens. Self-weight is excluded."))
    lines.append(("text", "These are preliminary elastic screens, not design-capacity or code-compliance checks. Buckling, shear capacity, bearing, and load combinations are not checked."))

    def new_figure(title):
        fig = Figure(figsize=(8.5, 11), facecolor="white")
        fig.text(.07, .97, "BEAM DESIGNER  |  CALCULATION SHEET", fontsize=10, fontweight="bold", color="#1d5ca8", va="top")
        fig.text(.07, .946, title, fontsize=15, fontweight="bold", color="#172338", va="top")
        fig.text(.07, .916, "PROTOTYPE: SYNTHETIC SECTION DATA - NOT FOR REAL DESIGN OR CONSTRUCTION", fontsize=8, fontweight="bold", color="#a22d1e", va="top")
        fig.text(.07, .025, "Preliminary analysis only  |  Self-weight excluded  |  Units: ft, kip, in, ksi", fontsize=8, color="#52647a")
        return fig

    target = Path(path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".beam-sheet-", suffix=".pdf", delete=False) as stream:
            temp_name = stream.name
        with PdfPages(temp_name, metadata={"Title": "Beam Designer calculation sheet", "Subject": "Synthetic prototype beam analysis"}) as pdf:
            fig = new_figure("Inputs and preliminary results")
            y = .885
            for kind, content in lines:
                wrapped = textwrap.wrap(content, width=98, break_long_words=True) or [""]
                for line in wrapped:
                    if y < .065:
                        pdf.savefig(fig); fig.clear()
                        fig = new_figure("Inputs and preliminary results (continued)")
                        y = .885
                    fig.text(.075, y, line, fontsize=9 if kind == "text" else 10,
                             fontweight="bold" if kind == "heading" else "normal", color="#172338", va="top")
                    y -= .020 if kind == "text" else .027
                if kind == "heading":
                    y -= .003
            pdf.savefig(fig); fig.clear()

            # Keep long load lists legible by using multiple beam pages if needed.
            all_loads = [("P", i, load) for i, load in enumerate(points, 1)] + [("W", i, load) for i, load in enumerate(uniforms, 1)]
            for start in range(0, max(1, len(all_loads)), 8):
                group = all_loads[start:start+8]
                fig = new_figure("Beam and applied loads")
                fig.text(.08, .875, "Loads are shown in groups; all loads are included in the analysis.", fontsize=9, color="#52647a")
                ax = fig.add_axes([.12, .22, .76, .59]); ax.set_xlim(-.1*span, 1.1*span); ax.set_ylim(-1.7, max(3, len(group)*1.15+1)); ax.axis("off")
                ax.plot([0, span], [0, 0], color="#263c59", lw=4)
                if design["support"] == "Cantilever":
                    ax.plot([0, 0], [-.55, .55], color="#263c59", lw=4)
                    for h in range(-2, 3):
                        ax.plot([-.035*span, 0], [h*.22-.12, h*.22+.05], color="#263c59", lw=1)
                else:
                    ax.plot([0, span], [-.24, -.24], linestyle="none", marker="^", markersize=12, markeredgecolor="#263c59", markerfacecolor="white")
                    ax.plot([span], [-.48], linestyle="none", marker="o", markersize=5, markeredgecolor="#263c59", markerfacecolor="white")
                for lane, (kind, number, load) in enumerate(group):
                    y = 1+lane*1.05
                    if kind == "P":
                        x = load['position_ft']; magnitude = load['magnitude_kip']
                        ax.annotate("", xy=(x, .12 if magnitude >= 0 else y), xytext=(x, y if magnitude >= 0 else .12), arrowprops=dict(arrowstyle="->", color="#bd4d35", lw=1.2))
                        align = "left" if x < .2*span else "right" if x > .8*span else "center"
                        ax.text(x, y+.15, f"P{number}: {magnitude:g} kip @ {x:g} ft", fontsize=8, ha=align, color="#9b402d", clip_on=False)
                    else:
                        a, b, magnitude = load['start_ft'], load['end_ft'], load['magnitude_kip_per_ft']
                        ax.plot([a, b], [y, y], color="#bd4d35", lw=1)
                        for j in range(7):
                            x = a+(b-a)*j/6
                            ax.annotate("", xy=(x, .12 if magnitude >= 0 else y), xytext=(x, y if magnitude >= 0 else .12), arrowprops=dict(arrowstyle="->", color="#bd4d35", lw=.8))
                        center = (a+b)/2
                        align = "left" if center < .2*span else "right" if center > .8*span else "center"
                        ax.text(center, y+.15, f"W{number}: {magnitude:g} kip/ft [{a:g}, {b:g}] ft", fontsize=8, ha=align, color="#9b402d", clip_on=False)
                ax.text(span/2, -1.1, f"Span = {span:g} ft", ha="center", fontsize=9)
                pdf.savefig(fig); fig.clear()

            fig = new_figure("Analysis diagrams")
            axes = fig.subplots(3, 1)
            fig.subplots_adjust(left=.14, right=.94, bottom=.085, top=.875, hspace=.55)
            for ax, key, title, unit, invert in zip(axes, ("shear", "moment", "deflection"),
                    ("Shear (positive upward)", "Moment (positive sagging)", "Deflection (positive downward)"),
                    ("kip", "kip-ft", "in"), (False, False, True)):
                ax.plot(result["xs"], result[key], color="#2471bd", lw=1.5)
                ax.axhline(0, color="#8290a0", lw=.7)
                ax.set_xlim(0, span); ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
                ax.set_ylabel(unit, fontsize=9); ax.set_xlabel("Position x (ft)", fontsize=9)
                ax.tick_params(labelsize=8); ax.grid(True, alpha=.25)
                if invert: ax.invert_yaxis()
            pdf.savefig(fig); fig.clear()
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
