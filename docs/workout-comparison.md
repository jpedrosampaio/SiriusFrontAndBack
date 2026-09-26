# Comparação de sessões

O histórico agora busca o nome literal e completo do exercício, escapando caracteres de regex. “Supino” não pode usar inadvertidamente séries de “Supino inclinado”. O limite de cinco sessões é intencional: corresponde ao histórico recente apresentado, não a um total analítico.

A sessão mostra volume (carga × repetições), repetições, média de RPE e quantidade de séries comparadas com a última sessão. Campos ausentes não são estimados. As diferenças são descritivas e não alteram carga ou prescrevem progressão. O usuário continua conferindo e salvando cada série explicitamente. Séries de uma sessão em andamento não são apresentadas como desempenho final.

Testes: nome literal com parênteses, não mistura de variações, propriedade, cálculo e dados insuficientes; smoke de persistência das séries em 1440/390/320 px.
