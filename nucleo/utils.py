# nucleo/utils.py
print("--- ESTOY EJECUTANDO LA VERSIÓN MEJORADA Y FUSIONADA DE UTILS.PY ---")

import re
import os
from datetime import date
from PIL import Image
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from skimage.transform import rotate
from skimage.color import rgb2gray
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks

# Importamos los modelos para buscar los IDs
from .models import TipoTramite, CalidadPeticionario

# --- IMPORTANTE: Configura las rutas a Tesseract y Poppler ---
# Es una buena práctica tener esto configurable, por ejemplo, desde settings.py
PYTESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
POPPLER_PATH = r'C:\poppler\Library\bin'

def determine_skew(image_array):
    """
    Función auxiliar MEJORADA para determinar el ángulo de inclinación de una imagen.
    Usa la mediana para ser más robusto frente a líneas irrelevantes.
    """
    edges = canny(image_array, sigma=3.0)
    h, a, d = hough_line(edges)
    _, angles, _ = hough_line_peaks(h, a, d)
    
    if not np.any(angles): # Revisa si el array de ángulos está vacío
        return 0.0

    # Convertir a grados y filtrar ángulos extremos para evitar correcciones exageradas
    angles_deg = np.rad2deg(angles)
    angles_deg = angles_deg[(angles_deg > -45) & (angles_deg < 45)]

    if not np.any(angles_deg):
        return 0.0

    # La mediana es más robusta que la media para este caso
    return np.median(angles_deg)


