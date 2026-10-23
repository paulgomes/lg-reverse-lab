# Estado dos testes no aparelho

**O candidato Clara native458 `c5183ed34966…` ainda não tem confirmação física de imagem no LG.** Passar nos testes do computador e conferir uma cópia no pendrive são etapas distintas de instalar e observar o resultado na TV.

## Evidência disponível

| Imagem | Origem da evidência | Resultado e limite |
| --- | --- | --- |
| Modificações iniciais de textos e recursos | Relatos e fotos do usuário | Textos alterados e identidade visual apareceram no aparelho; áudio, pausa, retomada, volume e Ajustes foram relatados como funcionais nas etapas correspondentes. Isso não valida versões posteriores. |
| `757ee81bad98…` | Teste físico anterior associado a essa imagem | USB visível, com layout inadequado; imagem WYS durante a leitura continuava estática. |
| `f1c0a95eccb7…` | Relato físico mais recente | Abertura WYS CORP estática visível, menu USB e atualizador pretos, música normal. O usuário relatou ter atualizado sem imagem pelo tempo memorizado; essa ação não deve ser repetida como procedimento. |
| `c5183ed34966…` | Testes nativos no computador, revisão independente e releitura da cópia USB | Verificações aprovadas; **teste físico da correção pendente**. |

O hash do arquivo enviado ao pendrive não é uma leitura do chip do LG. A associação entre uma imagem e um relato físico não deve ser apresentada como confirmação do hash instalado.

## Identidade da correção

```text
Fonte original:
27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a

Candidato Clara native458:
c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1

Tamanho de cada imagem: 2.091.376 bytes
```

A correção restaura os contratos nativos de janela, paleta e exibição do USB, preservando o desenho Clara. Ela remove a espera pela animação experimental para tornar o menu visível. Não foi demonstrado que esse mecanismo era a única causa do defeito físico.

## Abertura e animação

A abertura é uma imagem MPEG estática. O candidato não reproduz um arquivo GIF na inicialização nem inicia uma animação durante o reconhecimento do USB. Os seis quadros WYS da tela de descanso foram preservados, mas isso não comprova que a sequência completa funcionará em todos os estados do aparelho.

## Próxima evidência necessária

O usuário informou conexão por vídeo componente YPbPr. Um diagnóstico possível, **fora de qualquer atualização e sem pendrive**, é testar VIDEO OUT amarelo em uma entrada AV compatível e verificar se Ajustes reaparece. Essa alternativa não foi confirmada e não garante recuperar a imagem.

Antes de qualquer nova gravação, as instruções de atualização precisam estar visíveis. **Se o atualizador ficar preto, não retirar o USB nem pressionar PLAY com base em tempo memorizado.** Este repositório não fornece uma sequência de atualização às cegas.

Uma validação futura deve registrar o arquivo utilizado, o cabo e modo de vídeo, abertura, USB parado e tocando, seleção de itens, fila, Ajustes, pausa/retomada, volume e tela do atualizador. Fotos ou vídeos devem excluir informações pessoais antes de serem publicados.
