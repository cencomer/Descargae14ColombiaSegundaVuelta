# E14 Colombia — Auditoría Electoral Automatizada

Herramienta open source para descargar y analizar los formularios E14 de la Registraduría Nacional de Colombia, con detección automática de números sobreescritos o alterados.

## ¿Qué es un E14?

El formulario E14 es el **Acta de Escrutinio de los Jurados de Votación** — el documento físico donde se registran los votos contados en cada mesa electoral. Es la fuente primaria de los resultados electorales en Colombia.

## ¿Qué hace esta herramienta?

1. **Descarga masiva** de formularios E14 desde el sitio de divulgación de la Registraduría
2. **Detección automática** de números sobreescritos o alterados en las celdas de votación
3. **Generación de informes** con la ubicación exacta de cada mesa sospechosa

---

## Instalación

### Requisitos
- Python 3.10+
- Google Chrome instalado
- Conexión a internet estable
- 500 MB de espacio libre (mínimo por municipio)

### Windows

```bash
# 1. Instalar Python (si no lo tienes)
# Descargar desde https://www.python.org/downloads/
# IMPORTANTE: marcar "Add Python to PATH" durante la instalación

# 2. Clonar el proyecto
git clone https://github.com/tu-usuario/e14-colombia.git
cd e14-colombia

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar navegador Chromium
playwright install chromium

# 5. Instalar Poppler (necesario para analizar PDFs)
winget install oschwartz10612.Poppler
# Reiniciar la terminal después de instalar Poppler
```

### Linux (Ubuntu/Debian)

```bash
# 1. Instalar Python y dependencias del sistema
sudo apt update
sudo apt install python3 python3-pip git poppler-utils

# 2. Instalar dependencias de Playwright para Linux
sudo apt install libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2

# 3. Clonar el proyecto
git clone https://github.com/tu-usuario/e14-colombia.git
cd e14-colombia

# 4. Instalar dependencias Python
pip3 install -r requirements.txt

# 5. Instalar navegador Chromium
playwright install chromium
```

### Linux (Fedora/RHEL)

```bash
# 1. Instalar Python y dependencias
sudo dnf install python3 python3-pip git poppler-utils

# 2. Clonar e instalar
git clone https://github.com/tu-usuario/e14-colombia.git
cd e14-colombia
pip3 install -r requirements.txt
playwright install chromium
# Si falla, instalar dependencias: playwright install-deps chromium
```

### macOS

```bash
# 1. Instalar Homebrew (si no lo tienes)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Instalar Python y Poppler
brew install python poppler

# 3. Clonar e instalar
git clone https://github.com/tu-usuario/e14-colombia.git
cd e14-colombia
pip3 install -r requirements.txt
playwright install chromium
```

### Verificar instalación
```bash
python descargar_e14_playwright.py --descubrir
```
Si se abre un navegador y carga la página de la Registraduría, todo está listo.

---

## Descargar por municipio

Necesitas el **código del departamento** y el **nombre del municipio** (sin tildes funciona).

```bash
# El Peñol, Antioquia
python descargar_e14_playwright.py --departamento 01 --municipio PENOL

# Carmen de Viboral, Antioquia
python descargar_e14_playwright.py --departamento 01 --municipio VIBORAL

# Guatapé, Antioquia
python descargar_e14_playwright.py --departamento 01 --municipio GUATAPE

# Medellín, Antioquia
python descargar_e14_playwright.py --departamento 01 --municipio MEDELLIN

# Barranquilla, Atlántico
python descargar_e14_playwright.py --departamento 03 --municipio BARRANQUILLA

# Cali, Valle del Cauca
python descargar_e14_playwright.py --departamento 31 --municipio CALI

# Bogotá
python descargar_e14_playwright.py --departamento 16 --municipio BOGOTA
```

### ¿Qué nombre uso para el municipio?

Usa parte del nombre sin tildes. El script busca coincidencia parcial:
- `PENOL` encuentra "196 — PEÑOL (100%)"
- `VIBORAL` encuentra "082 — CARMEN DE VIBORAL (100%)"
- `MEDELLIN` encuentra "001 — MEDELLIN (100%)"

---

## Descargar por departamento completo

Sin `--municipio` descarga TODOS los municipios del departamento, con todas sus zonas, puestos y mesas. Puede tomar horas.

```bash
# Todo Antioquia (125 municipios, ~15,800 mesas)
python descargar_e14_playwright.py --departamento 01

# Todo Atlántico (23 municipios, ~6,190 mesas)
python descargar_e14_playwright.py --departamento 03

# Bogotá D.C. (~17,000 mesas)
python descargar_e14_playwright.py --departamento 16

# Varios departamentos a la vez
python descargar_e14_playwright.py --departamento 01 03 16
```

### Tiempos estimados

| Municipio/Departamento | Mesas aprox. | Tiempo estimado |
|------------------------|-------------|-----------------|
| El Peñol | 54 | 2 minutos |
| Guatapé | 24 | 1 minuto |
| Carmen de Viboral | 141 | 5 minutos |
| Bello | ~1,000 | 40 minutos |
| Medellín | ~4,000 | 3 horas |
| Antioquia completo | ~15,800 | 12+ horas |

---

## Códigos de departamento

