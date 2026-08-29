import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib import font_manager
from pathlib import Path

OUT=Path('/mnt/data/GMW_Neuron_V22/submission')
font_path=font_manager.findfont('Arimo')
font_bold=font_manager.findfont(font_manager.FontProperties(family='Arimo', weight='bold'))
plt.rcParams['font.family']='Arimo'
plt.rcParams['pdf.fonttype']=42
plt.rcParams['ps.fonttype']=42

fig=plt.figure(figsize=(4,4),dpi=300,facecolor='white')
ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')

# Palette
ink='#18242d'; teal='#1f9a8a'; teal_light='#dff2ee'; orange='#e97818'; orange_light='#fde7d2'
blue='#5478a8'; blue_light='#e7edf6'; purple='#7766a9'; purple_light='#ece8f7'; green='#5a9b6e'; green_light='#e5f1e8'; gray='#586873'; light='#f5f7f8'

# Header
ax.text(0.5,0.958,'GLOBAL MEDIATION WORKSPACE',ha='center',va='center',fontsize=14.8,fontweight='bold',color=ink)
ax.text(0.5,0.925,'A control-theoretic signature of global access',ha='center',va='center',fontsize=8.8,color=gray)

# Helper
def box(x,y,w,h,fc,ec=ink,r=0.02,lw=1.4):
    p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0.008,rounding_size={r}',facecolor=fc,edgecolor=ec,linewidth=lw)
    ax.add_patch(p); return p

def arrow(x1,y1,x2,y2,color,lw=2.2,ms=12,alpha=1,z=1):
    p=FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=ms,linewidth=lw,color=color,alpha=alpha,zorder=z,shrinkA=1,shrinkB=1)
    ax.add_patch(p); return p

# Top conceptual panel
ax.text(0.07,0.865,'Distributed specialist systems (R)',fontsize=8.5,fontweight='bold',color=ink,ha='left')
# Specialists around central GMW
specs=[(0.06,0.735,'Visual',teal_light,teal),(0.06,0.59,'Memory',purple_light,purple),(0.77,0.735,'Action',orange_light,orange),(0.77,0.59,'Value',green_light,green)]
for x,y,label,fc,ec in specs:
    box(x,y,0.17,0.07,fc,ec,r=0.018,lw=1.3)
    ax.text(x+0.085,y+0.035,label,ha='center',va='center',fontsize=9.2,color=ink)

box(0.34,0.61,0.32,0.19,blue_light,blue,r=0.025,lw=1.7)
ax.text(0.50,0.742,'Candidate subnetwork (S)',ha='center',va='center',fontsize=9.2,fontweight='bold',color=ink)
ax.text(0.50,0.687,'receive  →  transform  →  broadcast',ha='center',va='center',fontsize=8.7,fontweight='bold',color=ink)
ax.text(0.50,0.642,'shared internal modes',ha='center',va='center',fontsize=8.2,color=gray)
# bidirectional arrows
for x,y,label,fc,ec in specs[:2]:
    arrow(x+0.17,y+0.035,0.34,0.705 if y>0.65 else 0.655,teal,lw=2.1,ms=10)
    arrow(0.34,0.675 if y>0.65 else 0.635,x+0.17,y+0.035,orange,lw=1.6,ms=9)
for x,y,label,fc,ec in specs[2:]:
    arrow(x,y+0.035,0.66,0.705 if y>0.65 else 0.655,teal,lw=1.6,ms=9)
    arrow(0.66,0.675 if y>0.65 else 0.635,x,y+0.035,orange,lw=2.1,ms=10)
ax.text(0.5,0.562,'The same remainder supplies inputs and receives mediated outputs',ha='center',va='center',fontsize=7.6,color=gray)

# Signature band
ax.text(0.5,0.512,'GMW SIGNATURE',ha='center',va='center',fontsize=12.2,fontweight='bold',color=ink)
items=[('Capacity','available\nread/write gain',blue_light,blue),('Alignment','same modes\nin and out',purple_light,purple),('Mode diversity','independent\nroutes',green_light,green),('Routed breadth','source–target\ncoverage',orange_light,orange)]
xs=[0.055,0.285,0.515,0.745]
for x,(title,sub,fc,ec) in zip(xs,items):
    box(x,0.405,0.20,0.08,fc,ec,r=0.015,lw=1.2)
    ax.text(x+0.10,0.458,title,ha='center',va='center',fontsize=7.8,fontweight='bold',color=ink)
    ax.text(x+0.10,0.424,sub,ha='center',va='center',fontsize=6.8,color=gray,linespacing=1.0)

# Empirical contrast
ax.text(0.5,0.355,'MACAQUE ECoG',ha='center',va='center',fontsize=11.2,fontweight='bold',color=ink)
# State boxes
box(0.075,0.11,0.34,0.19,teal_light,teal,r=0.025,lw=1.5)
box(0.585,0.11,0.34,0.19,orange_light,orange,r=0.025,lw=1.5)
ax.text(0.245,0.272,'AWAKE',ha='center',va='center',fontsize=10.0,fontweight='bold',color=ink)
ax.text(0.755,0.272,'DEEP ANESTHESIA',ha='center',va='center',fontsize=9.5,fontweight='bold',color=ink)
# Awake differentiated routes
for i,(yy,c) in enumerate([(0.225,teal),(0.202,blue),(0.179,purple),(0.156,green)]):
    arrow(0.13,yy,0.36,yy,c,lw=1.6,ms=8)
ax.text(0.245,0.128,'differentiated routes',ha='center',va='center',fontsize=7.8,color=ink)
# Deep state: one dominant line + faded lines
arrow(0.64,0.218,0.87,0.177,orange,lw=4.2,ms=12)
for yy,c in [(0.205,blue),(0.182,purple),(0.158,green)]:
    arrow(0.64,yy,0.85,yy,c,lw=1.1,ms=7,alpha=0.25)
ax.text(0.755,0.145,'gain ↑',ha='center',va='center',fontsize=8.5,fontweight='bold',color=ink)
ax.text(0.755,0.123,'alignment & diversity ↓',ha='center',va='center',fontsize=7.2,color=ink)
# state arrow
arrow(0.44,0.205,0.56,0.205,gray,lw=1.5,ms=9)

ax.text(0.5,0.055,'Dynamical magnitude and global organization can change in different directions.',ha='center',va='center',fontsize=7.4,color=gray)

png=OUT/'graphical_abstract.png'; pdf=OUT/'graphical_abstract.pdf'
fig.savefig(png,dpi=300,facecolor='white')
fig.savefig(pdf,dpi=300,facecolor='white')
plt.close(fig)
print(png,pdf)
