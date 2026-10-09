"""
App de Streamlit para el SOC multiagente.

El supervisor coordina alert_analyzer → threat_analyzer → notification_agent
y la app muestra cada paso en directo y el resultado final.

Uso local:
    streamlit run streamlit_app.py
"""

import hmac
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).parent
# Trabajar en esta carpeta: aquí están .env, credenciales, token y las alertas JSON
os.chdir(BASE_DIR)

st.set_page_config(page_title="SOC multiagente", page_icon=":material/security:", layout="wide")


# --- Configuración: st.secrets (Streamlit Cloud) → variables de entorno ---------
# config.py lee os.getenv(), así que en la nube basta con volcar los secrets al entorno.
# En local no hace falta secrets.toml: se usa el .env como siempre.
def _load_secrets_into_env():
    try:
        secrets = dict(st.secrets)
    except Exception:
        return  # sin secrets.toml → se usa el .env

    for key, value in secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(key, value)

    # Gmail necesita ficheros: en la nube se guardan como texto JSON en los secrets
    tmp_dir = Path(tempfile.gettempdir()) / "soc_multiagent"
    tmp_dir.mkdir(exist_ok=True)
    for secret_name, env_name, file_name in [
        ("GMAIL_TOKEN_JSON", "GMAIL_TOKEN", "token.json"),
        ("GOOGLE_CREDENTIALS_JSON", "GOOGLE_APPLICATION_CREDENTIALS", "credenciales_google.json"),
    ]:
        if secret_name in secrets:
            path = tmp_dir / file_name
            if not path.exists():  # no pisar el token refrescado por Google
                path.write_text(secrets[secret_name], encoding="utf-8")
            os.environ[env_name] = str(path)


_load_secrets_into_env()


@st.cache_resource(show_spinner="Cargando agentes...")
def load_soc():
    # Import diferido: al importar se validan las claves y se conecta con Gmail
    import supervisor
    from config import config

    return supervisor, config


# --- Acceso (opcional): si hay APP_PASSWORD, la app pide contraseña -------------
def check_password() -> bool:
    expected = os.getenv("APP_PASSWORD")
    if not expected or st.session_state.get("authenticated"):
        return True

    with st.form("login"):
        st.subheader("Acceso restringido")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(password, expected):
                st.session_state.authenticated = True
                st.rerun()
            st.error("Contraseña incorrecta")
    return False


EXAMPLES = {
    "Ejemplo (EDR)": "alerta_ejemplo.json",
    "Verdadero positivo": "alerta_verdadero_positivo.json",
    "Falso positivo": "alerta_falso_positivo.json",
}

AGENTS = {
    "alert_analyzer": ":material/search: Análisis de la alerta (VirusTotal + Tavily)",
    "threat_analyzer": ":material/shield: Evaluación de la amenaza y mitigación",
    "notification_agent": ":material/mail: Notificación por email (Gmail)",
}


def _agent_messages(messages, agent):
    return [m for m in messages if getattr(m, "name", None) == agent and getattr(m, "type", None) == "ai"]


def _final_text(messages, agent):
    for m in reversed(_agent_messages(messages, agent)):
        if m.content and not m.tool_calls:
            return m.content
    return ""


def _tool_calls(messages, agent):
    return [
        tc
        for m in _agent_messages(messages, agent)
        for tc in (m.tool_calls or [])
        if not tc["name"].startswith("transfer_")
    ]


def _verdict(analysis: str):
    text = analysis.upper()
    if "VERDADERO POSITIVO" in text:
        return "Verdadero positivo", "red", ":material/warning:"
    if "FALSO POSITIVO" in text:
        return "Falso positivo", "green", ":material/check_circle:"
    return "Sin determinar", "gray", ":material/help:"


def _severity(threat: str):
    for level, color in [("CRÍTICA", "red"), ("ALTA", "orange"), ("MEDIA", "yellow"), ("BAJA", "blue")]:
        if f"SEVERIDAD: {level}" in threat.upper().replace("*", ""):
            return level.capitalize(), color
    return None, None


def run_analysis(alert: dict, incident_id: str, recipient: str):
    supervisor, _ = load_soc()
    result = None

    for event in supervisor.stream_security_alert(alert, incident_id, {"email_recipient": recipient}):
        if event["type"] == "result":
            result = event["result"]
            continue

        node, messages = event["node"], event["messages"]
        if node == "supervisor":
            transfers = [tc["name"].removeprefix("transfer_to_") for m in messages
                         if getattr(m, "type", None) == "ai" for tc in (m.tool_calls or [])
                         if tc["name"].startswith("transfer_to_")]
            label = f"Supervisor delega en `{transfers[-1]}`" if transfers else "Supervisor: proceso completado"
            with st.status(label, type="step", state="complete"):
                st.caption(":material/account_tree: Coordinación del flujo")
            continue

        with st.status(AGENTS.get(node, node), type="step", state="complete"):
            calls = _tool_calls(messages, node)
            if calls:
                st.caption("Herramientas usadas: " + ", ".join(f"`{c['name']}`" for c in calls))
            text = _final_text(messages, node)
            if text:
                st.markdown(text)

    return result


