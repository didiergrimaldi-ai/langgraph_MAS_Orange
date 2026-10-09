"""Sesión 3 · Controlar el agente: una persona revisa antes de que actúe
Mismo agente de soporte que 3_agente_con_herramientas.py, con un nodo «revisar» entre el
modelo y las herramientas: interrupt() para el grafo y una persona decide si la herramienta
se ejecuta. Para poder pararse y seguir después, el grafo necesita un checkpointer (memoria).
Requiere: OPENAI_API_KEY.
"""
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

INCIDENCIAS = {"28013": "Corte programado por obras hasta las 14:00.",
               "75001": "Sin incidencias abiertas."}


@tool
def consultar_incidencias(cp: str) -> str:
    """Consulta incidencias abiertas en la red para un código postal.
    Úsala cuando el cliente diga que no tiene servicio."""
    estado = INCIDENCIAS.get(cp, "Sin incidencias abiertas.")
    return f"Código postal {cp}: {estado}"


herramientas = [consultar_incidencias]
llm_con_tools = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(herramientas)
SISTEMA = SystemMessage(content="Eres soporte técnico. Usa las herramientas antes de responder. "
                                "Responde en español y en una o dos frases.")


def modelo(state: MessagesState) -> dict:                 # PENSAR
    return {"messages": [llm_con_tools.invoke([SISTEMA, *state["messages"]])]}


def revisar(state: MessagesState) -> Command:              # CONTROLAR: una persona decide
    llamada = state["messages"][-1].tool_calls[0]
    decision = interrupt(f"¿Ejecutar {llamada['name']}({llamada['args']})? (s/n)")
    if decision == "s":
        return Command(goto="tools")
    rechazo = ToolMessage(content="La persona no ha autorizado esta acción.", tool_call_id=llamada["id"])
    return Command(goto="modelo", update={"messages": [rechazo]})


g = StateGraph(MessagesState)
g.add_node("modelo", modelo)
g.add_node("revisar", revisar, destinations=("tools", "modelo"))
g.add_node("tools", ToolNode(herramientas))                # ACTUAR
g.add_edge(START, "modelo")
g.add_conditional_edges("modelo", tools_condition, {"tools": "revisar", END: END})
g.add_edge("tools", "modelo")                              # OBSERVAR
agente = g.compile(checkpointer=InMemorySaver())           # memoria para poder pausar y seguir

config = {"configurable": {"thread_id": "cliente-1"}}     # una conversación = un thread_id

pregunta = "No tengo internet en casa, código postal 28013."
resultado = agente.invoke({"messages": [("user", pregunta)]}, config)
while "__interrupt__" in resultado:                        # el grafo se ha parado a preguntar
    texto = resultado["__interrupt__"][0].value
    respuesta = input(texto + " ").strip().lower()
    resultado = agente.invoke(Command(resume=respuesta), config)   # sigue donde se paró
print("Respuesta:", resultado["messages"][-1].content)
