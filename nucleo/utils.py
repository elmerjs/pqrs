# nucleo/utils.py
print("--- EJECUTANDO VERSIÓN UNIFICADA CON VIEWS.PY ---")

import re
import os
from datetime import date
from PIL import Image
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes

# ✅ USAR LOS MISMOS IMPORTS QUE VIEWS.PY
from deskew import determine_skew  # ← ¡ESTE ES EL SECRETO!
from skimage.color import rgb2gray
from skimage.transform import rotate

# Importamos los modelos
from .models import TipoTramite, CalidadPeticionario

# ✅ MISMAS RUTAS QUE VIEWS.PY
PYTESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
POPPLER_PATH = r'C:\poppler\Library\bin'

def extraer_datos_de_pdf(pdf_bytes, pdf_filename=""):
    """
    Función que usa EXACTAMENTE la misma lógica que crear_pqrs_desde_pdf en views.py
    """
    datos = {
        'radicado': None,
        'asunto': None,
        'peticionario_nombre': None,
        'email': None,
        'fecha_recepcion_inicial': date.today(),
        'calidad_peticionario_id': None,
        'tipo_tramite_id': None,
    }

    try:
        # ✅ CONFIGURACIÓN IDÉNTICA A VIEWS.PY
        pytesseract.pytesseract.tesseract_cmd = PYTESSERACT_PATH

        # ✅ PROCESAMIENTO IDÉNTICO A VIEWS.PY
        imagenes = convert_from_bytes(pdf_bytes, poppler_path=POPPLER_PATH)
        texto_completo = ""
        
        for imagen_original in imagenes:
            # ✅ MISMOS PASOS DE PROCESAMIENTO QUE VIEWS.PY
            imagen_gris = rgb2gray(np.array(imagen_original))
            angulo = determine_skew(imagen_gris)  # ← ¡MISMA FUNCIÓN!
            imagen_corregida_array = rotate(np.array(imagen_original), angulo, resize=True) * 255
            imagen_corregida_pil = Image.fromarray(imagen_corregida_array.astype(np.uint8))
            
            # ✅ MISMA CONFIGURACIÓN TESSERACT
            texto_pagina = pytesseract.image_to_string(imagen_corregida_pil, lang='spa')
            texto_completo += texto_pagina + "\n"
            
            print(f"=== TEXTO PÁGINA EXTRAÍDO ===")
            print(texto_pagina if texto_pagina.strip() else "❌ NO SE EXTRAJO TEXTO")
            print("==============================")

        # ✅ DIAGNÓSTICO IDÉNTICO A VIEWS.PY
        print("\n\n===================================")
        print("INICIO DE TEXTO CRUDO EXTRAÍDO CON OCR")
        print("===================================")
        print(texto_completo)
        print("===================================")
        print("FIN DE TEXTO CRUDO EXTRAÍDO CON OCR")
        print("===================================\n\n")

        # --- EXTRACCIÓN DE DATOS (Misma lógica que views.py) ---
        
        # 1. Extracción de Radicado
        match_radicado = re.search(r"VU\s*(\d+)", texto_completo, re.IGNORECASE)
        if match_radicado:
            datos['radicado'] = "VU-" + match_radicado.group(1).strip()

        # 2. Extracción de Asunto y Peticionario (Misma lógica)
        asunto_extraido, peticionario_extraido = "", ""
        
        match_bloque_asunto = re.search(r"Cordial saludo,([\s\S]+?)(?=Por lo anterior|Es preciso)", texto_completo, re.IGNORECASE)
        if match_bloque_asunto:
            bloque_asunto_crudo = match_bloque_asunto.group(1).strip()

            match_peticionario = re.search(r"([A-ZÁÉÍÓÚÑ]{2,}\s[A-ZÁÉÍÓÚÑ\s,]+[A-ZÁÉÍÓÚÑ])", bloque_asunto_crudo)

            if match_peticionario:
                peticionario_extraido = match_peticionario.group(1).strip().rstrip(',')
                asunto_recortado = bloque_asunto_crudo[match_peticionario.start():]
                asunto_extraido = " ".join(asunto_recortado.split())
            else:
                peticionario_extraido = ""
                asunto_extraido = " ".join(bloque_asunto_crudo.split())

        if not asunto_extraido:
            asunto_extraido = "Asunto no extraído del PDF."

        datos['asunto'] = asunto_extraido
        datos['peticionario_nombre'] = peticionario_extraido

        # 3. Extracción de Fecha (Misma lógica)
        fecha_recepcion_extraida = None
        meses_es = {
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
        }

        # Plan A: Buscar "Date:" en correo
        for linea in texto_completo.splitlines():
            if 'date:' in linea.lower():
                match_fecha_correo = re.search(r"(\d{1,2})(?:\s+de)?\s+([a-z]{3,})(?:\s+de)?\s+(\d{4})", linea, re.IGNORECASE)
                if match_fecha_correo:
                    try:
                        dia = int(match_fecha_correo.group(1))
                        mes_str = match_fecha_correo.group(2).lower()[:3]
                        ano = int(match_fecha_correo.group(3))
                        if mes_str in meses_es:
                            fecha_recepcion_extraida = date(ano, meses_es[mes_str], dia)
                            break
                    except (ValueError, IndexError):
                        continue

        # Plan B: Buscar fecha en encabezado
        if not fecha_recepcion_extraida:
            match_fecha_encabezado = re.search(r"Popayán,\s*(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})", texto_completo, re.IGNORECASE)
            if match_fecha_encabezado:
                try:
                    dia = int(match_fecha_encabezado.group(1))
                    mes_str = match_fecha_encabezado.group(2).lower()[:3]
                    ano = int(match_fecha_encabezado.group(3))
                    if mes_str in meses_es:
                        fecha_recepcion_extraida = date(ano, meses_es[mes_str], dia)
                except (ValueError, IndexError):
                    pass

        if fecha_recepcion_extraida:
            datos['fecha_recepcion_inicial'] = fecha_recepcion_extraida

        # 4. Extracción de Email (Misma lógica)
        email_extraido = ""
        if peticionario_extraido:
            match_etiqueta = re.search(r"Correo electrónico:\s*(.+)", texto_completo, re.IGNORECASE)
            if match_etiqueta:
                email_extraido = match_etiqueta.group(1).strip().splitlines()[0].replace(" ", "")
            
            if not email_extraido:
                patron_email_flexible = r'[\w\.-]+(?:@|Q|Y|\(d|\(M|W)[\w\.-]+'
                correos_a_ignorar = ['rectoria@', 'quejasreclamos@', 'viceacad@', 'vri@', 'secgral@']
                nombres_peticionario = peticionario_extraido.lower().split()
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

        # Limpieza final del email
        if email_extraido:
            email_extraido = re.sub(r'(Q|Y|\(d|\(M|W)', '@', email_extraido)
            if '@' not in email_extraido:
                match_dominio = re.search(r'(unicauca\.edu\.co|gmail\.com|hotmail\.com)', email_extraido, re.IGNORECASE)
                if match_dominio:
                    pos = match_dominio.start()
                    usuario = email_extraido[:pos]
                    dominio = email_extraido[pos:]
                    email_extraido = f"{usuario}@{dominio}"
        
        datos['email'] = email_extraido

        # 5. Clasificación de Calidad de Peticionario (Misma lógica)
        calidad_peticionario_id = None
        calidad_peticionario_detectada = "Externo / Particular"

        diccionario_calidad = {
            'Estudiante': ['estudiante', 'alumno', 'judicatura'],
            'Profesor': ['profesor', 'docente'],
            'Egresado': ['egresado', 'exalumno'],
            'Directivo': ['directivo', 'rector', 'vicerrector', 'jefe', 'secretaria general', 'sintraunicol', 'sindicato', 'aspu'],
            'Funcionario': ['funcionario', 'profesional universitario', 'tecnico administrativo', 'empleado', 'contratista'],
            'Entidad Gubernamental': ['representante a la camara', 'ministro', 'ministerio', 'consejal', 'senador', 'congresista', 'juzgado', 'tribunal'],
            'Externo / Particular': ['madre', 'padre', 'representante legal', 'particular']
        }
        
        texto_a_buscar = asunto_extraido.lower() if asunto_extraido else texto_completo.lower()
        
        for calidad, palabras_clave in diccionario_calidad.items():
            if any(palabra in texto_a_buscar for palabra in palabras_clave):
                calidad_peticionario_detectada = calidad
                break

        try:
            calidad_obj = CalidadPeticionario.objects.get(tipo=calidad_peticionario_detectada)
            datos['calidad_peticionario_id'] = calidad_obj.id
        except CalidadPeticionario.DoesNotExist:
            try:
                calidad_obj = CalidadPeticionario.objects.get(tipo="Externo / Particular")
                datos['calidad_peticionario_id'] = calidad_obj.id
            except CalidadPeticionario.DoesNotExist:
                datos['calidad_peticionario_id'] = None

        # 6. Clasificación de Tipo de Trámite (Misma lógica)
        tipo_tramite_id = None
        tipo_tramite_detectado = None

        if calidad_peticionario_detectada == 'Entidad Gubernamental':
            tipo_tramite_detectado = 'peticiones especiales'
        elif 'queja' in asunto_extraido.lower():
            tipo_tramite_detectado = 'queja'
        elif 'gratuidad' in texto_completo.lower():
            tipo_tramite_detectado = 'petición general'
        elif 'documentos' in texto_completo.lower():
            tipo_tramite_detectado = 'petición de documentos'
        else:
            tipo_tramite_detectado = 'petición general'

        if tipo_tramite_detectado:
            try:
                tramite_obj = TipoTramite.objects.get(nombre__iexact=tipo_tramite_detectado)
                datos['tipo_tramite_id'] = tramite_obj.id
            except TipoTramite.DoesNotExist:
                datos['tipo_tramite_id'] = None

        # 7. Limpieza final del asunto
        frase_a_quitar = "Por ser un asunto de su competencia y a fin de brindar respuesta oportuna,"
        if datos['asunto']:
            datos['asunto'] = re.sub(frase_a_quitar, '', datos['asunto'], flags=re.IGNORECASE).strip(" ,")

        # ✅ 8. AÑADIR TEXTO DE VENCIMIENTO AL ASUNTO (NUEVA FUNCIONALIDAD)
        match_vencimiento = re.search(r"(vence el d[ií]a,[\s\S]+?\d{4})", texto_completo, re.IGNORECASE)
        if match_vencimiento:
            texto_vencimiento = " ".join(match_vencimiento.group(1).strip().split())
            # Usamos el asunto ya limpio
            datos['asunto'] = datos['asunto'] + f" (ATENCIÓN: {texto_vencimiento})"
            print(f"✅ VENCIMIENTO DETECTADO Y AÑADIDO: {texto_vencimiento}")
        # Si no hay vencimiento, 'datos['asunto']' ya tiene el valor limpio y no se toca.

        print("✅ EXTRACCIÓN COMPLETADA:")
        print(f"   Radicado: {datos['radicado']}")
        print(f"   Asunto: {datos['asunto']}")
        print(f"   Peticionario: {datos['peticionario_nombre']}")
        print(f"   Email: {datos['email']}")
        print(f"   Fecha Recepción: {datos['fecha_recepcion_inicial']}")
        print(f"   Calidad ID: {datos['calidad_peticionario_id']}")
        print(f"   Trámite ID: {datos['tipo_tramite_id']}")

    except Exception as e:
        print(f"❌ Error grave durante el procesamiento del PDF: {e}")

    return datos