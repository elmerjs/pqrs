import fitz  # PyMuPDF
from PIL import Image

from pdf2image import convert_from_bytes
import pytesseract
import re
from pypdf import PdfReader
import numpy as np
from deskew import determine_skew
from skimage.color import rgb2gray
from skimage.transform import rotate
# nucleo/views.py
import base64
import openpyxl
import cv2



from io import BytesIO
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib import messages

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.storage import staticfiles_storage
from xhtml2pdf import pisa
from openpyxl.utils import get_column_letter

from .models import Pqrs, ArchivoAdjunto, CalidadPeticionario, TipoTramite, ArchivoAdjunto
from .forms import PqrsForm, PqrsFilterForm, AbogadoPqrsForm, ArchivoAdjuntoForm, PdfUploadForm

# --- Funciones de Ayuda ---

def es_coordinador(user):
    return user.groups.filter(name='Coordinadores').exists()

def es_coordinador_o_abogado(user):
    """
    Verifica si un usuario pertenece al grupo 'Coordinadores' O 'Abogados'.
    """
    return user.groups.filter(name__in=['Coordinadores', 'Abogados']).exists()
# --- Vistas Principales ---
# nucleo/views.py

def puede_gestionar_respuesta(user):
    """Verifica si un usuario es Coordinador O Abogado."""
    return user.groups.filter(name__in=['Coordinadores', 'Abogados']).exists()

@login_required
def dashboard(request):
    queryset = Pqrs.objects.exclude(estado='Anulado').order_by('-fecha_recepcion_inicial')

    if not es_coordinador(request.user) and not request.user.is_superuser:
        queryset = queryset.filter(responsable=request.user)
    
    filter_form = PqrsFilterForm(request.GET, user=request.user)
    
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        vigencia = filter_form.cleaned_data.get('vigencia')
        responsable = filter_form.cleaned_data.get('responsable')
        estado = filter_form.cleaned_data.get('estado')
        
        if q:
            queryset = queryset.filter(Q(radicado__icontains=q) | Q(asunto__icontains=q))
        
        if vigencia:
            queryset = queryset.filter(fecha_recepcion_inicial__year=vigencia)
        elif not estado: # Solo aplicar filtro de año actual si no se filtra por estado
            current_year = date.today().year
            queryset = queryset.filter(fecha_recepcion_inicial__year=current_year)

        if responsable and (es_coordinador(request.user) or request.user.is_superuser):
            queryset = queryset.filter(responsable=responsable)
        
        if estado:
            queryset = queryset.filter(estado=estado)

    total_pqrs = Pqrs.objects.count()
    conteo_por_estado = Pqrs.objects.values('estado').annotate(total=Count('estado')).order_by('estado')
    es_coord = es_coordinador(request.user)
    
    lista_abogados = None
    if es_coord or request.user.is_superuser:
        lista_abogados = User.objects.filter(groups__name='Abogados')

    contexto = {
        'total_pqrs': total_pqrs,
        'conteo_por_estado': conteo_por_estado,
        'lista_pqrs': queryset,
        'filter_form': filter_form,
        'es_coordinador': es_coord,
        'lista_abogados': lista_abogados,
    }
    return render(request, 'nucleo/dashboard.html', contexto)


# nucleo/views.py
# nucleo/views.py

