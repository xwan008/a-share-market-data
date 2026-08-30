import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=json.loads((ROOT/'data/research/pipeline/weekly_manual_review_queue.json').read_text(encoding='utf-8'))
out={'queue_count':src.get('queue_count'),'companies':[{'code':x['code'],'name':x['name'],'reasons':x.get('reasons',[]),'covered_by_t2':x.get('covered_by_t2',False)} for x in src.get('queue',[])]}
(ROOT/'data/research/pipeline/weekly_review_names.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'count':len(out['companies'])},ensure_ascii=False))
