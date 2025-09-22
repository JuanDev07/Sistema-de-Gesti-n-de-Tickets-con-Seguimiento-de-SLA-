# Sistema-de-Gesti-n-de-Tickets-con-Seguimiento-de-SLA-

Este proyecto consiste en el desarrollo de una aplicación para la **gestión de tickets de soporte**, con enfoque en el cumplimiento de los **Acuerdos de Nivel de Servicio (SLA)**.  
Incluye módulos de empleados, asignación de tickets, reportes y un dashboard de seguimiento en Power BI.  

---

## 🚀 Características principales  

- ✅ Gestión de empleados (crear, actualizar, eliminar).  
- ✅ Registro y asignación de tickets.  
- ✅ Seguimiento de SLA por estado de ticket y responsable.  
- ✅ Exportación de reportes en formato CSV.  
- ✅ Dashboard en Power BI para análisis visual.  

---

## 🛠️ Tecnologías utilizadas  

- **Backend:** Python (Flask).  
- **Base de datos:** SQL Server.  
- **Frontend:** HTML, CSS, JavaScript.  
- **Reportes y visualización:** Power BI.  
- **Otros:** Pandas, Numpy, PyODBC.  

---

## 📂 Estructura del proyecto  

```bash
📦 proyecto-ticketing
 ┣ 📂 src
 ┃ ┣ 📂 templates      # Archivos HTML
 ┃ ┣ 📂 static         # CSS, JS, imágenes
 ┃ ┣ app.py            # Archivo principal Flask
 ┃ ┣ config.py         # Configuración de la BD
 ┣ 📂 data
 ┃ ┣ script_db.sql     # Script para crear BD y tablas
 ┣ 📂 reports
 ┃ ┣ dashboard.pbix    # Dashboard Power BI
 ┃ ┣ ejemplo_reporte.csv
 ┣ requirements.txt    # Dependencias del proyecto
 ┣ README.md           # Documentación
