"""Fast finite-horizon recurrence-required boundary-mediation metrics.
Rows are targets and columns are sources.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Sequence
import math
import numpy as np


def effective_rank(x, eps=1e-15):
    x=np.asarray(x,float); x=x[np.isfinite(x)&(x>eps)]
    if x.size==0:return 0.0
    p=x/x.sum(); return float(np.exp(-np.sum(p*np.log(p))))

def entropy_breadth(x):
    x=np.asarray(x,float); x=np.clip(x,0,None)
    if x.size==0 or x.sum()<=0:return 0.0
    p=x/x.sum(); p=p[p>0]
    return float(np.exp(-np.sum(p*np.log(p)))/len(x))

def psd_sqrt(M):
    vals,vecs=np.linalg.eigh((M+M.T)*.5)
    vals=np.clip(vals,0,None)
    return (vecs*np.sqrt(vals))@vecs.T

@dataclass
class Metrics:
    candidate: tuple[int,...]
    strength: float
    effective_rank: float
    direct_globality: float
    direct_score: float
    pair_globality: float|None
    wmi: float|None
    read_strength: float
    write_strength: float
    internal_strength: float
    singular_values: tuple[float,...]
    read_module_energy: tuple[float,...]
    write_module_energy: tuple[float,...]
    pair_module_energy: tuple[tuple[float,...],...]|None
    def to_dict(self): return asdict(self)

class FastBoundaryMediator:
    def __init__(self,A:np.ndarray,module_membership:np.ndarray,horizon=4,recurrence_steps=1):
        A=np.asarray(A,float)
        if A.ndim!=2 or A.shape[0]!=A.shape[1]:raise ValueError('A square')
        M=np.asarray(module_membership,float)
        if M.ndim!=2 or M.shape[1]!=A.shape[0]:raise ValueError('membership M x n')
        colsum=M.sum(axis=0)
        if not np.allclose(colsum,1,atol=1e-5):raise ValueError(('memberships must sum 1',colsum.min(),colsum.max()))
        self.A=A;self.M=M;self.n=A.shape[0];self.nmod=M.shape[0];self.L=int(horizon);self.q=int(recurrence_steps)
        self.rowGram=A@A.T;self.colGram=A.T@A
        self.row_module_energy=(A*A)@M.T
        self.col_module_energy=(A.T*A.T)@M.T
        self.GB=[];self.GC=[]
        for m in range(self.nmod):
            w=M[m]
            self.GB.append((A*w[None,:])@A.T)
            self.GC.append(A.T@(A*w[:,None]))
    def _base(self,S):
        S=np.array(sorted(set(map(int,S))),dtype=int);k=len(S)
        if k==0 or np.any(S<0) or np.any(S>=self.n):raise ValueError(S)
        Ass=self.A[np.ix_(S,S)]
        BBT=self.rowGram[np.ix_(S,S)]-Ass@Ass.T
        CTC=self.colGram[np.ix_(S,S)]-Ass.T@Ass
        # symmetrize numerical residuals
        BBT=(BBT+BBT.T)*.5;CTC=(CTC+CTC.T)*.5
        powers=[];P=np.eye(k)
        Wc=np.zeros((k,k));Wo=np.zeros((k,k))
        for _ in range(self.L):
            powers.append(P.copy())
            Wc+=P@BBT@P.T
            Wo+=P.T@CTC@P
            P=Ass@P
        Ap=np.linalg.matrix_power(Ass,self.q)
        sqrtWo=psd_sqrt(Wo)
        K=sqrtWo@Ap@Wc@Ap.T@sqrtWo
        vals=np.linalg.eigvalsh((K+K.T)*.5)
        sv=np.sqrt(np.clip(vals,0,None))[::-1]
        sv=sv[sv>1e-14]
        strength=float(sv.sum())
        deff=effective_rank(sv)
        # direct in/out module breadth, excluding candidate internal links
        read=self.row_module_energy[S].sum(axis=0)
        write=self.col_module_energy[S].sum(axis=0)
        Ms=self.M[:,S]
        # read: source t belongs to module; write: target t belongs to module
        internal_sq=Ass*Ass
        read-=np.einsum('st,mt->m',internal_sq,Ms)
        write-=np.einsum('ts,mt->m',internal_sq,Ms)
        read=np.clip(read,0,None);write=np.clip(write,0,None)
        gd=math.sqrt(entropy_breadth(read)*entropy_breadth(write))
        ds=float(strength*(deff/k)*gd)
        return S,Ass,powers,Ap,Wc,Wo,sv,strength,deff,read,write,gd,ds,BBT,CTC
    def direct_score(self,S):
        return float(self._base(S)[12])

    def metrics(self,S,full_pair=False):
        S,Ass,powers,Ap,Wc,Wo,sv,strength,deff,read,write,gd,ds,BBT,CTC=self._base(S);k=len(S)
        pair=None;pg=None;wmi=None
        if full_pair:
            Wcs=[];Wos=[];Ms=self.M[:,S]
            for m in range(self.nmod):
                D=np.diag(Ms[m])
                Bb=self.GB[m][np.ix_(S,S)]-Ass@D@Ass.T
                Cc=self.GC[m][np.ix_(S,S)]-Ass.T@D@Ass
                Bb=(Bb+Bb.T)*.5;Cc=(Cc+Cc.T)*.5
                wc=np.zeros((k,k));wo=np.zeros((k,k))
                for P in powers:
                    wc+=P@Bb@P.T
                    wo+=P.T@Cc@P
                Wcs.append(wc);Wos.append(wo)
            pair=np.zeros((self.nmod,self.nmod))
            for target in range(self.nmod):
                for source in range(self.nmod):
                    pair[target,source]=max(0.0,float(np.trace(Wos[target]@Ap@Wcs[source]@Ap.T)))
            pg=float(effective_rank(pair.ravel())/(self.nmod*self.nmod))
            wmi=float(strength*(deff/k)*pg)
        return Metrics(tuple(S.tolist()),strength,deff,gd,ds,pg,wmi,float(np.sqrt(max(0,np.trace(BBT)))),float(np.sqrt(max(0,np.trace(CTC)))),float(np.linalg.norm(Ass,'fro')),tuple(map(float,sv)),tuple(map(float,read)),tuple(map(float,write)),None if pair is None else tuple(tuple(map(float,r)) for r in pair))
