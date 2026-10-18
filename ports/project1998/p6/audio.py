"""Extract only actual WAV members from the frozen original 4.95 sound DAT."""
import argparse,hashlib,importlib.util,json,wave,io,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser()
    for k in ['originals','output','audit']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();spec=importlib.util.spec_from_file_location('p1',HERE.parent/'scripts/convert.py');p1=importlib.util.module_from_spec(spec);spec.loader.exec_module(p1)
    src=a.originals/'4x/NexusTK.snd';raw=src.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='f4c111b3865967a4afc8b1b8dd701797e507541744d88b3800387e712e153b69','Frozen sound archive drift'
    a.output.mkdir();members=[]
    for name,data in p1.dat_entries(raw).items():
        if not name.endswith('.WAV'):continue
        with wave.open(io.BytesIO(data)) as wav:
            info={'channels':wav.getnchannels(),'sample_rate':wav.getframerate(),'frames':wav.getnframes(),'sample_bytes':wav.getsampwidth()}
            assert info['channels'] in [1,2] and info['sample_bytes'] in [1,2]
            pcm=wav.readframes(wav.getnframes())
        # Original RIFF LIST tags contain legacy code-page metadata. Godot
        # expects UTF-8 tags. Strip metadata only, preserving every PCM byte.
        normalized=io.BytesIO()
        with wave.open(normalized,'wb') as wav:
            wav.setnchannels(info['channels']);wav.setsampwidth(info['sample_bytes']);wav.setframerate(info['sample_rate']);wav.writeframes(pcm)
        encoded=normalized.getvalue()
        if len(pcm)%2:
            # RIFF chunks align to even bytes; Python's wave writer omits the
            # terminal pad. Godot's importer correctly seeks past that pad.
            encoded+=b'\0';encoded=encoded[:4]+struct.pack('<I',len(encoded)-8)+encoded[8:]
        path=a.output/(str(int(name[:-4]))+'.wav');path.write_bytes(encoded)
        with wave.open(path.open('rb')) as wav:assert wav.readframes(wav.getnframes())==pcm
        members.append({'id':int(name[:-4]),'member':name,'source_sha256':hashlib.sha256(data).hexdigest(),
                        'normalized_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pcm_sha256':hashlib.sha256(pcm).hexdigest(),'pcm_preserved':True,**info})
    a.audit.write_text(json.dumps({'source':'4x/NexusTK.snd','sha256':hashlib.sha256(raw).hexdigest(),'wav_members':members,
        'music':'12 original MIDI files present; MIDI synthesizer not supplied or fabricated; background music not implemented',
        'playback':'native SendSound observer; no client-side inference from button presses'},indent=2)+'\n')
    print('SOURCE_WAV',len(members))
if __name__=='__main__':main()