@login_required
@user_passes_test(es_coordinador)
def crear_pqrs_desde_pdf(request):
    # (La configuración de Tesseract y Poppler se queda igual)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    path_a_poppler = r'C:\poppler\Library\bin'

    if request.method == 'POST':
        form = PdfUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            try:
                # 1. Leer texto con OCR y enderezar imagen
                imagenes = convert_from_bytes(pdf_file.read(), poppler_path=path_a_poppler)
                texto_completo = ""
                for imagen_original in imagenes:
                    imagen_gris = rgb2gray(np.array(imagen_original))
                    angulo = determine_skew(imagen_gris)
                    imagen_corregida_array = rotate(np.array(imagen_original), angulo, resize=True) * 255
                    imagen_corregida_pil = Image.fromarray(imagen_corregida_array.astype(np.uint8))
                    texto_completo += pytesseract.image_to_string(imagen_corregida_pil, lang='spa') + "\n"

                # 2. Extracción de datos básicos
                radicado_extraido, asunto_extraido, peticionario_extraido, email_extraido = "", "", "", ""
                match_radicado = re.search(r"VU\s*(\d+)", texto_completo, re.IGNORECASE)
                if match_radicado: radicado_extraido = "VU-" + match_radicado.group(1).strip()
                match_asunto = re.search(r"Cordial saludo,([\s\S]+?)(?=Por lo anterior|Es preciso)", texto_completo, re.IGNORECASE)
                if match_asunto: asunto_extraido = " ".join(match_asunto.group(1).strip().split())
                if asunto_extraido:
                    match_peticionario = re.search(r"([A-ZÁÉÍÓÚÑ]{2,}\s[A-ZÁÉÍÓÚÑ\s,]+[A-ZÁÉÍÓÚÑ])", asunto_extraido)
                    if match_peticionario: peticionario_extraido = match_peticionario.group(1).strip().rstrip(',')

                # 3. Búsqueda de email por capas (Tu versión estable)
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
                
                # --- ¡NUEVA LÓGICA DE CLASIFICACIÓN DE PETICIONARIO! ---
                calidad_peticionario_id = None
                # Asignamos el valor por defecto desde el principio
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
                    calidad_peticionario_id = calidad_obj.id
                except CalidadPeticionario.DoesNotExist:
                    # Si la categoría detectada no existe, intentamos con el default
                    try:
                        calidad_obj = CalidadPeticionario.objects.get(tipo="Externo / Particular")
                        calidad_peticionario_id = calidad_obj.id
                    except CalidadPeticionario.DoesNotExist:
                        calidad_peticionario_id = None
                # --- FIN DE LA NUEVA LÓGICA ---

                # 4. Limpieza y Reconstrucción final del Email
                if email_extraido:
                    email_extraido = re.sub(r'(Q|Y|\(d|\(M|W)', '@', email_extraido)
                    if '@' not in email_extraido:
                        match_dominio = re.search(r'(unicauca\.edu\.co|gmail\.com|hotmail\.com)', email_extraido, re.IGNORECASE)
                        if match_dominio:
                            pos = match_dominio.start()
                            usuario = email_extraido[:pos]
                            dominio = email_extraido[pos:]
                            email_extraido = f"{usuario}@{dominio}"

                # 5. Guardar en la sesión
                request.session['radicado_desde_pdf'] = radicado_extraido
                request.session['asunto_desde_pdf'] = asunto_extraido
                request.session['peticionario_desde_pdf'] = peticionario_extraido
                request.session['email_desde_pdf'] = email_extraido
                request.session['calidad_peticionario_id_desde_pdf'] = calidad_peticionario_id

                return redirect('crear_pqrs')

            except Exception as e:
                messages.error(request, f"Error al procesar el PDF: {e}")
                return redirect('crear_pqrs_desde_pdf')
    else:
        form = PdfUploadForm()

    return render(request, 'nucleo/crear_pqrs_desde_pdf.html', {'form': form})


@login_required
@user_passes_test(es_coordinador)
def crear_pqrs(request):
    initial_data = {}
    
    if 'radicado_desde_pdf' in request.session: initial_data['radicado'] = request.session.pop('radicado_desde_pdf')
    if 'asunto_desde_pdf' in request.session: initial_data['asunto'] = request.session.pop('asunto_desde_pdf')
    if 'peticionario_desde_pdf' in request.session: initial_data['peticionario_nombre'] = request.session.pop('peticionario_desde_pdf')
    if 'email_desde_pdf' in request.session: initial_data['peticionario_email'] = request.session.pop('email_desde_pdf')
    
    # --- ¡LÍNEA PARA LA CALIDAD DEL PETICIONARIO! ---
    if 'calidad_peticionario_id_desde_pdf' in request.session:
        initial_data['calidad_peticionario'] = request.session.pop('calidad_peticionario_id_desde_pdf')

    if request.method == 'POST':
        form = PqrsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'La PQRS ha sido registrada exitosamente.')
            return redirect('dashboard')
    else:
        form = PqrsForm(initial=initial_data)
        
    return render(request, 'nucleo/pqrs_form.html', {'form': form})

