#!/usr/bin/env python3
"""Bounded original-renderer clipping profile, isolated from the good decoder."""
import argparse,collections,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
from common import ROOT,WORK,load,write,file_sha,sha
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import Epf,Frame,region,dat_entries

class ClippedEpf(Epf):
    def __init__(self,data):
        super().__init__(data);self.clipped_runs=0;self.clipped_pixels=0;self.zero_runs=0
    def frame(self,index):
        if not 0<=index<self.count:raise ValueError('Frame out of bounds')
        top,left,bottom,right,po,mo=struct.unpack_from('<hhhhII',self.table,index*16);w,h=right-left,bottom-top
        if not 0<=w<=4096 or not 0<=h<=4096:raise ValueError('Invalid rectangle')
        if not w or not h:return Frame(index,left,top,w,h,b'',b'')
        pixels=region(self.pixels,po,w*h);cursor=mo;alpha=bytearray()
        for _ in range(h):
            row=bytearray(w);x=0;tokens=0
            while True:
                run=region(self.pixels,cursor,1)[0];cursor+=1;tokens+=1
                if tokens>2*w+256:raise ValueError('Unterminated/excessive stencil row')
                if not run:break
                length=run&127
                if not length:self.zero_runs+=1
                end=x+length
                if end>w:self.clipped_runs+=1;self.clipped_pixels+=max(0,end-max(x,w))
                # Source span positions advance without wrapping to next row;
                # only visible pixels inside the original rectangle are drawn.
                if run&128 and x<w:row[x:min(w,end)]=bytes([255])*max(0,min(w,end)-x)
                x=end
            alpha.extend(row)
        return Frame(index,left,top,w,h,pixels,bytes(alpha))

def probe(dat):
    entries=dat_entries(dat.read_bytes());old=load(WORK/'catalog/asset-errors.json');results=[]
    for error in old:
        key=error.get('source_file','')
        if not key.endswith('.epf'):continue
        try:
            ep=ClippedEpf(entries[key][2])
            if not ep.count:raise ValueError('ZERO_FRAMES')
            frames=[ep.frame(i) for i in range(ep.count)]
            results.append({'source_file':key,'result':'PASS','frames':ep.count,'clipped_runs':ep.clipped_runs,'clipped_pixels':ep.clipped_pixels,'zero_length_nonterminating_runs':ep.zero_runs,
                            'original_sha256':sha(entries[key][2]),'source_width_max':max(f.width for f in frames)})
        except ValueError as e:results.append({'source_file':key,'result':'BLOCKED','reason':str(e),'original_sha256':sha(entries[key][2])})
    regression=[]
    for key in ['body','head','monster','item','tilea']:
        a=Epf(entries[key+'.epf'][2]);b=ClippedEpf(entries[key+'.epf'][2])
        for i in sorted({0,min(3,a.count-1),a.count//2,a.count-1}):
            oldf=a.frame(i);newf=b.frame(i);same=oldf==newf
            regression.append({'source_file':key+'.epf','frame':i,'same_indices_offsets_alpha':same,'result':'PASS' if same else 'FAIL'})
    report={'scope':'DATA_ONLY_DECODE','source_dat_sha256':file_sha(dat),'decoder_sha256':file_sha(Path(__file__)),
      'profile':'ORIGINAL_SPAN_POSITION_WITH_RECTANGLE_CLIP','original_renderer_static_evidence':{'binary':'NA-4.95/NexusTK.exe','source_sha256':file_sha(dat.parent.parent/'NA-4.95/NexusTK.exe'),
        'address_ranges':['0x40218d–0x4021c7','0x402238–0x402272'],'observed':'Run length is run&0x7f, source x advances by full span, drawing intersects clip rectangle; no row overflow written'},
      'comparison_reference':{'repository':'DizzyThermal/EPFViewer','commit':'2bc585b3ae3310df5de46f7789eada92840fbd59','path':'FileHandlers/EpfFileHandler.gd','limitation':'Source viewer does not bound overshooting row writes; not accepted as safe raster oracle'},
      'attempts':results,'attempt_counts':dict(collections.Counter(r['result'] for r in results)), 'unchanged_good_samples':regression,
      'gameplay':'NOT_RUN','native_client_raster_comparison':'NOT_RUN','existing_good_decoder_changed':False}
    write(WORK/'catalog/expansion-2/epf-clipping-probe.json',report);print(report['attempt_counts'],'regression',len(regression),'failures',sum(r['result']=='FAIL' for r in regression))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dat',type=Path,required=True);probe(p.parse_args().dat)
