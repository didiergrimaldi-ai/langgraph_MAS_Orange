from langchain_classic.agents import create_tool_calling_agent, AgentExecutor # para crear agentes que llamen a herramientas
from langchain_core.prompts import ChatPromptTemplate 
from langchain.chat_models import init_chat_model
from langchain_community.agent_toolkits import GmailToolkit #para usar herramientas de Gmail
from langchain_community.tools.gmail.utils import get_gmail_credentials, build_resource_service, clean_email_body
from langchain_community.tools.gmail import search as gmail_search, get_message as gmail_get_message
from types import SimpleNamespace
import base64
import email
import email.header
import os
import sys

# Forzar UTF-8 en la consola de Windows (tildes, ñ y emojis de los emails)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# Configurar el directorio de trabajo
original_dir = os.getcwd()
os.chdir(r"C:\Users\Didier\Dropbox\Mas Orange\Focused_LangGraph\Nueva Sesion 3 - Vscode")

# Credenciales de Gmail con los scopes necesarios (leer emails + crear borradores)
credentials = get_gmail_credentials(
    token_file="token_agente_email.json",
    client_secrets_file="credenciales_google.json",
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ],
)
api_resource = build_resource_service(credentials=credentials)
gmail_toolkit = GmailToolkit(api_resource=api_resource)


def decodificar_cabecera(valor):
    """Convierte cabeceras MIME (=?UTF-8?B?...?=) a texto legible."""
    if not valor:
        return valor
    return str(email.header.make_header(email.header.decode_header(valor)))


def decodificar_cuerpo(parte):
    """Decodifica el cuerpo con el charset que declara el email (no siempre es UTF-8)."""
    contenido = parte.get_payload(decode=True) or b""
    charset = parte.get_content_charset() or "utf-8"
    try:
        return contenido.decode(charset)
    except (UnicodeDecodeError, LookupError):
        return contenido.decode("utf-8", errors="replace")


def leer_email(api_resource, message_id):
    """Descarga un email de Gmail y devuelve sus datos con el texto bien decodificado."""
    datos = api_resource.users().messages().get(userId="me", format="raw", id=message_id).execute()
    email_msg = email.message_from_bytes(base64.urlsafe_b64decode(datos["raw"]))

    cuerpo = ""
    if email_msg.is_multipart():
        for parte in email_msg.walk():
            if parte.get_content_type() == "text/plain" and "attachment" not in str(parte.get("Content-Disposition")):
                cuerpo = decodificar_cuerpo(parte)
                break
    else:
        cuerpo = decodificar_cuerpo(email_msg)

    return {
        "id": message_id,
        "threadId": datos["threadId"],
        "snippet": datos["snippet"],
        "body": clean_email_body(cuerpo),
        "subject": decodificar_cabecera(email_msg["Subject"]),
        "sender": decodificar_cabecera(email_msg["From"]),
        "date": email_msg["Date"],
        "to": decodificar_cabecera(email_msg["To"]),
    }


class GmailSearchUTF8(gmail_search.GmailSearch):
    """search_gmail, pero sin fallar con emails que no vienen en UTF-8."""

    def _parse_messages(self, messages):
        return [leer_email(self.api_resource, m["id"]) for m in messages]


class GmailGetMessageUTF8(gmail_get_message.GmailGetMessage):
    """get_gmail_message, pero sin fallar con emails que no vienen en UTF-8."""

    def _run(self, message_id, run_manager=None):
        return leer_email(self.api_resource, message_id)


herramientas_utf8 = {
    "search_gmail": GmailSearchUTF8(api_resource=api_resource),
    "get_gmail_message": GmailGetMessageUTF8(api_resource=api_resource),
}
tools = [herramientas_utf8.get(t.name, t) for t in gmail_toolkit.get_tools()]

# Configurar modelo del agente que soporte tool calling
model = init_chat_model("openai:gpt-4o", temperature=0)

# Prompt de agente que define su comportamiento
prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de email profesional. Para procesar emails sigue EXACTAMENTE estos pasos:

    1. PRIMERO: Usa 'search_gmail' con query 'in:inbox' para obtener la lista de mensajes en la bandeja de entrada.
    
    2. SEGUNDO: De la lista obtenida, identifica el message_id del email más reciente (el primer resultado).
    
    3. TERCERO: Usa 'get_gmail_message' con el message_id real obtenido en el paso anterior para obtener el contenido completo.
    
    4. CUARTO: Analiza el email y EXTRAE esta información crítica:
       - Thread ID (busca "Thread ID:" en el contenido)
       - Remitente original (busca "From:" y extrae el email)
       - Asunto original (busca "Subject:")
       - Contenido principal del mensaje
    
    5. QUINTO: Genera una respuesta profesional y apropiada en español.
    
    6. SEXTO: Usa 'create_gmail_draft' para crear un borrador de RESPUESTA (no email nuevo) con:
       - "message": tu respuesta generada
       - "subject": "Re: [asunto original]" (si no empieza ya con "Re:")
       - "to": email del remitente original
       - "thread_id": el Thread ID extraído del paso 4 (MUY IMPORTANTE para que sea una respuesta)

    CRÍTICO PARA RESPUESTAS:
    - SIEMPRE incluye "thread_id" en create_gmail_draft para que sea una respuesta, no un email nuevo
    - El "to" debe ser el email del remitente original
    - El "subject" debe empezar con "Re:" si no lo tiene ya

    IMPORTANTE: 
    - NUNCA uses message_id hardcodeados como '1' o '2' 
    - SIEMPRE obtén los IDs reales de los mensajes primero
    - Sin thread_id, el borrador será un email nuevo, no una respuesta
    - Si no encuentras thread_id, informa el problema pero intenta crear el borrador igual
    
    Si encuentras errores, explica qué información falta y por qué."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# Crear agente
agent = create_tool_calling_agent(model, tools, prompt) # agente funcional que llama a herramientas de Gmail según el prompt definido

# Crear executor del agente que se encarga de ejecutar el flujo de trabajo del agente
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True, # registros para mostrar información detallada del proceso
    handle_parsing_errors=True, # errores son manejado por el agente, no interrumpen la ejecución
    max_iterations=10 # Limitar iteraciones para evitar bucles *loops
)

def process_latest_email():
    try:
        response = agent_executor.invoke({
            "input": "Procesa el email más reciente en la bandeja de entrada y genera un borrador de respuesta profesional."
        })
        return response['output']
    except Exception as e:
        print(f"Error al procesar email: {str(e)}")
        return f"Error {str(e)}"
    
# La directiva para Ejecutar
if __name__ == "__main__":
    result = process_latest_email()
    print("\n" + "="*50)
    print("RESULTADO:")
    print("="*50)
    print(result)