@login_required
def editar_pqrs(request, pqrs_id):
    pqrs = get_object_or_404(Pqrs, pk=pqrs_id)
    es_coord = es_coordinador(request.user)

    if not (pqrs.responsable == request.user or es_coord or request.user.is_superuser):
        return HttpResponseForbidden("No tienes permiso para editar este caso.")

    FormularioAUsar = PqrsForm if (es_coord or request.user.is_superuser) else AbogadoPqrsForm

    if request.method == 'POST':
        form = FormularioAUsar(request.POST, instance=pqrs)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = FormularioAUsar(instance=pqrs)

    contexto = {
        'form': form,
        'pqrs': pqrs
    }
    return render(request, 'nucleo/pqrs_form.html', contexto)

@login_required
def detalle_pqrs(request, pqrs_id):
    pqrs = get_object_or_404(Pqrs, pk=pqrs_id)
    
    if request.method == 'POST':
        if not (pqrs.responsable == request.user or es_coordinador(request.user) or request.user.is_superuser):
            return HttpResponseForbidden("No tienes permiso para añadir archivos a este caso.")
        
        form_adjuntos = ArchivoAdjuntoForm(request.POST, request.FILES)
        if form_adjuntos.is_valid():
            nuevo_adjunto = form_adjuntos.save(commit=False)
            nuevo_adjunto.pqrs = pqrs
            nuevo_adjunto.save()
            messages.success(request, 'Archivo adjuntado correctamente.')
            return redirect('detalle_pqrs', pqrs_id=pqrs.id)
    else:
        form_adjuntos = ArchivoAdjuntoForm()

    adjuntos = pqrs.adjuntos.all()
    
    es_coord = es_coordinador(request.user)
    tiene_permiso_ver = (pqrs.responsable == request.user or es_coord or request.user.is_superuser)
    if not tiene_permiso_ver:
        return HttpResponseForbidden("No tienes permiso para ver este caso.")

    contexto = {
        'pqrs': pqrs,
        'adjuntos': adjuntos,
        'form_adjuntos': form_adjuntos,
         'puede_gestionar': puede_gestionar_respuesta(request.user) # <-- AÑADE ESTA LÍNEA


    }
    return render(request, 'nucleo/detalle_pqrs.html', contexto)

# --- Vistas de Acciones y Reportes ---

@login_required
@user_passes_test(es_coordinador)
def asignar_abogado(request, pqrs_id):
    if request.method == 'POST':
        pqrs = get_object_or_404(Pqrs, pk=pqrs_id)
        abogado_id = request.POST.get('responsable_id')
        
        if abogado_id:
            abogado = get_object_or_404(User, pk=abogado_id)
            pqrs.responsable = abogado
            pqrs.save()
            messages.success(request, f'Se ha asignado a {abogado.get_full_name()} al caso {pqrs.radicado}.')
        else:
            messages.error(request, 'No se seleccionó un abogado válido.')
    return redirect('dashboard')

@login_required
@user_passes_test(es_coordinador_o_abogado)
def enviar_respuesta_email(request, pqrs_id):
    pqrs = get_object_or_404(Pqrs, pk=pqrs_id)

    if request.method == 'POST':
        def imagen_a_base64(ruta_relativa):
            try:
                with staticfiles_storage.open(ruta_relativa) as image_file:
                    return f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
            except Exception as e:
                print(f"ERROR: {e}")
                return None
        
        contexto_pdf = {
            'pqrs': pqrs, 'fecha_actual': date.today(),
            'data_uri_encabezado': imagen_a_base64('nucleo/img/encabezado.png'),
            'data_uri_pie': imagen_a_base64('nucleo/img/pie_pagina.png'),
        }
        html_string = render_to_string('nucleo/respuesta_pdf.html', contexto_pdf)
        buffer = BytesIO()
        pisa.CreatePDF(html_string, dest=buffer)
        pdf_en_memoria = buffer.getvalue()
        buffer.close()

        try:
            asunto = f"Respuesta a su solicitud con radicado N° {pqrs.radicado}"
            mensaje = f"Estimado(a) {pqrs.peticionario_nombre},\n\nAdjunto encontrará la respuesta formal a su solicitud y los documentos relacionados.\n\nCordialmente,\n\nVicerrectoría Académica\nUniversidad del Cauca"
            
            email = EmailMessage(asunto, mensaje, settings.EMAIL_HOST_USER, [pqrs.peticionario_email])
            
            nombre_archivo_pdf = f"Respuesta_{pqrs.radicado}.pdf"
            email.attach(nombre_archivo_pdf, pdf_en_memoria, 'application/pdf')

            ids_adjuntos_seleccionados = request.POST.getlist('adjuntos_a_enviar')
            if ids_adjuntos_seleccionados:
                adjuntos_para_enviar = ArchivoAdjunto.objects.filter(id__in=ids_adjuntos_seleccionados)
                for adjunto in adjuntos_para_enviar:
                    email.attach(adjunto.nombre_corto, adjunto.archivo.read(), None)
            
            email.send()
            messages.success(request, f'El correo para la PQRS {pqrs.radicado} ha sido enviado exitosamente.')
        except Exception as e:
            messages.error(request, f'Ocurrió un error al enviar el correo: {e}')
        return redirect('detalle_pqrs', pqrs_id=pqrs.id)

