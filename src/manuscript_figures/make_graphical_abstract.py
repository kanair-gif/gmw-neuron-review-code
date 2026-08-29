import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib import rcParams
rcParams['font.family'] = 'DejaVu Sans'
fig, ax = plt.subplots(figsize=(4,4), dpi=300)
ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')

def box(x,y,w,h,text,fc,ec='#263238',fs=8,weight='normal',radius=0.025):
    p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0.01,rounding_size={radius}',facecolor=fc,edgecolor=ec,linewidth=1.1)
    ax.add_patch(p); ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fs,weight=weight,color='#17212b')
    return p

def arrow(x1,y1,x2,y2,color,lw=1.5,rad=0):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=9,linewidth=lw,color=color,connectionstyle=f'arc3,rad={rad}'))

ax.text(0.5,0.965,'GLOBAL MEDIATION WORKSPACE',ha='center',va='top',fontsize=12,weight='bold')
ax.text(0.5,0.925,'A control-theoretic signature of global access',ha='center',va='top',fontsize=7.5,color='#455a64')

# network layer
sources=[('Visual',0.05,0.79),('Memory',0.05,0.68),('Value',0.05,0.57)]
targets=[('Action',0.79,0.79),('Executive',0.79,0.68),('Memory',0.79,0.57)]
for t,x,y in sources: box(x,y,0.16,0.065,t,'#d9f0ea',fs=7)
for t,x,y in targets: box(x,y,0.16,0.065,t,'#fde2c2',fs=7)
box(0.36,0.61,0.28,0.20,'Candidate subnetwork\n\nreceive  →  transform  →  broadcast','#e8edf6',fs=8.5,weight='bold')
for _,x,y in sources: arrow(x+0.16,y+0.032,0.36,0.70,'#00897b',1.4)
for _,x,y in targets: arrow(0.64,0.70,x,y+0.032,'#ef6c00',1.4)
ax.text(0.50,0.585,'same remainder supplies inputs and receives outputs',ha='center',fontsize=6.5,color='#455a64')

# signature layer
ax.text(0.5,0.515,'GMW SIGNATURE',ha='center',fontsize=9,weight='bold')
items=[('Capacity','available\nread/write gain','#dceaf7'),('Alignment','same modes\nreceive and send','#e5e1f3'),('Mode diversity','independent\nmediation routes','#dff1e7'),('Routed breadth','source–target\ncoverage','#f8e4d3')]
xs=[0.05,0.285,0.52,0.755]
for x,(a,b,c) in zip(xs,items):
    box(x,0.37,0.19,0.115,f'{a}\n{b}',c,fs=6.7,weight='bold')

# result layer
ax.text(0.5,0.315,'MACAQUE ECoG: DEEP ANESTHESIA',ha='center',fontsize=9,weight='bold')
box(0.08,0.08,0.35,0.18,'AWAKE\n\ndifferentiated routes\nacross cortical systems','#e7f3ee',fs=7.5,weight='bold')
box(0.57,0.08,0.35,0.18,'DEEP ANESTHESIA\n\nshort-lag gain ↑\nalignment & differentiation ↓','#f7e7df',fs=7.5,weight='bold')
# awake routes
for yy in [0.115,0.155,0.195]:
    arrow(0.13,yy,0.38,yy,'#00897b',1.2)
# deep routes thick and convergent
arrow(0.62,0.13,0.86,0.17,'#d95f02',2.2)
arrow(0.62,0.21,0.86,0.17,'#d95f02',2.2)
arrow(0.43,0.17,0.57,0.17,'#455a64',1.2)
ax.text(0.5,0.035,'The signature separates dynamical magnitude from global organization.',ha='center',fontsize=6.4,color='#37474f')
fig.savefig('/mnt/data/GMW_Neuron_V22/submission/graphical_abstract.png',dpi=300,bbox_inches='tight',pad_inches=0.02)
fig.savefig('/mnt/data/GMW_Neuron_V22/submission/graphical_abstract.pdf',bbox_inches='tight',pad_inches=0.02)
