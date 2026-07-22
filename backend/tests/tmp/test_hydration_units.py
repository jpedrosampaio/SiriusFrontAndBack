import sys, os
sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'sirius_db')
from server import _merge_hydrated_disciplinas, _parse_json_lenient, _build_hydration_prompt

# 1. merge: comuns aplicadas a todos + específicas por nome exato e fuzzy
cargos = [
    {"nome": "Analista Administrativo", "disciplinas": []},
    {"nome": "Analista de Tecnologia da Informação"},
    {"nome": "Contador", "disciplinas": [{"nome": "Já tinha"}]},
]
parsed = {
    "disciplinas_comuns": [{"nome": "Língua Portuguesa"}, {"nome": "Raciocínio Lógico"}],
    "cargos": [
        {"nome": "analista administrativo", "disciplinas": [{"nome": "Administração Geral"}]},
        {"nome": "Analista de Tecnologia da Informacao", "disciplinas": [{"nome": "Redes"}]},
    ],
}
n = _merge_hydrated_disciplinas(cargos, parsed)
assert n == 2, n
d0 = [d["nome"] for d in cargos[0]["disciplinas"]]
assert d0 == ["Língua Portuguesa", "Raciocínio Lógico", "Administração Geral"], d0
d1 = [d["nome"] for d in cargos[1]["disciplinas"]]
assert d1 == ["Língua Portuguesa", "Raciocínio Lógico", "Redes"], d1  # fuzzy sem acentos
assert [d["nome"] for d in cargos[2]["disciplinas"]] == ["Já tinha"]
print("merge OK:", d0, "|", d1)

# 2. merge sem específicas -> só comuns
cargos2 = [{"nome": "Fiscal"}]
n2 = _merge_hydrated_disciplinas(cargos2, {"disciplinas_comuns": [{"nome": "Português"}], "cargos": []})
assert n2 == 1 and [d["nome"] for d in cargos2[0]["disciplinas"]] == ["Português"]
print("merge só comuns OK")

# 3. merge tudo vazio -> não hidrata (cargo continua sem disciplinas)
cargos3 = [{"nome": "Fiscal"}]
n3 = _merge_hydrated_disciplinas(cargos3, {"disciplinas_comuns": [], "cargos": []})
assert n3 == 0 and not cargos3[0].get("disciplinas")
print("merge vazio OK")

# 4. parse leniente com fences e JSON truncado reparável
assert _parse_json_lenient('```json\n{"a": 1}\n```') == {"a": 1}
rep = _parse_json_lenient('{"disciplinas_comuns": [{"nome": "PT"')
print("parse fences OK; repair result:", rep)

# 5. prompt contém nomes dos cargos
pr = _build_hydration_prompt(["Contador", "Analista"])
assert "- Contador" in pr and "- Analista" in pr and "disciplinas_comuns" in pr
print("prompt OK")
print("ALL UNIT TESTS PASSED")
