"""
Agente de Email con LangChain - Versión Simplificada
Sin complicaciones de UTF-8: google-auth maneja todo automáticamente
"""

from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import base64
from email.mime.text import MIMEText
import os
import sys

# UTF-8 en consola
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Trabajar en la carpeta del script: aquí están credenciales_google.json y el token
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# CONFIGURACIÓN DE AUTENTICACIÓN (Moderno - sin langchain_community)
# ============================================================================

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose'
]
TOKEN = 'token_agente_email.json'   # el script 2_ reutiliza este mismo token

def obtener_servicio_gmail():
    """Obtiene servicio Gmail con autenticación moderna."""
    creds = None

    # Cargar credenciales guardadas
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)

    # Si no hay credenciales válidas, pedir login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credenciales_google.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Guardar para próximas veces
        with open(TOKEN, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

gmail_service = obtener_servicio_gmail()


# ============================================================================
# HERRAMIENTAS SIMPLES (Sin clases complejas)
# ============================================================================

@tool
def buscar_emails(query: str = "in:inbox") -> list:
    """
    Busca emails en Gmail.

    Args:
        query: Query de Gmail (ej: "in:inbox", "from:alguien@example.com")

    Returns:
        Lista con los emails encontrados
    """
    try:
        results = gmail_service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            return []

        # Devolver info básica
        emails_info = []
        for msg in messages:
            header = gmail_service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in header.get('payload', {}).get('headers', [])}

            emails_info.append({
                'id': msg['id'],
                'threadId': header.get('threadId'),
                'from': headers.get('From', ''),
                'subject': headers.get('Subject', ''),
                'date': headers.get('Date', ''),
            })

        return emails_info

    except HttpError as error:
        return f"Error buscando emails: {error}"


@tool
def leer_email(message_id: str) -> dict:
    """
    Lee el contenido completo de un email.
    UTF-8 se maneja automáticamente.

    Args:
        message_id: ID del mensaje

    Returns:
        Diccionario con los datos del email
    """
    try:
        message = gmail_service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in message['payload']['headers']}

        # Extraer cuerpo (Google API lo maneja bien)
        cuerpo = ""
        if 'parts' in message['payload']:
            for parte in message['payload']['parts']:
                if parte['mimeType'] == 'text/plain':
                    data = parte['body'].get('data', '')
                    if data:
                        cuerpo = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                    break
        else:
            data = message['payload']['body'].get('data', '')
            if data:
                cuerpo = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')

        return {
            'id': message_id,
            'threadId': message.get('threadId'),
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'body': cuerpo.strip(),
        }

    except HttpError as error:
        return {'error': f"Error leyendo email: {error}"}


@tool
def crear_respuesta_borrador(message_id: str, cuerpo_respuesta: str) -> str:
    """
    Crea un borrador de respuesta a un email.

    Args:
        message_id: ID del email original
        cuerpo_respuesta: Contenido de la respuesta

    Returns:
        Confirmación con ID del borrador
    """
    try:
        # Obtener email original para extraer datos
        original = gmail_service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in original['payload']['headers']}

        # Preparar respuesta
        from_email = headers.get('From', '').split('<')[-1].rstrip('>')
        subject = headers.get('Subject', '')

        if not subject.startswith('Re:'):
            subject = f'Re: {subject}'

        # Crear mensaje MIME
        mensaje = MIMEText(cuerpo_respuesta, 'plain', 'utf-8')
        mensaje['to'] = from_email
        mensaje['subject'] = subject
        mensaje['In-Reply-To'] = headers.get('Message-ID', '')
        mensaje['References'] = headers.get('Message-ID', '')

        # Codificar
        raw_mensaje = base64.urlsafe_b64encode(
            mensaje.as_bytes()
        ).decode('utf-8')

        # Crear borrador
        borrador = gmail_service.users().drafts().create(
            userId='me',
            body={
                'message': {
                    'raw': raw_mensaje,
                    'threadId': original.get('threadId')
                }
            }
        ).execute()

        return f"✅ Borrador creado exitosamente. ID: {borrador['id']}"

    except HttpError as error:
        return f"❌ Error: {error}"


# ============================================================================
# AGENTE CON LANGCHAIN
# ============================================================================

tools = [
    buscar_emails,
    leer_email,
    crear_respuesta_borrador,
]

model = init_chat_model("openai:gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de email profesional. Para procesar emails:

1. Primero: Busca emails en la bandeja de entrada con 'buscar_emails'
2. Segundo: Lee el email más reciente con 'leer_email'
3. Tercero: Analiza y genera una respuesta profesional en español
4. Cuarto: Crea el borrador con 'crear_respuesta_borrador'

Sé conciso, profesional y amable en tus respuestas."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(model, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10
)


# ============================================================================
# EJECUCIÓN
# ============================================================================

def procesar_ultimo_email():
    """Procesa el email más reciente de la bandeja de entrada."""
    try:
        response = agent_executor.invoke({
            "input": "Procesa el email más reciente en la bandeja de entrada y crea un borrador de respuesta profesional."
        })
        return response['output']
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    resultado = procesar_ultimo_email()
    print("\n" + "="*60)
    print("RESULTADO:")
    print("="*60)
    print(resultado)
