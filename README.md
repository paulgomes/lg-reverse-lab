# LG Reverse Lab

Pesquisa independente do **LG HT306SU-A2**: editor local de textos OSD, ferramentas de observação por pendrive e um patch experimental da interface **Clara Biblioteca / WYS CORP**.

O repositório reúne código e um delta reversível. **Não inclui a ROM original, uma ROM modificada pronta para instalar, manuais, fotos pessoais, o GIF original ou catálogos completos de fontes e textos.** Você precisa fornecer sua própria imagem original, com o SHA-256 exato, para reconstruir a prévia localmente.

## Estado atual

| Etapa | Resultado conhecido |
| --- | --- |
| Firmware experimental anterior `f1c0a95eccb7…` no aparelho | Abertura WYS estática visível; USB e atualizador sem imagem; áudio normal, conforme relato do usuário. |
| Correção `c5183ed34966…` no PC | 98 casos MCU, 29 verificações ARM e revisão independente aprovados; cópia no pendrive conferida por releitura. |
| Correção `c5183ed34966…` no LG | **Novo teste físico pendente.** Os resultados no PC não demonstram a imagem real na TV. |

A correção usa a janela nativa de **720 × 458**, a paleta de fábrica e a exibição do menu sem depender da animação de entrada do USB. Mantém a composição Clara, com 403 imagens MTG únicas e 15 fontes. A abertura continua sendo uma imagem MPEG estática; os seis quadros WYS da tela de descanso foram preservados. Não há decodificador de GIF nem abertura animada durante a leitura do USB.

[Estado do aparelho](docs/hardware-status.md) · [Arquitetura](docs/architecture.md) · [Testes e limites](docs/testing.md) · [Resumo de validação](reports/validation-summary.json) · [Grafo de conhecimento](knowledge/graph.json)

## O que você pode usar

- **`tools/firmware_patch.py`**: inspeciona, verifica, aplica e reverte o delta, sempre vinculado aos hashes exatos de entrada e saída. Grava somente um novo arquivo `.preview.bin`.
- **`LG_REVERSE_LAB_EDITOR/`**: consulta textos OSD e gera prévias de alterações de tamanho fixo, com manifesto e restauração. Trabalha sobre a ROM original suportada; não é um editor visual completo do firmware Clara.
- **`tools/prepare_catalogs.py`**: reconstrói os catálogos locais do editor a partir da ROM fornecida pelo usuário, sem executar firmware.
- **`USB_SCOUT/`**: cria sessões, compara inventários e reúne observações externas. Executa no computador; não controla o LG nem lê sua memória interna.
- **`lab/osd_parse.py`**: parser de recursos OSD para análise local.

## Começar sem firmware

Use **Python 3.11 ou superior**. Os comandos abaixo funcionam no PowerShell e em shells comuns com `git` e `python` disponíveis. Em algumas instalações, o executável se chama `python3`.

```sh
git clone https://github.com/paulgomes/lg-reverse-lab.git
cd lg-reverse-lab
python tools/firmware_patch.py inspect patches/clara-native458-c5183ed34966.lgpatch.json
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s USB_SCOUT/tests -p "test_scout.py" -v
```

A inspeção do delta e os testes públicos com dados sintéticos não precisam da ROM nem de um aparelho conectado. Para a interface gráfica do Scout, o Python precisa incluir **Tkinter**; a prévia de fontes do editor usa **Pillow**, declarado em `requirements.txt`.

## Reconstruir a prévia experimental

O delta aceita somente esta imagem original:

```text
Arquivo de referência: LG_HT306LD1_1107200.rom
Tamanho: 2.091.376 bytes
SHA-256: 27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a
```

Coloque sua cópia dessa ROM na raiz do projeto. O programa verifica o conteúdo pelo hash; trocar o nome de outra ROM não a torna compatível.

```sh
python -c "from pathlib import Path; Path('local').mkdir(exist_ok=True)"
python tools/firmware_patch.py verify patches/clara-native458-c5183ed34966.lgpatch.json LG_HT306LD1_1107200.rom
python tools/firmware_patch.py apply patches/clara-native458-c5183ed34966.lgpatch.json LG_HT306LD1_1107200.rom local/clara-native458.preview.bin
```

A saída esperada tem o mesmo tamanho e este SHA-256:

```text
c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1
```

Para reconstruir a entrada a partir dessa saída e conferir a reversibilidade:

```sh
python tools/firmware_patch.py reverse patches/clara-native458-c5183ed34966.lgpatch.json local/clara-native458.preview.bin local/original-restaurado.preview.bin
```

O programa não sobrescreve arquivos existentes, não acessa o aparelho e não copia a prévia para um pendrive. O sufixo `.preview.bin` identifica uma saída de pesquisa; **hash correto e checksum válido não garantem que um firmware modificado funcionará no hardware**.

## Abrir o editor OSD

Esta etapa é opcional e também exige a ROM original acima. Os catálogos derivados são gerados localmente e estão excluídos do Git.

```sh
python -m pip install -r requirements.txt
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom --check
python LG_REVERSE_LAB_EDITOR/server.py --open
```

O navegador abre o servidor local do editor. As saídas ficam em `LG_REVERSE_LAB_EDITOR/outputs/`, com manifestos de alteração e restauração. A paleta usada na prévia é uma referência estimada, não uma medição das cores na TV. Alguns nomes de idiomas são inferidos a partir dos recursos e estão identificados como tal.

## Registrar um teste com o Scout

O Scout considera a pasta em que está instalado como a raiz do inventário. Para observar um pendrive, use uma cópia da pasta `USB_SCOUT` em um pendrive dedicado; executar a cópia do repositório inventaria essa pasta no computador.

```sh
cd USB_SCOUT
python lg_scout.py --new
python lg_scout.py --snapshot antes
```

Depois do teste de mídia e do retorno do pendrive ao computador:

```sh
python lg_scout.py --snapshot depois
python lg_scout.py --export
```

Sem argumentos, `python lg_scout.py` abre a interface gráfica. A função de verificação de mídia usa cinco arquivos sintéticos incluídos em `LG_TESTES`: três MP3 com sinais de teste e dois JPEG com padrões de cor. Eles não contêm gravações ou fotos pessoais. `tools/generate_test_media.py` permite regenerá-los com FFmpeg e Pillow.

Os inventários e arquivos exportados podem conter nomes e observações pessoais: mantenha-os locais ou revise-os antes de compartilhar.

## Testar no aparelho

Este projeto não oferece um instalador nem um procedimento de atualização sem imagem. **Não pressione PLAY por tempo memorizado se o atualizador estiver preto.** A confirmação de atualização precisa estar visível antes de qualquer gravação. O caso conhecido usa vídeo componente; uma tentativa de diagnóstico por VIDEO OUT/AV, sem pendrive e fora de uma atualização, continua pendente e não garante recuperar os menus.

Contribuições úteis incluem análises reproduzíveis, correções de parser e resultados de testes que distingam execução no PC, observação da TV e identidade do arquivo. Consulte [Testes e limites](docs/testing.md) antes de interpretar uma prévia como validação física.

## Autoria e escopo

Mantido por [paulgomes](https://github.com/paulgomes). Projeto independente, sem vínculo ou endosso da LG. Esta publicação não atribui uma licença ao firmware ou às marcas de terceiros e não declara uma licença de software para o código. Consulte [NOTICE.md](NOTICE.md).