def extraer_datos_de_pdf(pdf_bytes, pdf_filename=""):
    """
    Función central que recibe los bytes de un PDF, ejecuta OCR y extrae todos los datos.
    Devuelve un diccionario con la información encontrada.
    """
    datos = {
        'radicado': None,
        'asunto': None,
        'peticionario_nombre': None,
        'email': None,
        'fecha_recepcion_inicial': date.today(), # Valor por defecto
        'calidad_peticionario_id': None,
        'tipo_tramite_id': None,
    }

    try:
        pytesseract.pytesseract.tesseract_cmd = PYTESSERACT_PATH

        imagenes = convert_from_bytes(pdf_bytes, poppler_path=POPPLER_PATH)
        texto_completo = ""
        for imagen_original in imagenes:
            imagen_gris = rgb2gray(np.array(imagen_original))
            angulo = determine_skew(imagen_gris)
            imagen_corregida_array = rotate(np.array(imagen_original), angulo, resize=True) * 255
            imagen_corregida_pil = Image.fromarray(imagen_corregida_array.astype(np.uint8))
            texto_completo += pytesseract.image_to_string(imagen_corregida_pil, lang='spa') + "\n"
        
        # --- LÓGICA DE EXTRACCIÓN MEJORADA ---
        
        match_radicado = re.search(r"VU\s*(\d+)", texto_completo, re.IGNORECASE)
        if match_radicado:
            datos['radicado'] = "VU-" + match_radicado.group(1).strip()

        match_asunto = re.search(r"Cordial saludo,([\s\S]+?)(?=Por lo anterior|Es preciso)", texto_completo, re.IGNORECASE)
        asunto_extraido = " ".join(match_asunto.group(1).strip().split()) if match_asunto else ""

        # --- Búsqueda de Peticionario (se mantiene igual) ---
        if asunto_extraido:
            patron_a = r"([A-ZÁÉÍÓÚÑ]{2,}\s[A-ZÁÉÍÓÚÑ\s,]+[A-ZÁÉÍÓÚÑ])"
            match_peticionario = re.search(patron_a, asunto_extraido)
            if match_peticionario:
                datos['peticionario_nombre'] = " ".join(match_peticionario.group(1).strip().rstrip(',').split())

        if not datos.get('peticionario_nombre') and pdf_filename:
            match_filename = re.search(r'-\s*([A-ZÁÉÍÓÚÑ\s]{5,})', pdf_filename, re.IGNORECASE)
            if match_filename:
                datos['peticionario_nombre'] = " ".join(match_filename.group(1).strip().split())

        # --- ¡NUEVO BLOQUE DE LIMPIEZA DEL ASUNTO! ---
        # 1. Definimos la frase que queremos eliminar
        frase_a_quitar = "Por ser un asunto de su competencia y a fin de brindar respuesta oportuna,"

        # 2. Limpiamos la frase del asunto que extrajimos
        asunto_limpio = re.sub(frase_a_quitar, '', asunto_extraido, flags=re.IGNORECASE).strip(" ,")

        # 3. Guardamos el asunto ya limpio en nuestro diccionario de datos
        datos['asunto'] = asunto_limpio
        # --- FIN DEL NUEVO BLOQUE ---

        if not datos.get('peticionario_nombre'):
            datos['peticionario_nombre'] = "Pendiente por Asignar"

        # --- Búsqueda de Email por Capas (Más robusto) ---
        if datos['peticionario_nombre'] != "Pendiente por Asignar":
            email_extraido = ""
            match_etiqueta = re.search(r"Correo electrónico:\s*(.+)", texto_completo, re.IGNORECASE)
            if match_etiqueta:
                email_extraido = match_etiqueta.group(1).strip().splitlines()[0].replace(" ", "")
            
            if not email_extraido:
                patron_email_flexible = r'[\w\.-]+(?:@|Q|Y|\(d|\(M|W)[\w\.-]+'
                correos_a_ignorar = ['rectoria@', 'quejasreclamos@', 'viceacad@', 'vri@', 'secgral@']
                nombres_peticionario = datos['peticionario_nombre'].lower().split()
                lineas = texto_completo.splitlines()
                for i, linea in enumerate(lineas):
                    linea_limpia = linea.strip().lower()
                    if linea_limpia.startswith('de:') and any(nombre in linea_limpia for nombre in nombres_peticionario):
                        contexto_busqueda = "".join(lineas[i:i+4])
                        email_match = re.search(patron_email_flexible, contexto_busqueda)
                        if email_match:
                            email_encontrado = email_match.group(0)
                            if not any(ignorado in email_encontrado for ignorado in correos_a_ignorar):
                                email_extraido = email_encontrado
                                break
            
            if email_extraido:
                # Limpieza final del email
                datos['email'] = re.sub(r'(Q|Y|\(d|\(M|W)', '@', email_extraido)

        # Añadir texto de vencimiento al asunto
        match_vencimiento = re.search(r"(vence el d[ií]a,[\s\S]+?\d{4})", texto_completo, re.IGNORECASE)
        if match_vencimiento:
            texto_vencimiento = " ".join(match_vencimiento.group(1).strip().split())
            # Usamos la variable 'asunto_limpio' que ya teníamos
            asunto_final = datos['asunto'] + f" (ATENCIÓN: {texto_vencimiento})"
            datos['asunto'] = asunto_final
        # Si no hay vencimiento, 'datos['asunto']' ya tiene el valor limpio y no se toca.   
        
        # --- Extracción de Fecha (Prioridad 1: 'Date:', Prioridad 2: Encabezado) ---
        meses_es = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12}
        fecha_encontrada = None
        for linea in texto_completo.splitlines():
            if 'date:' in linea.lower():
                match_fecha = re.search(r"(\d{1,2})(?:\s+de)?\s+([a-z]{3,})(?:\s+de)?\s+(\d{4})", linea, re.IGNORECASE)
                if match_fecha:
                    try:
                        dia, mes_str, ano = int(match_fecha.group(1)), match_fecha.group(2).lower()[:3], int(match_fecha.group(3))
                        if mes_str in meses_es:
                            fecha_encontrada = date(ano, meses_es[mes_str], dia)
                            break
                    except (ValueError, IndexError): continue
        
        if not fecha_encontrada:
             match_fecha_encabezado = re.search(r"Popayán,\s*(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})", texto_completo, re.IGNORECASE)
             if match_fecha_encabezado:
                try:
                    dia = int(match_fecha_encabezado.group(1)); mes_str = match_fecha_encabezado.group(2).lower()[:3]; ano = int(match_fecha_encabezado.group(3))
                    if mes_str in meses_es: fecha_encontrada = date(ano, meses_es[mes_str], dia)
                except (ValueError, IndexError): pass
        
        if fecha_encontrada:
            datos['fecha_recepcion_inicial'] = fecha_encontrada

        # --- Clasificación (Diccionarios ampliados) ---
        diccionario_calidad = {
            'Estudiante': ['estudiante', 'alumno', 'judicatura'],
            'Profesor': ['profesor', 'docente'],
            'Egresado': ['egresado', 'exalumno'],
            'Directivo': ['directivo', 'rector', 'vicerrector', 'jefe', 'secretaria general', 'sintraunicol', 'sindicato', 'aspu'],
            'Funcionario': ['funcionario', 'profesional universitario', 'tecnico administrativo', 'empleado', 'contratista'],
            'Entidad Gubernamental': ['representante a la camara', 'ministro', 'ministerio', 'consejal', 'senador', 'congresista', 'juzgado', 'tribunal'],
            'Externo / Particular': ['madre', 'padre', 'representante legal', 'particular']
        }
        calidad_peticionario_detectada = "Externo / Particular"
        texto_a_buscar = (asunto_extraido + " " + texto_completo[:500]).lower()
        for calidad, palabras_clave in diccionario_calidad.items():
            if any(palabra in texto_a_buscar for palabra in palabras_clave):
                calidad_peticionario_detectada = calidad
                break
        try:
            calidad_obj = CalidadPeticionario.objects.get(tipo__iexact=calidad_peticionario_detectada)
            datos['calidad_peticionario_id'] = calidad_obj.id
        except CalidadPeticionario.DoesNotExist:
            print(f"ADVERTENCIA: No se encontró la calidad '{calidad_peticionario_detectada}' en la BD.")
            pass

        # Tipo Trámite (con valor por defecto claro)
        tipo_tramite_detectado = 'petición general' # Valor por defecto
        if calidad_peticionario_detectada == 'Entidad Gubernamental': tipo_tramite_detectado = 'peticiones especiales'
        elif 'queja' in asunto_extraido.lower(): tipo_tramite_detectado = 'queja'
        elif 'gratuidad' in texto_completo.lower(): tipo_tramite_detectado = 'petición general'
        elif 'documentos' in texto_completo.lower(): tipo_tramite_detectado = 'petición de documentos'
        
        try:
            tramite_obj = TipoTramite.objects.get(nombre__iexact=tipo_tramite_detectado)
            datos['tipo_tramite_id'] = tramite_obj.id
        except TipoTramite.DoesNotExist:
            print(f"ADVERTENCIA: No se encontró el tipo de trámite '{tipo_tramite_detectado}' en la BD.")
            pass

    except Exception as e:
        print(f"Error grave durante el procesamiento del PDF: {e}")
        # En caso de error, el diccionario `datos` se devolverá con sus valores iniciales,
        # lo que permite a la lógica que llama decidir qué hacer.

    return datos