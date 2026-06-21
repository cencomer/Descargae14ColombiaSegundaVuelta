"""
Analizador de tachones/enmendaduras en formularios E14.

Recorre los PDFs descargados, analiza las celdas de votación
usando Computer Vision, y genera:
- Carpeta 'sospechosos/' con copias de los PDFs con problemas
- Informe detallado con ubicación de cada mesa sospechosa

Uso:
    python analizar_tachones.py                          # Analiza todo
    python analizar_tachones.py --municipio PENOL        # Solo un municipio
    python analizar_tachones.py --umbral 0.3             # Ajustar sensibilidad
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from pdf2image import convert_from_path

# Configuración
INPUT_DIR = Path("e14_descargas")
OUTPUT_DIR = Path("e14_descargas/sospechosos")

# Coordenadas relativas de las celdas de VOTACIÓN (solo los números a la derecha)
# Formato: (y_start%, y_end%, x_start%, x_end%)
# Estas apuntan solo a la columna de números manuscritos
CELDAS_PAG1 = {
    "total_votantes_e11": (0.195, 0.218, 0.82, 0.97),
    "total_votos_urna": (0.218, 0.245, 0.82, 0.97),
    "total_incinerados": (0.245, 0.270, 0.82, 0.97),
    "candidato_1": (0.325, 0.385, 0.82, 0.97),
    "candidato_2": (0.395, 0.455, 0.82, 0.97),
    "candidato_3": (0.460, 0.520, 0.82, 0.97),
    "candidato_4": (0.530, 0.590, 0.82, 0.97),
    "candidato_5": (0.600, 0.660, 0.82, 0.97),
    "candidato_6": (0.670, 0.730, 0.82, 0.97),
    "candidato_7": (0.740, 0.800, 0.82, 0.97),
}

CELDAS_PAG2 = {
    "candidato_8": (0.10, 0.19, 0.82, 0.97),
    "candidato_9": (0.19, 0.28, 0.82, 0.97),
    "candidato_10": (0.28, 0.37, 0.82, 0.97),
    "candidato_11": (0.37, 0.46, 0.82, 0.97),
    "candidato_12": (0.46, 0.55, 0.82, 0.97),
    "candidato_13": (0.55, 0.64, 0.82, 0.97),
    "votos_blanco": (0.67, 0.71, 0.82, 0.97),
    "votos_nulos": (0.71, 0.75, 0.82, 0.97),
    "votos_no_marcados": (0.75, 0.79, 0.82, 0.97),
}


def extraer_celda(img, coords):
    """Extrae una celda de la imagen usando coordenadas relativas."""
    h, w = img.shape[:2]
    y1 = int(coords[0] * h)
    y2 = int(coords[1] * h)
    x1 = int(coords[2] * w)
    x2 = int(coords[3] * w)
    return img[y1:y2, x1:x2]


def detectar_tachon(celda_img, umbral_densidad=0.20):
    """
    Detecta números sobreescritos o alterados en una celda de votación.
    
    Un número sobreescrito tiene:
    - Densidad de tinta mayor a un dígito normal (>0.18 por dígito)
    - Grosor de trazo irregular (partes gruesas donde se superponen dos números)
    - Más intersecciones/esqueleto complejo que un dígito limpio
    
    Dígito limpio: densidad ~0.04-0.12, trazo uniforme
    Número sobreescrito: densidad >0.18, trazo grueso/irregular
    
    Retorna:
        score: float de 0 (limpio) a 1 (alterado evidente)
        detalle: dict con las métricas
    """
    if celda_img is None or celda_img.size == 0:
        return 0.0, {}

    if len(celda_img.shape) == 3:
        gray = cv2.cvtColor(celda_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = celda_img

    _, binary = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)

    # Métrica 1: Densidad total de tinta
    densidad = np.sum(binary > 0) / binary.size

    # Métrica 2: Grosor promedio del trazo
    # Esqueletizar y comparar con original — si el ratio es alto, trazo grueso
    skeleton = cv2.ximgproc.thinning(binary) if hasattr(cv2, 'ximgproc') else binary
    pixels_esqueleto = max(np.sum(skeleton > 0), 1)
    pixels_original = max(np.sum(binary > 0), 1)
    grosor_promedio = pixels_original / pixels_esqueleto

    # Métrica 3: Número de componentes conexos (sobreescritura crea fragmentos)
    num_labels, _ = cv2.connectedComponents(binary)

    # Score
    score = 0.0

    # Densidad muy alta para una celda de números = sobreescritura
    if densidad > 0.22:
        score += 0.5
    elif densidad > 0.16:
        score += 0.2

    # Trazo demasiado grueso (normal ~2-4px, sobreescrito ~5-8px)
    if grosor_promedio > 5.0:
        score += 0.3
    elif grosor_promedio > 4.0:
        score += 0.15

    # Muchos fragmentos = trazo irregular/sobreescrito
    if num_labels > 12:
        score += 0.2

    detalle = {
        "densidad": round(densidad, 4),
        "grosor": round(grosor_promedio, 2),
        "fragmentos": num_labels,
    }

    return min(score, 1.0), detalle


def analizar_pdf(pdf_path, umbral=0.4):
    """
    Analiza un PDF E14 completo.
    
    Retorna:
        es_sospechoso: bool
        celdas_problemas: list de dicts con detalle de cada celda con tachón
    """
    celdas_problemas = []

    try:
        poppler_path = r"C:\Users\luisc\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"
        pages = convert_from_path(str(pdf_path), dpi=200, poppler_path=poppler_path)
    except Exception as e:
        print(f"    Error convirtiendo {pdf_path.name}: {e}")
        return False, []

    # Analizar página 1
    if len(pages) >= 1:
        img1 = np.array(pages[0])
        for nombre, coords in CELDAS_PAG1.items():
            celda = extraer_celda(img1, coords)
            score, detalle = detectar_tachon(celda)
            if score >= umbral:
                celdas_problemas.append({
                    "celda": nombre,
                    "pagina": 1,
                    "score": round(score, 3),
                    **detalle,
                })

    # Analizar página 2
    if len(pages) >= 2:
        img2 = np.array(pages[1])
        for nombre, coords in CELDAS_PAG2.items():
            celda = extraer_celda(img2, coords)
            score, detalle = detectar_tachon(celda)
            if score >= umbral:
                celdas_problemas.append({
                    "celda": nombre,
                    "pagina": 2,
                    "score": round(score, 3),
                    **detalle,
                })

    es_sospechoso = len(celdas_problemas) > 0
    return es_sospechoso, celdas_problemas


def obtener_info_mesa(pdf_path):
    """Extrae municipio, zona, puesto y mesa del path del archivo."""
    parts = pdf_path.relative_to(INPUT_DIR).parts
    municipio = parts[0] if len(parts) > 0 else "?"
    zona = parts[1] if len(parts) > 1 else "?"
    puesto = parts[2] if len(parts) > 2 else "?"
    archivo = parts[-1]
    return {
        "municipio": municipio,
        "zona": zona,
        "puesto": puesto,
        "archivo": archivo,
    }


def main():
    parser = argparse.ArgumentParser(description="Analizar tachones en E14")
    parser.add_argument("--municipio", "-m", help="Filtrar por municipio")
    parser.add_argument("--umbral", "-u", type=float, default=0.4,
                        help="Umbral de score para marcar como sospechoso (0-1, default: 0.4)")
    args = parser.parse_args()

    # Crear carpeta de sospechosos
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Buscar PDFs
    pdfs = sorted(INPUT_DIR.rglob("*.pdf"))
    if args.municipio:
        import unicodedata
        def normalizar(s):
            return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii').upper()
        filtro = normalizar(args.municipio)
        pdfs = [p for p in pdfs if filtro in normalizar(str(p))]

    # Excluir carpeta sospechosos
    pdfs = [p for p in pdfs if "sospechosos" not in str(p)]

    print(f"{'='*60}")
    print(f"ANÁLISIS DE TACHONES - E14")
    print(f"{'='*60}")
    print(f"PDFs a analizar: {len(pdfs)}")
    print(f"Umbral: {args.umbral}")
    print(f"Salida: {OUTPUT_DIR.resolve()}")
    print()

    sospechosos = []
    total_analizados = 0

    for i, pdf in enumerate(pdfs):
        info = obtener_info_mesa(pdf)
        print(f"  [{i+1}/{len(pdfs)}] {info['municipio']} / {info['archivo']}", end="")

        es_sospechoso, problemas = analizar_pdf(pdf, umbral=args.umbral)
        total_analizados += 1

        if es_sospechoso:
            print(f"  ** ALTERADO ({len(problemas)} celdas)")
            sospechosos.append({"path": pdf, "info": info, "problemas": problemas})

            # Copiar PDF a carpeta sospechosos
            nombre_copia = f"{info['municipio']}_{info['archivo']}"
            destino = OUTPUT_DIR / nombre_copia
            shutil.copy2(pdf, destino)
        else:
            print(f"  OK")

    # Generar informe
    print(f"\n{'='*60}")
    print(f"RESUMEN")
    print(f"{'='*60}")
    print(f"  Analizados:   {total_analizados}")
    print(f"  Sospechosos:  {len(sospechosos)}")
    print(f"  Limpios:      {total_analizados - len(sospechosos)}")
    print(f"  % sospechoso: {100*len(sospechosos)/max(total_analizados,1):.1f}%")

    # Escribir informe detallado
    informe_path = OUTPUT_DIR / "informe_sospechosos.txt"
    with open(informe_path, "w", encoding="utf-8") as f:
        f.write(f"INFORME DE TACHONES/ENMENDADURAS - E14\n")
        f.write(f"{'='*50}\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Analizados: {total_analizados}\n")
        f.write(f"Sospechosos: {len(sospechosos)}\n")
        f.write(f"Umbral: {args.umbral}\n\n")

        if sospechosos:
            f.write(f"{'='*50}\n")
            f.write(f"DETALLE DE MESAS SOSPECHOSAS\n")
            f.write(f"{'='*50}\n\n")

            for s in sospechosos:
                info = s["info"]
                f.write(f"Municipio: {info['municipio']}\n")
                f.write(f"Zona:      {info['zona']}\n")
                f.write(f"Puesto:    {info['puesto']}\n")
                f.write(f"Archivo:   {info['archivo']}\n")
                f.write(f"Celdas con tachón:\n")
                for p in s["problemas"]:
                    f.write(f"  - {p['celda']} (pag {p['pagina']}) "
                            f"score={p['score']} densidad={p['densidad']} "
                            f"grosor={p.get('grosor','?')} fragmentos={p.get('fragmentos','?')}\n")
                f.write(f"\n")
        else:
            f.write("No se encontraron mesas sospechosas.\n")

    print(f"\n  Informe: {informe_path.resolve()}")
    print(f"  Copias:  {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
