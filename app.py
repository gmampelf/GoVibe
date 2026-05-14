"""GoVibe: Tu Conserje Social con IA
==================================
Agente conversacional construido con LangChain 1.x + LangGraph + Gemini + Gradio.
Ayuda a planificar salidas, buscar actividades y gestionar presupuestos.
"""

import os
import re
from typing import Any

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

# ---------------------------------------------------------------------------
# Configuración inicial
# ---------------------------------------------------------------------------

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# ---------------------------------------------------------------------------
# Herramientas (Tools)
# ---------------------------------------------------------------------------

@tool
def calcular_presupuesto(expresion: str) -> str:
    """
    Realiza cálculos matemáticos simples para ayudar con presupuestos de salidas.

    Útil para:
    - Sumar costes de actividades (ej. "35 + 20 + 15").
    - Dividir una cuenta entre varias personas (ej. "120 / 4").
    - Calcular presupuesto por persona (ej. "200 / 3").

    Args:
        expresion: Expresión matemática en texto, usando solo +, -, *, /.
                   Ejemplo: "50 + 30 / 2" o "120 / 4".

    Returns:
        El resultado numérico formateado como cadena de texto.
    """
    expresion_limpia = re.sub(r"[^\d\s\+\-\*\/\.\(\)]", "", expresion).strip()
    if not expresion_limpia:
        return "No pude interpretar la expresión. Usa solo números y operadores (+, -, *, /)."
    try:
        resultado = eval(expresion_limpia)  # noqa: S307 — entrada sanitizada
        return f"El resultado es: {resultado:.2f}"
    except ZeroDivisionError:
        return "Error: no se puede dividir entre cero."
    except Exception:
        return "No pude calcular eso. Escribe una expresión válida como '50 + 30' o '120 / 4'."


search = DuckDuckGoSearchRun()
search.description = (
    "Busca en internet planes de ocio, restaurantes, eventos, escape rooms, "
    "conciertos, cines u otras actividades. Úsala para encontrar opciones reales "
    "y actualizadas en una ciudad o zona concreta. "
    "Input: una consulta de búsqueda en español."
)

TOOLS = [search, calcular_presupuesto]


# ---------------------------------------------------------------------------
# Prompt maestro del sistema
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres GoVibe, un consejero social con inteligencia artificial: enérgico, creativo y sumamente útil.
Tu misión es ayudar a las personas a vivir experiencias increíbles diseñando planes de ocio personalizados.

PERSONALIDAD:
- Eres entusiasta y positivo, pero conciso.
- Usas emojis con moderación para dar dinamismo (🎉, 🍕, 🎭, 💡, 💰).
- Siempre preguntas lo necesario para personalizar el plan (ciudad, número de personas, presupuesto, horario).
- Eres proactivo: si te falta información clave, la pides antes de buscar.

CAPACIDADES:
1. Buscas actividades reales usando la herramienta de búsqueda.
2. Calculas presupuestos y divides cuentas con la herramienta de cálculo.
3. Recuerdas el contexto de la conversación para no repetir preguntas.

FLUJO DE TRABAJO:
1. Identifica ciudad, número de personas, presupuesto y tipo de plan.
2. Usa la herramienta de búsqueda para encontrar opciones concretas.
3. Presenta 2-3 opciones estructuradas con nombre, descripción, precio estimado y consejo práctico.
4. Ofrece crear un itinerario completo si el usuario quiere profundizar.
5. Usa la herramienta de cálculo cuando haya operaciones de presupuesto.

FORMATO DE RESPUESTA:
- Usa listas con viñetas o numeradas para las opciones.
- Incluye siempre un precio o rango de precio aproximado.
- Termina con una pregunta de seguimiento o una propuesta de itinerario.

