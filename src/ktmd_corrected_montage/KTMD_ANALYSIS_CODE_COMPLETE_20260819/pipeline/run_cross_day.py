#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from run_ktmd_state_v2 import combine_stats, fit_operator, choose_ridge, module_membership, beam_search, signature

AWAKE={'eyes_open','eyes_closed'}

def load_day(path:Path):
    plan=pd.read_csv(path/'block_plan.csv')
    z=np.load(path/'block_sufficient_stats.npz')
    stats={}
    for row in plan.itertuples(index=False):
        state=str(row.state); block=int(row.block); base=f'{state}__{block:02d}'
        stats[(state,block)]={
            'xx':z[f'{base}__xx'], 'yx':z[f'{base}__yx'], 'yy':z[f'{base}__yy'],
            'n':int(z[f'{base}__n'][0])}
    summary=json.loads((path/'summary.json').read_text())
    pairs=pd.read_csv(path/'bipolar_pairs.csv')
    return {'path':path,'date':str(summary['date']),'animal':summary['animal'],'stats':stats,'pairs':pairs,'summary':summary}

def keys(day, states): return sorted(k for k in day['stats'] if k[0] in set(states))
def combined(day,states): return combine_stats(day['stats'][k] for k in keys(day,states))
def state_operator(day,state,lam): return fit_operator(combined(day,[state]),lam)[0]
def awake_operator(day,lam): return fit_operator(combined(day,AWAKE),lam)[0]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--animal',required=True); ap.add_argument('--days',nargs='+',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    days=[load_day(p) for p in args.days]
    assert all(d['animal'].lower()==args.animal.lower() for d in days)
    first_pairs=days[0]['pairs'][['ch1','ch2','bipolar_id']].reset_index(drop=True)
    for d in days[1:]:
        pd.testing.assert_frame_equal(first_pairs,d['pairs'][['ch1','ch2','bipolar_id']].reset_index(drop=True))

    # Leave-one-day-out: candidate and lambda defined exclusively on other days.
    sigrows=[]; candrows=[]; ratrows=[]
    for held in days:
        train=[d for d in days if d is not held]
        train_awake_blocks=[d['stats'][k] for d in train for k in keys(d,AWAKE)]
        lam,cv=choose_ridge(train_awake_blocks)
        train_A=fit_operator(combine_stats(train_awake_blocks),lam)[0]
        membership,labels=module_membership(train_A)
        results=beam_search(train_A,membership,sizes=(3,4,5))
        models={'heldout_awake':awake_operator(held,lam),
                'deep_anesthesia':state_operator(held,'deep_anesthesia',lam)}
        for state in ('eyes_open','eyes_closed','recovery_eyes_closed','recovery_eyes_open'):
            if keys(held,[state]): models[state]=state_operator(held,state,lam)
        for k in (3,4,5):
            cand=tuple(results[k][0]); cs=';'.join(map(str,cand)); nodes=';'.join(first_pairs.iloc[list(cand)].bipolar_id)
            candrows.append({'fold':'LODO','heldout_date':held['date'],'training_dates':';'.join(d['date'] for d in train),'lambda':lam,'k':k,'candidate':cs,'nodes':nodes})
            local={}
            for ev,A in models.items():
                s=signature(A,membership,cand); local[ev]=s
                sigrows.append({'fold':'LODO','heldout_date':held['date'],'training_dates':';'.join(d['date'] for d in train),'lambda':lam,'k':k,'evaluation':ev,'candidate':cs,**s})
            base=local['heldout_awake']; rec={'fold':'LODO','heldout_date':held['date'],'training_dates':';'.join(d['date'] for d in train),'lambda':lam,'k':k,'candidate':cs}
            for metric in ('Q','Cspec','Aspec','Deff_frac','Gpair','Oorg','top_share','WMI'):
                for ev in ('deep_anesthesia','recovery_eyes_closed','recovery_eyes_open'):
                    if ev in local:
                        rec[f'{metric}_{ev}_over_awake']=local[ev][metric]/base[metric] if base[metric]!=0 else np.nan
            ratrows.append(rec)

    # Pooled-awake descriptive candidate; evaluate every day separately.
    all_awake_blocks=[d['stats'][k] for d in days for k in keys(d,AWAKE)]
    pooled_lam,pooled_cv=choose_ridge(all_awake_blocks)
    pooled_A=fit_operator(combine_stats(all_awake_blocks),pooled_lam)[0]
    pooled_mem,pooled_labels=module_membership(pooled_A)
    pooled_res=beam_search(pooled_A,pooled_mem,sizes=(3,4,5))
    pooled_cands=[]; pooled_sigs=[]
    for k in (3,4,5):
        cand=tuple(pooled_res[k][0]); cs=';'.join(map(str,cand)); nodes=';'.join(first_pairs.iloc[list(cand)].bipolar_id)
        pooled_cands.append({'k':k,'lambda':pooled_lam,'candidate':cs,'nodes':nodes})
        for d in days:
            models={'full_awake':awake_operator(d,pooled_lam),'deep_anesthesia':state_operator(d,'deep_anesthesia',pooled_lam)}
            for st in ('eyes_open','eyes_closed','recovery_eyes_closed','recovery_eyes_open'):
                if keys(d,[st]): models[st]=state_operator(d,st,pooled_lam)
            for ev,A in models.items(): pooled_sigs.append({'date':d['date'],'k':k,'evaluation':ev,'candidate':cs,**signature(A,pooled_mem,cand)})

    pd.DataFrame(sigrows).to_csv(args.out/'lodo_signatures.csv',index=False)
    pd.DataFrame(candrows).to_csv(args.out/'lodo_candidates.csv',index=False)
    pd.DataFrame(ratrows).to_csv(args.out/'lodo_ratios.csv',index=False)
    pd.DataFrame(pooled_cands).to_csv(args.out/'pooled_candidates.csv',index=False)
    pd.DataFrame(pooled_sigs).to_csv(args.out/'pooled_day_signatures.csv',index=False)
    pooled_cv.to_csv(args.out/'pooled_ridge_cv.csv',index=False)
    np.save(args.out/'pooled_module_labels.npy',pooled_labels)
    first_pairs.to_csv(args.out/'bipolar_pairs.csv',index=False)
    summary={'animal':args.animal,'dates':[d['date'] for d in days],'n_days':len(days),'pooled_lambda':pooled_lam}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
