"""Leitura da estrutura do bloco OSD do LG_HT306LD1_1107200.rom. Somente leitura; nao escreve nada."""
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
print('itens da parte de dados:',[(hex(s),hex(l)) for s,l in items])
O=items[0][0]+0x10   # base dos offsets internos (inicio da assinatura)
print('assinatura',d[O:O+12], 'ptr[3] fontes dir',hex(O+u32(O+12)))
F=O+u32(O+12); nf=u32(F); fonts=[u32(F+4+4*i) for i in range(nf+1)]
print('fontes',nf,[hex(O+x) for x in fonts])
I=F+4+4*(nf+1); ni=u32(I); icons=[u32(I+4+4*i) for i in range(ni+1)]
print('icones',ni,'primeiro',hex(O+icons[0]),'ultimo fim',hex(O+icons[-1]))
L=I+4+4*(ni+1); print('apos icones @',hex(L),d[L:L+16])
# diretorio de idiomas: tentar [count][start,len]*count
