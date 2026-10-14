import struct
import sys
import unittest
import zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from legacy_assets import AssetError,Frame,Palette
from legacy_installers import wise_streams,wise_named_records,installshield4


def stream(payload):
    compressor=zlib.compressobj(wbits=-15)
    blob=compressor.compress(payload)+compressor.flush()
    return blob+struct.pack('<I',zlib.crc32(payload)&0xffffffff)


class NewAssetCases(unittest.TestCase):
    def test_wise_chain_and_crc_truncation(self):
        data=stream(b'first bitmap')+stream(b'second payload')
        self.assertEqual([payload for row,payload in wise_streams(data,0)],[b'first bitmap',b'second payload'])
        for damaged in [data[:-1],data[:-4]+bytes(4),data+b'garbage']:
            with self.subTest(size=len(damaged)),self.assertRaises((AssetError,zlib.error)):
                list(wise_streams(damaged,0))

    def test_wise_name_requires_crc_and_size(self):
        raw=b'original file bytes';crc=zlib.crc32(raw)&0xffffffff
        prefix=bytearray(48);struct.pack_into('<II',prefix,8,824,840);struct.pack_into('<I',prefix,20,len(raw));struct.pack_into('<I',prefix,44,crc)
        script=bytes(prefix)+b'%MAINDIR%\\NexusTK.dat\0'
        records=[{'crc32':crc,'bytes':len(raw),'index':2,'offset':1024,'compressed_bytes':12}]
        self.assertEqual(list(wise_named_records(script,records))[0][0],'NexusTK.dat')
        self.assertEqual(list(wise_named_records(script,[records[0]|{'bytes':len(raw)+1}])),[])
        self.assertEqual(list(wise_named_records(script,records*2)),[])
        unsafe=bytes(prefix)+b'%MAINDIR%\\..\\NexusTK.dat\0'
        self.assertEqual(list(wise_named_records(unsafe,records)),[])

    def test_installshield_bounds_and_sync_flush(self):
        raw=b'expected original bytes';compressor=zlib.compressobj(wbits=-15)
        compressed=compressor.compress(raw)+compressor.flush(zlib.Z_SYNC_FLUSH)
        header=bytearray(512);struct.pack_into('<6I',header,0,0x28635349,0x01000004,0,512,0,768)
        desc=bytearray(128);struct.pack_into('<I',desc,12,128);struct.pack_into('<I',desc,20,128)
        struct.pack_into('<I',desc,28,1);struct.pack_into('<I',desc,40,1)
        table=bytearray(128);struct.pack_into('<II',table,0,100,8)
        struct.pack_into('<IIHII',table,8,64,0,4,len(raw),len(compressed));struct.pack_into('<I',table,46,768)
        table[64:73]=b'file.dat\0'
        data=bytes(header+desc+table)+compressed
        self.assertEqual(list(installshield4(data))[0][1],raw)
        with self.assertRaises(AssetError):list(installshield4(data[:-1]))

    def test_recolor_threshold_wrap_and_unchanged_outline(self):
        palette=Palette(tuple((i,i,i) for i in range(256)))
        frame=Frame(0,0,0,4,1,bytes([16,47,48,255]),bytes([255]*4))
        self.assertEqual(frame.rgba(palette,9),bytes([16,16,16,255,47,47,47,255,120,120,120,255,71,71,71,255]))
        self.assertEqual(frame.rgba(palette,0)[:4],bytes([16,16,16,255]))
        with self.assertRaises(AssetError):frame.rgba(palette,256)


if __name__=='__main__':unittest.main()
