"""Actual PostgreSQL RPC contract. Local auth.uid claims are TEST fixtures,
not a deployed Supabase login test. No original game assets are needed."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import unittest
import uuid
import psycopg

DSN = os.environ['BARAM_TEST_DATABASE_URL']
COMPAT = 'schema2:test-content'
def uid(): return str(uuid.uuid4())
def document(gold=1, schema=2):
    payload=json.dumps(dict(player=dict(level=1,hp=50,hp_max=50,mp=10,mp_max=10,gold=gold,inventory={}),world={},rng_state='123'),separators=(',',':'))
    return json.dumps(dict(schema=schema,content_version='test-content',payload=payload,sha256=hashlib.sha256(payload.encode()).hexdigest()))
def rpc(owner, name, *values):
    with psycopg.connect(DSN) as c:
        c.execute("select set_config('request.jwt.claim.sub', %s, true)",(owner or '',))
        c.execute('set local role authenticated')
        return c.execute('select public.'+name+'('+','.join(['%s']*len(values))+')',values).fetchone()[0]

class Transactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(DSN) as c:
            c.execute("create role anon; create role authenticated; create schema auth; create schema extensions; create extension pgcrypto with schema extensions;")
            c.execute("create table auth.users(id uuid primary key); create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid$$;")
            c.execute((Path(__file__).parents[1]/'migrations/20261015020000_continuity.sql').read_text())
    def setUp(self):
        self.owner=uid();self.pc=uid();self.android=uid()
        with psycopg.connect(DSN) as c: c.execute('insert into auth.users values(%s)',(self.owner,))
    def open(self,device,compat=COMPAT):return rpc(self.owner,'baram_open',device,compat)
    def push(self,device,base,doc=None,request=None,release=True):
        return rpc(self.owner,'baram_push',device,COMPAT,base,request or uid(),doc or document(),release)
    def test_pc_android_pc_and_backup(self):
        self.assertEqual(self.open(self.pc)['version'],0)
        first=document(7);self.assertEqual(self.push(self.pc,0,first)['version'],1)
        self.assertEqual(self.open(self.android)['document'],first)
        second=document(9);self.assertEqual(self.push(self.android,1,second)['version'],2)
        self.assertEqual(self.open(self.pc)['document'],second)
        with psycopg.connect(DSN) as c:
            r=c.execute('select document,backup from baram_private.saves where owner=%s',(self.owner,)).fetchone()
            self.assertEqual(r,(second,first))
    def test_offline_device_blocks_second_device(self):
        self.open(self.pc)
        self.assertEqual(self.open(self.android)['status'],'BUSY')
        self.assertEqual(self.open(self.pc)['status'],'OK')
    def test_stale_overwrite_is_rejected(self):
        self.open(self.pc);self.push(self.pc,0)
        self.open(self.android);self.push(self.android,1,document(9))
        r=self.push(self.pc,1,document(3))
        self.assertEqual(r['status'],'CONFLICT');self.assertEqual(r['document'],document(9))
    def test_lost_response_idempotent_retry(self):
        self.open(self.pc);request=uid();doc=document(7)
        self.assertEqual(self.push(self.pc,0,doc,request)['version'],1)
        self.assertEqual(self.push(self.pc,0,doc,request)['version'],1)
        with self.assertRaises(psycopg.Error):self.push(self.pc,0,document(8),request)
    def test_compatibility_does_not_modify_record(self):
        self.open(self.pc);self.push(self.pc,0)
        with psycopg.connect(DSN) as c:before=c.execute('select row_to_json(s) from baram_private.saves s where owner=%s',(self.owner,)).fetchone()
        self.assertEqual(self.open(self.android,'schema2:new-content')['status'],'UPDATE_REQUIRED')
        self.assertEqual(self.push(self.android,1,document(schema=3))['status'],'UPDATE_REQUIRED')
        with psycopg.connect(DSN) as c:self.assertEqual(before,c.execute('select row_to_json(s) from baram_private.saves s where owner=%s',(self.owner,)).fetchone())
    def test_auth_and_table_isolation(self):
        with self.assertRaises(psycopg.Error):rpc(None,'baram_open',self.pc,COMPAT)
        with psycopg.connect(DSN) as c:
            c.execute('set local role authenticated')
            with self.assertRaises(psycopg.Error):c.execute('select * from baram_private.saves')
        self.open(self.pc);self.push(self.pc,0,document(99))
        other=uid()
        with psycopg.connect(DSN) as c:c.execute('insert into auth.users values(%s)',(other,))
        self.assertIsNone(rpc(other,'baram_open',self.android,COMPAT)['document'])
    def test_concurrent_open_has_one_winner(self):
        with concurrent.futures.ThreadPoolExecutor(2) as e:
            results=list(e.map(self.open,[self.pc,self.android]))
        self.assertEqual(sorted(r['status'] for r in results),['BUSY','OK'])
    def test_checksum_and_invalid_state_keep_previous(self):
        self.open(self.pc);self.push(self.pc,0,document(7));self.open(self.pc)
        bad=json.loads(document());bad['sha256']='0'*64
        with self.assertRaises(psycopg.Error):self.push(self.pc,1,json.dumps(bad))
        with self.assertRaises(psycopg.Error):self.push(self.pc,1,document(-1))
        self.assertEqual(self.open(self.pc)['document'],document(7))
    def test_no_lease_cannot_push(self):
        self.open(self.pc)
        self.assertEqual(self.push(self.android,0)['status'],'BUSY')
    def test_null_stats_and_negative_inventory_rejected(self):
        self.open(self.pc)
        for field,value in [('hp',None),('inventory',{'item':-1}),('equipment_instances',None)]:
            d=json.loads(document());s=json.loads(d['payload']);s['player'][field]=value
            d['payload']=json.dumps(s);d['sha256']=hashlib.sha256(d['payload'].encode()).hexdigest()
            with self.assertRaises(psycopg.Error):self.push(self.pc,0,json.dumps(d))
        self.assertEqual(self.open(self.pc)['version'],0)
    def test_empty_character_release(self):
        self.open(self.pc)
        self.assertEqual(rpc(self.owner,'baram_release_empty',self.pc,COMPAT)['status'],'OK')
        self.assertEqual(self.open(self.android)['status'],'OK')

if __name__=='__main__':unittest.main(verbosity=2)
