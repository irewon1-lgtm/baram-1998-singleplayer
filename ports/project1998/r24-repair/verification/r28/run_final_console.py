import pathlib,subprocess,os,json,sys,hashlib
r=pathlib.Path(__file__).resolve().parents[2];attempt=sys.argv[1];products=pathlib.Path(sys.argv[2]).resolve();out=r/'evidence/r24'/('console-'+attempt);out.mkdir(parents=True,exist_ok=False)
env=os.environ|{'P1998_PROBE_PRODUCTS':str(products)}
cases=[(f'cosmetic-{t}',r/'verification/r24/CosmeticProbe.cs',[str(t)])for t in (24,25,27,28,29)]
cases += [('bags',r/'verification/r28/BagProbe.cs',['all']),('arrows',r/'verification/r24/ArrowProbe.cs',[]),('guides',r/'verification/r24/GuideProbe.cs',[]),('shop531',r/'verification/r24/ShopProbe.cs',[])]
cases += [(n.lower(),r/'verification/r23'/(n+'Probe.cs'),[])for n in ['Inventory','Flow','Regen','AliasOffer','Chance','World23','Repair','Bank32']]
cases += [('durability',r/'verification/r23/DurabilityProbe.cs',[str(r/'verification/r23/HIGH-DURABILITY-SPEC.json')])]
results=[]
for name,probe,args in cases:
 tag=attempt+'-'+name
 with(out/(name+'.log')).open('w')as log:code=subprocess.run(['python3',str(r/'verification/r24/run_console.py'),tag,str(probe),*args],env=env,stdout=log,stderr=subprocess.STDOUT).returncode
 result=r/'evidence/r24/runtime'/tag/'RESULT.json';x=json.loads(result.read_text())if result.exists()else{}
 failures=[c for c in x.get('checks',[])if c.get('status')=='FAIL'];row={'name':name,'exit':code,'status':x.get('status','NO_RESULT'),'checks':len(x.get('checks',[])),'failures':len(failures),'result':str(result.relative_to(r))};results.append(row);print(json.dumps(row),flush=True)
doc={'status':'PASS_SCOPED_FINAL_RUNTIME'if all(x['exit']==0 and x['failures']==0 for x in results)else'FAIL_OR_INCOMPLETE','results':results,'physical_android':'NOT_RUN','products':str(products),'game_data_archive_sha256':hashlib.sha256((r/'android/assets/game-data.zip').read_bytes()).hexdigest()};(out/'RESULT.json').write_text(json.dumps(doc,indent=2));sys.exit(0 if doc['status'].startswith('PASS')else 1)
