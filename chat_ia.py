import sqlite3
import pandas as pd
import streamlit as st
import time
from google import genai

st.set_page_config(page_title="Asistente Beco IA", page_icon="🤖", layout="wide")

st.title("🤖 Asistente Conversacional Beco Real Estate")
st.write("Haz preguntas en lenguaje natural sobre el portafolio, ocupación o cánones de arriendo.")

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("No se encontró la clave GEMINI_API_KEY en .streamlit/secrets.toml")
    st.stop()

client = genai.Client(api_key=api_key)

def obtener_esquema_db():
    conn = sqlite3.connect("modelo_definitivo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tablas = cursor.fetchall()
    conn.close()
    esquema = "\n".join([t[0] for t in tablas if t[0] is not None])
    return esquema

def ejecutar_consulta_sql(sql_query):
    conn = sqlite3.connect("modelo_definitivo.db")
    try:
        query_clean = sql_query.strip().upper()
        if not query_clean.startswith("SELECT"):
            return None, "Por seguridad, solo se permiten consultas de lectura (SELECT)."
        
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return df, None
    except Exception as e:
        conn.close()
        return None, str(e)

def generar_contenido_con_fallback(prompt_texto):
    # Lista de modelos en orden de prioridad
    modelos = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    for modelo in modelos:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt_texto
            )
            return response.text
        except Exception as e:
            # Si da error 503 o no disponible, espera medio segundo y prueba el siguiente
            time.sleep(0.5)
            continue
            
    raise Exception("Los servidores de la IA están experimentando alta demanda. Por favor intenta en unos segundos.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ej: ¿Cuántas bodegas tengo?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando la base de datos..."):
            esquema = obtener_esquema_db()
            
            system_prompt = f"""
            Eres un experto analista SQL para un sistema inmobiliario (Beco Real Estate).
            Dada la siguiente estructura de la base de datos SQLite:
            
            {esquema}
            
            Transforma la siguiente pregunta del usuario en una consulta SQL SQLite estricta y válida.
            REGLAS IMPORTANTES:
            1. Devuelve ÚNICAMENTE el código SQL sin explicaciones, sin formato markdown (sin ```sql ... ```).
            2. Usa solo sentencias SELECT.
            3. Si la pregunta no se refiere a los datos de la base, responde la pregunta de forma amigable sin SQL.
            """

            full_prompt = f"{system_prompt}\n\nPregunta del usuario: {prompt}"

            try:
                texto_respuesta = generar_contenido_con_fallback(full_prompt)
                sql_generada = texto_respuesta.strip().replace("```sql", "").replace("```", "").strip()

                if sql_generada.upper().startswith("SELECT"):
                    df_resultado, error = ejecutar_consulta_sql(sql_generada)
                    
                    if error:
                        st.error(f"Error al ejecutar SQL: {error}")
                        st.code(sql_generada, language="sql")
                    elif df_resultado is not None:
                        st.write("📊 **Resultado:**")
                        st.dataframe(df_resultado, use_container_width=True)
                        
                        with st.expander("Ver consulta SQL generada"):
                            st.code(sql_generada, language="sql")
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"He ejecutado la consulta para responder tu pregunta. Se encontraron {len(df_resultado)} registros."
                        })
                else:
                    st.write(texto_respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
            except Exception as ex:
                st.warning(str(ex))