| Código | Departamento | Código | Departamento |
|--------|-------------|--------|-------------|
| 01 | Antioquia | 25 | Norte de Santander |
| 03 | Atlántico | 26 | Quindío |
| 05 | Bolívar | 27 | Santander |
| 07 | Boyacá | 28 | Sucre |
| 09 | Caldas | 29 | Tolima |
| 11 | Cauca | 31 | Valle del Cauca |
| 12 | Cesar | 40 | Arauca |
| 13 | Córdoba | 44 | Caquetá |
| 15 | Cundinamarca | 46 | Casanare |
| 16 | Bogotá D.C. | 48 | La Guajira |
| 17 | Chocó | 50 | Guainía |
| 19 | Huila | 52 | Meta |
| 21 | Magdalena | 54 | Guaviare |
| 23 | Nariño | 56 | San Andrés |
| 24 | Risaralda | 60 | Amazonas |
| 64 | Putumayo | 68 | Vaupés |
| 72 | Vichada | 88 | Consulados |

---

## Opciones avanzadas

```bash
# Cambiar carpeta de salida
python descargar_e14_playwright.py --departamento 01 --municipio PENOL --output ./mis_descargas

# Sin ventana del navegador (puede fallar con reCAPTCHA)
python descargar_e14_playwright.py --departamento 01 --municipio PENOL --headless

# Más lento (sitio congestionado)
python descargar_e14_playwright.py --departamento 01 --municipio PENOL --delay 3

# Más rápido (buena conexión)
python descargar_e14_playwright.py --departamento 01 --municipio PENOL --delay 1
```

---

## Estructura de salida

```
e14_descargas/
└── NOMBRE_MUNICIPIO/
    ├── informe.txt              ← Resumen: zonas, puestos, mesas
    └── Zona XX/
        └── NN - NOMBRE PUESTO/
            ├── E14_XXX_X_01_196_000_01_000_X_XXX.pdf    (Mesa 1)
            ├── mesa_2_E14_XXX...pdf                      (Mesa 2)
            ├── mesa_3_E14_XXX...pdf                      (Mesa 3)
            └── ...
```

El `informe.txt` de cada municipio:
```
INFORME E14 - PEÑOL
========================================
Departamento: ANTIOQUIA
Municipio:    196 — PEÑOL (100%)
Zonas:        1
Puestos:      1
Mesas:        54
Descargados:  54
Errores:      0
```

---

## Analizar alteraciones (experimental)

Detecta números sobreescritos en las celdas de votación usando Computer Vision.

```bash
# Analizar todos los PDFs descargados
python analizar_tachones.py

# Analizar un municipio
python analizar_tachones.py --municipio PENOL

# Ajustar sensibilidad (0-1, más alto = menos falsos positivos)
python analizar_tachones.py --umbral 0.5
```

Los PDFs sospechosos se copian a `e14_descargas/sospechosos/` con un informe detallado.

⚠️ **Estado:** Las coordenadas de las celdas requieren calibración por tipo de elección. Puede generar falsos positivos.

---

## Configuración de la elección

Editar `BASE_URL` en `descargar_e14_playwright.py`:

```python
# Segunda vuelta presidente 2026 (actual)
BASE_URL = "https://e14segundavueltapresidente.registraduria.gov.co"

# Primera vuelta presidente 2026
# BASE_URL = "https://divulgacione14presidente.registraduria.gov.co"
```

---

## Cómo funciona

### Descargador
1. Abre Chromium con Playwright
2. Navega al sitio de divulgación E14
3. Selecciona departamento → municipio → zona → puesto desde menús desplegables
4. Hace clic en "Consultar" y sube la paginación al máximo
5. Hace clic en el botón de descarga de cada mesa
6. Guarda el PDF y cierra el modal "Descarga Exitosa"
7. Genera `informe.txt` con el resumen del municipio

### Analizador
1. Convierte cada PDF a imagen (200 DPI)
2. Recorta las celdas de votación (posiciones fijas)
3. Mide densidad de tinta, grosor de trazo y fragmentos
4. Si supera el umbral → copia a `sospechosos/` con informe

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| El navegador no carga la página | El sitio puede estar caído. Intenta más tarde |
| Solo descargó 12 mesas | Ejecuta de nuevo, la paginación se ajusta automáticamente |
| El script se detuvo a la mitad | Vuelve a ejecutar. Los archivos existentes no se sobreescriben |
| reCAPTCHA bloqueó la descarga | No uses `--headless`. Espera unos minutos |
| `playwright not found` | `pip install playwright && playwright install chromium` |

---

## Ejemplo completo

```bash
# 1. Instalar
pip install -r requirements.txt
playwright install chromium

# 2. Descargar El Peñol
python descargar_e14_playwright.py --departamento 01 --municipio PENOL

# 3. Se abre Chrome, navega automáticamente, descarga 54 mesas
# 4. Resultado:
#    e14_descargas/PEÑOL/informe.txt
#    e14_descargas/PEÑOL/Zona 00/01 - I.E. LEON XIII/*.pdf
```

---

## Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/mejora`)
3. Commit tus cambios (`git commit -m 'Agrega mejora'`)
4. Push (`git push origin feature/mejora`)
5. Abre un Pull Request

### Ideas para contribuir
- [ ] Calibrar coordenadas de celdas para segunda vuelta
- [ ] OCR para extraer números y validar sumas automáticamente
- [ ] Ley de Benford sobre resultados extraídos
- [ ] Dashboard web para visualizar resultados
- [ ] Soporte para Senado, Cámara, alcaldías
- [ ] Paralelizar descargas con múltiples navegadores

**Busco personas interesadas en aportar con OCR, análisis estadístico, dashboards y mejoras al modelo de detección.** Escríbeme a contacto@cencomer.com.

---

## Licencia

MIT

## Autor

**Luis Cabezas**  
Estudiante UdeA — Diplomado en Inteligencia Artificial, MinTIC  
contacto@cencomer.com

## Disclaimer

Esta herramienta es para fines de auditoría ciudadana y transparencia electoral. Los resultados del análisis automático son indicativos y requieren verificación humana. No constituyen prueba de fraude por sí solos.
