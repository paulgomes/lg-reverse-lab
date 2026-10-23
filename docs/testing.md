# Testes, evidência e limites

Há dois conjuntos diferentes: os testes executáveis publicados com as ferramentas e as verificações nativas realizadas durante a pesquisa do firmware. Os primeiros podem rodar em uma cópia limpa deste repositório; os segundos dependem de artefatos locais não distribuídos aqui.

## Testes públicos sem ROM ou aparelho

Na raiz do repositório, com Python 3.11 ou superior:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s USB_SCOUT/tests -p "test_scout.py" -v
```

O conjunto de patch usa imagens sintéticas para verificar reversibilidade, rejeição de entrada incompatível, hashes, dados comprimidos inválidos e recusa de sobrescrita. Também confere o delta publicado e sua marcação experimental. Isso não equivale a executar o firmware.

Os testes não gráficos do Scout verificam inventários, comparação, sessões e exportação usando dados temporários. A seleção `test_scout.py` evita abrir uma janela Tk durante a execução automatizada. Dados simulados desses testes não são observações do LG.

## Testes opcionais com a fonte original

Forneça localmente a ROM original com o SHA-256 documentado no README e gere os catálogos:

```sh
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom --check
python -m unittest discover -s LG_REVERSE_LAB_EDITOR -p "test_engine.py" -v
```

Esses testes conferem o motor de textos contra a imagem original, incluindo alterações concretas, checksum, limites e restauração. Não constituem um teste visual do candidato Clara completo. A ROM e os catálogos derivados ficam locais.

Para experimentar a interface gráfica do Scout, é necessário um ambiente com Tkinter e uma sessão gráfica. A função de verificação de mídias usa os cinco arquivos sintéticos incluídos em `USB_SCOUT/LG_TESTES`: três MP3 e dois JPEG. Eles podem ser regenerados com `tools/generate_test_media.py`, FFmpeg e Pillow; não são mídias pessoais de pesquisa.

## Verificações do candidato native458

O candidato de destino `c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1` passou, no ambiente de pesquisa, por **98 casos MCU, 29 verificações ARM, revisão independente e conferência da cópia USB por releitura**. O [resumo público de validação](../reports/validation-summary.json) registra esses resultados. O conjunto completo de emulação, ROMs e relatórios privados não faz parte deste pacote público; os comandos de testes acima não reproduzem esse conjunto de validação nativa.

A revisão incluiu preservação das regiões declaradas, reconstrução e inversão do patch, limites de recursos, comandos de desenho e execução do commit nativo de exibição em dois modos de vídeo. Recursos com problemas encontrados durante a preparação foram corrigidos ou rejeitados antes da cópia do candidato.

## O que esses resultados não comprovam

- Uma janela na lista lógica de visibilidade não é prova de saída de vídeo. A revisão passou a incluir o commit nativo `204AE` e suas escritas de MMIO, mas isso ainda ocorre no computador.
- PNGs de prévia não medem as cores do aparelho. A paleta representada e a composição de uma cena podem ser estimadas.
- Um checksum válido e o SHA-256 esperado provam identidade e consistência do arquivo, não compatibilidade física, possibilidade de recuperação ou funcionamento de todos os estados.
- A releitura do pendrive não confirma a memória flash instalada nem significa que o agente realizou a atualização no LG.
- A animação da tela de descanso não implica suporte a GIF na abertura ou durante a leitura do USB.

O teste físico mais recente do firmware anterior teve USB e atualizador pretos, com áudio normal. O candidato corretivo continua aguardando uma nova observação do aparelho. Consulte [Estado dos testes no aparelho](hardware-status.md).

## Como relatar um resultado

Informe o hash do arquivo usado, modelo do aparelho, tipo de cabo, modo de vídeo quando conhecido, passos reproduzíveis e comportamento observado. Distinga imagem no PC, cópia de arquivo no USB, atualização realizada e imagem observada na TV. Não publique dumps, manuais, catálogos completos ou fotos pessoais como anexos de um relato sem revisar seu conteúdo e sua distribuição.

Se as instruções de atualização não estiverem visíveis, pare a tentativa de gravação. Não use uma sequência de PLAY ou retirada do USB por memória de tempo.
