"""Servidor MCP com ferramentas farmacêuticas, consumido pelo agente LangGraph."""

import os

from mcp.server.fastmcp import FastMCP

DRUG_DATABASE = {
    "amoxicilina": {
        "generic_name": "Amoxicilina",
        "class": "Penicilinas / Beta-lactâmicos",
        "mechanism": "Inibe a síntese da parede celular bacteriana ligando-se às proteínas de ligação à penicilina (PBPs).",
        "indications": ["Infecções respiratórias", "ITU", "Otite média", "Sinusite", "H. pylori"],
        "contraindications": ["Alergia a penicilinas", "Histórico de anafilaxia a beta-lactâmicos"],
        "adverse_effects": ["Diarreia", "Náusea", "Rash cutâneo", "Colite pseudomembranosa (rara)"],
        "pregnancy_category": "B",
        "renal_adjustment": "ClCr 10-30: 250-500mg 12/12h. ClCr <10: 250-500mg 24/24h",
        "interactions": ["Metotrexato", "Varfarina", "Alopurinol"],
    },
    "warfarina": {
        "generic_name": "Varfarina",
        "class": "Anticoagulantes AVK",
        "mechanism": "Inibe vitamina K epóxido redutase → bloqueia fatores II, VII, IX, X.",
        "indications": ["Fibrilação atrial", "TVP", "TEP", "Válvulas mecânicas"],
        "contraindications": ["Sangramento ativo", "Gravidez", "Cirurgia recente SNC"],
        "adverse_effects": ["Sangramento", "Necrose cutânea (rara)", "Síndrome dos dedos roxos"],
        "pregnancy_category": "X",
        "renal_adjustment": "Monitorar INR mais frequentemente",
        "interactions": ["AAS/AINE", "Antibióticos", "Amiodarona", "Rifampicina"],
    },
    "metformina": {
        "generic_name": "Metformina",
        "class": "Biguanidas",
        "mechanism": "Ativa AMPK hepática, reduz gliconeogênese e melhora sensibilidade à insulina.",
        "indications": ["DM tipo 2 (1ª linha)", "Pré-diabetes", "SOP (off-label)"],
        "contraindications": ["TFG < 30 mL/min", "Insuficiência hepática", "Contraste iodado"],
        "adverse_effects": ["Diarreia", "Náusea", "Dor abdominal", "Acidose láctica (rara)"],
        "pregnancy_category": "B",
        "renal_adjustment": "TFG 30-45: máx 1000mg/dia. TFG <30: contraindicada",
        "interactions": ["Contraste iodado", "Álcool", "Cimetidina"],
    },
    "enalapril": {
        "generic_name": "Enalapril",
        "class": "IECA",
        "mechanism": "Inibe competitivamente a ECA, reduzindo angiotensina II e aldosterona.",
        "indications": ["HAS", "IC", "Pós-IAM", "Nefropatia diabética"],
        "contraindications": ["Gravidez (2-3º tri)", "Angioedema prévio com IECA", "Hipercalemia grave"],
        "adverse_effects": ["Tosse seca (10-20%)", "Hipotensão 1ª dose", "Angioedema (0,1%)"],
        "pregnancy_category": "D",
        "renal_adjustment": "TFG 30-80: dose inicial 2,5mg. TFG <30: monitorar hipercalemia",
        "interactions": ["AINE", "Suplemento K+", "Lítio", "Aliskiren"],
    },
    "aspirina": {
        "generic_name": "Ácido Acetilsalicílico",
        "class": "AINE / Antiplaquetário",
        "mechanism": "Inibe irreversivelmente COX-1 e COX-2, reduzindo prostaglandinas e tromboxano A2.",
        "indications": ["Prevenção CV secundária", "Dor leve a moderada", "Febre"],
        "contraindications": ["<16 anos c/ infecção viral", "Úlcera péptica ativa", "3º trimestre"],
        "adverse_effects": ["Irritação gástrica", "Sangramento GI", "Asma por AAS"],
        "pregnancy_category": "D (3º tri)",
        "renal_adjustment": "Evitar se TFG <10 mL/min",
        "interactions": ["Varfarina", "Metotrexato", "IECA", "Ibuprofeno"],
    },
}

INTERACTION_DATABASE = {
    ("warfarina", "aspirina"): {
        "severity": "maior",
        "mechanism": "Sinergismo: AAS inibe COX-1 + Varfarina inibe coagulação. AAS desloca varfarina de proteínas.",
        "clinical_effect": "Risco 3-15x maior de sangramento grave (GI, intracraniano).",
        "management": "Evitar; se necessário usar AAS 75-100mg + IBP + monitorar INR.",
        "evidence": "Nível A",
    },
    ("warfarina", "amoxicilina"): {
        "severity": "moderada",
        "mechanism": "Antibiótico altera flora intestinal, reduzindo síntese de vitamina K2.",
        "clinical_effect": "Elevação do INR com risco de sangramento variável.",
        "management": "Monitorar INR 3-5 dias após início/término do antibiótico.",
        "evidence": "Nível B",
    },
    ("enalapril", "aspirina"): {
        "severity": "moderada",
        "mechanism": "AAS inibe prostaglandinas vasodilatadoras, antagonizando efeito do IECA.",
        "clinical_effect": "Redução do efeito anti-hipertensivo. Possível deterioração renal.",
        "management": "Usar mínimo de AAS (75-100mg). Monitorar PA e função renal.",
        "evidence": "Nível B",
    },
}

