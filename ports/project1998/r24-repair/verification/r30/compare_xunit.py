"""Compare executed failures by test name and message; keep the inherited FAILs visible."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parents[2]
ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
def load(folder):
    files=list(folder.glob('*.trx'));assert len(files)==1,folder
    tree=ET.parse(files[0]);rows=tree.findall('.//t:UnitTestResult',ns)
    failures={r.attrib['testName']:(r.findtext('.//t:Message',namespaces=ns)or'') for r in rows if r.attrib['outcome']=='Failed'}
    return {'executed':len(rows),'passed':sum(r.attrib['outcome']=='Passed' for r in rows),'failed':len(failures),'failures':failures}
before=load(root/'evidence/r25/suite/r29-final002/xunit')
after=load(root/'evidence/r25/suite/r29-final002/xunit')
new=sorted(set(after['failures'])-set(before['failures']))
removed=sorted(set(before['failures'])-set(after['failures']))
changed=sorted(k for k in set(after['failures'])&set(before['failures']) if after['failures'][k]!=before['failures'][k])
result={'status':'PASS_NO_NEW_FAILURES' if not new and not changed else 'FAIL_NEW_OR_CHANGED_FAILURES',
        'baseline':before,'current':after,'new_failure_names':new,'removed_failure_names':removed,'changed_failure_messages':changed,
        'inherited_failures_remain_failures':True,'physical_android':'NOT_RUN'}
(root/'evidence/r30/XUNIT-COMPARISON.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['baseline','current']},ensure_ascii=False))
