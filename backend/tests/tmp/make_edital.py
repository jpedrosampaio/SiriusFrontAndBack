from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("/app/backend/tests/tmp/edital.pdf", pagesize=A4)
els = []


def p(t, s="Normal"):
    els.append(Paragraph(t, styles[s]))
    els.append(Spacer(1, 8))


p("EDITAL Nº 1/2026 – PREFEITURA MUNICIPAL DE ESTRELA DO SUL", "Title")
p("CONCURSO PÚBLICO PARA PROVIMENTO DE VAGAS", "Heading2")
p("A Prefeitura Municipal de Estrela do Sul, por meio da banca FUNDACAO SIRIUS, torna pública a realização de concurso público.")
p("1. DOS CARGOS", "Heading2")
p("1.1 Cargo: Analista Administrativo — Vagas: 10 — Remuneração: R$ 5.500,00 — Escolaridade: Nível superior em qualquer área.")
p("1.2 Cargo: Analista de Tecnologia da Informação — Vagas: 5 — Remuneração: R$ 7.200,00 — Escolaridade: Nível superior em TI.")
p("1.3 Cargo: Contador — Vagas: CR — Remuneração: R$ 6.800,00 — Escolaridade: Nível superior em Ciências Contábeis com CRC.")
p("2. DAS PROVAS", "Heading2")
p("2.1 A prova objetiva, comum a todos os cargos, será composta de: Língua Portuguesa (15 questões, peso 1), Raciocínio Lógico (10 questões, peso 1), Noções de Direito Administrativo (10 questões, peso 1) e Conhecimentos Específicos (25 questões, peso 2).")
p("3. DOS CONTEÚDOS PROGRAMÁTICOS", "Heading2")
p("3.1 CONHECIMENTOS BÁSICOS (COMUNS A TODOS OS CARGOS)", "Heading3")
p("LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos. 2 Ortografia oficial. 3 Acentuação gráfica. 4 Emprego das classes de palavras. 5 Sintaxe da oração e do período. 6 Concordância nominal e verbal. 7 Regência nominal e verbal. 8 Crase. 9 Pontuação.")
p("RACIOCÍNIO LÓGICO: 1 Estruturas lógicas. 2 Lógica de argumentação. 3 Diagramas lógicos. 4 Sequências. 5 Porcentagem e proporcionalidade.")
p("NOÇÕES DE DIREITO ADMINISTRATIVO: 1 Estado, governo e administração pública. 2 Ato administrativo. 3 Agentes públicos. 4 Poderes administrativos. 5 Licitação (Lei nº 14.133/2021). 6 Improbidade administrativa.")
p("3.2 CONHECIMENTOS ESPECÍFICOS", "Heading3")
p("ANALISTA ADMINISTRATIVO: 1 Administração geral: planejamento, organização, direção e controle. 2 Gestão de pessoas. 3 Gestão de processos. 4 Arquivologia. 5 Redação oficial. 6 Administração de materiais.")
p("ANALISTA DE TECNOLOGIA DA INFORMAÇÃO: 1 Redes de computadores: modelo OSI, TCP/IP. 2 Segurança da informação: criptografia, firewalls, LGPD. 3 Banco de dados: modelagem relacional, SQL. 4 Engenharia de software: metodologias ágeis. 5 Sistemas operacionais Linux e Windows.")
p("CONTADOR: 1 Contabilidade geral: patrimônio, escrituração, demonstrações contábeis. 2 Contabilidade pública: MCASP, plano de contas. 3 Lei nº 4.320/1964. 4 Lei de Responsabilidade Fiscal. 5 Auditoria e perícia contábil. 6 Custos.")
doc.build(els)
print("ok")
