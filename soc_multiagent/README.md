# SOC multiagente con LangGraph

Sistema multiagente que analiza alertas de seguridad. Un **supervisor** (`langgraph-supervisor`) coordina tres agentes:

1. **alert_analyzer** – extrae los IOCs (IPs, URLs, hashes) y los analiza con **VirusTotal** y **Tavily** → verdadero o falso positivo.
2. **threat_analyzer** – solo si es verdadero positivo: severidad, TTPs y mitigaciones.
3. **notification_agent** – envía el informe por **Gmail**.

Incluye una app de **Streamlit** que muestra cada paso del supervisor en directo.

## Estructura

| Fichero | Qué hace |
|---|---|
| `streamlit_app.py` | Interfaz web |
| `supervisor.py` | Workflow del supervisor (`process_security_alert`, `stream_security_alert`) |
| `agents.py` | Los tres agentes |
| `tools.py` | VirusTotal, Tavily y Gmail |
| `config.py` | Lee las claves del entorno |
| `probar_alerta.py` | Prueba por consola, sin web |
| `alerta_*.json` | Alertas de ejemplo |

## Ejecutar en local

```bash
pip install -r requirements.txt
cp .env.example .env          # y rellena tus claves
python tools.py               # la primera vez abre el navegador para autorizar Gmail y crea token.json
streamlit run streamlit_app.py
```

## Publicar en GitHub

`.gitignore` ya excluye `.env`, `token.json`, `credenciales_google.json` y `.streamlit/secrets.toml`. **Comprueba con `git status` que no aparecen antes del primer commit.**

```bash
git init
git add .
git status                    # .env, token.json y credenciales_google.json NO deben salir
git commit -m "SOC multiagente con Streamlit"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/soc-multiagent.git
git push -u origin main
```

## Desplegar en Streamlit Community Cloud

1. Entra en [share.streamlit.io](https://share.streamlit.io) → **Create app** → elige el repositorio, rama `main` y fichero `streamlit_app.py`.
2. En **Advanced settings → Secrets** pega el contenido de `.streamlit/secrets.toml.example` con tus valores:
   - Las claves de OpenAI, Tavily y VirusTotal.
   - `GMAIL_TOKEN_JSON`: el **contenido** de tu `token.json` generado en local (en la nube no se puede abrir el navegador para autorizar Gmail).
   - `APP_PASSWORD`: muy recomendable. Sin ella, cualquiera con el enlace puede gastar tus créditos y enviar emails desde tu cuenta.
3. **Deploy**.

La app copia los secrets a variables de entorno, así que `config.py` funciona igual en local (`.env`) y en la nube.
