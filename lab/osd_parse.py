"""Read the OSD block structure of LG_HT306LD1_1107200.rom without writing files."""
import struct,sys
d=open(sys.argv[1] if len(sys.argv)>1 else 'LG_HT306LD1_1107200.rom','rb').read()
u32=lambda o:struct.unpack_from('<I',d,o)[0]
DS=u32(0x203)&0xffffff
print('DataStart',hex(DS))
items=[]
for j in range(16):
    off,ln=u32(DS+8*j),u32(DS+8*j+4)
    if off==0 and ln==0: break
    items.append(((off<<2)+DS,ln))
print('data-section items:',[(hex(s),hex(l)) for s,l in items])
O=items[0][0]+0x10   # Internal offset base (start of signature).
print('signature',d[O:O+12], 'ptr[3] font directory',hex(O+u32(O+12)))
F=O+u32(O+12); nf=u32(F); fonts=[u32(F+4+4*i) for i in range(nf+1)]
print('fonts',nf,[hex(O+x) for x in fonts])
I=F+4+4*(nf+1); ni=u32(I); icons=[u32(I+4+4*i) for i in range(ni+1)]
print('icons',ni,'first',hex(O+icons[0]),'final end',hex(O+icons[-1]))
L=I+4+4*(ni+1); print('after icons @',hex(L),d[L:L+16])
# Language directory: try [count][start,len]*count.
