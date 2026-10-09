"""Sesión 3 · Un mini sistema multiagente: un supervisor y dos especialistas.
El supervisor (create_supervisor) lee la petición y delega en el agente adecuado
con una herramienta de traspaso (transfer_to_...). Requiere: OPENAI_API_KEY.
"""
import math

from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Definir herramientas personalizadas
@tool
def buscar_web(query: str) -> str:
    """Buscar informacion en la web."""
    return f"Resultados de busqueda para: {query}"     # simulada: no busca de verdad

@tool
def calcular(expresion: str) -> str:
    """Realizar calculos matematicos. Admite + - * / **, pi y sqrt()."""
    seguro = {"__builtins__": {}, "pi": math.pi, "sqrt": math.sqrt}   # sin acceso a Python
    try:
        return f"Resultado: {eval(expresion, seguro)}"
    except Exception as e:
        return f"No puedo calcular {expresion}: {e}"

# Crear agentes especializados
agente_investigacion = create_agent(
    model=model,
    tools=[buscar_web],
    system_prompt="Eres un especialista en investigacion web.",
    name="investigador"
)

agente_matematicas = create_agent(
    model=model,
    tools=[calcular],
    system_prompt="Eres un especialista en calculos matematicos.",
    name="matematico"
)

# Crear supervisor que coordina los agentes
supervisor_graph = create_supervisor(
    [agente_matematicas, agente_investigacion],
    model=model,
    prompt="Eres un supervisor que delega tareas a especialistas segun el tipo de consulta."
)

supervisor = supervisor_graph.compile()

# Uso del sistema multi-agente
response = supervisor.invoke({
    "messages": [{
        "role": "user",
        "content": "Busca informacion sobre pi y calcula su valor aproximado."
        # "content": "Busca informacion sobre las ultimas noticias de inteligencia artificial."
    }]
})

for msg in response["messages"]:                  # quién habla en cada paso
    llamadas = [t["name"] for t in getattr(msg, "tool_calls", [])]
    print(f"[{msg.name or msg.type}]", msg.content or f"→ llama a {llamadas}")