def show_result(result: dict):
    analysis = result["analysis_result"]
    threat = result["threat_assessment"]
    verdict, color, icon = _verdict(analysis)
    severity, sev_color = _severity(threat)
    email_ok = result["notification_sent"].strip().upper().startswith("EMAIL ENVIADO")

    with st.container(horizontal=True):
        st.badge(verdict, icon=icon, color=color)
        if severity:
            st.badge(f"Severidad {severity}", icon=":material/bolt:", color=sev_color)
        if email_ok:
            st.badge("Email enviado", icon=":material/mark_email_read:", color="green")
        else:
            st.badge("Email no enviado", icon=":material/unsubscribe:", color="orange")

    tab_analysis, tab_threat, tab_email, tab_json = st.tabs(
        [":material/search: Análisis", ":material/shield: Amenaza", ":material/mail: Notificación", ":material/data_object: JSON"]
    )
    with tab_analysis:
        st.markdown(analysis)
    with tab_threat:
        st.markdown(threat)
    with tab_email:
        st.markdown(result["notification_sent"])
    with tab_json:
        st.json({k: v for k, v in result.items() if k != "full_conversation"}, expanded=False)
        st.download_button(
            "Descargar informe",
            json.dumps({k: v for k, v in result.items() if k != "full_conversation"}, ensure_ascii=False, indent=2),
            file_name=f"{result['incident_id']}.json",
            mime="application/json",
            icon=":material/download:",
        )


# --- Interfaz -----------------------------------------------------------------
st.session_state.setdefault("history", [])

st.title(":material/security: SOC multiagente")
st.caption(
    "Un supervisor de LangGraph coordina tres agentes: analiza los IOCs de la alerta con VirusTotal y Tavily, "
    "evalúa la amenaza y envía el informe por email."
)

if not check_password():
    st.stop()

try:
    supervisor, config = load_soc()
except Exception as e:
    st.error(f"No se pudo iniciar el SOC: {e}", icon=":material/error:")
    st.info("Revisa las claves en `.env` (local) o en los *Secrets* de Streamlit Cloud. Mira el README.")
    st.stop()

with st.sidebar:
    st.header("Configuración")
    st.text_input("Destinatario del informe", value=config.SOC_EMAIL_RECIPIENT or "", disabled=True)
    st.caption("Se configura con `SOC_EMAIL_RECIPIENT`.")

    st.header("Historial")
    history_box = st.container()  # se rellena al final, tras el análisis

col_input, col_output = st.columns([2, 3], gap="large")

with col_input:
    st.subheader("Alerta")
    source = st.segmented_control(
        "Origen de la alerta",
        [":material/list: Ejemplo", ":material/upload_file: Subir JSON", ":material/edit: Escribir JSON"],
        default=":material/list: Ejemplo",
        required=True,
    )

    raw = ""
    if source.endswith("Ejemplo"):
        example = st.selectbox("Alerta de ejemplo", list(EXAMPLES))
        raw = (BASE_DIR / EXAMPLES[example]).read_text(encoding="utf-8")
        st.code(raw, language="json")
    elif source.endswith("Subir JSON"):
        uploaded = st.file_uploader("Fichero JSON de la alerta", type="json")
        if uploaded:
            raw = uploaded.getvalue().decode("utf-8")
            st.code(raw, language="json")
    else:
        raw = st.text_area(
            "JSON de la alerta",
            height=300,
            placeholder='{\n  "id": "ALERT-0100",\n  "source": "Email Gateway",\n  "rule": "...",\n  "sender_ip": "..."\n}',
        )

    alert, error = None, None
    if raw.strip():
        try:
            alert = json.loads(raw)
            if not isinstance(alert, dict):
                error = "La alerta debe ser un objeto JSON (`{...}`)."
                alert = None
        except json.JSONDecodeError as e:
            error = f"JSON no válido: {e}"
    if error:
        st.error(error, icon=":material/error:")

    run = st.button("Analizar alerta", type="primary", icon=":material/play_arrow:", disabled=alert is None)

with col_output:
    st.subheader("Resultado")
    if run and alert is not None:
        incident_id = str(alert.get("id") or f"ALERT-{datetime.now():%Y%m%d%H%M%S}")
        try:
            with st.status(f":shimmer[Procesando {incident_id}]", type="compact", expanded=True) as status:
                result = run_analysis(alert, incident_id, config.SOC_EMAIL_RECIPIENT)
                status.update(label=f"Proceso de {incident_id} completado", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Error en el SOC: {e}", icon=":material/error:")
            result = None

        if result:
            st.session_state.last_result = result
            st.session_state.history.insert(0, {
                "ID": incident_id,
                "Veredicto": _verdict(result["analysis_result"])[0],
                "Hora": datetime.now().strftime("%H:%M:%S"),
            })

    if "last_result" in st.session_state:
        show_result(st.session_state.last_result)
    elif not run:
        st.info("Elige una alerta y pulsa **Analizar alerta**.", icon=":material/info:")

with history_box:
    if st.session_state.history:
        st.dataframe(st.session_state.history, hide_index=True)
    else:
        st.caption("Aún no has analizado ninguna alerta.")
