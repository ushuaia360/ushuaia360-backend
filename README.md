# API Ushuaia360 Backend

API base construida con Quart (framework asíncrono para Python) con arquitectura modular.

## Estructura del Proyecto

```
ushuaia360-backend/
├── app.py                 # Aplicación principal y factory
├── config/                # Configuración
│   ├── __init__.py
│   └── settings.py        # Configuraciones de la app
├── routes/                # Rutas/Endpoints
│   ├── __init__.py        # Registro de blueprints
│   ├── health.py          # Health checks
│   └── api.py             # Rutas principales de la API
├── models/                # Modelos de datos
│   ├── __init__.py
│   ├── base.py            # Modelo base
│   └── example.py         # Modelo de ejemplo
├── services/              # Lógica de negocio
│   ├── __init__.py
│   └── example_service.py # Servicio de ejemplo
├── middleware/            # Middleware personalizado
│   ├── __init__.py
│   ├── request_handler.py # Manejo de requests
│   └── error_handler.py   # Manejo de errores
├── utils/                 # Utilidades
│   ├── __init__.py
│   ├── validators.py      # Validaciones
│   └── response.py        # Helpers de respuestas
├── requirements.txt       # Dependencias
└── README.md             # Este archivo
```

## Instalación

1. Crear un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno (opcional):
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

## Ejecución

### Desarrollo
```bash
python app.py
```

### Con hot-reload
```bash
quart --app app:app run --reload
```

La API estará disponible en `http://localhost:5000`

## Endpoints

- `GET /` - Endpoint raíz con información básica
- `GET /health` - Health check
- `GET /api/v1/status` - Estado de la API
- `GET /api/v1/example` - Endpoint de ejemplo

## Arquitectura

### Routes (Rutas)
Las rutas están organizadas en blueprints de Quart. Cada archivo en `routes/` representa un conjunto de endpoints relacionados.

### Models (Modelos)
Los modelos representan las entidades de datos. Todos heredan de `BaseModel` que proporciona métodos comunes como `to_dict()`.

### Services (Servicios)
Contienen la lógica de negocio. Los servicios se comunican con los modelos y proporcionan métodos reutilizables.

### Middleware
- **request_handler**: Maneja requests y respuestas (logging, headers de seguridad)
- **error_handler**: Maneja errores HTTP de forma centralizada

### Utils (Utilidades)
Funciones auxiliares para validación, respuestas HTTP, etc.

## Desarrollo

Para agregar nuevas funcionalidades:

1. **Nueva ruta**: Crear un archivo en `routes/` y registrarlo en `routes/__init__.py`
2. **Nuevo modelo**: Crear en `models/` heredando de `BaseModel`
3. **Nuevo servicio**: Crear en `services/` con la lógica de negocio
4. **Nueva utilidad**: Agregar funciones en `utils/`

## Configuración

Las configuraciones están en `config/settings.py`. Se pueden definir diferentes configuraciones para desarrollo, producción y testing.
