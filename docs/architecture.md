# Arquitetura e formatos

O LG Reverse Lab separa três atividades: edição de textos no computador, reconstrução de uma imagem experimental por delta e registro de observações de mídia no pendrive. Nenhuma delas fornece controle remoto do LG por USB.

## Fluxo dos arquivos

```text
ROM original fornecida pelo usuário
  ├─ prepare_catalogs.py → catálogos locais → editor OSD → prévia + manifestos
  └─ firmware_patch.py + delta publicado → Clara native458.preview.bin

USB Scout no computador
  → inventário antes → teste de mídia no LG → inventário depois + observações
```

A imagem de referência tem 2.091.376 bytes e SHA-256 `27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a`. Os parsers e o delta são específicos dessa imagem, não de toda a família HT306.

## Editor e catálogos locais

`tools/prepare_catalogs.py` valida tamanho, SHA-256 e XOR32 da fonte antes de interpretar os diretórios OSD. Gera `osd_strings.json` e `fontes.json` em `AUDITORIA_ROM/recursos_osd/`, incluindo limites dos recursos e metadados necessários ao editor. Esses arquivos são derivados da ROM e permanecem fora da publicação.

O diretório de textos da fonte contém 25 tabelas, com 542 registros cada: 13.550 registros no total. Há 15 fontes. Nem toda tabela pode ser tratada como texto Unicode comum; alguns rótulos de idiomas são inferências e certas sequências usam bancos de glifos ou valores dinâmicos.

O motor `LG_REVERSE_LAB_EDITOR/engine.py` compara os metadados com os limites e bytes da ROM. As edições permitidas preservam o espaço reservado ao registro e recalculam o rodapé XOR32. No banco latino suportado, o espaço digitado é codificado como `@` (`0x40`), de acordo com os textos OSD dessa fonte. O `@` literal não é uma opção de edição.

O servidor usa a interface de loopback do computador. `glyph_preview.py` lê os glifos da ROM fornecida e usa Pillow para a prévia. Sua paleta é uma referência; uma imagem produzida no PC não prova paleta, temporização ou saída de vídeo no aparelho.

## Delta experimental Clara native458

`tools/firmware_patch.py` usa o formato `lg-reverse-lab-xor-v1`. O JSON contém o tamanho, hashes da fonte, destino e delta, metadados e o delta XOR comprimido com zlib e codificado em base64. A aplicação exige a fonte exata; a reversão exige o destino exato. A saída só é aceita se o hash final corresponder ao esperado. O gravador cria um arquivo novo com sufixo `.preview.bin` e não sobrescreve arquivos.

O delta publicado reconstrói a imagem `c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1`. Ele não contém uma ROM completa, mas continua sendo específico de firmware proprietário. A publicação do delta não atribui direitos sobre esse firmware.

O candidato Clara mantém o motor nativo e seus comandos de desenho:

- Janela 12 nativa com 720 × 458 e paleta de fábrica.
- Dois recortes MTG para a composição superior e inferior, desenhados com o comando nativo `32`.
- Exibição direta do menu USB, sem a cobertura experimental que esperava a conclusão de uma animação.
- 403 MTGs únicos; 15 fontes; fonte 0 com 434 glifos em RLE explícito e proteção de leitura.
- Abertura WYS CORP estática e seis quadros preservados para a tela de descanso.

A alteração remove uma dependência de exibição observada no código e preserva a composição Clara. Isso é uma hipótese corretiva apoiada por testes no PC; o resultado visual dessa imagem no LG ainda precisa ser observado. A interface não implementa HTML, toque, desfoque de iOS, um decodificador de GIF ou uma abertura animada durante a leitura do USB.

## Exibição lógica e saída física

Marcar uma janela como visível no estado do software não demonstra que ela chegou à saída de vídeo. Os testes anteriores não executavam o caminho nativo de commit `204AE`; um compositor no computador podia mostrar uma janela que o aparelho não tinha necessariamente enviado à tela.

A revisão do candidato inclui a execução desse commit e as escritas de MMIO em dois modos de vídeo. Ela melhora a cobertura do caminho de exibição, mas continua sendo execução controlada no computador. Não mede o sinal componente, a cor real, a temporização, a memória flash instalada ou o comportamento de todos os periféricos.

## Scout

O Scout executa no computador usando a biblioteca padrão do Python, com Tkinter na interface gráfica. Ele compara arquivos por caminho, tamanho e hash quando aplicável, registra observações manuais e exporta uma sessão ZIP. Recursos opcionais de captura ou resumo local dependem de configuração adicional.

O pendrive transporta mídias e resultados. Não é um canal de depuração: o Scout não lê RAM, EEPROM, registradores ou o firmware instalado no LG; tampouco injeta comandos ou instala uma imagem. A tela e o som precisam de observação externa.
