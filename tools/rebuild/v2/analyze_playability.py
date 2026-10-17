#!/usr/bin/env python3
"""Summarize retained ordinary GUI evidence without changing it."""
import argparse
import bisect
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def records(path):
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try: result.append(json.loads(line))
            except json.JSONDecodeError: pass
    return result


def distribution(values):
    a=sorted(float(v) for v in values)
    if not a: return {'n':0,'status':'NOT_RUN'}
    def q(p):
        i=(len(a)-1)*p
        lo=int(i); hi=math.ceil(i)
        return round(a[lo]+(a[hi]-a[lo])*(i-lo),3)
    return {'n':len(a),'p50_ms':q(.5),'p95_ms':q(.95),'p99_ms':q(.99),
            'max_ms':round(a[-1],3),'over50ms':sum(v>50 for v in a),
            'over100ms':sum(v>100 for v in a)}


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    root=a.directory
    result=json.loads((root/'OS_PLAYABILITY.json').read_text())
    trace=records(root/'journey-frame-timeline.jsonl')
    frames=[r for r in trace if r.get('kind')=='frame']
    saves=[r for r in trace if r.get('kind')=='save']
    inputs=[r for r in trace if r.get('kind')=='input']
    feedback=[r for r in trace if r.get('kind')=='frame_post_draw_feedback']
    operator=records(root/'os-input-timeline.jsonl')
    sync=next((r for r in trace if r.get('kind')=='clock_sync'),None)
    summary={'scope':result['scope'],'status':result['status'],
             'wall_seconds':result['wall_seconds'],
             'ordinary_return_skill':result.get('ordinary_return_skill'),
             'milestones':[r for r in result.get('observations',[]) if r.get('name') not in ['live_progress']],
             'end_state':{k:result.get('final',result.get('before_restart',{})).get(k) for k in ['character','skills','equipment','stats','inventory']},
             'operator_sha256':result['operator_sha256'],
             'runtime_manifest_sha256':result['runtime_manifest_sha256'],
             'content_sha256':result['content_sha256'],
             'ordinary_checks':result['checks'],
             'frame_delta':distribution(r['interval_ms'] for r in frames),
             'engine_wall_frame_interval':distribution((b['us']-a['us'])/1000 for a,b in zip(frames,frames[1:])),
             'process_duration':distribution(r['process_ms'] for r in frames),
             'engine_input_to_frame_post_draw':distribution(r['elapsed_ms'] for r in feedback),
             'save_duration':distribution(r['duration_ms'] for r in saves),
             'save_statuses':dict(Counter(r['status'] for r in saves)),
             'recording_comparison':[],
             'external_rss':records(root/'external-rss.jsonl'),
             'video_validation':result.get('video_validation'),
             'limits':[
                 'Unaccelerated OS XTEST is automated input, not human play.',
                 'Full-session trace metrics mean every retained active-play frame/save/input event. The frozen app returns before frame tracing when state is empty or play is hidden; initial menus and full startup/loading intervals do not have frame events. Raw unedited video includes those visible intervals.',
                 'Save-to-menu profiling flushes accumulated trace data after the last active play frame; this instrumented flush is visible in video but is not an active-play frame sample.',
                 'Linux llvmpipe is not native Windows, Android or Galaxy performance.',
                 'Engine delta may be smoothed; engine wall interval is elapsed between process trace points.',
                 'frame_post_draw is engine rendering feedback; it does not prove a changed pixel for every input or measured OS display presentation.',
                 '30fps X11 recording validates visible continuity and route; capture PTS alone cannot prove app presentation FPS.',
                 'Trace dictionaries accumulate during play and can contribute to observed memory growth.',
                 'OS input envelope begins just before xdotool invocation, not at a kernel device timestamp.',
                 'Recording off/on samples reuse the same ordinary directional sequence but occurred during initial concurrent export/import activity; they are observations, not isolated causal capture-overhead estimates.',
                 'The long-session operator missed clipped skill controls and reserved insufficient learning materials; repeated teacher travel is an operator coverage limitation, not measured game progression balance. Targeted continuation evidence is reported separately.',
             ]}
    for phase in sorted({k for row in saves for k,v in row.get('phases',{}).items() if isinstance(v,(int,float))}):
        summary.setdefault('save_phases',{})[phase]=distribution(row['phases'][phase] for row in saves if phase in row.get('phases',{}))
    if sync:
        def unix_us(row): return sync['unix_us']+row['us']-sync['us']
        for recording in [False,True]:
            start=next((r for r in operator if r.get('name')=='recording_comparison_start' and r.get('recording')==recording),None)
            end=next((r for r in operator if r.get('name')=='recording_comparison_end' and r.get('recording')==recording),None)
            if start and end:
                lo=start['wall_unix_ns']/1000;hi=end['wall_unix_ns']/1000
                subset=[r for r in frames if lo<=unix_us(r)<=hi]
                summary['recording_comparison'].append({'recording':recording,'wall_seconds':(hi-lo)/1e6,'frame_delta':distribution(r['interval_ms'] for r in subset),'engine_wall_frame_interval':distribution((b['us']-a['us'])/1000 for a,b in zip(subset,subset[1:])),'save_duration':distribution(r['duration_ms'] for r in saves if lo<=unix_us(r)<=hi),'engine_input_to_frame_post_draw':distribution(r['elapsed_ms'] for r in feedback if lo<=unix_us(r)<=hi)})
        feedback_times=[unix_us(r) for r in feedback]
        engine_input_times=[unix_us(r) for r in inputs]
        matched=[];matching_records=[]
        action=[r for r in operator if r.get('kind') in ['key','mouse_click']]
        unmatched=0
        for index,r in enumerate(action):
            t=r['wall_unix_ns']/1000
            next_t=action[index+1]['wall_unix_ns']/1000 if index+1<len(action) else float('inf')
            i=bisect.bisect_left(engine_input_times,t)
            if i>=len(engine_input_times) or engine_input_times[i]>=next_t:
                unmatched+=1;matching_records.append({'action_unix_us':t,'status':'UNMATCHED'});continue
            j=bisect.bisect_left(feedback_times,engine_input_times[i])
            if j>=len(feedback_times):
                unmatched+=1;matching_records.append({'action_unix_us':t,'status':'UNMATCHED'});continue
            delay=(feedback_times[j]-t)/1000;matched.append(delay);matching_records.append({'action_unix_us':t,'status':'MATCHED','delay_ms':delay})
        summary['OS_command_log_to_engine_render_envelope']=distribution(matched)
        summary['OS_envelope_matching']={'all_logged_actions':len(action),'matched_before_next_action':len(matched),'unmatched':unmatched,'latency_outliers_removed':0}
        for comparison in summary['recording_comparison']:
            flag=comparison['recording']
            began=next(r for r in operator if r.get('name')=='recording_comparison_start' and r.get('recording')==flag)['wall_unix_ns']/1000
            ended=next(r for r in operator if r.get('name')=='recording_comparison_end' and r.get('recording')==flag)['wall_unix_ns']/1000
            rr=[r for r in matching_records if began<=r['action_unix_us']<=ended]
            vv=[r['delay_ms'] for r in rr if r['status']=='MATCHED']
            comparison['OS_command_log_to_engine_render_envelope']=distribution(vv)
            comparison['OS_envelope_matching']={'all_logged_actions':len(rr),'matched_before_next_action':len(vv),'unmatched':sum(r['status']=='UNMATCHED' for r in rr),'latency_outliers_removed':0}
        # Keep all long frames, with overlapping completed save intervals and
        # the most recent ordinary OS action for reproducible diagnosis.
        action=[r for r in operator if r.get('kind') in ['key','mouse_click']]
        action_times=[r['wall_unix_ns']/1000 for r in action]
        incidents=[]
        for prior,current in zip(frames,frames[1:]):
            duration=(current['us']-prior['us'])/1000
            if duration<=100:continue
            t=unix_us(current); i=bisect.bisect_right(action_times,t)-1
            overlap=[s for s in saves if s['us']>=prior['us'] and s['us']-s['duration_ms']*1000<=current['us']]
            incidents.append({'engine_us':current['us'],'unix_us':t,'wall_interval_ms':round(duration,3),'delta_ms':current['interval_ms'],'process_ms':current['process_ms'],'overlapping_saves':[{'status':s['status'],'duration_ms':s['duration_ms'],'revision':s['revision']} for s in overlap],'previous_OS_action':action[i] if i>=0 else None})
        summary['over100ms_wall_incidents']=incidents
    rss=summary['external_rss']
    summary['external_memory']={'samples':len(rss),'first':rss[0] if rss else None,'last':rss[-1] if rss else None,'scope':'Host RSS under accumulating per-frame tracing; not a product leak determination.'}
    summary['engine_static_memory']={'first_bytes':frames[0].get('memory_bytes') if frames else None,'last_bytes':frames[-1].get('memory_bytes') if frames else None}
    summary['environment']={**result.get('environment',{}),'renderer':'OpenGL Compatibility / Mesa llvmpipe software rendering','isolation':'Not an isolated hardware benchmark. See timestamped HOST_ENVIRONMENT evidence and separate preliminary-session contenders. No physical target-device, battery or thermal claim.'}
    host=root.parents[1]/'HOST_ENVIRONMENT.json'
    summary['host_environment_reference']={'file':str(host),'sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'details':json.loads(host.read_text())} if host.exists() else {'status':'NOT_FOUND'}
    stress_start=next((r for r in operator if r.get('name')=='continuous_stress_started'),None)
    stress_end=next((r for r in reversed(operator) if r.get('name')=='requested_play_duration_completed'),None)
    if sync and stress_start:
        lo=stress_start['wall_unix_ns']/1000;hi=stress_end['wall_unix_ns']/1000 if stress_end else float('inf')
        ff=[r for r in frames if lo<=sync['unix_us']+r['us']-sync['us']<=hi]
        ss=[r for r in saves if lo<=sync['unix_us']+r['us']-sync['us']<=hi]
        ii=[r for r in feedback if lo<=sync['unix_us']+r['us']-sync['us']<=hi]
        summary['continuous_stress']={'start':stress_start,'end':stress_end,'observed_seconds':stress_end.get('play_seconds') if stress_end else None,'required_seconds':result['requested_seconds'],'frame_delta':distribution(r['interval_ms'] for r in ff),'engine_wall_frame_interval':distribution((b['us']-a['us'])/1000 for a,b in zip(ff,ff[1:])),'process_duration':distribution(r['process_ms'] for r in ff),'engine_input_to_frame_post_draw':distribution(r['elapsed_ms'] for r in ii),'save_duration':distribution(r['duration_ms'] for r in ss),'static_memory_first_bytes':ff[0].get('memory_bytes') if ff else None,'static_memory_last_bytes':ff[-1].get('memory_bytes') if ff else None}
        phase_matching=[r for r in matching_records if lo<=r['action_unix_us']<=hi]
        phase_latencies=[r['delay_ms'] for r in phase_matching if r['status']=='MATCHED']
        summary['continuous_stress']['OS_command_log_to_engine_render_envelope']=distribution(phase_latencies)
        summary['continuous_stress']['OS_envelope_matching']={'all_logged_actions':len(phase_matching),'matched_before_next_action':len(phase_latencies),'unmatched':sum(r['status']=='UNMATCHED' for r in phase_matching),'latency_outliers_removed':0}
        summary['continuous_stress']['save_phases']={phase:distribution(row['phases'][phase] for row in ss if phase in row.get('phases',{})) for phase in summary.get('save_phases',{})}
        summary['continuous_stress']['over100ms_wall_incidents']=[row for row in summary.get('over100ms_wall_incidents',[]) if lo<=row['unix_us']<=hi]
        summary['continuous_stress']['scope']='Every frame, input feedback and save from explicit preregistered stress-start marker through completed duration marker, including loading and interactions within that phase. Full-session tail retained separately.'
    if result.get('targeted_followup') or result.get('transaction_followup'):
        summary['limits']=[s for s in summary['limits'] if not s.startswith('The long-session operator missed')]
        summary['exact_pack_sha256']=result.get('exact_pack_sha256')
        summary['continued_naturally_earned_data']=result.get('continued_naturally_earned_data')
    fps=result.get('performance_checkpoints',[])
    if result.get('controlled_capture_comparison'):
        summary['limits']=[line for line in summary['limits'] if not line.startswith('Recording off/on samples reuse')]
        summary['limits'].append('Capture comparison is one sequential30-second off/on pair using the same ordinary directional sequence, without randomized ABBA order or confidence intervals; it does not establish physical-device overhead.')
    summary['performance_checkpoints']=fps
    summary['all_frame_data_sha256']=hashlib.sha256((root/'journey-frame-timeline.jsonl').read_bytes()).hexdigest()
    summary['target_assessment']={
        'frame_delta_p95_le33_4':summary['frame_delta'].get('p95_ms',float('inf'))<=33.4,
        'frame_delta_p99_le50':summary['frame_delta'].get('p99_ms',float('inf'))<=50,
        'engine_wall_p95_le33_4':summary['engine_wall_frame_interval'].get('p95_ms',float('inf'))<=33.4,
        'engine_wall_p99_le50':summary['engine_wall_frame_interval'].get('p99_ms',float('inf'))<=50,
        'engine_render_feedback_p95_le100':summary['engine_input_to_frame_post_draw'].get('p95_ms',float('inf'))<=100,
        'saves_over100ms':summary['save_duration'].get('over100ms'),
        'actual_OS_presentation':'NOT_RUN',
        'human_fun_acceptance':'NOT_RUN',
    }
    (root/'FINAL_ANALYSIS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['status','frame_delta','engine_wall_frame_interval','engine_input_to_frame_post_draw','save_duration','target_assessment']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
