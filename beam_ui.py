"""Tkinter presentation for the Beam Designer prototype."""
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from design_file import read_design, write_design
from result_export import export_results
from calculation_sheet import write_calculation_sheet


def windows_wheel_lines():
    """Read Windows' current wheel setting; 0xffffffff means one page."""
    import ctypes
    from ctypes import wintypes
    lines = wintypes.UINT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0068, 0, ctypes.byref(lines), 0):
        return lines.value
    return 3


class BeamUI(tk.Tk):
    def __init__(self, calculate, sections, themes):
        # Establish DPI awareness before creating Tk, including screenshot tools.
        import sys
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        super().__init__()
        self.calculate, self.sections, self.themes = calculate, sections, themes
        self.title("Beam Designer — Prototype")
        self.ui_scale = max(1, float(self.tk.call("tk", "scaling"))/(96/72))
        self.fit_screen()
        self.style = ttk.Style(self)
        # Native Windows themes ignore several widget color settings.
        self.style.theme_use("clam")
        self.span = tk.DoubleVar(value=20)
        self.support = tk.StringVar(value="Simply supported")
        self.section = tk.StringVar(value="W12x26")
        self.allow = tk.StringVar()
        self.divisor = tk.StringVar(value="360")
        self.theme = tk.StringVar(value="Light")
        self.points, self.uniforms, self.sliders = [], [], []
        self.wheel_remainders = {}
        self.current_file = None
        self.pending = None
        self.build()
        self.add_load("uniform", [1, 0, 20])
        self.theme_changed()

    def fit_screen(self):
        """Fit the client area and window borders inside the desktop work area."""
        import sys
        left, top, right, bottom = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        border, title = int(8*self.ui_scale), int(38*self.ui_scale)
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            user32 = ctypes.windll.user32
            if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
            border = user32.GetSystemMetrics(32) + user32.GetSystemMetrics(92)
            title = user32.GetSystemMetrics(4) + border
        available_width = max(1, right-left-2*border)
        available_height = max(1, bottom-top-title-border)
        width = min(available_width, int(1320*self.ui_scale))
        height = min(available_height, int(940*self.ui_scale))
        self.minsize(min(available_width, int(600*self.ui_scale)),
                     min(available_height, int(450*self.ui_scale)))
        x = max(left, left+(right-left-width-2*border)//2)
        y = max(top, top+(bottom-top-height-title-border)//2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def build(self):
        self.menubar = tk.Menu(self)
        self.file_menu = tk.Menu(self.menubar, tearoff=False)
        self.file_menu.add_command(label="Open…", command=self.open_file, accelerator="Ctrl+O")
        self.file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        self.file_menu.add_command(label="Save As…", command=self.save_as)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.configure(menu=self.menubar)
        self.bind("<Control-o>", lambda event: self.open_file())
        self.bind("<Control-s>", lambda event: self.save_file())
        header = ttk.Frame(self, padding=(24, 18, 24, 12))
        header.pack(fill="x")
        title = ttk.Frame(header)
        title.pack(side="left")
        ttk.Label(title, text="BEAM ANALYSIS PROTOTYPE", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(title, text="Beam Designer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Reactions, internal diagrams, and preliminary stress / deflection screens.", style="Muted.TLabel").pack(anchor="w")
        actions = ttk.Frame(header)
        actions.pack(side="right", padx=(16, 0))
        ttk.Label(actions, text="Color scheme").pack(anchor="w", pady=(0, 4))
        self.picker = ttk.Combobox(actions, textvariable=self.theme, values=list(self.themes), state="readonly", width=16)
        self.picker.pack(fill="x")
        self.picker.bind("<<ComboboxSelected>>", lambda e: self.theme_changed())
        ttk.Label(actions, text="Prototype · synthetic data", style="Badge.TLabel", padding=(8, 4)).pack(pady=(6, 0))

        self.warning = tk.Label(self, anchor="w", justify="left", padx=14, pady=10,
            text="NOT FOR REAL DESIGN OR CONSTRUCTION\nSynthetic section properties are unsuitable for real design. These preliminary screens do not check code compliance, buckling, shear capacity, bearing, or load combinations.")
        self.warning.pack(fill="x", padx=24, pady=(0, 14))
        self.warning.bind("<Configure>", lambda e: self.warning.configure(wraplength=max(100, e.width-30)))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=24)
        self.body = body
        self.panes = ttk.Panedwindow(body, orient="horizontal")
        self.tabs = ttk.Notebook(body)
        self.form_panel, self.formcanvas, self.form = self.scroll_panel(body, 350)
        self.result_panel, self.resultcanvas, self.results = self.scroll_panel(body, 800)
        self.layout_mode = None
        body.bind("<Configure>", self.layout_body)
        self.build_form()
        self.build_results()
        self.results.bind("<Configure>", self.resize_results, add="+")
        footer = ttk.Label(self, text="Strong-axis bending · Demo A992: Fy = 50 ksi, E = 29,000 ksi · Self-weight excluded", style="Muted.TLabel", padding=(24, 10))
        footer.pack(fill="x")
        self.bind_all("<MouseWheel>", self.mousewheel)
        if self.tk.call("tk", "windowingsystem") == "x11":
            self.bind_all("<Button-4>", self.mousewheel)
            self.bind_all("<Button-5>", self.mousewheel)

    def design_data(self):
        allowable = float(self.allow.get()) if self.allow.get().strip() else None
        return {
            "version": 1, "support": self.support.get(), "span_ft": self.span.get(),
            "section": self.section.get(), "deflection_divisor": float(self.divisor.get()),
            "allowable_stress_ksi": allowable,
            "point_loads": [dict(magnitude_kip=v[0].get(), position_ft=v[1].get())
                            for v in (item["variables"] for item in self.points)],
            "uniform_loads": [dict(magnitude_kip_per_ft=v[0].get(), start_ft=v[1].get(), end_ft=v[2].get())
                              for v in (item["variables"] for item in self.uniforms)],
        }

    def save_file(self):
        if self.current_file is None:
            return self.save_as()
        return self.write_file(self.current_file)

    def save_as(self):
        path = filedialog.asksaveasfilename(parent=self, title="Save beam design",
                                           defaultextension=".json",
                                           filetypes=[("Beam design", "*.json"), ("All files", "*.*")])
        if path:
            return self.write_file(path)

    def write_file(self, path):
        try:
            write_design(path, self.design_data(), self.sections)
        except (OSError, ValueError, tk.TclError) as exc:
            messagebox.showerror("Could not save design", str(exc), parent=self)
            return False
        self.current_file = path
        self.title(f"Beam Designer — {Path(path).name}")
        return True

    def open_file(self):
        path = filedialog.askopenfilename(parent=self, title="Open beam design",
                                          filetypes=[("Beam design", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            design = read_design(path, self.sections)
        except (OSError, ValueError, UnicodeError) as exc:
            messagebox.showerror("Could not open design", str(exc), parent=self)
            return
        self.support.set(design["support"])
        self.span.set(design["span_ft"])
        self.section.set(design["section"])
        self.divisor.set(str(design["deflection_divisor"]))
        self.allow.set("" if design["allowable_stress_ksi"] is None else str(design["allowable_stress_ksi"]))
        for store in (self.points, self.uniforms):
            for item in store[:]:
                self.remove_load(store, item)
        for values in design["point_loads"]:
            self.add_load("point", values)
        for values in design["uniform_loads"]:
            self.add_load("uniform", values)
        self.current_file = path
        self.title(f"Beam Designer — {Path(path).name}")
        self.schedule()

    def scroll_panel(self, body, width):
        panel = ttk.Frame(body, style="Card.TFrame")
        canvas = tk.Canvas(panel, width=int(width*self.ui_scale), highlightthickness=0,
                           yscrollincrement=max(1, int(20*self.ui_scale)))
        bar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas, padding=16, style="Card.TFrame")
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        return panel, canvas, content

    def layout_body(self, event):
        # Tabs give both panels the full width on compact desktop windows.
        mode = "tabs" if event.width < 950*self.ui_scale else "panes"
        if mode == self.layout_mode:
            return
        if self.layout_mode == "panes":
            self.panes.forget(self.form_panel)
            self.panes.forget(self.result_panel)
            self.panes.pack_forget()
        elif self.layout_mode == "tabs":
            self.tabs.forget(self.form_panel)
            self.tabs.forget(self.result_panel)
            self.tabs.pack_forget()
        if mode == "panes":
            self.panes.add(self.form_panel, weight=0)
            self.panes.add(self.result_panel, weight=1)
            self.panes.pack(fill="both", expand=True)
        else:
            self.tabs.add(self.form_panel, text="Beam and loads")
            self.tabs.add(self.result_panel, text="Analysis results")
            self.tabs.pack(fill="both", expand=True)
        self.layout_mode = mode
        self.schedule()

    def mousewheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget:
            if widget in (self.formcanvas, self.form):
                canvas = self.formcanvas
                break
            elif widget in (self.resultcanvas, self.results):
                canvas = self.resultcanvas
                break
            widget = getattr(widget, "master", None)
        else:
            return
        window_system = self.tk.call("tk", "windowingsystem")
        if window_system == "win32":
            lines = windows_wheel_lines()
            if not lines:
                return "break"
            mode = "pages" if lines == 0xffffffff else "units"
            amount = -event.delta / 120 * (1 if mode == "pages" else lines)
        elif window_system == "aqua":
            mode, amount = "units", -event.delta
        else:
            # X11 emits one button event per step; the desktop controls their rate.
            mode = "units"
            amount = -3 if event.num == 4 else 3 if event.num == 5 else -3*event.delta/120
        key = (canvas, mode)
        amount += self.wheel_remainders.get(key, 0)
        whole = math.trunc(amount)
        self.wheel_remainders[key] = amount - whole
        if whole:
            canvas.yview_scroll(whole, mode)
        return "break"

    def label(self, parent, text, style="Card.TLabel", **kw):
        label = ttk.Label(parent, text=text, style=style, **kw)
        label.pack(anchor="w", fill="x", pady=(6, 3))
        if "wraplength" not in kw:
            label.bind("<Configure>", lambda e: label.configure(wraplength=max(50, e.width-4)))
        return label

    def choice(self, parent, text, variable, values):
        self.label(parent, text)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.pack(fill="x", pady=(0, 5))
        combo.bind("<<ComboboxSelected>>", lambda e: self.schedule())

    def slider(self, parent, label, variable, low, high, step, unit):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=(7, 3))
        line = ttk.Frame(frame, style="Card.TFrame")
        line.pack(fill="x")
        ttk.Label(line, text=label, style="Card.TLabel").pack(side="left")
        readout = ttk.Label(line, style="Readout.TLabel")
        readout.pack(side="right")
        def refresh(*_):
            readout.configure(text=f"{variable.get():g} {unit}".strip())
        def moved(value):
            snapped = round(float(value)/step)*step
            if abs(variable.get()-snapped) > 1e-8:
                variable.set(round(snapped, 4))
            self.schedule()
        scale = ttk.Scale(frame, from_=low, to=high, variable=variable, command=moved, takefocus=True)
        scale.pack(fill="x", pady=(4, 2))
        def keymove(event, direction):
            variable.set(max(float(scale.cget("from")), min(float(scale.cget("to")), variable.get()+direction*step)))
            self.schedule()
            return "break"
        for key, direction in (("Left", -1), ("Down", -1), ("Right", 1), ("Up", 1)):
            scale.bind(f"<{key}>", lambda e, d=direction: keymove(e, d))
        variable.trace_add("write", refresh)
        refresh()
        self.sliders.append((scale, variable, step))
        return scale

    def build_form(self):
        f = self.form
        self.label(f, "Beam and loads", "Heading.TLabel")
        self.choice(f, "Support condition", self.support, ["Simply supported", "Cantilever"])
        self.slider(f, "Span", self.span, 0, 100, .5, "ft")
        self.choice(f, "Demo section (synthetic)", self.section, list(self.sections))
        self.properties = self.label(f, "", "Hint.TLabel")
        self.label(f, "Synthetic placeholders — unsuitable for real design.", "Notice.TLabel")
        for kind, text in (("point", "Point loads"), ("uniform", "Uniform loads")):
            ttk.Separator(f).pack(fill="x", pady=12)
            row = ttk.Frame(f, style="Card.TFrame"); row.pack(fill="x")
            ttk.Label(row, text=text, style="Heading.TLabel").pack(side="left")
            ttk.Button(row, text="+ Add", command=lambda k=kind: self.add_load(k)).pack(side="right")
            box = ttk.Frame(f, style="Card.TFrame"); box.pack(fill="x", pady=4)
            setattr(self, kind+"_box", box)
        self.label(f, "Loads: positive downward, negative upward. Positions are measured from the left support; beam self-weight is excluded.", "Hint.TLabel")
        ttk.Separator(f).pack(fill="x", pady=12)
        for label, var in (("Allowable bending stress (ksi, optional)", self.allow), ("Deflection limit divisor (L/)", self.divisor)):
            self.label(f, label)
            entry = ttk.Entry(f, textvariable=var)
            entry.pack(fill="x", pady=(0, 5))
            var.trace_add("write", lambda *_: self.schedule())
        self.label(f, "L/360 is an application-dependent screening default. Allowable stress is user-supplied and is not derived from Fy.", "Hint.TLabel")
        ttk.Button(f, text="Analyze beam", style="Accent.TButton", command=self.analyze).pack(fill="x", pady=(12, 5))
        self.error = self.label(f, "", "Error.TLabel")

    def add_load(self, kind, values=None):
        store = self.points if kind == "point" else self.uniforms
        if values is None:
            values = [5, self.span.get()/2] if kind == "point" else [0, 0, self.span.get()]
        row = ttk.Frame(getattr(self, kind+"_box"), padding=(0, 5), style="Card.TFrame")
        row.pack(fill="x")
        variables = [tk.DoubleVar(value=v) for v in values]
        item = dict(row=row, variables=variables, positions=[])
        self.slider(row, "Magnitude", variables[0], -20 if kind == "point" else -5,
                    20 if kind == "point" else 5, .25 if kind == "point" else .1,
                    "kip" if kind == "point" else "kip/ft")
        for i, variable in enumerate(variables[1:]):
            scale = self.slider(row, "Position" if kind == "point" else ("Start" if i == 0 else "End"), variable, 0, self.span.get(), .25, "ft")
            item["positions"].append(scale)
        ttk.Button(row, text="Remove load", command=lambda: self.remove_load(store, item)).pack(anchor="e", pady=4)
        store.append(item)
        self.schedule()

    def remove_load(self, store, item):
        # Drop references to destroyed widgets before applying another theme.
        self.sliders = [s for s in self.sliders if not str(s[0]).startswith(str(item["row"])+".")]
        store.remove(item)
        item["row"].destroy()
        self.schedule()

    def build_results(self):
        r = self.results
        self.label(r, "Analysis results", "Heading.TLabel")
        ttk.Button(r, text="Export results to CSV", command=self.export_csv).pack(anchor="w", pady=(4, 6))
        ttk.Button(r, text="Save calculation sheet (PDF)", command=self.export_pdf).pack(anchor="w", pady=(0, 6))
        self.summary = self.label(r, "", "MutedCard.TLabel")
        self.label(r, "Self-weight excluded · All entered loads used for stress and deflection", "Hint.TLabel")
        self.metrics = [self.label(r, "", "Metric.TLabel", padding=(12, 9)) for _ in range(3)]
        self.stress = self.label(r, "", "Check.TLabel", padding=(12, 10))
        self.deflection = self.label(r, "", "Check.TLabel", padding=(12, 10))
        self.label(r, "Preliminary stress and deflection screens only. Buckling and overall member adequacy are not checked.", "Hint.TLabel")
        self.diagrams = []
        for title in ("Beam and applied loads (+ downward)", "Shear diagram (positive upward)", "Moment diagram (positive sagging)", "Deflection diagram (positive downward)"):
            self.label(r, title, "DiagramTitle.TLabel")
            c = tk.Canvas(r, height=int(180*self.ui_scale), highlightthickness=1)
            c.pack(fill="x", pady=(0, 10))
            self.diagrams.append(c)

    def resize_results(self, event):
        self.schedule()

    def export_csv(self):
        # Analyze immediately so a pending slider edit cannot export stale values.
        result = self.analyze()
        if result is None:
            messagebox.showerror("Could not export results", "Check the beam inputs before exporting.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export beam results",
                                           defaultextension=".csv",
                                           filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            export_results(path, result)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not export results", str(exc), parent=self)

    def export_pdf(self):
        result = self.analyze()
        if result is None:
            messagebox.showerror("Could not save calculation sheet", "Check the beam inputs before exporting.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Save calculation sheet",
                                           defaultextension=".pdf",
                                           filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        try:
            write_calculation_sheet(path, self.design_data(), self.sections[self.section.get()], result)
        except (OSError, ValueError, RuntimeError, tk.TclError) as exc:
            messagebox.showerror("Could not save calculation sheet", str(exc), parent=self)

    def schedule(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
        self.pending = self.after(45, self.analyze)

    def analyze(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None
        try:
            span = self.span.get()
            for item in self.points+self.uniforms:
                for scale, variable in zip(item["positions"], item["variables"][1:]):
                    scale.configure(to=span)
                    variable.set(min(span, max(0, variable.get())))
                if len(item["variables"]) == 3 and item["variables"][1].get() > item["variables"][2].get():
                    item["variables"][1].set(item["variables"][2].get())
            pts = [tuple(v.get() for v in i["variables"]) for i in self.points]
            loads = [tuple(v.get() for v in i["variables"]) for i in self.uniforms]
            loads = [l for l in loads if l[2] > l[1]]
            allow = float(self.allow.get()) if self.allow.get().strip() else None
            divisor = float(self.divisor.get())
            if allow is not None and (not math.isfinite(allow) or allow <= 0):
                raise ValueError("Enter a positive allowable stress, or leave it blank.")
            if not math.isfinite(divisor) or divisor <= 0:
                raise ValueError("Enter a positive deflection divisor.")
            sec = self.sections[self.section.get()]
            result = self.calculate(span, self.support.get(), pts, loads, sec, allow, divisor)
            self.error.configure(text="")
            self.render(result, span, pts, loads, sec, divisor)
            return result
        except (ValueError, tk.TclError, ZeroDivisionError) as exc:
            self.error.configure(text=str(exc))
            self.summary.configure(text="Analysis unavailable — check the inputs.")
            for widget in self.metrics+[self.stress, self.deflection]:
                widget.configure(text="—")
            for c in self.diagrams:
                c.delete("all")

    def render(self, r, span, pts, loads, sec, divisor):
        self.properties.configure(text=f"Synthetic: W = {sec['weight']} lb/ft; d = {sec['depth']} in; bf = {sec['bf']} in; tw = {sec['tw']} in; tf = {sec['tf']} in; Ix = {sec['Ix']} in⁴; Sx = {sec['Sx']} in³.")
        self.summary.configure(text=f"{span:g} ft {self.support.get().lower()} beam · {self.section.get()} (synthetic)")
        reactions = f"Left: {r['left']:.2f} kip · Right: {r['right']:.2f} kip\nUpward-positive reactions" if self.support.get() == "Simply supported" else f"Fixed reaction: {r['left']:.2f} kip upward-positive\nFixed-end reaction moment: {-r['fixed']:.2f} kip-ft (counterclockwise positive)"
        for label, text in zip(self.metrics, ["SUPPORT REACTIONS\n"+reactions, f"PEAK SHEAR (ABSOLUTE)\n{r['vmax']:.2f} kip at x = {r['vx']:.2f} ft", f"PEAK MOMENT (ABSOLUTE)\n{r['mmax']:.2f} kip-ft at x = {r['mx']:.2f} ft · signed {r['msigned']:.2f} kip-ft"]):
            label.configure(text=text)
        compared = "Not compared — enter an allowable stress" if r['allowable'] is None else f"{'Below' if r['stress'] <= r['allowable'] else 'Above'} entered limit of {r['allowable']:.2f} ksi"
        self.stress.configure(text=f"PRELIMINARY BENDING STRESS\nElastic |M|/Sx = {r['stress']:.2f} ksi\n{compared}")
        self.deflection.configure(text=f"DEFLECTION SCREEN\nPeak absolute deflection = {r['dmax']:.3f} in at x = {r['dx']:.2f} ft\n{'Within' if r['dmax'] <= r['limit'] else 'Exceeds'} selected L/{divisor:g} limit = {r['limit']:.3f} in. Limit depends on application.")
        self.draw_beam(self.diagrams[0], span, pts, loads)
        for c, key, unit, down in zip(self.diagrams[1:], ("shear", "moment", "deflection"), ("kip", "kip-ft", "in"), (False, False, True)):
            self.plot(c, r['xs'], r[key], unit, down)

    def draw_beam(self, c, span, points, loads):
        c.delete("all")
        p = self.palette
        width = max(280, c.winfo_width()/self.ui_scale)
        left, right, beam_y = 48, width-48, 112
        def xx(x): return left+(right-left)*x/span
        def load_label(x, y, text):
            item = c.create_text(x, y, text=text, fill=p['load'], font=("Segoe UI", 9))
            # Text fonts already use the screen DPI; the coordinates are scaled below.
            from tkinter import font
            half = font.Font(self, font=("Segoe UI", 9)).measure(text)/(2*self.ui_scale)
            c.coords(item, max(half+8, min(width-half-8, x)), y)
        # Each load gets a separate vertical lane so labels and arrows do not overlap.
        count = len(points)+len(loads)
        beam_y = max(94, 30+count*30)
        c.configure(height=int((beam_y+65)*self.ui_scale))
        c.create_line(left, beam_y, right, beam_y, fill=p['text'], width=6)
        if self.support.get() == "Cantilever":
            c.create_line(left-5, beam_y-24, left-5, beam_y+25, fill=p['text'], width=4)
            for dy in range(-24, 25, 8):
                c.create_line(left-15, beam_y+dy+8, left-5, beam_y+dy, fill=p['text'])
        else:
            for x in (left, right):
                c.create_polygon(x-12, beam_y+22, x, beam_y+3, x+12, beam_y+22, fill=p['bg'], outline=p['text'], width=2)
            for dx in (-6, 6): c.create_oval(right+dx-3, beam_y+24, right+dx+3, beam_y+30, outline=p['text'])
        lane = 0
        for q, a, b in loads:
            y = 26+lane*30; lane += 1
            load_label((xx(a)+xx(b))/2, y-8, f"w = {q:g} kip/ft [{a:g}–{b:g} ft]")
            c.create_line(xx(a), y+4, xx(b), y+4, fill=p['load'])
            for j in range(9):
                x = xx(a+(b-a)*j/8)
                if any(abs(x-xx(pos)) < 9 for _, pos in points): continue
                c.create_line(x, y+4, x, beam_y-6, fill=p['load'], arrow=tk.LAST if q >= 0 else tk.FIRST)
        for q, pos in points:
            y = 26+lane*30; lane += 1
            x = xx(pos)
            load_label(x, y-8, f"P = {q:g} kip @ {pos:g} ft")
            c.create_line(x, y+4, x, beam_y-6, fill=p['load'], width=2, arrow=tk.LAST if q >= 0 else tk.FIRST)
        c.create_text((left+right)/2, beam_y+46, text=f"Span {span:g} ft · fixed at left" if self.support.get() == "Cantilever" else f"Span {span:g} ft · pin / roller", fill=p['muted'])
        c.scale("all", 0, 0, self.ui_scale, self.ui_scale)

    def plot(self, c, xs, values, unit, down):
        c.delete("all")
        p = self.palette
        width = max(280, c.winfo_width()/self.ui_scale); left, right, top, bottom = 68, width-30, 24, 146
        lo, hi = min(0, min(values)), max(0, max(values))
        if hi-lo < 1e-9: lo, hi = -1, 1
        pad = (hi-lo)*.12; lo -= pad; hi += pad
        def yy(v): return top+((v-lo) if down else (hi-v))/(hi-lo)*(bottom-top)
        for value in (min(values), 0, max(values)):
            y = yy(value)
            c.create_line(left, y, right, y, fill=p['border'], dash=(3, 4) if value else ())
            c.create_text(left-8, y, text=f"{value:.3g}", anchor="e", fill=p['muted'], font=("Segoe UI", 8))
        coords = []
        for x, value in zip(xs, values): coords.extend((left+(right-left)*x/xs[-1], yy(value)))
        c.create_line(*coords, fill=p['curve'], width=2.5)
        c.create_text(10, 10, text=unit, anchor="nw", fill=p['muted'], font=("Segoe UI", 9))
        c.create_text(left, bottom+18, text="0 ft", fill=p['muted'])
        c.create_text(right, bottom+18, text=f"{xs[-1]:g} ft", fill=p['muted'])
        c.scale("all", 0, 0, self.ui_scale, self.ui_scale)

    def theme_changed(self):
        bg, surface, text, accent, curve, load = self.themes[self.theme.get()]
        dark = self.theme.get() in ("Dark mode", "Night mode")
        self.palette = p = dict(bg=bg, surface=surface, text=text, accent=accent, curve=curve, load=load,
            muted="#b4c2d8" if dark else "#52647a", border="#465776" if dark else "#c9d2df",
            notice="#382b34" if dark else "#fff2e9", notice_text="#ffccb8" if dark else "#783d22")
        p['notice'], p['notice_text'] = {
            "Light": ("#fff2ee", "#64291d"),
            "Dark mode": ("#38252a", "#ffd9d1"),
            "Night mode": ("#30243b", "#f4d8ff"),
            "Ocean": ("#fff4e8", "#6d3e25"),
            "Sunset": ("#fff0e8", "#713525"),
            "Forest": ("#fff5e7", "#684128"),
        }[self.theme.get()]
        self.configure(background=bg)
        self.menubar.configure(background=surface, foreground=text, activebackground=accent,
                               activeforeground=bg if dark else "#ffffff")
        self.file_menu.configure(background=surface, foreground=text, activebackground=accent,
                                 activeforeground=bg if dark else "#ffffff")
        s = self.style
        s.configure(".", background=surface, foreground=text, font=("Segoe UI", 10), bordercolor=p['border'], lightcolor=p['border'], darkcolor=p['border'], troughcolor=bg, focuscolor=accent)
        s.configure("TFrame", background=bg)
        s.configure("Card.TFrame", background=surface)
        s.configure("TLabel", background=bg, foreground=text)
        for name in ("Card", "Heading", "Hint", "MutedCard", "Readout", "DiagramTitle"):
            s.configure(name+".TLabel", background=surface, foreground=text)
        s.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        for name in ("Heading", "DiagramTitle"):
            s.configure(name+".TLabel", font=("Segoe UI", 12, "bold"))
        for name in ("Muted", "Hint", "MutedCard"):
            s.configure(name+".TLabel", foreground=p['muted'], font=("Segoe UI", 9))
        s.configure("Readout.TLabel", foreground=accent, font=("Segoe UI", 10, "bold"))
        for name in ("Notice", "Badge", "Error"):
            s.configure(name+".TLabel", background=p['notice'], foreground=p['notice_text'])
        s.configure("Metric.TLabel", background=bg, foreground=text, font=("Segoe UI", 11, "bold"))
        s.configure("Check.TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        s.configure("TButton", background=surface, foreground=text, padding=(10, 6))
        s.map("TButton", background=[("active", bg), ("pressed", bg)], foreground=[("disabled", p['muted'])])
        s.configure("Accent.TButton", background=accent, foreground=bg if dark else "#ffffff")
        s.map("Accent.TButton", background=[("active", curve), ("pressed", curve)])
        for name in ("TEntry", "TCombobox"):
            s.configure(name, fieldbackground=surface, foreground=text, insertcolor=text, selectbackground=accent, selectforeground=bg if dark else "#ffffff", padding=6, arrowcolor=text)
            s.map(name, fieldbackground=[("readonly", surface), ("focus", surface)], foreground=[("readonly", text)], selectbackground=[("!focus", surface)], selectforeground=[("!focus", text)])
        s.configure("Horizontal.TScale", background=surface, troughcolor=bg, bordercolor=p['border'])
        s.map("Horizontal.TScale", background=[("active", accent), ("pressed", accent)])
        s.configure("Vertical.TScrollbar", background=surface, troughcolor=bg, arrowcolor=text)
        s.map("Vertical.TScrollbar", background=[("active", accent), ("pressed", accent)])
        s.configure("TPanedwindow", background=bg)
        s.configure("TNotebook", background=bg, bordercolor=p['border'])
        s.configure("TNotebook.Tab", background=bg, foreground=text, padding=(12, 6))
        s.map("TNotebook.Tab", background=[("selected", surface), ("active", surface)], foreground=[("selected", accent)])
        s.configure("TSeparator", background=p['border'])
        self.option_add("*TCombobox*Listbox.background", surface)
        self.option_add("*TCombobox*Listbox.foreground", text)
        self.option_add("*TCombobox*Listbox.selectBackground", accent)
        self.option_add("*TCombobox*Listbox.selectForeground", bg if dark else "#ffffff")
        # Existing pop-down lists also need refreshing after a theme change.
        def update_popdowns(widget):
            if isinstance(widget, ttk.Combobox):
                pop = self.tk.call("ttk::combobox::PopdownWindow", str(widget))
                self.tk.call(str(pop)+".f.l", "configure", "-background", surface, "-foreground", text,
                             "-selectbackground", accent, "-selectforeground", bg if dark else "#ffffff")
            for child in widget.winfo_children(): update_popdowns(child)
        update_popdowns(self)
        self.warning.configure(background=p['notice'], foreground=p['notice_text'])
        for c in (self.formcanvas, self.resultcanvas, *self.diagrams):
            c.configure(background=surface, highlightbackground=p['border'])
        self.schedule()
