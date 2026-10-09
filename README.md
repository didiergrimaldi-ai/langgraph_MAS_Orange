# Sesión 3 · Agentes de IA con LangGraph

Cuatro ejemplos cortos (más una variante del 3 para controlar el agente) y un taller: un SOC (Centro de
Operaciones de Seguridad) con agentes. El hilo de las tres sesiones: cómo se **define**, se **controla** y se
**corrige** lo que hace un agente.

## Ejemplos

| Archivo | Qué muestra | Necesita |
|---|---|---|
| `1_agente_ia_langchain_simplificado.py` | Agente de email con LangChain: el LLM elige las herramientas en cada paso (patrón ReAct, `AgentExecutor`) | OpenAI + Gmail |
| `2_agente_email_langgraph.py` | El mismo agente con LangGraph: estado, nodos y aristas fijan el orden | OpenAI + Gmail |
| `3_agente_con_herramientas.py` | El bucle del agente como grafo: `bind_tools`, `ToolNode` y `tools_condition` | OpenAI |
| `3b_controlar_el_agente.py` | Controlar el agente: un nodo «revisar» con `interrupt()` pide permiso a una persona antes de ejecutar la herramienta | OpenAI |
| `4_sistema_multiagente.py` | Un mini sistema multiagente: un supervisor y dos especialistas (`create_supervisor`) | OpenAI |

Los ejemplos 1 y 2 leen el último email de tu bandeja de entrada y dejan un **borrador** de respuesta (no envían nada).

## Taller: `soc_multiagent/`

Un SOC recibe alertas de las herramientas de seguridad, separa los verdaderos positivos de los falsos positivos y
responde. Automatizamos tres pasos con agentes:

1. **alert_analyzer**: extrae los indicadores (IP, URL, hash), los consulta en VirusTotal, busca contexto con Tavily
   y decide: VERDADERO POSITIVO o FALSO POSITIVO.
2. **threat_analyzer** (solo si es verdadero positivo): evalúa la severidad y propone mitigaciones.
3. **notification_agent**: envía el informe por email (Gmail).

Un **supervisor** (`create_supervisor`) coordina a los tres. `probar_alerta.py` le pasa una alerta en formato JSON.

| Archivo | Qué hace |
|---|---|
| `config.py` | Lee las claves del archivo `.env` y valida las obligatorias |
| `tools.py` | Herramientas: TavilySearch, Gmail (enviar y borrador) y `virustotal_checker` (@tool propia). `python tools.py` las prueba |
| `agents.py` | Los tres agentes especialistas (`create_agent`) |
| `supervisor.py` | El supervisor (`create_supervisor`) y `process_security_alert()` |
| `probar_alerta.py` | Lanza una alerta JSON contra el supervisor y muestra el resultado |
| `alerta_*.json` | Alertas de prueba: `alerta_ejemplo.json`, `alerta_verdadero_positivo.json` y `alerta_falso_positivo.json` |

## Preparar el entorno

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
setx OPENAI_API_KEY "tu_clave"   # ejemplos 1–4 (macOS/Linux: export OPENAI_API_KEY="tu_clave")
```

- **Gmail** (ejemplos 1 y 2, y el taller): en Google Cloud Console, crea un proyecto, activa la Gmail API y crea un ID
  de cliente OAuth de tipo «Aplicación de escritorio». Descarga el JSON como `credenciales_google.json` en esta carpeta
  y en `soc_multiagent/`. La primera ejecución pide autorizar el acceso (en el taller, abre en el navegador la URL que
  aparece en la terminal) y guarda el token: `token_agente_email.json` (ejemplos 1 y 2) y `soc_multiagent/token.json`.
  Permisos: `gmail.readonly` + `gmail.compose` en los ejemplos; solo `gmail.compose` (borradores y envío) en el taller.
- **Taller**: crea el archivo `soc_multiagent/.env` con tus claves:

```
OPENAI_API_KEY=tu_clave
TAVILY_API_KEY=tu_clave
VIRUSTOTAL_API_KEY=tu_clave
GOOGLE_APPLICATION_CREDENTIALS=credenciales_google.json
GMAIL_TOKEN=token.json
SOC_EMAIL_RECIPIENT=tu_correo@ejemplo.com
```

  - **Tavily**: tavily.com (plan gratuito con créditos mensuales).
  - **VirusTotal**: virustotal.com, cuenta gratuita (API pública: 4 consultas por minuto).
  - **SOC_EMAIL_RECIPIENT**: a quién avisa el SOC (una dirección tuya o del equipo).

## Ejecutar

```bash
python 1_agente_ia_langchain_simplificado.py
python 2_agente_email_langgraph.py
python 3_agente_con_herramientas.py
python 3b_controlar_el_agente.py                    # te pregunta antes de ejecutar la herramienta (s/n)
python 4_sistema_multiagente.py

cd soc_multiagent
python tools.py                                       # prueba las herramientas (1 consulta a VirusTotal)
python probar_alerta.py                               # alerta_ejemplo.json
python probar_alerta.py alerta_verdadero_positivo.json
python probar_alerta.py alerta_falso_positivo.json
```

El análisis de una alerta tarda entre 45 y 90 segundos: la terminal muestra cada paso del supervisor.

## Alertas de prueba

| Archivo | Indicador | Resultado esperado |
|---|---|---|
| `alerta_verdadero_positivo.json` | Hash `275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f` (archivo de prueba EICAR, inofensivo) | VirusTotal lo marca como malicioso → análisis de amenaza → email |
| `alerta_falso_positivo.json` | IP origen `8.8.8.8` (DNS público de Google) | Sin detecciones relevantes → normalmente falso positivo: email informativo, sin análisis de amenaza |
| `alerta_ejemplo.json` | El mismo hash EICAR y una URL de prueba de Google | Verdadero positivo |

## Notas

- El agente de notificación **envía** el email de verdad: usa como destinatario una dirección tuya o del equipo.
- Cada indicador es una consulta a VirusTotal: con la cuenta gratuita, no lances muchas alertas seguidas.
- Las salidas de los agentes cambian entre ejecuciones: el LLM no responde dos veces igual.
- Nunca subas a GitHub `.env`, `credenciales_google.json` ni los tokens (ya están en `.gitignore`).
- La carpeta `old/` guarda la versión anterior del taller (webhook con FastAPI y dashboard con Streamlit); no se usa en clase.