@login_required
@user_passes_test(es_coordinador_o_abogado)
def generar_pdf(request, pqrs_id):
    pqrs = get_object_or_404(Pqrs, pk=pqrs_id)
    
    def imagen_a_base64(ruta_relativa):
        try:
            with staticfiles_storage.open(ruta_relativa) as image_file:
                return f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
        except Exception as e:
            print(f"ERROR al codificar la imagen {ruta_relativa}: {e}")
            return None

    contexto = {
        'pqrs': pqrs,
        'fecha_actual': date.today(),
        'data_uri_encabezado': imagen_a_base64('nucleo/img/encabezado.png'),
        'data_uri_pie': imagen_a_base64('nucleo/img/pie_pagina.png'),
    }

    html_string = render_to_string('nucleo/respuesta_pdf.html', contexto)
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=buffer)

    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF <pre>' + html_string + '</pre>')

    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    nombre_archivo = f"Respuesta_{pqrs.radicado}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

@login_required
def exportar_excel(request):
    queryset = Pqrs.objects.exclude(estado='Anulado').order_by('-fecha_recepcion_inicial')

    if not es_coordinador(request.user) and not request.user.is_superuser:
        queryset = queryset.filter(responsable=request.user)

    filter_form = PqrsFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        vigencia = filter_form.cleaned_data.get('vigencia')
        responsable = filter_form.cleaned_data.get('responsable')
        estado = filter_form.cleaned_data.get('estado')
        # ... (lógica de filtros idéntica)
        if q: queryset = queryset.filter(Q(radicado__icontains=q) | Q(asunto__icontains=q))
        if vigencia: queryset = queryset.filter(fecha_recepcion_inicial__year=vigencia)
        elif not estado: queryset = queryset.filter(fecha_recepcion_inicial__year=date.today().year)
        if responsable and (es_coordinador(request.user) or request.user.is_superuser): queryset = queryset.filter(responsable=responsable)
        if estado: queryset = queryset.filter(estado=estado)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte PQRS"

    headers = ["Radicado", "Asunto", "Responsable", "Fecha Recepción", "Fecha Vencimiento", "Fecha Respuesta", "Estado Proceso", "Estado Tiempo", "Peticionario"]
    ws.append(headers)

    for pqrs in queryset:
        responsable_nombre = pqrs.responsable.get_full_name() if pqrs.responsable else "No asignado"
        ws.append([pqrs.radicado, pqrs.asunto, responsable_nombre, pqrs.fecha_recepcion_inicial, pqrs.fecha_vencimiento, pqrs.fecha_respuesta, pqrs.estado, pqrs.estado_tiempo, pqrs.peticionario_nombre])

    for col_num, header in enumerate(headers, 1):
        column_letter = get_column_letter(col_num)
        max_length = 0
        for cell in ws[column_letter]:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nombre_archivo = f"reporte_pqrs_{date.today().strftime('%Y-%m-%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    wb.save(response)
    return response
@login_required
@user_passes_test(es_coordinador_o_abogado) # Usamos el permiso que ya creamos
def eliminar_adjunto(request, adjunto_id):
    # Buscamos el archivo adjunto específico por su ID
    adjunto = get_object_or_404(ArchivoAdjunto, id=adjunto_id)
    pqrs_id = adjunto.pqrs.id # Guardamos el ID de la PQRS para poder regresar

    if request.method == 'POST':
        # Borra el archivo del almacenamiento
        adjunto.archivo.delete()
        # Borra el registro de la base de datos
        adjunto.delete()
        messages.success(request, 'Archivo adjunto eliminado exitosamente.')
    
    # Redirigimos al usuario de vuelta a la página de detalles de la PQRS
    return redirect('detalle_pqrs', pqrs_id=pqrs_id)
