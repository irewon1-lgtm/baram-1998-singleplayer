#!/usr/bin/env python3
"""Playable G2 catalog and normal routes. Shared mechanics, distinct tactical choices.

New names/values are explicit offline reconstructions, not historical source facts.
No grant-all feature is present in the normal game.
"""
from __future__ import annotations
import argparse, json, hashlib, shutil
from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
from build_g2_world import World,stable,write,digest,GEN,reachable

JOBS=('전사','도적','주술사','도사')
MATERIALS=('약초','광석','수정','가죽','송진','어금니','영혼석','천조각')
ROLES=('척후','맹독','수호')

class Content:
 def __init__(self,world):
  self.w=world;self.d=world.data;self.before=world.before;self.adoptions=[];self.regions=[]
  self.actors=json.loads((world.output/'gameplay-assets/actors.json').read_text())
  self.item_templates=defaultdict(list)
  for item in self.before['items'].values():self.item_templates[item['kind']].append(item)
  self.used_cells={mid:{(int(p['x']),int(p['y']))for p in m['spawns']+m['exits']}for mid,m in self.d['maps'].items()}
  for npc in self.d['npcs'].values():self.used_cells[npc['map_id']].add((npc['x'],npc['y']))
  for m in self.d['maps'].values():
   for e in m['exits']:self.used_cells[e['to_map']].add((e['to_x'],e['to_y']))
  for v in [self.d['start'],self.d['respawn']]+list(self.d.get('return_points',{}).values()):self.used_cells[v['map_id']].add((v['x'],v['y']))
 def adoption(self,kind,obj,role,deps=()):
  self.adoptions.append({'content_id':obj['id'],'source_ref':obj.get('source_ref','G1_KOREAN_CATALOG_AND_APPROVED_G2_RECONSTRUCTION'),'source_tier':'LEGACY_RECONSTRUCTED','reconstructed_fields':['G2 name','offline stats','behavior and acquisition links'],'role':role,'runtime_ref':kind+'.'+obj['id'],'dependencies':list(deps),'generation':'G2','test_status':'IMPLEMENTED_TUNING_PENDING_NOT_YET_EXECUTED'})
 def location(self,mid,want):
  p=self.w.point(mid,want,self.used_cells[mid]);self.used_cells[mid].add(p)
  self.w.changes[mid]['anchors'].append(p)
  return p
 def npc(self,mid,name,role,position):
  iid=stable('npc',mid+name);x,y=self.location(mid,position)
  looks={'guide':'warrior_master','trader':'tavern','crafter':'forge','healer':'poet_master','storage':'tavern'}
  available=set(self.actors['looks']);look=looks.get(role,'tavern')
  if look not in available:look=next(n['look_id']for n in self.before['npcs'].values())
  services={'guide':['quest','travel'],'trader':['shop','quest'],'crafter':['craft','repair','quest'],'healer':['heal','revive','quest'],'storage':['storage','quest']}[role]
  n={'id':iid,'name':name,'map_id':mid,'x':x,'y':y,'look':look,'look_id':look,'services':services,'interaction_range':2,'shop':{},'dialogue':{'greeting':{'guide':'새 길은 직접 발견해야 나루와 야영지에서 다시 오갈 수 있습니다. 이곳 의뢰와 지도를 살펴보세요.','trader':'이 고장에서 쓰는 장비와 회복 도구를 준비했습니다. 직업과 착용 조건을 확인하세요.','crafter':'근처에서 모은 재료로 장비와 약을 만들 수 있습니다. 수리도 맡겨 주세요.','healer':'상처를 치료하고 다시 길을 떠나세요.','storage':'짐을 맡아 두겠습니다. 같은 캐릭터의 창고에 안전하게 보관합니다.'}[role],'cancel':'안전한 여행 되세요.','success':'준비가 끝났습니다.','failure':'조건과 재료를 확인하세요.'},'generation':'G2','source_tier':'LEGACY_RECONSTRUCTED','role':role}
  self.d['npcs'][iid]=n;self.d['maps'][mid]['npcs'].append(iid);self.d['maps'][mid]['landmarks'].append({'name':name,'x':x,'y':y,'kind':'service'});self.adoption('npcs',n,role)
  return iid
 def icon(self,new,template):
  ref=self.actors['icons'].get(template['id'])
  assert ref,template['id']
  self.actors['icons'][new['id']]=deepcopy(ref)
  if template.get('icon'):new['icon']=template['icon']
 def material(self,region,kind,n):
  originals=list(self.before['items'].values());hints={'약초':['홍성초','장미'],'광석':['부싯돌'],'수정':['유리구슬','호박'],'가죽':['토끼가죽','곰가죽'],'송진':['노송의가지'],'어금니':['황룡의어금니'],'영혼석':['진호박','여의주'],'천조각':['빨간양말']}
  template=next((x for x in originals if x['name']in hints[kind]and x['id']in self.actors['icons']),self.item_templates['material'][n%len(self.item_templates['material'])])
  iid=stable('item',region+kind);x={'id':iid,'name':region+' '+kind,'kind':'material','stack_max':999,'sell_price':4+3*n,'buy_price':None,'durability':0,'description':region+'의 채집·사냥 재료. 지역 공방의 조합과 의뢰에 사용합니다.','source_tier':'LEGACY_RECONSTRUCTED','generation':'G2','function_paths':[],'acquisition_paths':[]};self.icon(x,template);self.d['items'][iid]=x;self.adoption('items',x,'regional_crafting_reagent');return iid
 def equipment(self,label,level,job,slot,rank):
  templates=[x for x in self.before['items'].values()if x.get('slot')==slot and x['id']in self.actors['icons']]
  template=next((x for x in templates if x.get('required_job')in('any',job,None)),templates[0])
  suffix={'weapon':{'전사':'파쇄검','도적':'추적도','주술사':'화인봉','도사':'치유선'},'armor':{'전사':'철갑','도적':'야행복','주술사':'주법포','도사':'성의'},'helmet':{j:'호위관'for j in JOBS},'ring':{j:'인장'for j in JOBS},'cape':{j:'망토'for j in JOBS}}[slot][job]
  name=label+' '+job+' '+suffix;iid=stable('item',name)
  x={'id':iid,'name':name,'kind':'weapon'if slot=='weapon'else'armor','slot':slot,'stack_max':1,'required_level':level,'required_job':job,'durability':200+rank*30,'attack':(6+level*2+rank)if slot=='weapon'else 0,'defense':(2+level//3+rank//2)if slot=='armor'else 1+level//12,'buy_price':100+level*level*3+rank*40,'sell_price':max(1,(100+level*level*3)//5),'look':template.get('look','player_base'),'hp_bonus':level*(2 if job=='전사'else 1)if slot=='armor'else 0,'mp_bonus':level*2 if job in('주술사','도사')and slot in('ring','helmet')else 0,'strength_bonus':rank+2 if job=='전사'and slot=='ring'else 0,'dexterity_bonus':rank+2 if job=='도적'and slot=='ring'else 0,'intelligence_bonus':rank+2 if job in('주술사','도사')and slot=='ring'else 0,'accuracy_bonus':2+rank if job=='도적'and slot=='weapon'else 0,'magic_defense_bonus':2+rank if slot=='cape'else 0,'regen_bonus':1+rank//3 if job=='도사'and slot=='cape'else 0,'description':label+'의 재료로 만든 '+job+'용 '+suffix+'. '+('힘과 생존'if job=='전사'else'기동과 명중'if job=='도적'else'마력과 지력'if job=='주술사'else'회복과 지속력')+'에 맞춘 장비.','generation':'G2','source_tier':'LEGACY_RECONSTRUCTED','acquisition_paths':[],'function_paths':[{'kind':'equip','slot':slot}]}
  self.icon(x,template);self.d['items'][iid]=x;self.adoption('items',x,job+'_'+slot);return iid
 def potion(self,label,level,kind,rank):
  suffix={'hp':'회복약','mp':'명상수','dual':'활력탕','cleanse':'해독환'}[kind];iid=stable('item',label+suffix)
  originals=[x for x in self.item_templates['consumable']if x['id']in self.actors['icons']]
  template=next((x for x in originals if (int(x.get('hp_restore',0))>0 if kind=='hp'else int(x.get('mp_restore',0))>0)),originals[rank%len(originals)])
  x={'id':iid,'name':label+' '+suffix,'kind':'consumable','stack_max':99,'durability':0,'buy_price':max(8,10+level*3),'sell_price':max(1,(10+level*3)//5),'hp_restore':(35+level*8)if kind in('hp','dual')else 0,'mp_restore':(25+level*6)if kind in('mp','dual')else 0,'action_type':'cleanse'if kind=='cleanse'else'','description':{'hp':'체력 회복','mp':'마력 회복','dual':'체력·마력 동시 회복','cleanse':'중독·마비·둔화·침묵 해제'}[kind]+' 도구. 전투 중 물품 사용 간격을 따릅니다.','generation':'G2','source_tier':'LEGACY_RECONSTRUCTED','acquisition_paths':[],'function_paths':[{'kind':'use_item','action':kind}]}
  self.icon(x,template);self.d['items'][iid]=x;self.adoption('items',x,'consumable_'+kind);return iid
 def spawn(self,mid,mob,position,tag):
  x,y=self.location(mid,position);sid=stable('spawn',mid+mob+tag)
  self.d['maps'][mid]['spawns'].append({'id':sid,'monster_id':mob,'x':x,'y':y,'respawn_seconds':float(self.d['monsters'][mob].get('respawn_seconds',20)),'generation':'G2'})
  return sid
 def make_regions(self):
  baseline_mobs=list(self.before['monsters'].values());eligible=[m for m in baseline_mobs if int(m.get('level',20))>=5]
  for i,mid in enumerate(self.w.fields):
   m=self.d['maps'][mid];label=m['g2_region_label'];level=1 if i<4 else min(90,6+(i-4)*7)
   guide=self.npc(mid,label+' 길잡이','guide',(20,20));trader=self.npc(mid,label+' 행상','trader',(24,21));crafter=self.npc(mid,label+' 장인','crafter',(20,24))
   self.w.room(mid,20,20,9,8)
   r={'map':mid,'label':label,'level':level,'guide':guide,'trader':trader,'crafter':crafter,'materials':[],'gear':[],'potions':[],'monsters':[],'recipes':[]}
   for n,kind in enumerate(MATERIALS):r['materials'].append(self.material(label,kind,i))
   for j,job in enumerate(JOBS):
    for slot in ['weapon','armor','helmet','ring','cape']:r['gear'].append(self.equipment(label,max(1,min(98,4+i*5)),job,slot,i))
   for kind in ['hp','mp','dual','cleanse']:r['potions'].append(self.potion(label,max(1,level),kind,i))
   for iid in r['gear']+r['potions']:
    item=self.d['items'][iid];self.d['npcs'][trader]['shop'][iid]={'buy_price':item['buy_price'],'sell_price':item['sell_price']};item['acquisition_paths'].append({'kind':'shop','npc_id':trader})
   # Eight distinct regional reagents are guaranteed gatherable, with bounded persisted respawn.
   for n in range(16):
    x,y=self.location(mid,(12+(n*23)%103,12+(n*31)%103));iid=r['materials'][n%8];nid=stable('node',mid+str(n))
    self.d['maps'][mid]['gather_nodes'].append({'id':nid,'name':self.d['items'][iid]['name'],'x':x,'y':y,'item_id':iid,'quantity':1+n//8,'respawn_seconds':35+n%4*5,'minimum_level':1,'icon_item':iid});self.d['items'][iid]['acquisition_paths'].append({'kind':'gather','map_id':mid,'node_id':nid})
   self.regions.append(r)
  # Fifty-eight distinct base species, each with three actual combat roles.
  bases=[];seen=set()
  for mob in eligible:
   if mob['name']in seen:continue
   bases.append(mob);seen.add(mob['name'])
   if len(bases)==58:break
  assert len(bases)==58
  for n,base in enumerate(bases):
   r=self.regions[n%16];level=max(4,min(98,r['level']+n//16*2))
   for j,role in enumerate(ROLES):
    iid=stable('monster',r['label']+base['name']+role);mob=deepcopy(base)
    for k in ['source_value','source_id','source_pointer','source_name_aliases','source_record']:mob.pop(k,None)
    mob.update(id=iid,name=r['label']+' '+role+' '+base['name'],level=level,region=r['label'],hp=int(28+level*7+level*level*.15)*(2 if role=='수호'else 1),attack=3+int(level*.55),defense=level//7+(4 if role=='수호'else 0),xp=12+level*level//3,money_min=2+level//3,money_max=6+level,aggression='hostile',attack_interval=2.2 if role=='척후'else 1.8,move_interval=1.1 if role=='척후'else 1.5,chase_range=10,leash_range=14,attack_range=5 if role=='척후'else 1,low_hp_flee=role=='척후',flee_hp_fraction=.3,on_hit_status='poison'if role=='맹독'else'',status_duration=5,status_power=1+level//15,guard_reduction=.22 if role=='수호'else 0,resistances={'fire':.55 if j==0 else 1.15,'ice':.55 if j==1 else 1.15,'lightning':.55 if j==2 else 1.15},drops=[{'item_id':r['materials'][(n+j)%8],'chance':.65,'quantity_min':1,'quantity_max':2},{'item_id':r['materials'][(n+j+4)%8],'chance':.35,'quantity_min':1,'quantity_max':1},{'item_id':r['potions'][j],'chance':.1,'quantity_min':1,'quantity_max':1}],generation='G2',source_ref=base['id'],source_tier='LEGACY_RECONSTRUCTED',tactical_role=role,respawn_seconds=25+5*j)
    self.d['monsters'][iid]=mob;r['monsters'].append(iid);self.adoption('monsters',mob,'ranged_flee'if j==0 else'poison_melee'if j==1 else'armored_guard',r['materials'])
    self.spawn(r['map'],iid,(30+(n*19+j*7)%85,28+(n*13+j*11)%85),str(n)+role)
  # Fill reachable habitats, not the whole global world simulation each frame.
  for i,r in enumerate(self.regions):
   for n in range(24):self.spawn(r['map'],r['monsters'][n%len(r['monsters'])],(10+(n*29)%108,10+(n*43)%108),'habitat'+str(n))
   for n in range(4):
    result=r['gear'][(i%4)*5+n%3]if n<3 else r['potions'][2]
    iid=stable('recipe',r['label']+str(n));recipe={'id':iid,'name':self.d['items'][result]['name']+' 조합','npc_id':r['crafter'],'minimum_level':max(1,r['level']-5),'ingredients':{r['materials'][n*2]:2+n,r['materials'][n*2+1]:2},'money':10+r['level']*2,'results':{result:2 if n==3 else 1},'success_probability':1.0,'source_tier':'LEGACY_RECONSTRUCTED','generation':'G2'}
    self.d['recipes'][iid]=recipe;r['recipes'].append(iid);self.adoption('recipes',recipe,'regional_crafting',list(recipe['ingredients'])+[result]);self.d['items'][result]['acquisition_paths'].append({'kind':'craft','recipe_id':iid})
    for mat in recipe['ingredients']:self.d['items'][mat]['function_paths'].append({'kind':'craft_material','recipe_id':iid})
   for n,iid in enumerate(r['materials']):self.d['npcs'][r['trader']]['shop'][iid]={'buy_price':None,'sell_price':self.d['items'][iid]['sell_price']}
  # Service districts are distinct in the two cities, with real open services.
  for j,mid in enumerate(['gp:map:domestic_city','g1:map:buya_city']):
   title='국내'if j==0 else'부여'
   for n,role in enumerate(['guide','storage','healer','trader','crafter','guide']):
    x=25+(n%3)*95;y=40+(n//3)*195;self.w.room(mid,x,y,7,6,True)
    iid=self.npc(mid,title+' '+['성문지기','곡물창고지기','의원','약재상','수리공','나루지기'][n],role,(x,y))
    if role=='trader':
     for r in self.regions[j*8:j*8+2]:
      for item in r['potions']:
       d=self.d['items'][item];self.d['npcs'][iid]['shop'][item]={'buy_price':d['buy_price'],'sell_price':d['sell_price']}
    if role=='guide':self.d['npcs'][iid]['services'].append('heal')
  # Actual hazards/rewards on each floor and a stronger last-floor guard.
  for i,ids in enumerate(self.w.families):
   r=self.regions[i]
   for floor,mid in enumerate(ids):
    if mid not in self.used_cells:self.used_cells[mid]=set()
    for n in range(10):self.spawn(mid,r['monsters'][(n+floor)%len(r['monsters'])],(12+(n*23+floor*7)%82,14+(n*17+floor*11)%80),'dungeon'+str(floor)+':'+str(n))
    self.d['maps'][mid]['landmarks'].append({'name':'보상 구역'if floor==3 else'갈림길 · 지하 계단','x':70,'y':65})
    if floor==3:
     boss=deepcopy(self.d['monsters'][r['monsters'][-1]]);boss['id']=stable('monster',ids[-1]+'boss');boss['name']=self.d['maps'][mid]['dungeon_family']+' 심층 수문장';boss['hp']*=3;boss['xp']*=5;boss['attack']+=5;boss['money_min']*=5;boss['money_max']*=5;boss['tactical_role']='boss_guard';boss['drops'].append({'item_id':r['gear'][(i%4)*5+3],'chance':1,'quantity_min':1,'quantity_max':1});self.d['monsters'][boss['id']]=boss;self.adoption('monsters',boss,'guaranteed_reward_boss');self.spawn(mid,boss['id'],(85,85),'boss');r['boss']=boss['id'];r['boss_map']=mid

 def quest(self,r,name,objectives,reward=None,level=None):
  iid=stable('quest',r['label']+name);x={'id':iid,'name':r['label']+' · '+name,'npc_id':r['guide'],'minimum_level':max(1,r['level']-5)if level is None else level,'required_job':'any','objectives':objectives,'rewards':{'xp':50+max(1,r['level'])**2*2,'money':60+r['level']*15,'items':reward or{}},'description':'목표를 수행하고 '+self.d['npcs'][r['guide']]['name']+'에게 보고하세요.','generation':'G2','source_tier':'LEGACY_RECONSTRUCTED'}
  self.d['quests'][iid]=x;self.adoption('quests',x,'+'.join(o['kind']for o in objectives),[o['id']for o in objectives]);return iid
 def make_quests(self):
  for i,r in enumerate(self.regions):
   O=lambda kind,iid,count=1:{'kind':kind,'id':iid,'count':count}
   self.quest(r,'길과 마을을 잇다',[O('visit',r['map']),O('talk',r['trader'])],{r['potions'][0]:3},1)
   self.quest(r,'야영지 지키기',[O('kill',r['monsters'][0],4),O('kill',r['monsters'][1],2)],{r['potions'][1]:3})
   self.quest(r,'공방의 새 재료',[O('collect',r['materials'][0],3),O('collect',r['materials'][3],2)],{r['potions'][2]:2})
   self.quest(r,'장인의 부탁',[O('talk',r['crafter']),O('craft',r['recipes'][3])],{r['materials'][6]:3})
   equip_quest=self.quest(r,'원정대 무장 점검',[O('equip',r['gear'][(i%4)*5+4]),O('kill',r['monsters'][-1],2)],{r['materials'][7]:4},min(98,4+i*5))
   self.d['quests'][equip_quest]['required_job']=JOBS[i%4]
   nextmap=self.regions[(i+1)%16]['map'];self.quest(r,'이웃 땅 소식',[O('visit',nextmap),O('talk',self.regions[(i+1)%16]['guide'])],{r['potions'][3]:2},1 if i<3 else max(1,r['level']-5))
   if 'boss'in r:self.quest(r,'심층 수문장을 넘어서',[O('visit',r['boss_map']),O('kill',r['boss'])],{r['gear'][(i%4)*5+2]:1})

 def make_skills(self):
  # Values are shared level-model values. Each tuple changes an executed mechanic.
  entries={
  '전사':[
   ('선봉베기','damage',{'directional_pattern':['front'],'power':28}),('반월가르기','damage',{'directional_pattern':['front','left','right'],'power':22}),('후방역습','damage',{'directional_pattern':['back'],'power':35}),('지진참','damage',{'delivery':'area','radius':2,'power':44}),('돌진격','damage',{'blink_to_target':True,'range':5,'power':48}),('끌어오기','damage',{'pull_target':True,'range':5,'power':18}),('위압','status',{'status':'slow','duration':9}),('기절타','damage',{'on_hit_status':'paralysis','duration':2,'power':30}),('피의일격','damage',{'heal_fraction':.35,'power':65}),('철벽진','buff',{'defense_bonus':16,'damage_multiplier':.6}),('분노의깃발','buff',{'attack_multiplier':1.6,'defense_bonus':-5}),('굳건한발','buff',{'rooted':True,'damage_multiplier':.35,'duration':5}),('반격태세','buff',{'reflect_fraction':.5,'reflect_probability':.8}),('파진준비','buff',{'next_hit_multiplier':2.2,'duration':6}),('전장의호흡','heal',{'power':180}),('전의회복','restore_mp',{'power':90}),('정신집중','cleanse',{'cleanse_statuses':['silence','blindness']}),('사방격','damage',{'directional_pattern':['front','back','left','right'],'power':95})],
  '도적':[
   ('급소찌르기','damage',{'power':34}),('쌍월베기','damage',{'directional_pattern':['front','back'],'power':32}),('그림자도약','damage',{'blink_to_target':True,'range':6,'power':44}),('인력표창','damage',{'delivery':'projectile','pull_target':True,'range':5,'power':20}),('맹독표창','damage',{'on_hit_status':'poison','status_power':7,'duration':10,'tick_interval':1,'power':22}),('발목표창','damage',{'on_hit_status':'slow','duration':8,'power':24}),('연막탄','status',{'status':'blindness','duration':8}),('침묵침','status',{'status':'silence','duration':6}),('교란술','debuff',{'status':'slow','forget_aggro':True,'duration':5}),('자취감추기','status',{'target':'self','status':'stealth','duration':12}),('질주','buff',{'move_multiplier':.55,'duration':9}),('회피보법','buff',{'evasion_chance':.4,'duration':10}),('결정타준비','buff',{'next_hit_multiplier':2.6,'duration':5}),('흡혈도','damage',{'power':75,'heal_fraction':.5}),('사방수리검','damage',{'delivery':'area','radius':2,'power':62}),('탐지술','identify',{'reveal_hidden':True,'inspect_self_fields':['inventory','equipment']}),('원거리수집','loot',{'pickup_front_only':False,'range':4}),('탈출호흡','cleanse',{'cleanse_statuses':['poison','paralysis','slow']})],
  '주술사':[
   ('홍염구','damage',{'element':'fire','delivery':'projectile','range':7,'power':40}),('빙결구','damage',{'element':'ice','on_hit_status':'slow','duration':5,'range':7,'power':35}),('뇌광구','damage',{'element':'lightning','delivery':'projectile','range':8,'power':45}),('불꽃폭풍','damage',{'element':'fire','delivery':'area','radius':2,'power':72}),('빙설폭풍','damage',{'element':'ice','delivery':'area','radius':2,'on_hit_status':'slow','duration':6,'power':58}),('낙뢰폭풍','damage',{'element':'lightning','delivery':'area','radius':3,'power':65}),('봉인술','status',{'status':'silence','range':6,'duration':10}),('서리감옥','status',{'status':'paralysis','range':6,'duration':3}),('부식주','status',{'status':'poison','range':6,'status_power':10,'duration':12,'tick_interval':1}),('흡마호흡','restore_mp',{'power':150}),('마력장벽','buff',{'damage_multiplier':.55,'defense_bonus':8}),('반사주문','buff',{'reflect_fraction':.3,'reflect_probability':1.0}),('가속주문','buff',{'move_multiplier':.7,'duration':12}),('정화주문','cleanse',{'cleanse_statuses':['poison','slow','silence','blindness']}),('생기전환','heal',{'power':210,'mp_cost':40}),('화령소환','summon',{'power':38,'range':6,'duration':22,'attack_interval':1.4}),('마력집중','buff',{'attack_multiplier':1.45,'accuracy_bonus':.2}),('별빛관통','damage',{'element':'lightning','power':160,'range':9,'delivery':'projectile'})],
  '도사':[
   ('온기치유','heal',{'power':65}),('활력치유','heal',{'power':150}),('생명치유','heal',{'power':310}),('선기충전','restore_mp',{'power':130}),('정화의손','cleanse',{'cleanse_statuses':['poison','paralysis','slow']}),('해명의손','cleanse',{'cleanse_statuses':['silence','blindness']}),('수호결계','buff',{'damage_multiplier':.45,'duration':12}),('금강호신','buff',{'defense_bonus':22,'duration':16}),('가호의발','buff',{'move_multiplier':.65,'duration':14}),('반탄호신','buff',{'reflect_fraction':.45,'reflect_probability':1.0}),('축복의힘','buff',{'attack_bonus':28,'accuracy_bonus':.15}),('빛의심판','damage',{'element':'light','range':6,'delivery':'projectile','power':65}),('진혼광','damage',{'element':'light','delivery':'area','radius':2,'power':85}),('억혼술','status',{'status':'paralysis','range':5,'duration':3}),('퇴마빛','damage',{'element':'light','power':105,'on_hit_status':'blindness','duration':5}),('수호령소환','summon',{'power':32,'range':5,'duration':28,'attack_interval':1.3}),('무영가호','buff',{'evasion_chance':.3,'duration':12}),('소생의기운','revive',{'hp_fraction':.65,'cast_while_dead':True})]}
  for job in JOBS:
   teachers=[n['id']for n in self.d['npcs'].values()if n.get('job')==job and'teach_skill'in n['services']]
   if not teachers:teachers=[n['id']for n in self.d['npcs'].values()if'teach_skill'in n['services']and job in n.get('dialogue',{}).get('greeting','')]
   assert teachers,job
   original=next(s for s in self.before['skills'].values()if s.get('job')==job)
   for n,(name,kind,fields)in enumerate(entries[job]):
    iid=stable('skill',job+name);level=8+n*5
    s={'id':iid,'name':name,'job':job,'learn_level':level,'learn_money':40+level*12,'ingredients':{self.regions[n%16]['materials'][n%8]:1 if n<6 else 2},'teacher_ids':teachers,'guardian':None,'enabled':True,'kind':kind,'delivery':'projectile'if job in('주술사','도사')and kind=='damage'else'melee','target':'monster'if kind in('damage','debuff','status')else'self','range':1 if job=='전사'else 6,'power':0,'mp_cost':4+level//4,'hp_cost':0,'cooldown':1.5+n*.08,'windup':.12,'impact_delay':.25,'visual_duration':.7,'duration':10,'effect_id':original['effect_id'],'sound_id':original['sound_id'],'generation':'G2','source_tier':'LEGACY_RECONSTRUCTED','description':job+'의 '+name+'. 별도 전술·대상·소모 조건을 가진 재구성 기술.'}
    s.update(fields)
    if kind=='summon':s['monster_id']=self.regions[n%16]['monsters'][0]
    if kind=='status'and s.get('status')=='stealth':s['target']='self'
    self.d['skills'][iid]=s;self.adoption('skills',s,job+'_'+kind,list(s['ingredients'])+teachers)

 def finish(self):
  # New services, habitat and node coordinates are connected with the same world joins.
  for mid,t in self.w.changes.items():
   anchors=list(dict.fromkeys(p for p in t['anchors'] if p));connected=[anchors[0]]
   for p in anchors[1:]:
    near=min(connected,key=lambda a:abs(a[0]-p[0])+abs(a[1]-p[1]));self.w.connect(mid,near,p);connected.append(p)
  report=self.w.finalize()
  # Inputs and source save generations remain pinned; every legacy coordinate has an offset.
  transforms={mid:{'to_map_id':mid,'dx':dx,'dy':dy}for mid,(dx,dy)in self.w.offsets.items()}
  accepted=[]
  for row in self.before.get('accepted_compatibility',[]):
   row=deepcopy(row);old=row.get('map_transforms',{});combined=deepcopy(transforms)
   for mid,t in old.items():
    dst=t['to_map_id'];dx,dy=self.w.offsets.get(dst,(0,0));ct=deepcopy(t);ct['dx']+=dx;ct['dy']+=dy
    for cell,p in ct.get('cell_mappings',{}).items():p['x']+=dx;p['y']+=dy
    combined[mid]=ct
   row['map_transforms']=combined;accepted.append(row)
  accepted.append({'profile':self.before['profile'],'compatibility':deepcopy(self.before['compatibility']),'manifest_sha256':self.before['manifest_sha256'],'map_transforms':transforms})
  self.d['accepted_compatibility']=accepted;self.d['require_geometry_migration_contract']=True
  self.d['config'].update(lazy_world_spawns=True,active_ai_radius=32,max_world_monsters=4096)
  self.d['compatibility']={'schema':'1','rules':digest({k:self.d[k]for k in ['items','monsters','skills','npcs','quests','recipes','config']}),'idset':digest({k:sorted(self.d[k])for k in ['maps','items','monsters','skills','npcs','quests','recipes']}),'map_geometry':digest({k:m.get('geometry_sha256')for k,m in self.d['maps'].items()})}
  self.d['manifest_sha256']=digest({'generation':GEN,'compatibility':self.d['compatibility'],'parent':self.before['manifest_sha256']})
  self.d['config'].update(lazy_world_spawns=True,active_ai_radius=32,max_world_monsters=4096)
  self.d['g2_regions']=self.regions
  write(self.w.output/'gameplay-assets/actors.json',self.actors);write(self.w.output/'G2_ADOPTION.json',{'schema':'baram.g2.adoption/1','generation':'G2','records':self.adoptions,'source_field_policy':'Prior original fields kept; additions are explicitly reconstructed.'});write(self.w.output/'G2_MAP_MIGRATION.json',{'source_manifest':self.before['manifest_sha256'],'target_manifest':self.d['manifest_sha256'],'map_transforms':transforms,'all_source_ids_preserved':True,'source_user_saves_modified':False});write(self.w.output/'gameplay_content.json',self.d)
  paths=[]
  for p in sorted(self.w.output.rglob('*')):
   if p.is_file()and p.name!='runtime.json':paths.append({'path':str(p.relative_to(self.w.output)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  manifest={'schema':'baram.work.p3.runtime/1','generation':GEN,'profile':self.d['profile'],'world_profile':self.d['world_profile'],'files':paths,'private_only':True,'compatibility':self.d['compatibility'],'parent_generation':self.before['generation'],'parent_runtime_sha256':hashlib.sha256((self.w.baseline/'runtime.json').read_bytes()).hexdigest(),'fingerprint':digest(paths),'input_definitions_sha256':hashlib.sha256((self.w.output/'gameplay_content.json').read_bytes()).hexdigest(),'excluded':['source archives','private keys','user saves']}
  write(self.w.output/'runtime.json',manifest)
  counts={k:len(self.d[k])for k in['maps','items','monsters','skills','npcs','quests','recipes']}
  return {'status':'COMPILED_NOT_YET_EXECUTION_VERIFIED','counts':counts,'spawn_definitions':sum(len(m['spawns'])for m in self.d['maps'].values()),'gather_nodes':sum(len(m.get('gather_nodes',[]))for m in self.d['maps'].values()),'unique_chunks_placed':report['unique_chunks_placed'],'A0':report['baseline_area_A0'],'A1':report['g2_area_A1'],'ratio':report['ratio'],'runtime_sha256':hashlib.sha256((self.w.output/'runtime.json').read_bytes()).hexdigest()}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['base','priority','output']:p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args();assert not a.output.exists(),'fresh generation required';shutil.copytree(a.base,a.output)
 w=World(a.base,a.priority,a.output);w.make_world();c=Content(w);c.make_regions();c.make_quests();c.make_skills();r=c.finish();print(json.dumps(r,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
