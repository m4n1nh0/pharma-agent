"""Agente LangGraph que orquestra as ferramentas MCP num grafo de raciocínio multi-etapa."""

import logging
import operator
from typing import Annotated, AsyncGenerator, List, Optional, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.config.settings import settings
from src.domain.entities.pharma import (
    DrugAnalysisResult as DrugAnalysisResponse,
    DrugInteraction,
    InteractionCheckResult as InteractionCheckResponse,
    InteractionSeverity,
    PrescriptionAlert,
    PrescriptionReviewResult as PrescriptionReviewResponse,
)
from src.infrastructure.ai.agent.schemas import (
    DrugAnalysisLLM,
    InteractionCheckLLM,
    PrescriptionReviewLLM,
)

logger = logging.getLogger(__name__)


# ─── State Definition ────────────────────────────────────────────────────────
class PharmaState(TypedDict):
    messages: Annotated[List, operator.add]
    drug_name: Optional[str]
    drugs_list: Optional[List[str]]
    patient_info: Optional[dict]
    context: Optional[str]
    analysis_type: str  # "drug" | "interaction" | "prescription"
    steps_taken: Annotated[List[str], operator.add]
    final_result: Optional[dict]
    error: Optional[str]


PHARMA_SYSTEM_PROMPT = """Você é um farmacêutico clínico sênior especializado em análise de medicamentos,
segurança farmacológica e revisão de prescrições. Você tem acesso a ferramentas especializadas.

Sua abordagem:
1. Sempre use as ferramentas disponíveis para buscar informações atualizadas
2. Seja sistemático e completo - analise todos os aspectos relevantes
3. Priorize a segurança do paciente
4. Apresente informações de forma clara e clinicamente relevante
5. Quando houver dados do paciente, personalize a análise
6. Sempre inclua alertas críticos quando identificados

Para análises de medicamento: mecanismo → indicações → contraindicações → efeitos adversos → interações → ajustes
Para interações: severidade → mecanismo → efeito clínico → manejo
Para prescrições: revisar cada item → verificar interações par a par → posologia → duplicidades → alertas

Responda SEMPRE em português do Brasil.
"""