ALTERNATIVES_DATABASE = {
    "warfarina": {"alternatives": ["Rivaroxabana", "Apixabana", "Dabigatrana"]},
    "amoxicilina": {"alternatives": ["Azitromicina", "Cefalexina", "Clindamicina"]},
    "metformina": {"alternatives": ["Empagliflozina", "Liraglutida", "Sitagliptina"]},
    "enalapril": {"alternatives": ["Losartana", "Valsartana", "Ramipril"]},
}

# host/port valem apenas para os transportes HTTP; em stdio são ignorados.
# Lidos do ambiente e não de settings para o servidor não arrastar a config da
# aplicação (ele roda sozinho, sem chave da Anthropic nem Redis).
mcp = FastMCP(
    "pharma-mcp",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("PORT") or os.getenv("MCP_PORT") or 8080),
)


@mcp.tool()
def get_drug_info(drug_name: str) -> dict:
    """Busca o perfil farmacológico completo de um medicamento: mecanismo de ação, indicações, contraindicações, efeitos adversos, categoria gestacional e ajuste renal."""
    key = drug_name.lower()
    found = next((v for k, v in DRUG_DATABASE.items() if k in key or key in k), None)
    if found:
        return {"status": "found", "data": found}
    return {"status": "not_found", "message": f"'{drug_name}' não encontrado."}


@mcp.tool()
def check_drug_interaction(drug_a: str, drug_b: str) -> dict:
    """Verifica a interação medicamentosa entre dois fármacos: severidade, mecanismo, efeito clínico e manejo recomendado."""
    a, b = drug_a.lower(), drug_b.lower()
    ix = next(
        (v for (k1, k2), v in INTERACTION_DATABASE.items() if (k1 in a and k2 in b) or (k1 in b and k2 in a)),
        None,
    )
    if ix:
        return {"status": "found", **ix}
    return {"status": "no_interaction"}


@mcp.tool()
def calculate_dose_adjustment(drug_name: str, tfg: float | None = None) -> dict:
    """Calcula o ajuste posológico de um medicamento para disfunção renal, a partir da taxa de filtração glomerular (TFG)."""
    info = DRUG_DATABASE.get(drug_name.lower(), {})
    stage = (
        "Normal (TFG ≥60)" if tfg is not None and tfg >= 60 else
        "Leve redução (TFG 30-59)" if tfg is not None and tfg >= 30 else
        "Grave redução (TFG <30)" if tfg is not None else "TFG não informada"
    )
    return {
        "drug": drug_name,
        "stage": stage,
        "recommendation": info.get("renal_adjustment", "Sem dado específico"),
    }


@mcp.tool()
def check_pregnancy_safety(drug_name: str, trimester: int = 2) -> dict:
    """Avalia a categoria de segurança gestacional (FDA) de um medicamento."""
    info = DRUG_DATABASE.get(drug_name.lower(), {})
    cat = info.get("pregnancy_category", "?")
    safety = {"A": "Seguro", "B": "Provável seguro", "C": "Cautela", "D": "Risco documentado", "X": "Contraindicado"}
    return {"drug": drug_name, "category": cat, "safety": safety.get(cat, "?")}


@mcp.tool()
def search_therapeutic_alternatives(drug_name: str, indication: str | None = None) -> dict:
    """Busca alternativas terapêuticas da mesma classe farmacológica para um medicamento."""
    key = drug_name.lower()
    found = next((v for k, v in ALTERNATIVES_DATABASE.items() if k in key), {"alternatives": []})
    return {"drug": drug_name, **found}


@mcp.tool()
def calculate_creatinine_clearance(age: int, weight_kg: float, creatinine_mg_dl: float, sex: str) -> dict:
    """Calcula o clearance de creatinina pela fórmula de Cockcroft-Gault e classifica o estágio de função renal."""
    clcr = ((140 - age) * weight_kg) / (72 * creatinine_mg_dl) * (0.85 if sex == "F" else 1)
    stage = "Normal" if clcr >= 60 else ("Leve" if clcr >= 30 else ("Grave" if clcr >= 15 else "Falência"))
    return {"clcr_ml_min": round(clcr, 1), "stage": stage}


if __name__ == "__main__":
    # stdio: subprocesso do agente (dev, um container só).
    # streamable-http: serviço próprio, consumido por api e worker via MCP_URL.
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