RESTRICCIONES:
- Si no encuentras información suficiente, comunícalo con honestidad y ofrece alternativas.
- No inventes precios ni direcciones; basa tus respuestas en los resultados de búsqueda.
- Responde siempre en el idioma del usuario."""


# ---------------------------------------------------------------------------
# Construcción del agente (LangGraph)
# ---------------------------------------------------------------------------

def build_agent() -> Any:
    """
    Instancia el LLM y construye el agente ReactAgent con LangGraph.

    Returns:
        Agente compilado listo para invocar con {"messages": [...]}.

    Raises:
        ValueError: Si GOOGLE_API_KEY no está configurada.
    """
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY no encontrada. "
            "Crea un archivo .env con GOOGLE_API_KEY=tu_clave o configúrala como variable de entorno."
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY,
    )

    return create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


try:
    agent = build_agent()
    AGENT_READY = True
except ValueError as exc:
    print(f"[GoVibe] Advertencia: {exc}")
    agent = None
    AGENT_READY = False


# ---------------------------------------------------------------------------
# Función principal de chat
# ---------------------------------------------------------------------------

def chat(message: str, history: list[dict]) -> str:
    """
    Procesa un mensaje del usuario y devuelve la respuesta del agente.

    Convierte el historial de Gradio 6 (lista de dicts {role, content})
    al formato de mensajes de LangChain, invoca el agente y captura errores.

    Args:
        message: Texto enviado por el usuario en el turno actual.
        history: Historial en formato Gradio 6: [{"role": "user"|"assistant", "content": str}, ...].

    Returns:
        Respuesta del agente como cadena de texto.
    """
    if not AGENT_READY or agent is None:
        return (
            "⚠️ GoVibe no está disponible porque falta la clave de API de Google. "
            "Configura `GOOGLE_API_KEY` en tu archivo `.env` y reinicia la aplicación."
        )

    # Gradio 6 pasa el historial como lista de dicts con claves "role" y "content"
    messages: list[HumanMessage | AIMessage] = []
    for msg in history:
        role = msg.get("role", "") if isinstance(msg, dict) else ""
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=message))

    try:
        result = agent.invoke({"messages": messages})
        # El último mensaje de la respuesta es la respuesta del agente
        return result["messages"][-1].content

    except Exception as exc:  # noqa: BLE001
        print(f"[GoVibe] Error al invocar el agente: {exc}")
        return (
            "😅 Vaya, algo salió mal al procesar tu petición. "
            "Puede ser un problema temporal con la búsqueda o con la API. "
            "¿Puedes reformular tu pregunta o intentarlo de nuevo en un momento?"
        )


# ---------------------------------------------------------------------------
# Interfaz Gradio
# ---------------------------------------------------------------------------

EJEMPLOS = [
    "Planea una tarde en Madrid para 2 personas con un presupuesto de 50€",
    "¿Qué escape rooms hay en Barcelona este fin de semana?",
    "Somos 4 amigos en Valencia, gastamos 180€ en total, ¿cuánto toca por persona?",
    "Mi pareja y yo no sabemos dónde ir de vacaciones, haznos una propuesta de un destino europeo con playa"
]

LOGO_HTML = """
<div style="display:flex; align-items:center; gap:14px; padding:16px 0 4px;">
  <svg width="60" height="60" viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="gvGrad" x1="15" y1="70" x2="125" y2="70" gradientUnits="userSpaceOnUse">
        <stop offset="0%"   stop-color="#00d4ff"/>
        <stop offset="45%"  stop-color="#a855f7"/>
        <stop offset="100%" stop-color="#ff6969"/>
      </linearGradient>
      <filter id="gvGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="4" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    <rect x="8" y="8" width="124" height="124" rx="24" ry="24"
          fill="#13131f" stroke="#252540" stroke-width="2"/>
    <path d="M 66,42 L 30,42 L 30,102 L 78,102 L 78,74 L 55,74"
          fill="none" stroke="url(#gvGrad)" stroke-width="8"
          stroke-linecap="round" stroke-linejoin="round" filter="url(#gvGlow)"/>
    <path d="M 62,42 L 112,42 L 78,102"
          fill="none" stroke="url(#gvGrad)" stroke-width="8"
          stroke-linecap="round" stroke-linejoin="round" filter="url(#gvGlow)"/>
  </svg>
  <h2 style="margin:0; font-size:1.4rem; font-weight:700; line-height:1.2;">GoVibe: Tu Consejero Social con IA</h2>
</div>
"""


CSS = """
html, body { overflow: hidden !important; }
footer     { display: none !important; }
.chatbot   { height: calc(100vh - 250px) !important; overflow-y: auto !important; }
"""

with gr.Blocks(title="GoVibe") as demo:
    gr.HTML(LOGO_HTML)
    gr.Markdown(
        "**GoVibe** te ayuda a diseñar planes de ocio perfectos. "
        "Dime tu ciudad, cuántos sois, tu presupuesto y qué tipo de plan buscas "
        "y encontraré opciones reales para que lo paséis en grande. 🎉\n\n"
        "Puedo buscar restaurantes, conciertos, escape rooms, cine, actividades al aire libre "
        "y también calcular presupuestos y dividir cuentas."
    )
    gr.ChatInterface(
        fn=chat,
        examples=EJEMPLOS,
        chatbot=gr.Chatbot(show_label=False, layout="bubble"),
        textbox=gr.Textbox(placeholder="Escribe tu mensaje aquí…", show_label=False, autofocus=True),
    )


if __name__ == "__main__":
    demo.launch(share=False, css=CSS, theme=gr.themes.Soft(primary_hue="violet", font=gr.themes.GoogleFont("Google Sans")))
