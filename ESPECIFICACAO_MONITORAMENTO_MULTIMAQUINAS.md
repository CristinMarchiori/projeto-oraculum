# Especificação: Monitoramento Multimáquinas

## 1. Objetivo

Permitir que o Oraculum consulte simultaneamente o estado de máquinas Schneider e Rockwell cadastradas no backend.

A primeira implementação será somente de leitura e não substituirá o monitoramento individual de ciclos já existente.

## 2. Situação atual

O sistema atual utiliza:

- Uma única máquina ativa.
- Uma única thread de aquisição.
- Variáveis globais para buffers, ciclos, tempos e comunicação.
- Uma fila compartilhada de salvamento.
- Seleção de máquina controlada pelo backend.

A rotina atual não permite monitorar várias máquinas simultaneamente com segurança.

## 3. Primeira etapa

Implementar um monitor de estado independente do monitoramento atual de ciclos.

A validação inicial utilizará:

- Schneider 1410.
- Rockwell 1582.

Para cada máquina, consultar somente:

- Disponibilidade da comunicação.
- Valor do trigger de ciclo.
- Data e hora da última leitura válida.
- Mensagem da última falha.
- Protocolo, IP e slot aplicáveis.

## 4. Comportamento desejado

Cada máquina deverá possuir um estado independente:

- `desconectada`
- `conectada`
- `aguardando_ciclo`
- `em_ciclo`
- `falha_comunicacao`

Uma falha em uma máquina não poderá interromper a leitura das demais.

## 5. Segurança

Nesta etapa:

- Não escrever nos CLPs.
- Não alterar `Flag_MonitorStatus`.
- Não iniciar captura de ciclo.
- Não gerar CSV ou PNG.
- Não alterar os drivers existentes.
- Não alterar a rotina atual `leitor_com_trigger()`.
- Não alterar a seleção individual de máquina.
- Não testar escrita sem autorização explícita.

## 6. Dados conhecidos

### Schneider 1410

- IP: `172.25.217.210`
- Protocolo: `SCHNEIDER`
- Porta: `502`
- Trigger atual: `MW29970:BOOL:0`

### Rockwell 1582

- IP: `172.25.217.155`
- Protocolo: `ROCKWELL`
- Porta: `44818`
- Slot: `0`
- Trigger: `Flag_MonitorPrensaEmCiclo`

## 7. Estrutura proposta

Criar um estado separado por máquina contendo:

- Identificador.
- Nome.
- IP.
- Protocolo.
- Porta.
- Slot.
- Tag do trigger.
- Valor atual do trigger.
- Estado da comunicação.
- Última leitura válida.
- Último erro.
- Controle de execução.
- Thread independente.

## 8. Arquivos inicialmente impactados

### `app.py`

Responsável por:

- Criar o estado independente das máquinas.
- Iniciar e encerrar o monitoramento simultâneo.
- Executar leituras somente de trigger.
- Disponibilizar os estados para a interface.

### `index.html`

Não será alterado na primeira implementação do backend.

Uma alteração visual somente será realizada depois que as leituras simultâneas forem validadas localmente.

## 9. Critérios de validação

A primeira etapa será considerada válida quando:

1. A máquina 1410 responder corretamente.
2. A máquina 1582 responder corretamente.
3. As leituras ocorrerem sem escrita nos CLPs.
4. Cada máquina mantiver estado independente.
5. A falha de uma máquina não interromper a outra.
6. O monitoramento individual atual continuar funcionando.
7. O encerramento do programa finalizar todas as threads.
8. Nenhum CSV ou PNG for criado pelo monitor múltiplo.

## 10. Expansão futura

Somente após a validação inicial:

- Cadastrar tags oficiais das demais máquinas Rockwell.
- Incluir progressivamente outras máquinas.
- Exibir os estados na interface.
- Avaliar captura simultânea de ciclos.
- Separar buffers, FORM, limites, histórico e salvamento por máquina.

## 11. Rollback

Branch de desenvolvimento:

`feature/monitoramento-multimaquinas`

Versão estável preservada:

`release/oraculum-instalacao`

Último commit estável informado:

`e7c8682 - build: configurar executavel Oraculum`

Nenhuma alteração desta funcionalidade deverá ser aplicada diretamente na branch estável.