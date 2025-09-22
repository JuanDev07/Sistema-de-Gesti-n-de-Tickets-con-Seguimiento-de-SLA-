-- =========================================
-- Script de creación de la base de datos
-- Proyecto: Ticketing SLA Tracker
-- Base de datos: SQL Server
-- =========================================

-- 1. Crear la base de datos
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'TicketingDB')
BEGIN
    CREATE DATABASE TicketingDB;
END
GO

USE TicketingDB;
GO

-- 2. Tabla de usuarios
IF OBJECT_ID('usuarios', 'U') IS NOT NULL DROP TABLE usuarios;
CREATE TABLE usuarios (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre NVARCHAR(100) NOT NULL,
    username NVARCHAR(50) UNIQUE NOT NULL,
    password NVARCHAR(255) NOT NULL, -- se recomienda encriptar
    rol NVARCHAR(20) CHECK (rol IN ('admin', 'empleado', 'cliente')) DEFAULT 'empleado'
);
GO

-- 3. Tabla de tickets
IF OBJECT_ID('tickets', 'U') IS NOT NULL DROP TABLE tickets;
CREATE TABLE tickets (
    id INT IDENTITY(1,1) PRIMARY KEY,
    titulo NVARCHAR(200) NOT NULL,
    descripcion NVARCHAR(MAX),
    empleado_id INT NULL,
    fecha_recibido DATETIME NOT NULL,
    fecha_esperada DATETIME NOT NULL,
    fecha_completado DATETIME NULL,
    estado NVARCHAR(30) CHECK (estado IN ('Pendiente', 'En Progreso', 'Cerrado', 'Cerrado con retraso')) DEFAULT 'Pendiente',
    FOREIGN KEY (empleado_id) REFERENCES usuarios(id)
);
GO

-- 4. Tabla de historial de acciones
IF OBJECT_ID('historial', 'U') IS NOT NULL DROP TABLE historial;
CREATE TABLE historial (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ticket_id INT NOT NULL,
    usuario_id INT NOT NULL,
    accion NVARCHAR(200) NOT NULL,
    fecha DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);
GO

-- 5. Datos de ejemplo
INSERT INTO usuarios (nombre, username, password, rol) VALUES
(N'Julian', 'julian', '1234', 'empleado'),
(N'Alfredo Perez', 'alfredo', '1234', 'empleado'),
(N'Juan', 'juan', '1234', 'empleado');
GO

INSERT INTO tickets (titulo, descripcion, empleado_id, fecha_recibido, fecha_esperada, estado)
VALUES
(N'Error en login', N'El sistema no permite acceder con usuario válido', 1, GETDATE(), DATEADD(HOUR, 2, GETDATE()), 'Pendiente'),
(N'Falla en reporte', N'El reporte no exporta en CSV correctamente', 2, GETDATE(), DATEADD(HOUR, 5, GETDATE()), 'En Progreso');
GO
