# Anexos finais e disciplinas por cargo

O caso reproduzido foi um edital de 50 páginas com aproximadamente 246 mil
caracteres. O conteúdo programático começa na página 31, depois dos primeiros
100 mil caracteres, e o cargo Técnico aparece depois dos 200 mil caracteres.
O PDF original do usuário não foi incluído no repositório.

## Causas corrigidas

- A análise e a complementação enviavam somente o início do documento à IA.
- A complementação detectava cargos com grupos genéricos, mas o merge ignorava
  qualquer cargo que já tivesse uma lista não vazia.
- Nomes como `Conhecimentos Gerais (P1)` não eram reconhecidos como grupos.
- A importação podia copiar disciplinas de outro cargo quando faltavam dados.

## Comportamento

A primeira análise recebe o documento completo, até 600 mil caracteres. Acima
desse limite, há erro explícito pedindo um recorte que preserve cargos, provas e
conteúdo programático. Não há truncamento silencioso. O texto completo também é
armazenado para complementar posteriormente o cargo selecionado.

A complementação trabalha com até dois cargos por chamada. Quando o anexo tem
seções explicitamente delimitadas por código e nome, recebe a introdução/regras,
o conteúdo comum e os blocos completos dos cargos correspondentes. Caso a
delimitação ou correspondência exata não seja possível, usa o documento completo.

O merge substitui os grupos genéricos, preserva disciplinas reais já extraídas e
não usa correspondência aproximada entre cargos. Falhas continuam marcadas como
extração incompleta, com criação do programa bloqueada e opção de reanalisar.
Uma contagem pequena, sozinha, não invalida um edital que realmente tenha duas
disciplinas. Essas verificações detectam conteúdo ausente/genérico, mas não
certificam que a IA extraiu cada assunto de forma perfeita.

O cache passa à versão 3. Análises antigas incompletas exigem reenvio do PDF para
não reutilizar texto previamente cortado. Programas existentes não são alterados.

## Validação

Onze regressões cobrem anexos depois de 100/200 mil caracteres, seleção de
conteúdo comum/específico, reparo de grupos preenchidos, nova tentativa após
resposta genérica, identificação de extração incompleta e bloqueio da cópia de
disciplinas entre cargos. O PDF fornecido foi extraído e inspecionado localmente;
não foram usadas as credenciais da IA nem modificados dados da conta do usuário.