class PharmaAnalysisAgent:
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            temperature=0,
            max_tokens=4000,
            api_key=settings.anthropic_api_key,
        )
        self._mcp_config = {
            "pharma-server": {
                "command": "python",
                "args": ["-m", "src.infrastructure.ai.mcp.pharma_tools"],
                "transport": "stdio",
            }
        }
        self._tools: Optional[list] = None
        self._graph = None

    async def start(self) -> None:
        """Conecta ao MCP server e compila o grafo uma única vez."""
        try:
            client = MultiServerMCPClient(self._mcp_config)
            self._tools = await client.get_tools()
            logger.info("Conectado ao MCP server 'pharma-server' (%d ferramentas)", len(self._tools))
        except Exception:
            logger.warning(
                "MCP server indisponível — usando ferramentas mock de fallback (dev/demo)",
                exc_info=True,
            )
            self._tools = self._get_mock_tools()
        self._graph = self._build_graph(self._tools)

    async def stop(self) -> None:
        self._tools = None
        self._graph = None

    def _get_mock_tools(self):
        """Ferramentas mock — fallback apenas quando o MCP server real está indisponível."""
        from langchain_core.tools import tool
        import json

        @tool
        def get_drug_info(drug_name: str) -> str:
            """Busca informações de um medicamento."""
            db = {
                "amoxicilina": {
                    "class": "Penicilinas",
                    "mechanism": "Inibe síntese da parede celular bacteriana via PBPs",
                    "indications": ["ITU", "Infecções respiratórias", "Otite média"],
                    "contraindications": ["Alergia a penicilinas"],
                    "adverse_effects": ["Diarreia", "Náusea", "Rash"],
                    "pregnancy_category": "B",
                    "renal_adjustment": "Reduzir dose se TFG < 30 mL/min",
                    "interactions": ["Varfarina", "Metotrexato"],
                },
                "warfarina": {
                    "class": "Anticoagulantes AVK",
                    "mechanism": "Inibe vitamina K epóxido redutase → bloqueia fatores II, VII, IX, X",
                    "indications": ["Fibrilação atrial", "TVP", "TEP"],
                    "contraindications": ["Sangramento ativo", "Gravidez"],
                    "adverse_effects": ["Sangramento", "Necrose cutânea"],
                    "pregnancy_category": "X",
                    "renal_adjustment": "Monitorar INR mais frequentemente",
                    "interactions": ["AAS", "Antibióticos", "Amiodarona"],
                },
            }
            key = drug_name.lower()
            for k, v in db.items():
                if k in key or key in k:
                    return json.dumps({"status": "found", "data": v}, ensure_ascii=False)
            return json.dumps({"status": "not_found", "message": f"Dados de '{drug_name}' não encontrados."})

        @tool
        def check_drug_interaction(drug_a: str, drug_b: str) -> str:
            """Verifica interação entre dois medicamentos."""
            interactions = {
                ("warfarina", "aspirina"): {
                    "severity": "maior",
                    "mechanism": "Sinergismo: AAS inibe COX-1 plaquetária + Varfarina inibe coagulação",
                    "clinical_effect": "Risco aumentado de sangramento grave (3-15x)",
                    "management": "Evitar; se necessário usar AAS 75-100mg + IBP + monitorar INR",
                },
                ("warfarina", "amoxicilina"): {
                    "severity": "moderada",
                    "mechanism": "Antibiótico altera flora intestinal → reduz síntese de vitamina K2",
                    "clinical_effect": "Elevação do INR → risco de sangramento",
                    "management": "Monitorar INR 3-5 dias após início e término do antibiótico",
                },
            }
            a, b = drug_a.lower(), drug_b.lower()
            for (k1, k2), v in interactions.items():
                if (k1 in a and k2 in b) or (k1 in b and k2 in a):
                    return json.dumps({"status": "found", **v}, ensure_ascii=False)
            return json.dumps({"status": "no_interaction", "message": f"Sem interação documentada entre {drug_a} e {drug_b}."})

        @tool
        def check_pregnancy_safety(drug_name: str, trimester: int = 2) -> str:
            """Avalia segurança na gestação."""
            categories = {"amoxicilina": "B", "warfarina": "X", "metformina": "B", "enalapril": "D", "aspirina": "D"}
            cat = categories.get(drug_name.lower(), "C")
            safety = {"A": "Seguro", "B": "Provavelmente seguro", "C": "Cautela", "D": "Risco documentado", "X": "Contraindicado"}
            return json.dumps({"drug": drug_name, "category": cat, "safety": safety.get(cat, "Indeterminado")})

        @tool
        def calculate_creatinine_clearance(age: int, weight_kg: float, creatinine_mg_dl: float, sex: str) -> str:
            """Calcula clearance de creatinina (Cockcroft-Gault)."""
            clcr = ((140 - age) * weight_kg) / (72 * creatinine_mg_dl)
            if sex == "F":
                clcr *= 0.85
            stage = "Normal" if clcr >= 60 else ("Leve" if clcr >= 30 else ("Grave" if clcr >= 15 else "Falência"))
            return json.dumps({"clcr_ml_min": round(clcr, 1), "ckd_stage": stage})

        return [get_drug_info, check_drug_interaction, check_pregnancy_safety, calculate_creatinine_clearance]

    def _build_graph(self, tools):
        """Constrói o grafo LangGraph (loop ReAct: agent ⇄ tools)."""
        llm_with_tools = self.llm.bind_tools(tools)
        tool_node = ToolNode(tools)

        def should_continue(state: PharmaState) -> str:
            messages = state["messages"]
            last = messages[-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "tools"
            return "end"

        async def agent_node(state: PharmaState) -> PharmaState:
            messages = state["messages"]
            response = await llm_with_tools.ainvoke(messages)
            step = f"Agente: {response.content[:80]}..." if len(str(response.content)) > 80 else f"Agente: {response.content}"
            return {"messages": [response], "steps_taken": [step]}

        async def tool_execution_node(state: PharmaState) -> PharmaState:
            result = await tool_node.ainvoke(state)
            steps = []
            for msg in result.get("messages", []):
                if hasattr(msg, "name"):
                    steps.append(f"Tool '{msg.name}': executada")
            return {**result, "steps_taken": steps}

        graph = StateGraph(PharmaState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tool_execution_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
        graph.add_edge("tools", "agent")

        return graph.compile()

    _FINALIZE_PROMPT = HumanMessage(
        content="Com base em toda a análise e ferramentas executadas acima, gere agora a saída estruturada final."
    )

    def _initial_state(self, **overrides) -> PharmaState:
        base: PharmaState = {
            "messages": [],
            "drug_name": None,
            "drugs_list": None,
            "patient_info": None,
            "context": None,
            "analysis_type": "drug",
            "steps_taken": [],
            "final_result": None,
            "error": None,
        }
        base.update(overrides)
        return base

    async def analyze_drug(
        self,
        drug_name: str,
        context: Optional[str] = None,
        patient_info=None,
    ) -> DrugAnalysisResponse:
        patient_str = ""
        if patient_info:
            patient_str = f"\nDados do paciente: {patient_info.model_dump(exclude_none=True)}"

        prompt = f"""Realize uma análise farmacológica COMPLETA do medicamento: **{drug_name}**
{f'Contexto clínico: {context}' if context else ''}
{patient_str}

Use as ferramentas disponíveis para:
1. Buscar informações do medicamento (get_drug_info)
2. Verificar segurança se for gestante (check_pregnancy_safety)
3. Calcular ClCr se dados renais disponíveis (calculate_creatinine_clearance)"""

        state = await self._graph.ainvoke(
            self._initial_state(
                messages=[SystemMessage(content=PHARMA_SYSTEM_PROMPT), HumanMessage(content=prompt)],
                drug_name=drug_name,
                analysis_type="drug",
                steps_taken=[f"Iniciando análise de: {drug_name}"],
                patient_info=patient_info.model_dump() if patient_info else None,
                context=context,
            )
        )

        structured = await self.llm.with_structured_output(DrugAnalysisLLM).ainvoke(
            state["messages"] + [self._FINALIZE_PROMPT]
        )
        return DrugAnalysisResponse(
            drug_name=drug_name,
            agent_steps=state.get("steps_taken", []),
            **structured.model_dump(),
        )

    async def check_interactions(self, drugs: List[str], patient_info=None) -> InteractionCheckResponse:
        pairs = [(drugs[i], drugs[j]) for i in range(len(drugs)) for j in range(i + 1, len(drugs))]
        pairs_str = "\n".join([f"- {a} × {b}" for a, b in pairs])

        prompt = f"""Verifique TODAS as interações medicamentosas entre os seguintes fármacos:
**Medicamentos:** {', '.join(drugs)}

**Pares a verificar:**
{pairs_str}

Para cada par, use check_drug_interaction e documente:
- Severidade (contraindicada/maior/moderada/menor)
- Mecanismo farmacológico
- Efeito clínico esperado
- Manejo recomendado

Ao final, calcule o risco geral (baixo/moderado/alto/crítico)."""

        state = await self._graph.ainvoke(
            self._initial_state(
                messages=[SystemMessage(content=PHARMA_SYSTEM_PROMPT), HumanMessage(content=prompt)],
                drugs_list=drugs,
                analysis_type="interaction",
                steps_taken=[f"Verificando interações entre: {', '.join(drugs)}"],
                patient_info=patient_info.model_dump() if patient_info else None,
            )
        )

        structured = await self.llm.with_structured_output(InteractionCheckLLM).ainvoke(
            state["messages"] + [self._FINALIZE_PROMPT]
        )
        return InteractionCheckResponse(
            drugs_analyzed=drugs,
            agent_steps=state.get("steps_taken", []),
            **structured.model_dump(),
        )

    async def review_prescription(self, prescription, patient_info=None, clinical_context: Optional[str] = None) -> PrescriptionReviewResponse:
        items_str = "\n".join([f"- {item.drug_name} {item.dose} {item.frequency} ({item.indication or 'sem indicação registrada'})" for item in prescription])

        prompt = f"""Realize uma REVISÃO FARMACÊUTICA COMPLETA da seguinte prescrição:

**Prescrição:**
{items_str}

{f'Contexto clínico: {clinical_context}' if clinical_context else ''}
{f'Dados do paciente: {patient_info.model_dump(exclude_none=True)}' if patient_info else ''}

Analise:
1. Cada medicamento individualmente (get_drug_info)
2. Todas as interações par a par (check_drug_interaction)
3. Adequação das doses para função renal se aplicável
4. Duplicidades terapêuticas
5. Alertas de segurança críticos

Forneça uma revisão farmacêutica estruturada com score de segurança (0-10)."""

        state = await self._graph.ainvoke(
            self._initial_state(
                messages=[SystemMessage(content=PHARMA_SYSTEM_PROMPT), HumanMessage(content=prompt)],
                analysis_type="prescription",
                steps_taken=[f"Revisando prescrição com {len(prescription)} item(s)"],
                patient_info=patient_info.model_dump() if patient_info else None,
                context=clinical_context,
                drugs_list=[item.drug_name for item in prescription],
            )
        )

        structured = await self.llm.with_structured_output(PrescriptionReviewLLM).ainvoke(
            state["messages"] + [self._FINALIZE_PROMPT]
        )
        return PrescriptionReviewResponse(
            total_items=len(prescription),
            items_reviewed=[f"{item.drug_name} {item.dose}" for item in prescription],
            agent_steps=state.get("steps_taken", []),
            **structured.model_dump(),
        )

    async def stream_analysis(self, drug_name: str, context=None, patient_info=None) -> AsyncGenerator[dict, None]:
        yield {"type": "start", "message": f"Iniciando análise de {drug_name}..."}

        prompt = f"Analise o medicamento: {drug_name}. {context or ''}"
        state = self._initial_state(
            messages=[SystemMessage(content=PHARMA_SYSTEM_PROMPT), HumanMessage(content=prompt)],
            drug_name=drug_name,
            analysis_type="drug",
            steps_taken=[f"Iniciando análise de: {drug_name}"],
            patient_info=patient_info.model_dump() if patient_info else None,
            context=context,
        )

        step = 0
        async for update in self._graph.astream(state, stream_mode="updates"):
            for node_name, node_output in update.items():
                step += 1
                yield {"type": "step", "step": step, "message": f"Executando nó '{node_name}'..."}

                for msg in node_output.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        yield {"type": "tool_call", "tool": msg.name, "result": str(msg.content)[:200]}
                    elif getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            yield {"type": "tool_call", "tool": tc["name"], "args": tc["args"]}
                    elif msg.content:
                        yield {"type": "content", "content": str(msg.content)[:200]}

        yield {"type": "complete", "message": "Análise concluída com sucesso"}
