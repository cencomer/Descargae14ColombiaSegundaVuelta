"""
Descargador de E14 - Registraduría Nacional de Colombia
Elecciones Presidente y Vicepresidente 2026

Usa Playwright para:
- Interceptar TODAS las llamadas de red (descubrir API automáticamente)
- Navegar la SPA Angular como un usuario real
- Resolver reCAPTCHA invisible automáticamente
- Descargar PDFs/imágenes de los E14

Requisitos:
    pip install playwright
    playwright install chromium

Uso:
    python descargar_e14_playwright.py                        # Todos
    python descargar_e14_playwright.py --departamento 03      # Solo Atlántico
    python descargar_e14_playwright.py --headless             # Sin ventana
    python descargar_e14_playwright.py --descubrir            # Solo descubrir API
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("e14_playwright.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://e14segundavueltapresidente.registraduria.gov.co"

DEPARTAMENTOS = {
    "60": "AMAZONAS", "01": "ANTIOQUIA", "40": "ARAUCA",
    "03": "ATLANTICO", "16": "BOGOTA_DC", "05": "BOLIVAR",
    "07": "BOYACA", "09": "CALDAS", "44": "CAQUETA",
    "46": "CASANARE", "11": "CAUCA", "12": "CESAR",
    "17": "CHOCO", "88": "CONSULADOS", "13": "CORDOBA",
    "15": "CUNDINAMARCA", "50": "GUAINIA", "54": "GUAVIARE",
    "19": "HUILA", "48": "LA_GUAJIRA", "21": "MAGDALENA",
    "52": "META", "23": "NARINO", "25": "NORTE_DE_SANTANDER",
    "64": "PUTUMAYO", "26": "QUINDIO", "24": "RISARALDA",
    "56": "SAN_ANDRES", "27": "SANTANDER", "28": "SUCRE",
    "29": "TOLIMA", "31": "VALLE", "68": "VAUPES", "72": "VICHADA",
}


class E14PlaywrightScraper:
    """
    Scraper con Playwright que intercepta la red para descubrir
    la API y descargar los E14 automáticamente.
    """

    def __init__(self, output_dir="e14_descargas", headless=False, delay=1.5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.delay = delay
        self.api_calls = []        # Todas las llamadas API capturadas
        self.api_base = None       # Base URL de la API descubierta
        self.auth_token = None     # Token de autenticación
        self.e14_urls = []         # URLs de E14 encontradas
        self.stats = {"descargados": 0, "errores": 0, "omitidos": 0}

    async def interceptar_request(self, route):
        """Intercepta requests para capturar headers de auth."""
        request = route.request
        headers = request.headers
        # Capturar token de autorización
        if "authorization" in headers and not self.auth_token:
            self.auth_token = headers["authorization"]
            logger.info(f"  🔑 Token capturado: {self.auth_token[:60]}...")
        await route.continue_()

    def on_response(self, response):
        """Callback para capturar respuestas de la API."""
        url = response.url
        status = response.status
        content_type = response.headers.get("content-type", "")

        # Ignorar assets estáticos y servicios externos
        if any(ext in url for ext in [
            ".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".ico",
            ".woff", ".ttf", "fonts.", "/assets/", "/media/",
            "boomerang", "recaptcha", "cognito", "go-mpulse",
            "google.com", "amazonaws.com", "akamai"
        ]):
            return

        # Ignorar navegación de la SPA (mismas URLs del sitio)
        parsed = urlparse(url)
        if parsed.netloc == "divulgacione14presidente.registraduria.gov.co":
            if not parsed.path.startswith("/api"):
                # Es navegación interna de la SPA, no API
                return

        # Capturar llamadas a API de datos
        if status == 200 and ("json" in content_type or "/api/" in url):
            self.api_calls.append({
                "url": url,
                "status": status,
                "content_type": content_type,
            })
            logger.info(f"  📡 API: {url}")

        # Capturar URLs de E14 (PDF o imagen) - solo si es un archivo real
        if ("pdf" in content_type or ".pdf" in url) and "registraduria" in url:
            self.e14_urls.append(url)
            logger.info(f"  📄 PDF encontrado: {url}")

        if "boletin" in url.lower() and "registraduria" in url:
            self.e14_urls.append(url)
            logger.info(f"  📄 Boletín encontrado: {url}")

    async def iniciar(self):
        """Inicia el navegador Playwright."""
        from playwright.async_api import async_playwright
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self.page = await self.context.new_page()

        # Interceptar red
        self.page.on("response", self.on_response)

        # Ocultar webdriver
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)

        logger.info("✅ Navegador Playwright iniciado")

    async def cerrar(self):
        """Cierra el navegador."""
        if hasattr(self, "browser"):
            await self.browser.close()
        if hasattr(self, "pw"):
            await self.pw.stop()

    async def esperar_carga(self, timeout=30000):
        """Espera a que la página termine de cargar."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass
        await asyncio.sleep(self.delay)

    async def navegar_home(self):
        """Navega al home y espera la carga."""
        logger.info(f"🏠 Navegando a {BASE_URL}/home ...")
        await self.page.goto(f"{BASE_URL}/home", timeout=90000)
        await self.esperar_carga(timeout=60000)

        title = await self.page.title()
        logger.info(f"   Título: {title}")

        if "Visor Ciudadano" not in title:
            logger.error("❌ La página no cargó correctamente")
            return False

        logger.info("✅ Página cargada correctamente")
        return True

    async def obtener_departamentos(self):
        """Obtiene departamentos desde la página."""
        deptos = []
        links = await self.page.query_selector_all("a[href*='/departamento/']")
        for link in links:
            href = await link.get_attribute("href")
            texto = (await link.inner_text()).strip()
            if href and texto:
                cod = href.split("/departamento/")[-1].strip("/")
                deptos.append({"codigo": cod, "nombre": texto, "url": href})

        if not deptos:
            logger.info("  Usando lista predefinida de departamentos")
            for cod, nombre in DEPARTAMENTOS.items():
                deptos.append({
                    "codigo": cod, "nombre": nombre,
                    "url": f"{BASE_URL}/departamento/{cod}"
                })
        return deptos

    async def navegar_departamento(self, url):
        """Navega a un departamento."""
        await self.page.goto(url, timeout=90000)
        await self.esperar_carga(timeout=45000)
        await asyncio.sleep(2)  # Espera extra para que carguen los dropdowns

    async def abrir_dropdown_y_listar(self, placeholder):
        """Abre un dropdown por placeholder y retorna las opciones."""
        opciones = []
        try:
            input_el = self.page.locator(
                f"input[placeholder*='{placeholder}' i]"
            ).first
            if await input_el.count() == 0:
                return opciones

            await input_el.click()
            await asyncio.sleep(2)

            # Leer opciones del dropdown
            items = self.page.locator(".dropdown-list li p")
            count = await items.count()
            for i in range(count):
                texto = (await items.nth(i).inner_text()).strip()
                if texto:
                    opciones.append(texto)

            # Cerrar dropdown haciendo clic fuera
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.debug(f"  Error en dropdown '{placeholder}': {e}")
        return opciones

    async def seleccionar_opcion(self, placeholder, valor):
        """Selecciona una opción de un dropdown haciendo clic directo."""
        try:
            input_el = self.page.locator(
                f"input[placeholder*='{placeholder}' i]"
            ).first
            if await input_el.count() == 0:
                return False

            # Abrir el dropdown
            await input_el.click()
            await asyncio.sleep(2)

            # Buscar la opción y hacer clic directo
            items = self.page.locator(".dropdown-list li p")
            count = await items.count()
            for i in range(count):
                texto = (await items.nth(i).inner_text()).strip()
                if valor.upper() in texto.upper() or texto.upper() in valor.upper():
                    await items.nth(i).click()
                    await asyncio.sleep(1.5)
                    return True

            # No encontró coincidencia, cerrar dropdown
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            return False

        except Exception as e:
            logger.debug(f"  Error seleccionando '{valor}': {e}")
        return False

    async def clic_consultar(self):
        """Hace clic en el botón Consultar y sube la paginación al máximo."""
        try:
            btn = self.page.locator("text=Consultar").first
            if await btn.count() > 0:
                await btn.click()
                await self.esperar_carga(timeout=30000)

                # Cambiar paginación: clic en "12 por página" para mostrar más mesas
                try:
                    pag_btn = self.page.locator("text=12 por página").first
                    if await pag_btn.is_visible():
                        await pag_btn.click()
                        await asyncio.sleep(1)
                        # Seleccionar la opción más alta del dropdown
                        opciones_pag = self.page.locator(".dropdown-list li p")
                        count = await opciones_pag.count()
                        if count > 0:
                            await opciones_pag.nth(count - 1).click()
                            await asyncio.sleep(2)
                except Exception:
                    pass

                return True
        except Exception:
            pass
        return False

    async def descargar_e14_desde_pagina(self, dir_destino):
        """
        Descarga E14s haciendo clic en el botón de descarga de cada mesa.
        Cada mesa tiene un ícono de descarga (clase 'open-pdf').
        Después aparece un modal "Descarga Exitosa" que hay que cerrar.
        """
        descargados = 0
        dir_destino.mkdir(parents=True, exist_ok=True)

        # Contar botones de descarga disponibles
        dl_btns = self.page.locator(".open-pdf")
        total = await dl_btns.count()

        if total == 0:
            return 0

        logger.info(f"      📊 Mesas con botón descarga: {total}")

        for i in range(total):
            try:
                # Re-localizar los botones cada vez (el DOM puede cambiar tras el modal)
                dl_btns = self.page.locator(".open-pdf")
                current_count = await dl_btns.count()
                if i >= current_count:
                    break

                # Esperar el evento download al hacer clic
                async with self.page.expect_download(timeout=30000) as dl_info:
                    await dl_btns.nth(i).click()

                download = await dl_info.value
                # Guardar el archivo
                filename = download.suggested_filename or f"E14_mesa_{i+1}.pdf"
                archivo = dir_destino / filename
                # Si ya existe con ese nombre, agregar sufijo
                if archivo.exists():
                    archivo = dir_destino / f"mesa_{i+1}_{filename}"
                await download.save_as(str(archivo))
                descargados += 1
                self.stats["descargados"] += 1
                logger.info(f"    ✓ [{i+1}/{total}] {filename}")

                # Cerrar modal "Descarga Exitosa" -> clic en "Aceptar"
                try:
                    aceptar = self.page.locator("text=Aceptar").first
                    await aceptar.wait_for(state="visible", timeout=5000)
                    await aceptar.click()
                    await asyncio.sleep(1)
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"      Error mesa {i+1}: {e}")
                self.stats["errores"] += 1
                # Intentar cerrar modal si quedó abierto
                try:
                    aceptar = self.page.locator("text=Aceptar").first
                    if await aceptar.is_visible():
                        await aceptar.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

        return descargados

    async def _descargar_url(self, url, ruta_destino):
        """Descarga un archivo desde una URL usando el contexto del navegador."""
        try:
            ruta_destino.parent.mkdir(parents=True, exist_ok=True)
            response = await self.page.request.get(url)
            if response.status == 200:
                body = await response.body()
                if len(body) > 100:  # No guardar respuestas vacías
                    # Determinar extensión
                    ct = response.headers.get("content-type", "")
                    if "pdf" in ct or body[:4] == b"%PDF":
                        ruta_destino = ruta_destino.with_suffix(".pdf")
                    elif "png" in ct:
                        ruta_destino = ruta_destino.with_suffix(".png")
                    elif "jpeg" in ct or "jpg" in ct:
                        ruta_destino = ruta_destino.with_suffix(".jpg")

                    ruta_destino.write_bytes(body)
                    self.stats["descargados"] += 1
                    logger.info(f"    ✓ {ruta_destino.name} ({len(body)} bytes)")
                    return True
        except Exception as e:
            logger.debug(f"    Error descargando {url}: {e}")
            self.stats["errores"] += 1
        return False

    async def procesar_departamento(self, depto):
        """Procesa un departamento completo."""
        nombre = depto["nombre"]
        codigo = depto["codigo"]
        logger.info(f"\n{'='*60}")
        logger.info(f"📍 DEPARTAMENTO: {codigo} - {nombre}")
        logger.info(f"{'='*60}")

        dir_depto = self.output_dir / f"{codigo}_{nombre}"

        # Navegar al departamento
        url = depto["url"]
        if not url.startswith("http"):
            url = f"{BASE_URL}/departamento/{codigo}"
        await self.navegar_departamento(url)

        # Listar municipios
        municipios = await self.abrir_dropdown_y_listar("municipio")

        logger.info(f"  📋 Municipios: {len(municipios)}")

        if not municipios:
            logger.warning(f"  No se encontraron municipios para {nombre}")
            # Intentar descargar E14 directamente
            await self.descargar_e14_desde_pagina(dir_depto)
            return

        # Procesar cada municipio
        for mun in municipios:
            # Filtrar por municipio si se especificó
            if hasattr(self, 'municipio_filtro') and self.municipio_filtro:
                # Normalizar: quitar tildes y comparar sin acentos
                import unicodedata
                def normalizar(s):
                    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii').upper()
                if normalizar(self.municipio_filtro) not in normalizar(mun):
                    continue

            mun_safe = re.sub(r'[<>:"/\\|?*]', "_", mun)
            # Extraer solo el nombre del municipio (quitar código y porcentaje)
            # Formato: "196 — PEÑOL (100%)" → "PENOL"
            nombre_mun = mun.split("—")[-1].strip() if "—" in mun else mun
            nombre_mun = re.sub(r'\(.*?\)', '', nombre_mun).strip()
            nombre_mun = re.sub(r'[<>:"/\\|?*]', "_", nombre_mun)
            dir_mun = self.output_dir / nombre_mun
            logger.info(f"  🏘️  Municipio: {mun}")

            # Seleccionar municipio
            if not await self.seleccionar_opcion("municipio", mun):
                logger.warning(f"    No se pudo seleccionar {mun}")
                continue

            # Listar zonas
            zonas = await self.abrir_dropdown_y_listar("zona")

            # Informe del municipio
            total_puestos = 0
            total_mesas = 0

            if zonas:
                logger.info(f"    Zonas: {len(zonas)}")
                for zona in zonas:
                    zona_safe = re.sub(r'[<>:"/\\|?*]', "_", zona)
                    dir_zona = dir_mun / zona_safe

                    await self.seleccionar_opcion("zona", zona)

                    # Listar puestos
                    puestos = await self.abrir_dropdown_y_listar("puesto")

                    if puestos:
                        total_puestos += len(puestos)
                        logger.info(f"      Puestos: {len(puestos)}")
                        for puesto in puestos:
                            puesto_safe = re.sub(r'[<>:"/\\|?*]', "_", puesto)
                            dir_puesto = dir_zona / puesto_safe

                            await self.seleccionar_opcion("puesto", puesto)

                            # Clic en Consultar
                            await self.clic_consultar()

                            # Contar mesas disponibles
                            dl_btns = self.page.locator(".open-pdf")
                            mesas_puesto = await dl_btns.count()
                            total_mesas += mesas_puesto

                            # Descargar E14s
                            n = await self.descargar_e14_desde_pagina(dir_puesto)
                            if n == 0:
                                # Intentar navegar mesas individuales
                                await self._procesar_mesas(dir_puesto)

                            # Volver al departamento
                            await self.navegar_departamento(url)
                            # Re-seleccionar municipio y zona
                            await self.seleccionar_opcion("municipio", mun)
                            await self.seleccionar_opcion("zona", zona)
                    else:
                        # Sin puestos, intentar consultar directamente
                        await self.clic_consultar()
                        await self.descargar_e14_desde_pagina(dir_zona)
                        await self.navegar_departamento(url)
                        await self.seleccionar_opcion("municipio", mun)
            else:
                # Sin zonas, intentar consultar directamente
                await self.clic_consultar()
                n = await self.descargar_e14_desde_pagina(dir_mun)
                if n == 0:
                    await self._procesar_mesas(dir_mun)

            # Informe final del municipio
            logger.info(f"\n  📊 INFORME {nombre_mun}:")
            logger.info(f"     Zonas:  {len(zonas) if zonas else 0}")
            logger.info(f"     Puestos: {total_puestos}")
            logger.info(f"     Mesas:   {total_mesas}")
            logger.info(f"     Descargados: {self.stats['descargados']}")

            # Guardar informe como txt en la carpeta del municipio
            informe_path = dir_mun / "informe.txt"
            dir_mun.mkdir(parents=True, exist_ok=True)
            with open(informe_path, "w", encoding="utf-8") as f:
                f.write(f"INFORME E14 - {nombre_mun}\n")
                f.write(f"{'='*40}\n")
                f.write(f"Departamento: {nombre}\n")
                f.write(f"Municipio:    {mun}\n")
                f.write(f"Zonas:        {len(zonas) if zonas else 0}\n")
                f.write(f"Puestos:      {total_puestos}\n")
                f.write(f"Mesas:        {total_mesas}\n")
                f.write(f"Descargados:  {self.stats['descargados']}\n")
                f.write(f"Errores:      {self.stats['errores']}\n")
                f.write(f"\nDetalle:\n")
                if zonas:
                    for zona in zonas:
                        f.write(f"  {zona}\n")

            # Volver al departamento para el siguiente municipio
            await self.navegar_departamento(url)

    async def _procesar_mesas(self, dir_destino):
        """Busca y procesa mesas individuales en la página actual."""
        # Buscar tabla o lista de mesas
        mesas = await self.page.query_selector_all(
            "tr[class*='mesa'], [class*='mesa-row'], "
            "a[href*='mesa'], [class*='table'] tr"
        )
        if not mesas:
            return

        logger.info(f"      📊 Mesas encontradas: {len(mesas)}")
        for i, mesa in enumerate(mesas):
            try:
                # Intentar clic en la mesa para ver el E14
                await mesa.click()
                await asyncio.sleep(2)
                await self.descargar_e14_desde_pagina(
                    dir_destino / f"mesa_{i+1}"
                )
                await self.page.go_back()
                await asyncio.sleep(1)
            except Exception:
                continue

    async def descubrir_api(self):
        """
        Modo descubrimiento: navega el sitio capturando todas las
        llamadas de API para documentar los endpoints.
        """
        logger.info("🔍 MODO DESCUBRIMIENTO DE API")
        logger.info("=" * 60)

        await self.iniciar()

        try:
            if not await self.navegar_home():
                return

            logger.info(f"\n  APIs capturadas en home: {len(self.api_calls)}")
            for call in self.api_calls:
                logger.info(f"    {call['url']}")

            # Navegar a un departamento
            logger.info("\n  Navegando a departamento 03 (Atlántico)...")
            self.api_calls.clear()
            await self.navegar_departamento(f"{BASE_URL}/departamento/03")

            logger.info(f"\n  APIs capturadas en departamento: {len(self.api_calls)}")
            for call in self.api_calls:
                logger.info(f"    {call['url']}")

            # Intentar seleccionar un municipio
            municipios = await self.abrir_dropdown_y_listar("municipio")
            logger.info(f"\n  Municipios encontrados: {len(municipios)}")
            if municipios:
                logger.info(f"    Primeros 5: {municipios[:5]}")

            if municipios:
                self.api_calls.clear()
                await self.seleccionar_opcion("Municipio", municipios[0])
                logger.info(f"\n  APIs tras seleccionar municipio: {len(self.api_calls)}")
                for call in self.api_calls:
                    logger.info(f"    {call['url']}")

                # Intentar zonas
                zonas = await self.abrir_dropdown_y_listar("Zona")
                logger.info(f"\n  Zonas encontradas: {len(zonas)}")
                if zonas:
                    logger.info(f"    Primeras 5: {zonas[:5]}")
                    self.api_calls.clear()
                    await self.seleccionar_opcion("Zona", zonas[0])
                    logger.info(f"\n  APIs tras seleccionar zona: {len(self.api_calls)}")
                    for call in self.api_calls:
                        logger.info(f"    {call['url']}")

                    # Puestos
                    puestos = await self.abrir_dropdown_y_listar("Puesto")
                    logger.info(f"\n  Puestos encontrados: {len(puestos)}")
                    if puestos:
                        logger.info(f"    Primeros 5: {puestos[:5]}")
                        self.api_calls.clear()
                        await self.seleccionar_opcion("Puesto", puestos[0])

                        # Consultar
                        self.api_calls.clear()
                        self.e14_urls.clear()
                        await self.clic_consultar()

                        logger.info(f"\n  APIs tras Consultar: {len(self.api_calls)}")
                        for call in self.api_calls:
                            logger.info(f"    {call['url']}")

                        logger.info(f"\n  E14 URLs encontradas: {len(self.e14_urls)}")
                        for url in self.e14_urls:
                            logger.info(f"    📄 {url}")

                        # Guardar screenshot
                        await self.page.screenshot(
                            path=str(self.output_dir / "screenshot_resultado.png")
                        )
                        logger.info("  📸 Screenshot guardado")

            # Resumen
            logger.info(f"\n{'='*60}")
            logger.info("RESUMEN DE DESCUBRIMIENTO")
            logger.info(f"{'='*60}")
            logger.info(f"  Token de auth: {'Sí' if self.auth_token else 'No'}")
            logger.info(f"  Total APIs capturadas: {len(self.api_calls)}")
            logger.info(f"  E14 URLs: {len(self.e14_urls)}")

        finally:
            await self.cerrar()

    async def ejecutar(self, departamentos_filtro=None):
        """Ejecuta el proceso completo de descarga."""
        logger.info("=" * 60)
        logger.info("📥 DESCARGADOR DE E14 - Playwright")
        logger.info("   Registraduría Nacional - Presidente 2026")
        logger.info("=" * 60)
        logger.info(f"   Carpeta: {self.output_dir.resolve()}")
        logger.info(f"   Headless: {self.headless}")
        logger.info("")

        await self.iniciar()

        try:
            # Cargar home
            if not await self.navegar_home():
                logger.error("No se pudo cargar el sitio")
                return

            # Obtener departamentos
            deptos = await self.obtener_departamentos()
            logger.info(f"📋 Departamentos: {len(deptos)}")

            # Filtrar
            if departamentos_filtro:
                deptos = [d for d in deptos if d["codigo"] in departamentos_filtro]
                logger.info(f"   Filtrados: {len(deptos)}")

            # Procesar
            for depto in deptos:
                try:
                    await self.procesar_departamento(depto)
                except Exception as e:
                    logger.error(f"Error en {depto['nombre']}: {e}")
                    continue

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
        finally:
            # Resumen
            logger.info(f"\n{'='*60}")
            logger.info("📊 RESUMEN")
            logger.info(f"{'='*60}")
            logger.info(f"   ✅ Descargados: {self.stats['descargados']}")
            logger.info(f"   ❌ Errores:     {self.stats['errores']}")
            logger.info(f"   ⏭️  Omitidos:    {self.stats['omitidos']}")
            logger.info(f"   📁 Carpeta:     {self.output_dir.resolve()}")
            logger.info(f"   🔑 Token:       {'Sí' if self.auth_token else 'No'}")
            logger.info(f"   📡 APIs vistas: {len(self.api_calls)}")
            logger.info(f"{'='*60}")

            await self.cerrar()


