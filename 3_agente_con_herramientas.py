"""Sesión 3 · Agente con herramientas: el bucle del agente como grafo
El patrón ReAct construido con LangGraph: un nodo «modelo» (el LLM con herramientas), un nodo
«herramientas» (ToolNode, que las ejecuta) y una arista condicional (tools_condition) que vuelve
al modelo mientras pida herramientas. Requiere: OPENAI_API_KEY.
"""
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

INCIDENCIAS = {"28013": "Corte programado por obras hasta las 14:00.",
               "75001": "Sin incidencias abiertas."}

LINEAS = {"666123456": "activa - fibra 600Mb - router conectado"}


@tool
def consultar_incidencias(cp: str) -> str:
    """Consulta incidencias abiertas en la red para un código postal.
    Úsala cuando el cliente diga que no tiene servicio."""
    estado = INCIDENCIAS.get(cp, "Sin incidencias abiertas.") # busca el codigo postal en la base de datos de incidencias abiertas
    return f"Código postal {cp}: {estado}" # devuelve el estado si coincide con algún código postal de la base de datos


@tool
def consultar_linea(telefono: str) -> str:
    """Consulta el estado de la línea de un cliente a partir de su teléfono."""
    estado = LINEAS.get(telefono, "activa - fibra 600Mb - router conectado") # busca el telefono en la base de datos de lineas activas
    return f"Línea {telefono}: {estado}." # devuelve el estado si coincide con algún teléfono de la base de datos


herramientas = [consultar_incidencias, consultar_linea]
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_con_tools = llm.bind_tools(herramientas)     # Le dice qué herramientas existen: el LLM las asocia a sus descripciones y las puede invocar con tool_calls
SISTEMA = SystemMessage(content="Eres soporte técnico. Usa las herramientas antes de responder. "
                                "Responde en español y en una o dos frases.")


def modelo(state: MessagesState) -> dict:        # PENSAR
    mensajes = [SISTEMA, *state["messages"]]
    return {"messages": [llm_con_tools.invoke(mensajes)]}


g = StateGraph(MessagesState)                    # lista de mensajes
g.add_edge(START, "modelo")                      # se empieza en el nodo modelo, que llama al LLM con herramientas
g.add_node("modelo", modelo)                    # nodo que piensa y llama al LLM con herramientas
g.add_node("tools", ToolNode(herramientas))      # nodo que actúa: ejecuta las herramientas
g.add_conditional_edges("modelo", tools_condition)   # si el ultimo mensaje del modelo tiene tool_calls, se va al nodo tools, que ejecuta la herramienta y devuelve el resultado al modelo. Sino, va a END
g.add_edge("tools", "modelo")                    # tras ejecutar, vuelve al modelo para observar el resultado y decidir si necesita otra herramienta o responder al usuario
agente = g.compile()

# pregunta = "No tengo internet en casa, código postal 28014."  # pregunta del usuario que activa el bucle del agente
pregunta = "Mi telefono 666123456 no tiene línea."  # otra pregunta del usuario que activa el bucle del agente

for paso in agente.stream({"messages": [("user", pregunta)]}, stream_mode="updates"): # para cada paso del grafo, se va a ir mostrando el estado de la conversación
    for nodo, cambios in paso.items():
        m = cambios["messages"][-1] # cogemos el último mensaje del estado de la conversación
        if getattr(m, "tool_calls", None): # comprueba si el mensaje tiene tool_calls, es decir, si el LLM ha pedido ejecutar una herramienta
            print(f"{nodo} → pide {m.tool_calls[0]['name']}({m.tool_calls[0]['args']})") # si pide una herramienta, muestra el nombre de la herramienta y los argumentos que le pasa
        else:
            print(f"{nodo} → {m.content}") #sino, muestra el contenido del mensaje del LLM
