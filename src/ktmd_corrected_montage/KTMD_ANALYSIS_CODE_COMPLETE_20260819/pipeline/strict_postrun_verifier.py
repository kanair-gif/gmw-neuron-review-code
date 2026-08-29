#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
TARGETS={('Kin2','20110513'),('Kin2','20110524'),('Kin2','20110525'),('Su','20110523'),('Su','20110526'),('Su','20110527')}
def main():
 p=argparse.ArgumentParser();p.add_argument('output_root',type=Path);a=p.parse_args();r=a.output_root
 required=[r/'ALL_ANALYSES_COMPLETE.ok',r/'REAL_RAW_DATA_PROVENANCE_VERIFIED.ok',r/'COMPLETION_AUDIT.json',r/'FINAL_SUMMARY.json',r/'tables/RAW_ARCHIVE_PROVENANCE_ALL_SIX_DAYS.csv',r/'tables/updated_hierarchical_lodo_deep_effects.csv',r/'tables/updated_within_day_awake_crossfit_ratios_11days.csv',r/'tables/updated_same_animal_leave_one_day_out_ratios.csv',r/'manuscript_materials/RESULTS_FOR_WRITING_THREAD.json',r/'manuscript_materials/MANUSCRIPT_RESULTS_PATCH.md']
 miss=[str(x) for x in required if not x.exists()]
 if miss: raise RuntimeError('Missing required outputs:\n'+'\n'.join(miss))
 audit=json.loads((r/'COMPLETION_AUDIT.json').read_text())
 if not audit.get('all_required_complete'): raise RuntimeError(f'Completion audit not final: {audit}')
 d=pd.read_csv(r/'tables/RAW_ARCHIVE_PROVENANCE_ALL_SIX_DAYS.csv')
 ids=set(zip(d.animal.astype(str),d.date.astype(str)))
 checks={'six_rows':len(d)==6,'six_identities':ids==TARGETS,'six_distinct_hashes':d.archive_sha256.nunique()==6,'archive_manifest_match':(d.archive_sha256==d.manifest_sha256).all(),'parts_all_verified':(d.part_count==d.verified_part_count).all()}
 fail=[k for k,v in checks.items() if not v]
 if fail: raise RuntimeError(f'Raw provenance failed: {fail}')
 summary=json.loads((r/'FINAL_SUMMARY.json').read_text())
 if not summary.get('raw_data_provenance_locked'): raise RuntimeError('Final summary lacks provenance lock')
 print('SUBMISSION-READY COMPLETION VERIFIED');print(json.dumps({'checks':checks,'audit':audit},indent=2));return 0
if __name__=='__main__': raise SystemExit(main())
