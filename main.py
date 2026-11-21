from fastapi import FastAPI
from db import get_connection

app = FastAPI(title="Barbería Citas")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from datetime import datetime, timedelta
from pydantic import BaseModel
@app.get("/")
def inicio():
    return {"estado": "ok", "mensaje": "API de Barbería funcionando"}


@app.get("/test-db")
def probar_bd():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tablas = [fila[0] for fila in cursor.fetchall()]
    cursor.close()
    conn.close()
    return {"conectado": True, "tablas": tablas}

@app.get("/servicios")
def listar_servicios():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, duracion_minutos, precio FROM servicios WHERE activo = 1;")
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    return datos


@app.get("/barberos")
def listar_barberos():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, especialidad FROM barberos WHERE activo = 1;")
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    return datos

class CitaCrear(BaseModel):
    barbero_id: int
    servicio_id: int
    cliente_nombre: str
    cliente_telefono: str
    cliente_correo: str | None = None
    fecha: str          # Formato YYYY-MM-DD, ej: "2026-11-23"
    hora_inicio: str    # Formato HH:MM, ej: "10:00"
    notas: str | None = None


@app.post("/citas")
def crear_cita(cita: CitaCrear):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Buscar duración del servicio
    cursor.execute(
        "SELECT duracion_minutos FROM servicios WHERE id = %s AND activo = 1;",
        (cita.servicio_id,),
    )
    servicio = cursor.fetchone()
    if not servicio:
        cursor.close()
        conn.close()
        return {"error": "Servicio no encontrado o inactivo"}

    # 2. Calcular hora_fin sumando duracion_minutos
    inicio_dt = datetime.strptime(cita.hora_inicio, "%H:%M")
    fin_dt = inicio_dt + timedelta(minutes=servicio["duracion_minutos"])
    hora_fin_str = fin_dt.strftime("%H:%M:%S")
    hora_inicio_str = inicio_dt.strftime("%H:%M:%S")

    # 2.5 Verificar si el barbero ya tiene una cita que se cruce en ese horario
    cursor.execute(
        """
        SELECT id FROM citas
        WHERE barbero_id = %s
          AND fecha = %s
          AND estado != 'cancelada'
          AND hora_inicio < %s
          AND hora_fin > %s;
        """,
        (cita.barbero_id, cita.fecha, hora_fin_str, hora_inicio_str),
    )
    choque = cursor.fetchone()
    if choque:
        cursor.close()
        conn.close()
        return {"error": "El barbero ya tiene una cita en ese horario"}

    # 3. Registrar cliente y obtener su id
    cursor.execute(
        "INSERT INTO clientes (nombre, telefono, correo) VALUES (%s, %s, %s);",
        (cita.cliente_nombre, cita.cliente_telefono, cita.cliente_correo),
    )
    cliente_id = cursor.lastrowid

    # 4. Guardar la cita
    cursor.execute(
        """
        INSERT INTO citas (barbero_id, servicio_id, cliente_id, fecha, hora_inicio, hora_fin, estado, notas)
        VALUES (%s, %s, %s, %s, %s, %s, 'confirmada', %s);
        """,
        (
            cita.barbero_id,
            cita.servicio_id,
            cliente_id,
            cita.fecha,
            hora_inicio_str,
            hora_fin_str,
            cita.notas,
        ),
    )
    conn.commit()
    cita_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return {
        "mensaje": "Cita agendada",
        "cita_id": cita_id,
        "fecha": cita.fecha,
        "hora_inicio": hora_inicio_str,
        "hora_fin": hora_fin_str,
    }


@app.get("/citas")
def listar_citas():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            c.id,
            c.fecha,
            c.hora_inicio,
            c.hora_fin,
            c.estado,
            c.notas,
            b.nombre AS barbero,
            s.nombre AS servicio,
            cl.nombre AS cliente,
            cl.telefono
        FROM citas c
        JOIN barberos b ON c.barbero_id = b.id
        JOIN servicios s ON c.servicio_id = s.id
        JOIN clientes cl ON c.cliente_id = cl.id
        ORDER BY c.fecha, c.hora_inicio;
        """
    )
    datos = cursor.fetchall()
    cursor.close()
    conn.close()
    return datos

class EstadoCitaActualizar(BaseModel):
    estado: str  # Ej: "confirmada", "completada", "cancelada"


@app.patch("/citas/{cita_id}/estado")
def actualizar_estado_cita(cita_id: int, datos: EstadoCitaActualizar):
    estados_validos = {"confirmada", "completada", "cancelada"}
    nuevo_estado = datos.estado.lower().strip()

    if nuevo_estado not in estados_validos:
        return {
            "error": "Estado no válido. Usa: confirmada, completada o cancelada"
        }

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM citas WHERE id = %s;", (cita_id,))
    cita = cursor.fetchone()
    if not cita:
        cursor.close()
        conn.close()
        return {"error": "Cita no encontrada"}

    cursor.execute(
        "UPDATE citas SET estado = %s WHERE id = %s;",
        (nuevo_estado, cita_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "mensaje": "Estado actualizado",
        "cita_id": cita_id,
        "estado": nuevo_estado,
    }