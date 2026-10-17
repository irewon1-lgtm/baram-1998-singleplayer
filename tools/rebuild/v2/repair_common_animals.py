#!/usr/bin/env python3
"""Bounded source-palette common animals and explicit reconstructed bear anatomy.
No game content/stat/AI/collision/timing fields are edited. New per-entity color
aliases are consumed only by the focused monster art lookup in the UI.
"""
import argparse,copy,hashlib,importlib.util,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
DAT_SHA='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['runtime','dat','reader']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();root=a.runtime.resolve();raw=a.dat.read_bytes()
 if sha(raw)!=DAT_SHA:raise ValueError('Held source container differs')
 sp=importlib.util.spec_from_file_location('common_animal_reader',a.reader);r=importlib.util.module_from_spec(sp);sys.modules[sp.name]=r;sp.loader.exec_module(r);dat=r.dat_entries(raw);epf=r.Epf(dat['monster.epf'][2]);pals=r.read_palettes(dat['monster.pal'][2]);actors=json.loads((root/'gameplay-assets/actors.json').read_text());game=json.loads((root/'gameplay_content.json').read_text());before=sha((root/'gameplay_content.json').read_bytes());original=copy.deepcopy(actors['looks']);generated={};paths=set();aliases={};affected=set();source_cache={}
 def source(src,color):
  key=(src['frame'],src['palette'],color)
  if key not in source_cache:
   f=epf.frame(src['frame']);rgba=f.rgba(pals[src['palette']],color);source_cache[key]=(f,rgba)
  return source_cache[key]
 def bear(src,direction,action,color):
  native,rgba=source(src,color);pal=pals[src['palette']];ramp=48+color*8;fur=[(*pal.colors[ramp+i],255)for i in range(8)];outline=(*pal.colors[16],255);im=Image.new('RGBA',(128,128));dr=ImageDraw.Draw(im);ox,oy=64,96
  def ellipse(b,fill,edge=True):dr.ellipse(tuple([b[0]+ox,b[1]+oy,b[2]+ox,b[3]+oy]),fill=fill,outline=outline if edge else fill)
  def rect(b,fill):dr.rectangle((b[0]+ox,b[1]+oy,b[2]+ox,b[3]+oy),fill=fill)
  def point(x,y,c):dr.point((x+ox,y+oy),fill=c)
  phase=int(src.get('relative_frame',0))%3;stride=[0,2,-1][phase]if action=='walking'else 0;rearing=action=='attack';lift=12 if rearing else 0
  # Stocky fur body and visible paws, reconstructed at the retained foot origin.
  if direction in [0,2]:
   ellipse((-11,-35-lift//2,11,-8),fur[2]);ellipse((-8,-33-lift//2,8,-13),fur[3],False)
   for x,dy in [(-8,stride),(6,-stride)]:
    ellipse((x-4,-14+dy,x+3,-1+min(0,dy)),fur[1]);rect((x-2,-3+min(0,dy),x+2,-1+min(0,dy)),fur[2])
    for claw in [x-2,x,x+2]:point(claw,-1+min(0,dy),fur[5])
   if direction==2:
    cy=-22-lift
    ellipse((-9,cy-9,-4,cy-3),fur[1]);ellipse((4,cy-9,9,cy-3),fur[1])
    ellipse((-8,cy-7,8,cy+8),fur[3]);ellipse((-6,cy-5,6,cy+4),fur[4],False)
    ellipse((-5,cy+1,5,cy+7),fur[5]);rect((-2,cy+2,2,cy+3),outline);point(0,cy+4,outline)
    for x in [-4,4]:point(x,cy-2,outline);point(x-1,cy-3,fur[7])
   else:
    cy=-31-lift
    ellipse((-9,cy-7,-4,cy-1),fur[1]);ellipse((4,cy-7,9,cy-1),fur[1]);ellipse((-8,cy-5,8,cy+9),fur[2]);ellipse((-5,cy-3,5,cy+5),fur[3],False)
    # Tiny solid stump tail; no circular rump or curly pig tail.
    ellipse((-2,-14,2,-10),fur[2])
   if rearing:
    for x in [-13,9]:ellipse((x,-33,x+4,-23),fur[1])
  else:
   # Draw a right-facing stocky body then mirror anatomy for the opposite view.
   ellipse((-14,-31-lift//2,7,-9),fur[2]);ellipse((-11,-29-lift//2,4,-13),fur[3],False)
   for x,dy in [(-9,stride),(7,-stride)]:
    ellipse((x-3,-14+dy,x+3,-1+min(0,dy)),fur[1]);rect((x-1,-3+min(0,dy),x+4,-1+min(0,dy)),fur[2]);point(x+3,-1+min(0,dy),fur[5])
   cy=-23-lift;ellipse((2,cy-10,7,cy-4),fur[1]);ellipse((8,cy-9,12,cy-4),fur[1]);ellipse((1,cy-7,15,cy+7),fur[3]);ellipse((11,cy,17,cy+5),fur[5]);rect((16,cy+1,18,cy+3),outline);point(10,cy-2,outline);point(9,cy-3,fur[7]);ellipse((-16,-21,-12,-17),fur[2])
   if rearing:ellipse((8,-34,13,-23),fur[1])
   if direction==3:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);im=Image.Image.transform(im,im.size,Image.Transform.AFFINE,(1,0,1,0,1,0),Image.Resampling.NEAREST)
  # Retain leaf frame rectangle/offset and source timing, with alpha padding.
  crop=im.crop((64+native.left,96+native.top,64+native.left+native.width,96+native.top+native.height))
  if not crop.getbbox():raise ValueError('Empty reconstructed bear')
  return crop
 def make(part,color):
  key=(part,color)
  if key in generated:return generated[key]
  base='g1_native_monster_'+str(part);lid=base if color=={'24':5,'29':5,'21':11,'23':5}[str(part)]else base+'_color'+str(color);look=copy.deepcopy(original[base]);look['id']=lid;look['source_parts']['recolor_byte']=color;look['binding_scope']=('Explicit reconstructed bear anatomy: stocky fur body, round ears, short muzzle/blacknose, shortsolidtail/paws; native Monster24 foot rectangle/timing and Monster.pal fur ramp retained; not a native bear source claim.'if part==24 else'Original native animal silhouette/offset/timing; explicit named-category palette adaptation, exact historical entity color unproven.')
  for action,dirs in look['animations'].items():
   for direction,frames in dirs.items():
    for fr in frames:
     src=fr['source_frames'][0];native,rgba=source(src,color);src['recolor_byte']=color;src['rgba_sha256']=sha(rgba);src['recolor_semantics']='EXPLICIT_CATEGORY_SOURCE_PALETTE_ADAPTATION';im=bear(src,int(direction),action,color)if part==24 else Image.frombytes('RGBA',(native.width,native.height),rgba)
     if part==24:src['reconstructed_bear_anatomy']=True;src['original_native_rgba_sha256']=sha(rgba)
     digest=sha(im.tobytes()+str(fr['offset']).encode());path='images/common-animal-'+digest[:24]+'.png';dest=root/'gameplay-assets'/path;im.save(dest);paths.add(path);fr.update(path=path,png_sha256=sha(dest.read_bytes()))
  actors['looks'][lid]=look;generated[key]=lid;affected.add(lid);return lid
 # Base common categories, then preserve named variants with art-only aliases.
 for part,color in [(24,5),(29,5),(21,11),(23,5)]:make(part,color)
 for iid,m in game['monsters'].items():
  old=m.get('look_id','');part=next((p for p in [24,29,21,23]if old=='g1_native_monster_'+str(p)),None)
  if part is None:continue
  name=m['name'];color={24:5,29:5,21:11,23:5}[part]
  if part==24:
   if '청웅'in name:color=2
   elif '황웅'in name:color=5
  elif part==29:
   if '적호'in name:color=4
   elif '자호'in name:color=7
  elif part==21:
   if '초록'in name:color=0
   elif '흑'in name:color=10
   elif any(s in name for s in ['붉','불']):color=4
   elif '갈색'in name:color=5
  elif part==23:
   if any(s in name for s in ['백','은']):color=11
   elif '흑'in name:color=10
   elif '불'in name:color=4
  lid=make(part,color);actors.setdefault('actor_aliases',{})[iid]=lid;aliases[iid]={'name':name,'old_look':old,'new_look':lid,'palette_category_reconstructed':True}
 actors['source']['common_animal_repair']={'tool_sha256':sha(Path(__file__).read_bytes()),'container_sha256':DAT_SHA,'reader_sha256':sha(a.reader.read_bytes()),'bear_scope':'RECONSTRUCTED_ANATOMY_NOT_NATIVE_BEAR_ID','native_held_search':'Existingruntime animal looks, held34–71 and118–126 boundedstanding frames; no native bear identified; no downloads/full corpus rerun','recipe':'NativeMonster24 rectangle/foot/timing, sourceMonster.pal ramps; stockybody/roundears/shortmuzzle/blacknose/shortsolidtail/paws reconstructed. Tiger29native silhouette goldenbrown palette5; namedrabbit/fox colors native ramps with perentity artaliases.'}
 actorfile=root/'gameplay-assets/actors.json';actorfile.write_text(json.dumps(actors,ensure_ascii=False,separators=(',',':'))+'\n')
 spawnmaps={}
 for mid,mp in game['maps'].items():
  spawned=[r for r in mp.get('spawns',[])if r.get('monster_id')in aliases]
  if spawned:spawnmaps[mid]={'name':mp['name'],'monster_ids':sorted(set(r['monster_id']for r in spawned))}
 report={'schema':'baram.common-animal-repair/1','status':'ISOLATED_ACTUAL_GAME_REVIEW_REQUIRED','source':actors['source']['common_animal_repair'],'affected_looks':sorted(affected),'entity_aliases':aliases,'affected_maps':spawnmaps,'unique_new_pngs':len(paths),'decoded_source_leaf_frames':len(source_cache),'content_unchanged_sha256':before,'actor_sha256':sha(actorfile.read_bytes()),'preserved':'Every ID/stat/AI/hitbox/collision/map/exit/route/skill/timing/leaf offset unchanged; source art rectangles retained. Runtime actoraliases only.'}
 (root/'COMMON_ANIMAL_REPAIR.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');mf=root/'runtime.json';m=json.loads(mf.read_text());m['files']=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(root.rglob('*'))if p.is_file()and p.name!='runtime.json'];m['fingerprint']=sha(json.dumps(m['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());mf.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'looks':len(affected),'aliases':len(aliases),'maps':len(spawnmaps),'pngs':len(paths),'actor':report['actor_sha256']}))
if __name__=='__main__':main()
