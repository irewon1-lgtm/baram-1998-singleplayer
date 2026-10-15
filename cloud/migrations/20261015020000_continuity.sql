-- One Supabase project: Auth + transactional PostgreSQL RPC. No game server.
-- Clients receive only a public publishable/anon key and their own Auth session.
create schema if not exists baram_private;
revoke all on schema baram_private from public, anon, authenticated;
create table baram_private.saves (
  owner uuid primary key references auth.users(id) on delete cascade,
  compatibility text not null,
  version bigint not null default 0,
  document text,
  backup text,
  device uuid,
  last_request uuid,
  updated_at timestamptz not null default now()
);
alter table baram_private.saves enable row level security;
revoke all on baram_private.saves from public, anon, authenticated;

create function public.baram_open(p_device uuid, p_compatibility text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare r baram_private.saves; u uuid := auth.uid();
begin
  if u is null or p_device is null then raise exception 'Authentication required' using errcode='42501'; end if;
  if length(p_compatibility) not between 3 and 200 then raise exception 'Invalid compatibility'; end if;
  insert into baram_private.saves(owner,compatibility) values(u,p_compatibility) on conflict do nothing;
  select * into r from baram_private.saves where owner=u for update;
  if r.compatibility <> p_compatibility then return jsonb_build_object('status','UPDATE_REQUIRED'); end if;
  if r.device is not null and r.device <> p_device then return jsonb_build_object('status','BUSY'); end if;
  -- No timeout takeover. An offline/force-stopped device must sync first.
  update baram_private.saves set device=p_device where owner=u;
  return jsonb_build_object('status','OK','version',r.version,'document',r.document,'last_request',r.last_request);
end $$;

create function public.baram_push(p_device uuid, p_compatibility text, p_base bigint,
  p_request uuid, p_document text, p_release boolean)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare r baram_private.saves; u uuid := auth.uid(); d jsonb; s jsonb;
begin
  if u is null or p_device is null or p_request is null then raise exception 'Authentication required' using errcode='42501'; end if;
  if p_document is null or octet_length(p_document) > 16777216 then raise exception 'Save size limit'; end if;
  d := p_document::jsonb;
  if (d->>'schema')::integer <> 2 or jsonb_typeof(d->'payload') <> 'string' then
    return jsonb_build_object('status','UPDATE_REQUIRED');
  end if;
  if encode(extensions.digest(convert_to(d->>'payload','UTF8'),'sha256'),'hex') is distinct from d->>'sha256' then
    raise exception 'Save checksum mismatch';
  end if;
  s := (d->>'payload')::jsonb;
  if jsonb_typeof(s->'player') is distinct from 'object' or jsonb_typeof(s->'world') is distinct from 'object'
    or not s ? 'rng_state' or not (s->'player') ?& array['level','hp','hp_max','mp','mp_max','gold','inventory']
    or jsonb_typeof(s->'player'->'inventory') is distinct from 'object'
    or (s->'player'->>'level')::numeric not between 1 and 99
    or (s->'player'->>'hp_max')::numeric <= 0
    or (s->'player'->>'hp')::numeric not between 0 and (s->'player'->>'hp_max')::numeric
    or (s->'player'->>'mp')::numeric not between 0 and (s->'player'->>'mp_max')::numeric
    or (s->'player'->>'gold')::numeric < 0 then raise exception 'Invalid save'; end if;
  if p_compatibility is distinct from 'schema2:' || (d->>'content_version') then
    return jsonb_build_object('status','UPDATE_REQUIRED');
  end if;
  select * into r from baram_private.saves where owner=u for update;
  if not found then return jsonb_build_object('status','NO_SESSION'); end if;
  if r.compatibility <> p_compatibility then return jsonb_build_object('status','UPDATE_REQUIRED'); end if;
  -- Idempotent reply after the committed response was lost in transit.
  if r.last_request=p_request then
    if r.document is distinct from p_document then raise exception 'Request id reused'; end if;
    return jsonb_build_object('status','OK','version',r.version);
  end if;
  if r.version <> p_base then
    return jsonb_build_object('status','CONFLICT','version',r.version,'document',r.document);
  end if;
  if r.device is distinct from p_device then return jsonb_build_object('status','BUSY'); end if;
  update baram_private.saves set backup=document, document=p_document, version=version+1,
    last_request=p_request, device=case when p_release then null else p_device end, updated_at=now()
    where owner=u returning * into r;
  return jsonb_build_object('status','OK','version',r.version);
end $$;

-- Empty accounts can leave without manufacturing a character or a save.
create function public.baram_release_empty(p_device uuid, p_compatibility text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare u uuid := auth.uid();
begin
  if u is null then raise exception 'Authentication required' using errcode='42501'; end if;
  update baram_private.saves set device=null where owner=u and device=p_device
    and compatibility=p_compatibility and version=0 and document is null;
  if not found then return jsonb_build_object('status','BUSY'); end if;
  return jsonb_build_object('status','OK');
end $$;

revoke all on function public.baram_open(uuid,text) from public, anon;
revoke all on function public.baram_push(uuid,text,bigint,uuid,text,boolean) from public, anon;
revoke all on function public.baram_release_empty(uuid,text) from public, anon;
grant execute on function public.baram_open(uuid,text), public.baram_push(uuid,text,bigint,uuid,text,boolean),
  public.baram_release_empty(uuid,text) to authenticated;
