"""Beam Designer desktop prototype. Section properties are synthetic."""
import tkinter as tk
from tkinter import ttk

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
        m = left*x - sum(p*(x-at) for p, at in points if at < x)
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
    def peak(values):
        i = max(range(len(values)), key=lambda j: abs(values[j]))
        return abs(values[i]), xs[i], values[i]
    vmax, vx, _ = peak(shear); mmax, mx, msigned = peak(moment); dmax, ddx, _ = peak(disp)
    return dict(xs=xs, shear=shear, moment=moment, deflection=disp, left=left, right=right,
                fixed=fixed, vmax=vmax, vx=vx, mmax=mmax, mx=mx, msigned=msigned,
                dmax=dmax, dx=ddx, stress=mmax*12/section["Sx"], allowable=allowable,
                limit=span*12/divisor)


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Beam Designer"); self.geometry("1280x900"); self.minsize(980,700)
        self.span=tk.DoubleVar(value=20); self.support=tk.StringVar(value="Simply supported")
        self.section=tk.StringVar(value="W12x26"); self.allow=tk.StringVar(value="")
        self.divisor=tk.IntVar(value=360); self.theme=tk.StringVar(value="Light")
        self.points=[]; self.uniforms=[]
        self.build(); self.add_uniform(1,0,20); self.theme_changed(); self.update()

    def build(self):
        head=ttk.Frame(self,padding=14); head.pack(fill="x")
        ttk.Label(head,text="BEAM DESIGNER",font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Label(head,text="Color scheme").pack(side="right",padx=5)
        pick=ttk.Combobox(head,textvariable=self.theme,values=list(THEMES),state="readonly",width=14); pick.pack(side="right"); pick.bind("<<ComboboxSelected>>",lambda e:self.theme_changed())
        ttk.Label(self,text="Shear, moment and deflection",font=("Segoe UI",22,"bold")).pack(anchor="w",padx=18)
        self.warning=tk.Label(self,text="Prototype properties are synthetic and unsuitable for real design. Results are preliminary screens, not a code-compliant design.",anchor="w",justify="left",padx=12,pady=10,wraplength=1100); self.warning.pack(fill="x",padx=18,pady=10)
        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=18)
        left=ttk.Frame(pan,width=365); pan.add(left,weight=0)
        self.formcanvas=tk.Canvas(left,width=350,highlightthickness=0); sb=ttk.Scrollbar(left,orient="vertical",command=self.formcanvas.yview); self.formcanvas.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); self.formcanvas.pack(fill="both",expand=True)
        self.form=ttk.Frame(self.formcanvas,padding=10); self.fwin=self.formcanvas.create_window((0,0),window=self.form,anchor="nw")
        self.form.bind("<Configure>",lambda e:self.formcanvas.configure(scrollregion=self.formcanvas.bbox("all"))); self.formcanvas.bind("<Configure>",lambda e:self.formcanvas.itemconfigure(self.fwin,width=e.width))
        right=ttk.Frame(pan); pan.add(right,weight=1)
        self.canvas=tk.Canvas(right,highlightthickness=0); rs=ttk.Scrollbar(right,orient="vertical",command=self.canvas.yview); self.canvas.configure(yscrollcommand=rs.set); rs.pack(side="right",fill="y"); self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.update())
        f=self.form; ttk.Label(f,text="Beam setup",font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.choice(f,"Support",self.support,["Simply supported","Cantilever"])
        self.slider(f,"Span (ft)",self.span,0,100,.5)
        self.choice(f,"Steel W-shape · synthetic",self.section,list(SECTIONS))
        ttk.Label(f,text="Allowable bending stress (ksi, optional)").pack(anchor="w",pady=(8,2)); e=ttk.Entry(f,textvariable=self.allow); e.pack(fill="x"); e.bind("<KeyRelease>",lambda e:self.update())
        self.slider(f,"Deflection limit L/",self.divisor,120,1200,1)
        ttk.Label(f,text="Loads: positive is downward, negative is upward. Self-weight excluded.",wraplength=320).pack(anchor="w",pady=10)
        self.pbox=ttk.LabelFrame(f,text="Point loads"); self.pbox.pack(fill="x",pady=4)
        self.wbox=ttk.LabelFrame(f,text="Uniform loads"); self.wbox.pack(fill="x",pady=4)
        ttk.Button(f,text="+ Add point load",command=self.add_point).pack(fill="x",pady=2); ttk.Button(f,text="+ Add uniform load",command=self.add_uniform).pack(fill="x",pady=2)
        ttk.Label(self,text="Strong-axis analysis · Demonstration assumptions: A992, Fy=50 ksi, E=29,000 ksi · Results do not establish member adequacy.",padding=8).pack(fill="x")

    def choice(self,parent,label,var,values):
        ttk.Label(parent,text=label).pack(anchor="w",pady=(8,2)); w=ttk.Combobox(parent,textvariable=var,values=values,state="readonly"); w.pack(fill="x"); w.bind("<<ComboboxSelected>>",lambda e:self.update())
    def slider(self,parent,label,var,lo,hi,res):
        ttk.Label(parent,text=label).pack(anchor="w",pady=(8,0)); s=tk.Scale(parent,from_=lo,to=hi,resolution=res,variable=var,orient="horizontal",showvalue=True,command=lambda v:self.update()); s.pack(fill="x")
    def add_point(self,load=5,pos=10): self.add_load(self.pbox,self.points,"p",[load,pos])
    def add_uniform(self,load=0,a=0,b=None): self.add_load(self.wbox,self.uniforms,"w",[load,a,self.span.get() if b is None else b])
    def add_load(self,box,store,kind,values):
        row=ttk.Frame(box,padding=3); row.pack(fill="x"); vars=[]
        limits=[(-20,20,.25),(0,100,.25)] if kind=="p" else [(-5,5,.1),(0,100,.25),(0,100,.25)]
        for i,(val,(lo,hi,res)) in enumerate(zip(values,limits)):
            var=tk.DoubleVar(value=val); vars.append(var); tk.Scale(row,from_=lo,to=hi,resolution=res,variable=var,orient="horizontal",showvalue=True,length=100,command=lambda v:self.update()).pack(side="left",fill="x",expand=True)
        item=(row,vars); store.append(item); ttk.Button(row,text="×",width=2,command=lambda:self.remove(store,item)).pack(side="right"); self.update()
    def remove(self,store,item): store.remove(item); item[0].destroy(); self.update()

    def update(self):
        if not hasattr(self,"canvas"): return
        try:
            span=self.span.get(); pts=[(v[0].get(),min(span,v[1].get())) for _,v in self.points]
            loads=[(v[0].get(),min(span,v[1].get()),min(span,v[2].get())) for _,v in self.uniforms]; loads=[v for v in loads if v[2]>v[1]]
            allowable=float(self.allow.get()) if self.allow.get().strip() else None
            if allowable is not None and allowable<=0: raise ValueError("Allowable stress must be positive.")
            self.draw(calculate(span,self.support.get(),pts,loads,SECTIONS[self.section.get()],allowable,self.divisor.get()),span,pts,loads)
        except (ValueError,tk.TclError,ZeroDivisionError) as ex:
            self.canvas.delete("all"); self.status=str(ex)

    def draw(self,r,span,pts,loads):
        c=self.canvas; c.delete("all"); bg,surf,fg,accent,curve,load=THEMES[self.theme.get()]; width=max(550,c.winfo_width()-25); x=15; y=18
        def text(s,yy,size=10,bold=False): c.create_text(x,yy,text=s,anchor="nw",fill=fg,font=("Segoe UI",size,"bold" if bold else "normal"),width=width-30)
        text(f"{span:.1f} ft {self.support.get().lower()} · {self.section.get()}",y,16,True); y+=32
        sec=SECTIONS[self.section.get()]
        text(f"Synthetic properties: W={sec['weight']} lb/ft, d={sec['depth']} in, bf={sec['bf']} in, tw={sec['tw']} in, tf={sec['tf']} in, Ix={sec['Ix']} in⁴, Sx={sec['Sx']} in³. Self-weight excluded.",y,9); y+=40
        reaction=(f"Reactions: left {r['left']:.2f} kip, right {r['right']:.2f} kip (upward-positive)" if self.support.get()=="Simply supported" else f"Fixed reaction: {r['left']:.2f} kip upward-positive · fixed-end moment {r['fixed']:.2f} kip-ft")
        rows=[reaction,f"Peak shear |V| = {r['vmax']:.2f} kip at x={r['vx']:.2f} ft",f"Peak moment |M| = {r['mmax']:.2f} kip-ft at x={r['mx']:.2f} ft (signed {r['msigned']:.2f})",f"Preliminary stress |M|/Sx = {r['stress']:.2f} ksi"+(f" · {'within' if r['stress']<=r['allowable'] else 'above'} entered limit {r['allowable']:.2f} ksi" if r['allowable'] else " · no allowable entered"),f"Peak |deflection| = {r['dmax']:.3f} in at x={r['dx']:.2f} ft · L/{self.divisor.get()} = {r['limit']:.3f} in ({'within' if r['dmax']<=r['limit'] else 'exceeds'} selected limit)"]
        for line in rows:
            c.create_rectangle(x,y,width-12,y+28,fill=surf,outline="#9aa8b8"); c.create_text(x+8,y+14,text=line,anchor="w",fill=fg,font=("Segoe UI",9,"bold")); y+=33
        y+=8; self.beam(y,width,span,pts,loads,fg,load); y+=145
        for title,key,unit,down in [("Shear diagram (positive upward)","shear","kip",False),("Moment diagram (positive sagging)","moment","kip-ft",False),("Deflection diagram (positive downward)","deflection","in",True)]:
            y=self.plot(y,width,title,r["xs"],r[key],unit,down,curve,fg)
        c.configure(scrollregion=(0,0,width,y+20))

    def beam(self,y,w,span,pts,loads,fg,load):
        c=self.canvas; c.create_text(15,y,text="Beam and applied loads (+ downward)",anchor="nw",fill=fg,font=("Segoe UI",11,"bold")); y+=30; x0=60; x1=w-35; by=y+55
        c.create_line(x0,by,x1,by,fill=fg,width=4)
        if self.support.get()=="Cantilever": c.create_line(x0-8,by-30,x0-8,by+30,fill=fg,width=4)
        else:
            for xx in (x0,x1): c.create_polygon(xx-12,by+18,xx,by,xx+12,by+18,outline=fg,fill="",width=2)
        for p,pos in pts:
            xx=x0+(x1-x0)*pos/span; top=by-38 if p>=0 else by+38; c.create_line(xx,top,xx,by,fill=load,arrow=tk.LAST); c.create_text(xx,top-3,text=f"P {p:g} kip",fill=load,font=("Segoe UI",8))
        for q,a,b in loads:
            xa=x0+(x1-x0)*a/span; xb=x0+(x1-x0)*b/span; top=by-32 if q>=0 else by+32
            c.create_line(xa,top,xb,top,fill=load,width=2)
            for j in range(9):
                xx=xa+(xb-xa)*j/8; c.create_line(xx,top,xx,by,fill=load,arrow=tk.LAST)
            c.create_text((xa+xb)/2,top-4,text=f"w {q:g} kip/ft",fill=load,font=("Segoe UI",8))
        c.create_text((x0+x1)/2,by+35,text=f"Span {span:.2f} ft",fill=fg)

    def plot(self,y,w,title,xs,vals,unit,down,color,fg):
        c=self.canvas; x=15; c.create_text(x,y,text=title,anchor="nw",fill=fg,font=("Segoe UI",11,"bold")); y+=25
        left=x+50; right=w-18; top=y; bottom=y+95; lo=min(0,min(vals)); hi=max(0,max(vals))
        if hi-lo<1e-9: lo,hi=-1,1
        pad=(hi-lo)*.12; lo-=pad; hi+=pad
        def yy(v): return top+(v-lo)/(hi-lo)*(bottom-top) if down else top+(hi-v)/(hi-lo)*(bottom-top)
        zero=yy(0); c.create_line(left,zero,right,zero,fill="#8997a8")
        coords=[]
        for xx,v in zip(xs,vals): coords += [left+(right-left)*xx/(xs[-1] or 1),yy(v)]
        c.create_line(*coords,fill=color,width=2)
        c.create_text(x,top,text=unit,anchor="nw",fill=fg,font=("Segoe UI",8)); c.create_text(left,bottom+2,text="0 ft",anchor="nw",fill=fg,font=("Segoe UI",8)); c.create_text(right,bottom+2,text=f"{xs[-1]:.1f} ft",anchor="ne",fill=fg,font=("Segoe UI",8))
        return bottom+30

    def theme_changed(self):
        bg,surface,fg,accent,curve,load=THEMES[self.theme.get()]; self.configure(bg=bg)
        st=ttk.Style(self); st.configure("TFrame",background=bg); st.configure("TLabel",background=bg,foreground=fg); st.configure("TLabelframe",background=bg,foreground=fg); st.configure("TLabelframe.Label",background=bg,foreground=fg); st.configure("TCombobox",fieldbackground=surface,foreground=fg)
        if hasattr(self,"warning"): self.warning.configure(background=surface,foreground=fg)
        if hasattr(self,"canvas"): self.canvas.configure(background=bg); self.formcanvas.configure(background=bg); self.update()


if __name__ == "__main__":
    App().mainloop()
