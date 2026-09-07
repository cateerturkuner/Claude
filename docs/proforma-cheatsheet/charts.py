import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle
import matplotlib.font_manager as fm

plt.rcParams["font.family"] = "Liberation Sans"
BLUE="#2a78d6"; ORANGE="#eb6834"; INK="#0b0b0b"; INK2="#52514e"; MUTED="#c9c8c2"; LIGHT="#eef2f8"; SURF="#ffffff"
W=7.2

def save(fig,name):
    fig.savefig(name,dpi=220,bbox_inches="tight",facecolor=SURF,pad_inches=0.05); plt.close(fig)

# 1. Timeline ---------------------------------------------------------------
fig,ax=plt.subplots(figsize=(W,2.1)); ax.set_xlim(-0.25,3.25); ax.set_ylim(-1.1,1.6); ax.axis("off")
for i,lab in enumerate(["Year 1","Year 2","Year 3"]):
    ax.add_patch(FancyBboxPatch((i+0.02,-0.3),0.96,0.6,boxstyle="round,pad=0,rounding_size=0.06",fc=LIGHT if i else BLUE,ec="none"))
    ax.text(i+0.5,0,lab,ha="center",va="center",fontsize=13,fontweight="bold",color="white" if i==0 else INK)
ax.plot([0,0],[-0.75,0.45],color=INK,lw=2)
ax.text(0,-0.95,"CLOSE = Day 1 of Year 1",ha="center",va="center",fontsize=10.5,fontweight="bold",color=INK)
# OC bracket
ax.annotate("",xy=(0.02,0.62),xytext=(0.98,0.62),arrowprops=dict(arrowstyle="-",color=ORANGE,lw=2.2))
ax.text(0.5,0.78,"OC events",ha="center",va="bottom",fontsize=11,fontweight="bold",color=ORANGE)
ax.text(0.5,1.15,"booked BEFORE close",ha="center",va="bottom",fontsize=9.5,color=INK2)
# New bracket
ax.annotate("",xy=(1.02,0.62),xytext=(2.98,0.62),arrowprops=dict(arrowstyle="-",color=BLUE,lw=2.2))
ax.text(2.0,0.78,"New contracts",ha="center",va="bottom",fontsize=11,fontweight="bold",color=BLUE)
ax.text(2.0,1.15,"booked AFTER close (any year)",ha="center",va="bottom",fontsize=9.5,color=INK2)
# dashed continuation of new contracts into Y1
ax.annotate("",xy=(0.02,0.52),xytext=(0.98,0.52),arrowprops=dict(arrowstyle="-",color=BLUE,lw=2.2,ls=(0,(3,3))))
save(fig,"timeline.png")

# 2. Attachment ramp + bar switch ----------------------------------------------
fig,(a1,a2)=plt.subplots(1,2,figsize=(W,2.5),gridspec_kw=dict(wspace=0.35))
for ax in (a1,a2):
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED); ax.set_yticks([]); ax.tick_params(axis="x",length=0,labelsize=10.5,colors=INK)
yrs=["Year 1","Year 2","Year 3"]
vals=[0.35,0.7,1.0]
bars=a1.bar(yrs,vals,width=0.55,color=[LIGHT,"#9dbfe9",BLUE],edgecolor="none")
a1.axhline(1.0,color=INK2,lw=1.5,ls=(0,(4,3)))
a1.text(2.35,1.02,"Walters avg\nattachment",ha="right",va="bottom",fontsize=9,color=INK2)
a1.set_ylim(0,1.35); a1.set_title("Most vendor services: ramp up to\nWalters average by Year 3",fontsize=10.5,color=INK,loc="left",pad=8)
# bar step
import numpy as np
x=np.array([0,1.2,1.2,3]); y=np.array([0,0,1,1])
a2.step(x,y,where="post",color=BLUE,lw=2.5)
a2.fill_between([1.2,3],0,1,color=LIGHT,step="post")
a2.set_xlim(0,3); a2.set_ylim(0,1.35); a2.set_xticks([0.5,1.7,2.6]); a2.set_xticklabels(["Before\nlicense","Licensed","→"])
a2.text(2.1,1.06,"In-house bar on",ha="center",va="bottom",fontsize=9,color=INK2)
a2.text(0.6,0.08,"off",ha="center",va="bottom",fontsize=9,color=INK2)
a2.set_title("Bar: on/off switch\n(needs a liquor license)",fontsize=10.5,color=INK,loc="left",pad=8)
save(fig,"ramp.png")

