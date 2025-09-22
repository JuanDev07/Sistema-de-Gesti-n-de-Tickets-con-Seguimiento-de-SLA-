# ----------------------------------------------------------------
# 1. IMPORTACIONES NECESARIAS
# ----------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from PIL import Image, ImageTk
import datetime
from decimal import Decimal
import pandas as pd
import pyodbc
import hashlib

# ----------------------------------------------------------------
# 2. FUNCIÓN DE CONEXIÓN A LA BASE DE DATOS
# ----------------------------------------------------------------
def get_db_connection():
    """Establece y devuelve una conexión a SQL Server usando Autenticación de Windows."""
    try:
        # --- ¡CONFIGURA ESTOS VALORES! ---
        # Usa el nombre EXACTO de tu driver ODBC. 'ODBC Driver 17 for SQL Server' o '18' son comunes.
        driver_name = '{ODBC Driver 17 for SQL Server}' 
        server_name = 'DESKTOP-5O72M0D'  # Ej: 'localhost', 'MI-PC\\SQLEXPRESS'
        database_name = 'APP_TRACK'     # El nombre de tu base de datos
        
        conn_str = (
            f'DRIVER={driver_name};'
            f'SERVER={server_name};'
            f'DATABASE={database_name};'
            f'Trusted_Connection=yes;'
            f'TrustServerCertificate=yes;' # Necesario para conexiones locales/de desarrollo
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        messagebox.showerror("Error de Conexión", f"No se pudo conectar a SQL Server: {e}")
        return None

# ----------------------------------------------------------------
# 3. LÓGICA DE NEGOCIO (BACKEND) - CLASE TaskTrackingSystem
# ----------------------------------------------------------------
class TaskTrackingSystem:
    def __init__(self):
        # Este diccionario puede permanecer en memoria ya que es configuración estática
        self.task_types = {
            "Gestión Creación de Usuario": 4,
            "Gestión de Implementación Dar de Baja BD": 8,
        }

    def _execute_query(self, query, params=(), fetch=None, is_commit=False):
        """Método privado para manejar la ejecución de consultas de forma segura."""
        conn = get_db_connection()
        if not conn:
            return None if fetch else False
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if is_commit:
                conn.commit()
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            return True
        except pyodbc.Error as e:
            messagebox.showerror("Error de Base de Datos", f"Ocurrió un error: {e}")
            return None if fetch else False
        finally:
            if conn:
                conn.close()

    def add_employee(self, employee_name):
        if not employee_name.strip():
            return False, "El nombre no puede estar vacío."
        
        query = "INSERT INTO empleados (nombre) VALUES (?)"
        try:
            success = self._execute_query(query, (employee_name,), is_commit=True)
            if success:
                return True, f"Empleado {employee_name} agregado."
            return False, "Fallo al agregar empleado."
        except pyodbc.IntegrityError: # Se maneja implícitamente en el _execute_query
             return False, f"El empleado {employee_name} ya existe."

    def get_employees(self):
        return self._execute_query("SELECT nombre FROM empleados ORDER BY nombre", fetch='all')

    def assign_ticket(self, ticket_number, employee_name, task_type, received_time):
        if not all([ticket_number, employee_name, task_type, received_time]):
            return False, "Todos los campos son requeridos."

        # 1. Obtener el ID del empleado
        employee_id_result = self._execute_query("SELECT id FROM empleados WHERE nombre = ?", (employee_name,), fetch='one')
        if not employee_id_result:
            return False, f"Empleado '{employee_name}' no encontrado."
        employee_id = employee_id_result[0]

        # 2. Calcular fecha de finalización esperada
        sla_hours = self.task_types.get(task_type, 0)
        expected_completion = received_time + datetime.timedelta(hours=sla_hours)

        # 3. Insertar el ticket
        sql = """
        INSERT INTO tickets (ticket_number, employee_id, task_type, received_time, expected_completion, status)
        VALUES (?, ?, ?, ?, ?, 'Open')
        """
        params = (ticket_number, employee_id, task_type, received_time, expected_completion)
        success = self._execute_query(sql, params, is_commit=True)
        if success:
            return True, f"Ticket {ticket_number} asignado."
        return False, "Fallo al asignar ticket (posiblemente el número de ticket ya existe)."

    def complete_ticket(self, ticket_number, completion_time):
        # Obtener ticket para calcular retraso
        ticket_query = """
        SELECT t.expected_completion FROM tickets t WHERE t.ticket_number = ?
        """
        ticket = self._execute_query(ticket_query, (ticket_number,), fetch='one')
        if not ticket:
            return False, "Ticket no encontrado."

        expected_completion = ticket[0]
        delay_hours = 0
        status = "Completed On Time"
        if completion_time > expected_completion:
            delay_seconds = (completion_time - expected_completion).total_seconds()
            delay_hours = round(delay_seconds / 3600, 2)
            status = "Completed Late"

        # Actualizar ticket
        sql = """
        UPDATE tickets 
        SET actual_completion = ?, status = ?, delay_hours = ? 
        WHERE ticket_number = ?
        """
        params = (completion_time, status, delay_hours, ticket_number)
        success = self._execute_query(sql, params, is_commit=True)
        if success:
            return True, f"Ticket {ticket_number} completado."
        return False, "Fallo al completar el ticket."

    def get_open_tickets(self):
        sql = "SELECT ticket_number FROM tickets WHERE status IN ('Open', 'Overdue') ORDER BY received_time"
        return self._execute_query(sql, fetch='all')

    def get_ticket_details(self, ticket_number):
        sql = """
        SELECT t.ticket_number, e.nombre, t.task_type, t.received_time, 
               t.expected_completion, t.status
        FROM tickets t JOIN empleados e ON t.employee_id = e.id
        WHERE t.ticket_number = ?
        """
        return self._execute_query(sql, (ticket_number,), fetch='one')
        
    def generate_report_data(self):
        # Actualizar estado de tickets a "Overdue" si aplica
        overdue_sql = "UPDATE tickets SET status = 'Overdue' WHERE status = 'Open' AND expected_completion < GETDATE()"
        self._execute_query(overdue_sql, is_commit=True)

        # Obtener datos para el reporte
        report_sql = """
        SELECT t.ticket_number, e.nombre, t.task_type, t.received_time, 
               t.expected_completion, t.actual_completion, t.status, t.delay_hours
        FROM tickets t JOIN empleados e ON t.employee_id = e.id
        ORDER BY t.received_time DESC
        """
        return self._execute_query(report_sql, fetch='all')
    
    def delete_ticket(self, ticket_number):
    # Borra un ticket específico de la base de datos.
        if not ticket_number:
            return False, "No se seleccionó ningún número de ticket."

        # La sentencia SQL DELETE es simple: borra de la tabla 'tickets'
        # donde el 'ticket_number' coincida [2][4][5].
        # La cláusula WHERE es CRUCIAL para no borrar toda la tabla.
        query = "DELETE FROM tickets WHERE ticket_number = ?"
    
        success = self._execute_query(query, (ticket_number,), is_commit=True)
    
        if success:
            return True, f"Ticket {ticket_number} borrado exitosamente."
        else:
            return False, f"Fallo al borrar el ticket {ticket_number}."

# ----------------------------------------------------------------
# 4. INTERFAZ GRÁFICA (FRONTEND) - CLASE TaskTrackingGUI
# ----------------------------------------------------------------
class TaskTrackingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Tracking System (SQL Server Edition)")
        self.root.geometry("950x700")
        self.root.minsize(950, 700)
        
        self.tracker = TaskTrackingSystem()
        
        self.setup_ui()
        self.initial_load()

    def setup_ui(self):
        # COPIA TU CÓDIGO DE UI (PESTAÑAS, BOTONES, ETC.) AQUÍ
        # He copiado la estructura de tu archivo `paste.txt` y la he adaptado
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.employee_tab = ttk.Frame(self.notebook)
        self.ticket_tab = ttk.Frame(self.notebook)
        self.complete_tab = ttk.Frame(self.notebook)
        self.report_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.employee_tab, text="Gestionar Empleados")
        self.notebook.add(self.ticket_tab, text="Asignar Tickets")
        self.notebook.add(self.complete_tab, text="Completar Tickets")
        self.notebook.add(self.report_tab, text="Reportes")

        self.setup_employee_tab()
        self.setup_ticket_tab()
        self.setup_complete_tab()
        self.setup_report_tab()

        # --- BOTONES Y BARRA DE ESTADO ---
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self.status_var = tk.StringVar(value="Listo")
        status_bar = ttk.Label(bottom_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # BOTÓN DE SALIR (FUNCIONAL)
        exit_btn = ttk.Button(bottom_frame, text="Salir", command=self.confirm_exit)
        exit_btn.pack(side=tk.RIGHT)
        
    def setup_employee_tab(self):
        # ... (El resto de la configuración de la UI es casi idéntica a tu código `paste.txt`)
        # Employee management frame
        employee_frame = ttk.LabelFrame(self.employee_tab, text="Añadir Empleado", padding=10)
        employee_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(employee_frame, text="Nombre:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.employee_name_entry = ttk.Entry(employee_frame, width=40)
        self.employee_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        add_btn = ttk.Button(employee_frame, text="Añadir Empleado", command=self.add_employee)
        add_btn.grid(row=0, column=2, padx=10, pady=5)
        
        # Employee list frame
        list_frame = ttk.LabelFrame(self.employee_tab, text="Lista de Empleados", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.employee_listbox = tk.Listbox(list_frame, height=15)
        self.employee_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def setup_ticket_tab(self):
        ticket_frame = ttk.LabelFrame(self.ticket_tab, text="Asignar Nuevo Ticket", padding=10)
        ticket_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ... (Aquí va toda la configuración de la pestaña de tickets de tu código)
        ttk.Label(ticket_frame, text="Número de Ticket:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.ticket_number_entry = ttk.Entry(ticket_frame, width=30)
        self.ticket_number_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(ticket_frame, text="Empleado:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.employee_combo = ttk.Combobox(ticket_frame, width=28, state="readonly")
        self.employee_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(ticket_frame, text="Tipo de Tarea:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.task_combo = ttk.Combobox(ticket_frame, width=28, state="readonly", values=list(self.tracker.task_types.keys()))
        self.task_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        if list(self.tracker.task_types.keys()): self.task_combo.current(0)
        
        ttk.Label(ticket_frame, text="Fecha Recibido:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.received_date = DateEntry(ticket_frame, width=12, date_pattern='y-mm-dd')
        self.received_date.grid(row=3, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(ticket_frame, text="Hora Recibido:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        time_frame = ttk.Frame(ticket_frame)
        time_frame.grid(row=4, column=1, padx=5, pady=2, sticky="w")

        # Variables para almacenar la hora y minuto seleccionados, inicializadas con la hora actual
        current_time = datetime.datetime.now()
        self.hour_var = tk.StringVar(value=current_time.strftime("%H"))
        self.minute_var = tk.StringVar(value=current_time.strftime("%M"))

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(60)]

        # Combobox para las horas
        hour_combo = ttk.Combobox(time_frame, textvariable=self.hour_var, values=hours, width=5, state="readonly")
        hour_combo.pack(side=tk.LEFT)

        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)

        # Combobox para los minutos
        minute_combo = ttk.Combobox(time_frame, textvariable=self.minute_var, values=minutes, width=5, state="readonly")
        minute_combo.pack(side=tk.LEFT)
        
        # ... (resto de UI)
        assign_btn = ttk.Button(ticket_frame, text="Asignar Ticket", command=self.assign_ticket)
        assign_btn.grid(row=5, column=1, pady=10, sticky="w")

    def _format_delay_hours(self, decimal_hours):
        # Si no hay retraso o el valor es nulo, devuelve 00:00:00
        if not decimal_hours or decimal_hours <= 0:
            return "00:00:00"

        # Convertir las horas decimales a segundos totales
        total_seconds = int(decimal_hours * 3600)
    
        # Usar divmod para separar los minutos de los segundos
        minutes, seconds = divmod(total_seconds, 60)
        # Usar divmod de nuevo para separar las horas de los minutos
        hours, minutes = divmod(minutes, 60)
    
        # Devolver la cadena formateada con ceros a la izquierda (ej: 01:05:09)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
  
    def setup_complete_tab(self):
        complete_frame = ttk.LabelFrame(self.complete_tab, text="Completar Ticket", padding=10)
        complete_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(complete_frame, text="Seleccionar Ticket:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.complete_ticket_combo = ttk.Combobox(complete_frame, width=30, state="readonly")
        self.complete_ticket_combo.grid(row=0, column=1, padx=5, pady=2)
        self.complete_ticket_combo.bind("<<ComboboxSelected>>", self.show_ticket_details)
        
        ttk.Label(complete_frame, text="Fecha Completado:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.completion_date = DateEntry(complete_frame, width=12, date_pattern='y-mm-dd')
        self.completion_date.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
    
        # Campos para la hora de finalización (NUEVO)
        ttk.Label(complete_frame, text="Hora Completado:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        complete_time_frame = ttk.Frame(complete_frame)
        complete_time_frame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        #Frame para agrupar los botones de acción
        action_buttons_frame = ttk.Frame(complete_frame)
        action_buttons_frame.grid(row=3, column=1, padx=5, pady=10, sticky=tk.W)
        
        complete_btn = ttk.Button(action_buttons_frame, text="Marcar como Completado", command=self.complete_ticket)
        complete_btn.pack(side=tk.LEFT)

        # BOTÓN PARA BORRAR
        delete_btn = ttk.Button(action_buttons_frame, text="Borrar Ticket", command=self.delete_selected_ticket, style="Danger.TButton")
        delete_btn.pack(side=tk.LEFT, padx=10)

        # Variables para almacenar la hora y minuto, inicializadas a la hora actual
        current_time = datetime.datetime.now()
        self.complete_hour_var = tk.StringVar(value=current_time.strftime("%H"))
        self.complete_minute_var = tk.StringVar(value=current_time.strftime("%M"))
    
        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(60)]
    
        # Menús desplegables para hora y minuto
        ttk.Combobox(complete_time_frame, textvariable=self.complete_hour_var, values=hours, width=5, state="readonly").pack(side=tk.LEFT)
        ttk.Label(complete_time_frame, text=":").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(complete_time_frame, textvariable=self.complete_minute_var, values=minutes, width=5, state="readonly").pack(side=tk.LEFT)
        
        detail_frame = ttk.LabelFrame(self.complete_tab, text="Detalles del Ticket", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.detail_text.pack(fill=tk.BOTH, expand=True)

    def setup_report_tab(self):
        control_frame = ttk.Frame(self.report_tab, padding=10)
        control_frame.pack(fill=tk.X)
        
        refresh_btn = ttk.Button(control_frame, text="Refrescar Reporte", command=self.refresh_report)
        refresh_btn.pack(side=tk.LEFT)
        
        # BOTÓN EXPORTAR/GUARDAR (FUNCIONAL)
        export_btn = ttk.Button(control_frame, text="Exportar a CSV", command=self.export_report)
        export_btn.pack(side=tk.LEFT, padx=10)

        report_frame = ttk.LabelFrame(self.report_tab, text="Reporte de Seguimiento", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("Ticket", "Empleado", "Tarea", "Recibido", "Esperado", "Completado", "Estado", "Retraso (h)")
        self.report_tree = ttk.Treeview(report_frame, columns=cols, show="headings")
        for col in cols:
            self.report_tree.heading(col, text=col)
        self.report_tree.pack(fill=tk.BOTH, expand=True)
        # Añadir scrollbars si se desea

    # --- MÉTODOS DE LÓGICA DE LA UI ---
    
    def initial_load(self):
        """Carga los datos iniciales de la BD al abrir la app."""
        self.refresh_employee_list()
        self.refresh_open_ticket_list()
        self.refresh_report()

    def add_employee(self):
        name = self.employee_name_entry.get()
        success, message = self.tracker.add_employee(name)
        if success:
            self.status_var.set(message)
            self.employee_name_entry.delete(0, tk.END)
            self.refresh_employee_list() # Actualiza las listas
        else:
            messagebox.showerror("Error", message)

    def assign_ticket(self):
        # Obtener valores de la UI
        ticket_num = self.ticket_number_entry.get()
        employee = self.employee_combo.get()
        task = self.task_combo.get()
        try:
            date_part = self.received_date.get_date()
            hour_part = int(self.hour_var.get())
            minute_part = int(self.minute_var.get())
        
            # Esta es la línea clave: combina la fecha con la hora
            received_time = datetime.datetime.combine(date_part, datetime.time(hour=hour_part, minute=minute_part))

        except (ValueError, TypeError):
            messagebox.showerror("Error", "Formato de fecha inválido.")
            return

        success, message = self.tracker.assign_ticket(ticket_num, employee, task, received_time)
        if success:
            self.status_var.set(message)
            # Limpiar campos
            self.ticket_number_entry.delete(0, tk.END)
            self.refresh_open_ticket_list() # Actualizar lista de tickets a completar
            self.refresh_report() # Actualizar reporte
        else:
            messagebox.showerror("Error", message)

    def complete_ticket(self):
        ticket_num = self.complete_ticket_combo.get()
        if not ticket_num:
            messagebox.showwarning("Aviso", "Por favor, seleccione un ticket.")
            return
        try:
            date_part = self.completion_date.get_date()
            hour_part = int(self.complete_hour_var.get())
            minute_part = int(self.complete_minute_var.get())
            completion_time = datetime.datetime.combine(date_part, datetime.time(hour=hour_part, minute=minute_part))

        except (ValueError, TypeError):
            messagebox.showerror("Error", "Formato de fecha inválido.")
            return
        
        success, message = self.tracker.complete_ticket(ticket_num, completion_time)
        if success:
            self.status_var.set(message)
            self.refresh_open_ticket_list()
            self.refresh_report()
            self.detail_text.config(state=tk.NORMAL)
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.config(state=tk.DISABLED)
        else:
            messagebox.showerror("Error", message)
    
    def delete_selected_ticket(self):
    #Borra el ticket seleccionado en el Combobox, con previa confirmación.
        selected_ticket = self.complete_ticket_combo.get()
        if not selected_ticket:
            messagebox.showwarning("Acción Requerida", "Por favor, seleccione un ticket para borrar.")
            return

        # --- Cuadro de diálogo de confirmación ---
        # Esto es crucial para evitar borrados accidentales.
        confirm = messagebox.askyesno(
        "Confirmar Borrado",
        f"¿Está seguro de que desea borrar permanentemente el ticket '{selected_ticket}'?\n\nEsta acción no se puede deshacer."
    )

        if not confirm:
        # Si el usuario hace clic en "No", no hacemos nada.
            self.status_var.set("Borrado cancelado por el usuario.")
            return
    
        # Si el usuario confirma, procedemos a llamar al backend.
        success, message = self.tracker.delete_ticket(selected_ticket)

        if success:
            self.status_var.set(message)
        
        # Limpiar la caja de detalles
            self.detail_text.config(state=tk.NORMAL)
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.config(state=tk.DISABLED)
        
        # Es VITAL refrescar las listas para que el ticket borrado desaparezca de la UI.
            self.refresh_open_ticket_list()
            self.refresh_report()
            messagebox.showinfo("Éxito", message)
        else:
            messagebox.showerror("Error", message)
    
    def refresh_employee_list(self):
        employees = self.tracker.get_employees()
        employee_names = [row[0] for row in employees] if employees else []
        
        # Actualizar Listbox
        self.employee_listbox.delete(0, tk.END)
        for name in employee_names:
            self.employee_listbox.insert(tk.END, name)

        # Actualizar Combobox de tickets
        self.employee_combo['values'] = employee_names
        if employee_names:
            self.employee_combo.current(0)

    def refresh_open_ticket_list(self):
        open_tickets_raw = self.tracker.get_open_tickets()
        open_tickets = [row[0] for row in open_tickets_raw] if open_tickets_raw else []
        self.complete_ticket_combo['values'] = open_tickets
        if open_tickets:
            self.complete_ticket_combo.set(open_tickets[0])
            self.show_ticket_details()
        else:
            self.complete_ticket_combo.set('')


    def show_ticket_details(self, event=None):
        ticket_num = self.complete_ticket_combo.get()
        if not ticket_num: return

        details_raw = self.tracker.get_ticket_details(ticket_num)
        if not details_raw: return

        # Formatear detalles
        details_text = (
            f"Ticket: {details_raw[0]}\n"
            f"Empleado: {details_raw[1]}\n"
            f"Tarea: {details_raw[2]}\n"
            f"Recibido: {details_raw[3].strftime('%Y-%m-%d %H:%M')}\n"
            f"Esperado: {details_raw[4].strftime('%Y-%m-%d %H:%M')}\n"
            f"Estado: {details_raw[5]}"
        )
        
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, details_text)
        self.detail_text.config(state=tk.DISABLED)

    def refresh_report(self):
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        
        report_data = self.tracker.generate_report_data()
        if report_data:
            for row in report_data:
                # Formatear fechas para una mejor visualización
                received = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'N/A'
                expected = row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else 'N/A'
                actual = row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else '---'
                self.report_tree.insert('', 'end', values=(row[0], row[1], row[2], received, expected, actual, row[6], row[7] or '0'))

            # Obtener el valor de delay_hours (índice 7)
            delay_decimal = row[7] 
            # Usar nuestra nueva función para formatearlo
            delay_formatted = self._format_delay_hours(delay_decimal)
            # --- FIN DE LA MODIFICACIÓN ---

            self.report_tree.insert('', 'end', values=(
                row[0],         # ticket_number
                row[1],         # employee_name
                row[2],         # task_type
                received,       # received_time (formateado)
                expected,       # expected_completion (formateado)
                actual,         # actual_completion (formateado)
                row[6],         # status
                delay_formatted # delay_hours (FORMATEADO)
            ))

    def export_report(self):
        """Función 'Save'. Exporta el reporte actual a un archivo CSV."""
        report_data_raw = self.tracker.generate_report_data()
        if not report_data_raw:
            messagebox.showinfo("Información", "No hay datos para exportar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
            title="Guardar reporte como..."
        )
        if not filepath:
            return # El usuario canceló

        cols = ["Ticket", "Empleado", "Tarea", "Recibido", "Esperado", "Completado", "Estado", "Retraso_Horas"]
        
        # --- Convertir datetime y Decimal a string/float ---
        cleaned_data = []
        for row in report_data_raw:
            new_row = []
            for value in row:
                if isinstance(value, datetime.datetime):
                    new_row.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                elif isinstance(value, Decimal):
                    new_row.append(float(value))
                else:
                    new_row.append(value)
            cleaned_data.append(new_row)


        try:
            df = pd.DataFrame(cleaned_data)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            self.status_var.set(f"Reporte guardado en {filepath}")
            messagebox.showinfo("Éxito", "Reporte exportado exitosamente.")
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo: {e}")

    def confirm_exit(self):
        """Función 'Exit'. Pide confirmación antes de cerrar."""
        if messagebox.askyesno("Salir", "¿Estás seguro de que quieres salir de la aplicación?"):
            self.root.destroy()

# ----------------------------------------------------------------
# 5. LÓGICA DE LOGIN (PUNTO DE ENTRADA)
# ----------------------------------------------------------------
def run_login():
    # Crea la ventana de login
    login_root = tk.Tk()
    login_root.title("Login TCS Beta")

    # Carga la imagen de fondo (ajusta el nombre a tu archivo real, p. ej. "login.png")
    bg_image = Image.open("logo.png")
    bg_photo = ImageTk.PhotoImage(bg_image)

    # Ajusta la ventana al tamaño de la imagen
    login_root.geometry(f"{bg_image.width}x{bg_image.height}")

    # Label para mostrar la imagen de fondo
    background_label = tk.Label(login_root, image=bg_photo)
    background_label.image = bg_photo  # Evita que Python la recolecte como basura
    background_label.place(x=0, y=0, relwidth=1, relheight=1)

    # ----------------------------------------------------------------------------
    # CAMPOS DE TEXTO (Entries) Y BOTÓN SOBRE LA IMAGEN, PLACEHOLDERS EN LOS ENTRY
    # ----------------------------------------------------------------------------
    def on_entry_click_user(event):
        if entry_user.get() == placeholder_user:
            entry_user.delete(0, "end")
            entry_user.config(fg="black")

    def on_focusout_user(event):
        if entry_user.get() == "":
            entry_user.insert(0, placeholder_user)
            entry_user.config(fg="grey")

    def on_entry_click_pass(event):
        if entry_pass.get() == placeholder_pass:
            entry_pass.delete(0, "end")
            entry_pass.config(fg="black", show="*")

    def on_focusout_pass(event):
        if entry_pass.get() == "":
            entry_pass.insert(0, placeholder_pass)
            entry_pass.config(fg="grey", show="")

    # Texto a usar como placeholder
    placeholder_user = "User Admin"
    placeholder_pass = "Password"

    # Campo "User Admin"
    entry_user = tk.Entry(login_root, font=("Helvetica", 12), fg="grey", bd=0, highlightthickness=0,relief=tk.FLAT)
    entry_user.insert(0, "User Admin")
    # Ajusta estas coordenadas y tamaños según tu imagen
    entry_user.place(x=154, y=225, width=229, height=30)
    entry_user.bind("<FocusIn>", on_entry_click_user)
    entry_user.bind("<FocusOut>", on_focusout_user)

    # Campo "Password"
    entry_pass = tk.Entry(login_root, font=("Helvetica", 12), show="*", fg="grey",bd=0, highlightthickness=0, relief=tk.FLAT)
    entry_pass.insert(0, "")  # Texto inicial (opcional)
    entry_pass.place(x=154, y=288, width=229, height=30)
    entry_pass.bind("<FocusIn>", on_entry_click_pass)
    entry_pass.bind("<FocusOut>", on_focusout_pass)

    # --- Función para validar login (CONECTADA A SQL SERVER) ---
    def validar_login():
        user = entry_user.get().strip()
        password = entry_pass.get().strip()
        
        # Ignorar la validación si los campos tienen el texto de placeholder
        if user == placeholder_user or password == placeholder_pass:
            messagebox.showerror("Login", "Por favor, ingrese sus credenciales.")
            return

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn: return
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM usuarios WHERE username = ?", (user,))
            result = cursor.fetchone()
        except pyodbc.Error as e:
            messagebox.showerror("Error de Consulta", f"Error al validar credenciales: {e}")
            result = None
        finally:
            conn.close()

        if result and result[0] == password_hash:
            messagebox.showinfo("Login", "¡Login Exitoso!")
            login_root.destroy()
            open_main_window()
        else:
            messagebox.showerror("Login", "Credenciales inválidas.")

    # --- Botón de Entrar ---
    btn_entrar = tk.Button(login_root, text="ENTRAR", font=("Helvetica", 10, "bold"),
                           bg="#1E1E1E", fg="white", highlightthickness=0,
                           relief=tk.FLAT, command=validar_login)
    btn_entrar.place(x=225, y=350, width=100, height=35)

    login_root.mainloop()

def open_main_window():
    """Abre la ventana principal de la aplicación."""
    # NOTA: Debes tener las clases TaskTrackingSystem y TaskTrackingGUI definidas en este mismo archivo.
    # Por brevedad, no las he vuelto a pegar, pero deben estar presentes para que esto funcione.
    main_root = tk.Tk()
    app = TaskTrackingGUI(main_root)
    main_root.protocol("WM_DELETE_WINDOW", app.confirm_exit)
    main_root.mainloop()

# ----------------------------------------------------------------
# 6. INICIO DE LA APLICACIÓN
# ----------------------------------------------------------------
if __name__ == "__main__":
    run_login()
