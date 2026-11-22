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
@app.on_event("startup")
def inicializar_bd():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS barberos (
          id INT AUTO_INCREMENT PRIMARY KEY,
          nombre VARCHAR(100) NOT NULL,
          especialidad VARCHAR(120) DEFAULT NULL,
          activo TINYINT(1) NOT NULL DEFAULT 1
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS horarios_barbero (
          id INT AUTO_INCREMENT PRIMARY KEY,
          barbero_id INT NOT NULL,
          dia_semana TINYINT NOT NULL,
          hora_inicio TIME NOT NULL,
          hora_fin TIME NOT NULL,
          CONSTRAINT fk_horario_barbero
            FOREIGN KEY (barbero_id) REFERENCES barberos(id)
            ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueos_horario (
          id INT AUTO_INCREMENT PRIMARY KEY,
          barbero_id INT NOT NULL,
          fecha DATE NOT NULL,
          hora_inicio TIME NOT NULL,
          hora_fin TIME NOT NULL,
          motivo VARCHAR(150) DEFAULT NULL,
          CONSTRAINT fk_bloqueo_barbero
            FOREIGN KEY (barbero_id) REFERENCES barberos(id)
            ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicios (
          id INT AUTO_INCREMENT PRIMARY KEY,
          nombre VARCHAR(100) NOT NULL,
          duracion_minutos INT NOT NULL,
          precio DECIMAL(10, 2) NOT NULL,
          activo TINYINT(1) NOT NULL DEFAULT 1
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
          id INT AUTO_INCREMENT PRIMARY KEY,
          nombre VARCHAR(100) NOT NULL,
          telefono VARCHAR(30) NOT NULL,
          correo VARCHAR(120) DEFAULT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS citas (
          id INT AUTO_INCREMENT PRIMARY KEY,
          barbero_id INT NOT NULL,
          servicio_id INT NOT NULL,
          cliente_id INT NOT NULL,
          fecha DATE NOT NULL,
          hora_inicio TIME NOT NULL,
          hora_fin TIME NOT NULL,
          estado VARCHAR(20) NOT NULL DEFAULT 'confirmada',
          notas VARCHAR(255) DEFAULT NULL,
          CONSTRAINT fk_cita_barbero
            FOREIGN KEY (barbero_id) REFERENCES barberos(id),
          CONSTRAINT fk_cita_servicio
            FOREIGN KEY (servicio_id) REFERENCES servicios(id),
          CONSTRAINT fk_cita_cliente
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM barberos;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO barberos (nombre, especialidad, activo) VALUES (%s, %s, %s);",
            [
                ("Carlos Vera", "Degradados y barba", 1),
                ("Mateo Mendoza", "Colorimetría y rayitos", 1),
                ("Pablo Murillo", "Degradados y barba", 1),
                ("Tony Quimis", "Colorimetría y rayitos", 1),
            ],
        )

    cursor.execute("SELECT COUNT(*) FROM servicios;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO servicios (nombre, duracion_minutos, precio, activo) VALUES (%s, %s, %s, %s);",
            [
                ("Corte clásico / fade", 30, 8.00, 1),
                ("Perfilado de barba", 20, 5.00, 1),
                ("Rayitos / iluminación", 60, 20.00, 1),
            ],
        )

    cursor.execute("SELECT COUNT(*) FROM horarios_barbero;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO horarios_barbero (barbero_id, dia_semana, hora_inicio, hora_fin) VALUES (%s, %s, %s, %s);",
            [
                (1, 0, "09:00:00", "19:00:00"),
                (1, 1, "09:00:00", "19:00:00"),
                (1, 2, "09:00:00", "19:00:00"),
                (1, 3, "09:00:00", "19:00:00"),
                (1, 4, "09:00:00", "19:00:00"),
                (1, 5, "09:00:00", "18:00:00"),
                (2, 0, "10:00:00", "19:00:00"),
                (2, 1, "10:00:00", "19:00:00"),
                (2, 2, "10:00:00", "19:00:00"),
                (2, 3, "10:00:00", "19:00:00"),
                (2, 4, "10:00:00", "19:00:00"),
                (2, 5, "10:00:00", "18:00:00"),
            ],
        )

    conn.commit()
    cursor.close()
    conn.close()
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