# 3. Speed to implement ---------------------------------------------------------
fig,ax=plt.subplots(figsize=(W,2.4))
items=[("Photography · DJ · Stationery","Quick — set pricing, start selling",0.28,BLUE),
       ("Bar (in-house)","Off until liquor license, then on",0.5,BLUE),
       ("Catering","Attach slowly — test, don't flip at close",0.72,"#9dbfe9"),
       ("Floral · Bakery","Depends on hub distance — may be zero",0.92,LIGHT)]
for i,(name,note,v,c) in enumerate(items):
    y=len(items)-1-i
    ax.barh(y,v,height=0.55,color=c,edgecolor="none")
    ax.text(-0.02,y,name,ha="right",va="center",fontsize=10.5,fontweight="bold",color=INK)
    ax.text(v+0.02,y,note,ha="left",va="center",fontsize=9.5,color=INK2)
ax.set_xlim(0,1.75); ax.set_ylim(-0.6,len(items)-0.4); ax.axis("off")
ax.annotate("",xy=(1.0,-0.55),xytext=(0,-0.55),arrowprops=dict(arrowstyle="->",color=INK2,lw=1.2))
ax.text(0,-0.75,"Fast to implement",fontsize=9,color=INK2,va="top"); ax.text(1.0,-0.75,"Slower",fontsize=9,color=INK2,va="top",ha="right")
ax.set_ylim(-1.1,len(items)-0.4)
save(fig,"speed.png")

# 4. Market / hub ring ----------------------------------------------------------------
fig,ax=plt.subplots(figsize=(W,2.6)); ax.set_aspect("equal"); ax.axis("off")
ax.set_xlim(-2.2,5.2); ax.set_ylim(-1.45,1.45)
ax.add_patch(Circle((0,0),1.25,fc=LIGHT,ec=BLUE,lw=1.8,ls=(0,(5,3))))
ax.add_patch(Circle((0,0),0.16,fc=BLUE,ec="none")); ax.text(0,-0.32,"Hub",ha="center",va="top",fontsize=10,fontweight="bold",color=INK)
ax.text(0,0.85,"within 90 min",ha="center",va="center",fontsize=9.5,color=BLUE,fontweight="bold")
for (x,y) in [(-0.7,0.3),(0.55,-0.55)]:
    ax.add_patch(Circle((x,y),0.09,fc=ORANGE,ec="none"))
ax.add_patch(Circle((3.1,0.55),0.09,fc=ORANGE,ec="none"))
ax.text(-1.55,-1.3,"Venue",fontsize=9,color=INK2,va="center"); ax.add_patch(Circle((-1.85,-1.3),0.07,fc=ORANGE,ec="none"))
ax.text(1.75,0.05,"CURRENT MARKET",fontsize=10.5,fontweight="bold",color=BLUE,va="bottom")
ax.text(1.75,-0.02,"Inside the ring → model vendor services in Y1–Y3",fontsize=9.5,color=INK2,va="top")
ax.text(1.75,-0.75,"NEW MARKET",fontsize=10.5,fontweight="bold",color=INK2,va="bottom")
ax.text(1.75,-0.82,"Outside the ring → venue must stand on its own;\nvendor services come later, once volume exists",fontsize=9.5,color=INK2,va="top")
ax.text(3.1,0.72,"too far → $0 for that hub's service",fontsize=9,color=INK2,ha="center",va="bottom")
save(fig,"market.png")
print("charts done")