# =============================================================================
# MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Descargador de E14 con Playwright - Registraduría Nacional",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python descargar_e14_playwright.py                       # Todos
  python descargar_e14_playwright.py --departamento 03     # Atlántico
  python descargar_e14_playwright.py --departamento 16     # Bogotá
  python descargar_e14_playwright.py --descubrir           # Solo descubrir API
  python descargar_e14_playwright.py --headless            # Sin ventana
  python descargar_e14_playwright.py --delay 3             # Más lento
        """,
    )
    parser.add_argument(
        "--departamento", "-d", nargs="+",
        help="Código(s) de departamento"
    )
    parser.add_argument(
        "--municipio", "-m",
        help="Filtrar por nombre de municipio (ej: 'PEÑOL', 'MEDELLIN')"
    )
    parser.add_argument(
        "--output", "-o", default="e14_descargas",
        help="Carpeta de salida"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Sin ventana visible"
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Pausa entre acciones (segundos)"
    )
    parser.add_argument(
        "--descubrir", action="store_true",
        help="Solo descubrir endpoints de la API"
    )

    args = parser.parse_args()

    scraper = E14PlaywrightScraper(
        output_dir=args.output,
        headless=args.headless,
        delay=args.delay,
    )
    scraper.municipio_filtro = args.municipio

    if args.descubrir:
        asyncio.run(scraper.descubrir_api())
    else:
        asyncio.run(scraper.ejecutar(departamentos_filtro=args.departamento))


if __name__ == "__main__":
    main()
