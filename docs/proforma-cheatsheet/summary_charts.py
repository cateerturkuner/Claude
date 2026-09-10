import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
from PIL import Image
plt.rcParams["font.family"]="Liberation Sans"
TEAL="#1a939b"; TEAL2="#8fc9cd"; LIGHT="#eff6f9"; INK="#0b0b0b"; INK2="#52514e"; MUTED="#c9c8c2"; SURF="#ffffff"; GREY="#b9b8b3"; DARK="#0f5f65"
def clean(ax):
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED); ax.set_yticks([]); ax.tick_params(axis="x",length=0,labelsize=9.5,colors=INK)
def save(fig,name):
    fig.savefig(name,dpi=150,bbox_inches="tight",facecolor=SURF,pad_inches=0.05); plt.close(fig)
    im=Image.open(name).convert("RGBA"); bg=Image.new("RGBA",im.size,(255,255,255,255)); bg.alpha_composite(im)
    bg.convert("RGB").quantize(colors=48,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).save(name,optimize=True)
per=["2024","2025","LTM Jul-26","Year 1","Year 2","Year 3"]
# Events: historical (grey) then OC/new
fig,ax=plt.subplots(figsize=(3.6,2.3)); clean(ax)
hist=[42,43,39,0,0,0]; oc=[0,0,0,24,1,0]; new=[0,0,0,16,64,80]
x=np.arange(6)
ax.bar(x,hist,color=GREY,width=0.62); ax.bar(x,oc,color=TEAL,width=0.62); ax.bar(x,new,bottom=oc,color=TEAL2,width=0.62,edgecolor=SURF,linewidth=1)
for i,t in enumerate([42,43,39,40,65,80]): ax.text(i,t+2,str(t),ha="center",va="bottom",fontsize=9,fontweight="bold",color=INK)
ax.set_xticks(x); ax.set_xticklabels(["2024","2025","LTM","Y1","Y2","Y3"]); ax.set_ylim(0,95)
ax.text(0,90,"Actual",fontsize=8.5,color=INK2); ax.text(3.0,90,"OC",fontsize=8.5,color=TEAL,fontweight="bold"); ax.text(3.6,90,"New",fontsize=8.5,color="#3f8f96",fontweight="bold")
ax.set_title("Events per year",fontsize=10,color=INK,loc="left",pad=6)
save(fig,"s_events.png")
# Revenue & EBITDA ($000s)
fig,ax=plt.subplots(figsize=(3.6,2.3)); clean(ax)
rev=[466.5,437.7,560.8,906.4,1749.6,2602.1]; ebitda=[-96.1,-97.5,-23.7,11.2,604.0,1168.1]
w=0.36
ax.bar(x-w/2,rev,width=w,color=TEAL2); ax.bar(x+w/2,ebitda,width=w,color=TEAL)
for i,v in enumerate(rev): ax.text(i-w/2,v+40,f"{v/1000:.1f}" if v>=1000 else f"{v:.0f}",ha="center",va="bottom",fontsize=7.5,color=INK)
for i,v in enumerate(ebitda): ax.text(i+w/2,(v+40) if v>0 else (v-30),f"{v/1000:.1f}" if v>=1000 else f"{v:.0f}",ha="center",va="bottom" if v>0 else "top",fontsize=7.5,color=INK)
ax.axhline(0,color=MUTED,lw=1)
ax.set_xticks(x); ax.set_xticklabels(["2024","2025","LTM","Y1","Y2","Y3"]); ax.set_ylim(-330,3000)
ax.text(0-0.2,2750,"Revenue",fontsize=8.5,color="#3f8f96",fontweight="bold"); ax.text(1.4,2750,"EBITDA",fontsize=8.5,color=TEAL,fontweight="bold")
ax.set_title(r"Revenue and EBITDA (\$000s; 1.7 = \$1.7M)",fontsize=10,color=INK,loc="left",pad=6)
save(fig,"s_pnl.png")
print("ok")
