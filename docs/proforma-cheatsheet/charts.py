import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch
import numpy as np
plt.rcParams["font.family"] = "Liberation Sans"
TEAL="#1a939b"; TEAL2="#8fc9cd"; LIGHT="#eff6f9"; INK="#0b0b0b"; INK2="#52514e"; MUTED="#c9c8c2"; SURF="#ffffff"
W=7.2
def save(fig,name): fig.savefig(name,dpi=220,bbox_inches="tight",facecolor=SURF,pad_inches=0.05); plt.close(fig)
def clean(ax):
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED); ax.set_yticks([]); ax.tick_params(axis="x",length=0,labelsize=11,colors=INK)

# 1. OC vs new contracts mix by year ---------------------------------------------------
fig,ax=plt.subplots(figsize=(W,2.6)); clean(ax)
yrs=["Year 1","Year 2","Year 3"]; oc=np.array([75,25,0]); new=100-oc
ax.bar(yrs,oc,width=0.55,color=TEAL,edgecolor=SURF,linewidth=2)
ax.bar(yrs,new,bottom=oc,width=0.55,color=TEAL2,edgecolor=SURF,linewidth=2)
labels_oc=["Most OC","~25% OC","0% OC"]
for i in range(3):
    if oc[i]>0: ax.text(i,oc[i]/2,labels_oc[i],ha="center",va="center",fontsize=10.5,color="white",fontweight="bold")
    else: ax.text(i,-9,"0% OC",ha="center",va="center",fontsize=10,color=INK2)
    ax.text(i,oc[i]+new[i]/2,"New contracts",ha="center",va="center",fontsize=10,color=INK)
ax.set_ylim(-14,112); ax.set_xlim(-0.6,2.6)
ax.plot([-0.45,-0.45],[0,100],color=INK,lw=2); ax.text(-0.5,104,"Close = Day 1 of Year 1",ha="left",va="bottom",fontsize=10,fontweight="bold",color=INK)
ax.text(2.55,104,"Share of events held each year",ha="right",va="bottom",fontsize=9.5,color=INK2)
save(fig,"ocmix.png")

# 2. Attachment ramp + bar switch ----------------------------------------------
fig,(a1,a2)=plt.subplots(1,2,figsize=(W,2.5),gridspec_kw=dict(wspace=0.35))
clean(a1); clean(a2)
vals=[30,60,100]
a1.bar(yrs,vals,width=0.55,color=[TEAL2,TEAL2,TEAL],edgecolor="none")
for i,v in enumerate(vals): a1.text(i,v+3,f"{v}%",ha="center",va="bottom",fontsize=10.5,fontweight="bold",color=INK)
a1.axhline(100,color=INK2,lw=1.3,ls=(0,(4,3)))
a1.text(-0.45,103,"Walters avg attachment",ha="left",va="bottom",fontsize=9,color=INK2)
a1.set_ylim(0,128); a1.set_xlim(-0.6,2.6)
a1.set_title("Typical attachment ramp (our assumption)",fontsize=10.5,color=INK,loc="left",pad=8)
x=np.array([0,1.2,1.2,3]); y=np.array([0,0,1,1])
a2.step(x,y,where="post",color=TEAL,lw=2.5); a2.fill_between([1.2,3],0,1,color=LIGHT,step="post")
a2.set_xlim(0,3); a2.set_ylim(0,1.28); a2.set_xticks([0.5,2.1]); a2.set_xticklabels(["Before license","Licensed"])
a2.text(2.1,1.04,"In-house bar on",ha="center",va="bottom",fontsize=9,color=INK2); a2.text(0.6,0.08,"off",ha="center",va="bottom",fontsize=9,color=INK2)
a2.set_title("Bar: on/off switch (liquor license)",fontsize=10.5,color=INK,loc="left",pad=8)
save(fig,"ramp.png")

# 3. Market: three zones ---------------------------------------------------------------
fig,ax=plt.subplots(figsize=(W,2.9)); ax.set_aspect("equal"); ax.axis("off")
ax.set_xlim(-3.0,4.2); ax.set_ylim(-1.75,1.75)
ax.add_patch(Ellipse((-0.4,0),5.0,3.2,fc="#f7f7f5",ec=MUTED,lw=1.5))          # region
ax.add_patch(Circle((-1.0,0),1.15,fc=LIGHT,ec=TEAL,lw=1.8,ls=(0,(5,3))))       # hub ring
ax.add_patch(Circle((-1.0,0),0.14,fc=TEAL,ec="none")); ax.text(-1.0,-0.28,"Hub",ha="center",va="top",fontsize=10,fontweight="bold",color=INK)
ax.text(-1.0,0.78,"90 min",ha="center",va="center",fontsize=9.5,color=TEAL,fontweight="bold")
ax.text(-0.4,-1.42,"Current market (region)",ha="center",va="center",fontsize=9.5,color=INK2)
def venue(x,y,n):
    ax.add_patch(Circle((x,y),0.17,fc=INK,ec="none")); ax.text(x,y,str(n),ha="center",va="center",fontsize=9,color="white",fontweight="bold")
venue(-1.6,0.35,1); venue(1.2,0.45,2); venue(3.4,-0.6,3)
ax.text(3.4,0.9,"New market",ha="center",va="center",fontsize=9.5,color=INK2)
save(fig,"market.png")
print("charts done")
