"""
Agente de email con LangGraph

Flujo:  START → buscar_emails → leer_email → generar_respuesta → crear_borrador → END

Cada nodo lee del estado y devuelve SOLO las claves que cambia;
LangGraph las fusiona en el estado global compartido.
"""

import base64
import os
import sys
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import TypedDict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END

# Solo para que los print de la consola de Windows muestren tildes y ñ
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Trabajar en la carpeta del script: aquí están credenciales_google.json y el token
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Conexión a Gmail (reutiliza el token de la versión LangChain: no vuelve a pedir login)
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
TOKEN = "token_agente_email.json"


def conectar_gmail():
    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credenciales_google.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


gmail = conectar_gmail()
modelo = init_chat_model("openai:gpt-4o", temperature=0)


# ---------------------------------------------------------------------------
# 1. Estado global compartido
# ---------------------------------------------------------------------------
class EstadoAgente(TypedDict, total=False):
    consulta: str      # entrada: búsqueda de Gmail, p. ej. "in:inbox"
    message_id: str    # lo escribe buscar_emails
    email: dict        # lo escribe leer_email
    respuesta: str     # lo escribe generar_respuesta
    borrador_id: str   # lo escribe crear_borrador


# ---------------------------------------------------------------------------
# 2. Nodos: funciones normales (sin @tool: aquí no es el LLM quien las elige)
# ---------------------------------------------------------------------------
def buscar_emails(state: EstadoAgente) -> dict:
    resultado = gmail.users().messages().list(
        userId="me", q=state["consulta"], maxResults=1
    ).execute()
    mensajes = resultado.get("messages", [])
    return {"message_id": mensajes[0]["id"] if mensajes else ""}


def leer_email(state: EstadoAgente) -> dict:
    datos = gmail.users().messages().get(
        userId="me", id=state["message_id"], format="raw"
    ).execute()

    # policy.default decodifica cabeceras y cuerpo con el charset que declara
    # cada email (UTF-8, ISO-8859-1, Windows-1252...). Esto sustituye a todo
    # el código manual de UTF-8 de la versión original.
    raw = base64.urlsafe_b64decode(datos["raw"])
    msg = message_from_bytes(raw, policy=policy.default)
    cuerpo = msg.get_body(preferencelist=("plain", "html"))

    return {"email": {
        "thread_id": datos["threadId"],
        "message_id_header": str(msg["Message-ID"] or ""),
        "remitente": msg["From"].addresses[0].addr_spec,
        "asunto": str(msg["Subject"] or ""),
        "cuerpo": cuerpo.get_content() if cuerpo else "",
    }}


def generar_respuesta(state: EstadoAgente) -> dict:
    email = state["email"]
    prompt = (
        "Eres un asistente de email profesional. Escribe solo el cuerpo de una "
        "respuesta breve y profesional en español a este email (sin asunto ni análisis).\n\n"
        f"De: {email['remitente']}\nAsunto: {email['asunto']}\n\n{email['cuerpo']}"
    )
    return {"respuesta": modelo.invoke(prompt).content}


def crear_borrador(state: EstadoAgente) -> dict:
    email = state["email"]
    asunto = email["asunto"]

    respuesta = EmailMessage()  # codifica en UTF-8 automáticamente
    respuesta.set_content(state["respuesta"])
    respuesta["To"] = email["remitente"]
    respuesta["Subject"] = asunto if asunto.lower().startswith("re:") else f"Re: {asunto}"
    if email["message_id_header"]:
        respuesta["In-Reply-To"] = email["message_id_header"]
        respuesta["References"] = email["message_id_header"]

    raw = base64.urlsafe_b64encode(respuesta.as_bytes()).decode()
    borrador = gmail.users().drafts().create(
        userId="me", body={"message": {"raw": raw, "threadId": email["thread_id"]}}
    ).execute()
    return {"borrador_id": borrador["id"]}


# ---------------------------------------------------------------------------
# 3. Arista condicional: la única decisión real del flujo (bandeja vacía)
# ---------------------------------------------------------------------------
def hay_email(state: EstadoAgente) -> str:
    return "leer_email" if state.get("message_id") else END


# ---------------------------------------------------------------------------
# 4. Grafo: add_node registra los nodos, add_edge fija el orden
# ---------------------------------------------------------------------------
grafo = StateGraph(EstadoAgente)
grafo.add_node("buscar_emails", buscar_emails)
grafo.add_node("leer_email", leer_email)
grafo.add_node("generar_respuesta", generar_respuesta)
grafo.add_node("crear_borrador", crear_borrador)

grafo.add_edge(START, "buscar_emails")
grafo.add_conditional_edges("buscar_emails", hay_email,
                            ["leer_email", END])
grafo.add_edge("leer_email", "generar_respuesta")
grafo.add_edge("generar_respuesta", "crear_borrador")
grafo.add_edge("crear_borrador", END)

agente = grafo.compile()


if __name__ == "__main__":
    resultado = agente.invoke({"consulta": "in:inbox"})

    if not resultado.get("borrador_id"):
        print("No hay emails en la bandeja de entrada.")
    else:
        print("Asunto:", resultado["email"]["asunto"])
        print("Borrador creado:", resultado["borrador_id"])
        print("\nRespuesta:\n" + resultado["respuesta"])
