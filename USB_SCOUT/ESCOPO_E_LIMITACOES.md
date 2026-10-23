# LG Reverse Lab — USB Scout 0.1

## Arquitetura real (sem alegar capacidades não demonstradas)

`Notebook Windows (Python 3 + Ollama opcional) ↔ pendrive FAT32 ↔ LG HT306SU-A2`

A seta com o LG representa **transporte de mídia e arquivos**, não uma conexão de controle ou execução remota. O firmware da LG, de acordo com o manual do proprietário fornecido, suporta USB para mídias FAT16/FAT32, e documenta que sua porta USB **não pode ser conectada ao PC**. A interface HDMI é **saída**.

**O agente não é uma cópia do ChatGPT e não habita o LG.** É uma ferramenta externa com coleta local, registro de observações, análise determinística de mudanças no pendrive e resumo textual opcional via Ollama. Não toma decisões sobre edição de EEPROM nem emite comandos de serviço.

## Fontes e confiança

- `LG_HT306LD1_1107200.rom`: SHA-256 verificado no arquivo anexado ao chat: `27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a`, tamanho 2.091.376 bytes; **não foi incluído neste pacote**.
- Manual LG HT306SU (P/NO MFL66983891): página 8 informa USB FAT16/FAT32, não suporta conexão USB para PC; página 14 apresenta HDMI OUT; página 16 apresenta entrada AUX L/R.
- `RELATORIO-ENGENHARIA-REVERSA.md`: cita `.ROM`, `.EPM`, `.HEX` e interpreta rotinas; essas alegações **ainda requerem auditoria independente do disassembly**.

## O que faz

1. Valida por hash 3 MP3 estéreo de teste e 2 JPEG. Os MP3 usam 44,1 kHz e 128 kbit/s, dentro dos limites documentados no manual.
2. Cria sessão identificada no pendrive.
3. Registra inventário do pendrive antes/depois, comparando arquivos novos, removidos e modificados.
4. Salva notas manuais e evidências (fotos, vídeos, áudio); permite capturar um quadro de webcam e cinco segundos de microfone no notebook **somente após clique** e com dependências opcionais.
5. Gera ZIP com manifesto JSON, inventários, comparações e observações para envio posterior ao ChatGPT.
6. Opcionalmente resume as observações em um modelo local acessado via `127.0.0.1:11434` (Ollama). Não há chamadas a modelos remotos no programa.

## O que não faz

- Não lê a EEPROM, RAM, registradores, logs de HDMI ou comunicação infravermelha do LG.
- Não executa código no LG via USB.
- Não modifica nem instala firmware; não contém `.ROM`, `.EPM` ou `.HEX`.
- Não extrai conhecimento automaticamente de tudo o que o LG faz. Mudanças no USB só aparecem se o LG **gravar arquivos**, como pela função normal de gravação, e as respostas de tela e som dependem de observação humana ou mídia capturada externamente.
- Não oferece equivalência com GPT-6, mesmo usando um LLM via Ollama.

## Próximos desenvolvimentos possíveis

Em versões futuras, acrescentar captura contínua controlada da câmera para observar o visor do LG, análise de espectro do áudio e, se houver emissor IR compatível, ações de controle via API local com permissões limitadas. Cada recurso exige hardware e testes de segurança próprios.
