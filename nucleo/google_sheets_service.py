import gspread
from django.conf import settings
from .models import Pqrs
from background_task import background
from gspread_formatting import *
from django.contrib.auth.models import User

print("--- MÓDULO GOOGLE SHEETS SERVICE CARGADO (VERSIÓN CON PESTAÑAS POR PERIODO) ---")

@background(schedule=1)
def update_pqrs_sheet(pqrs_id):
    print("--- ⚠️ ¡ATENCIÓN! ESTOY EJECUTANDO LA VERSIÓN CON PESTAÑAS POR PERIODO ---")
    try:
        gc = gspread.service_account(filename=settings.GOOGLE_SHEETS_CREDENTIALS_FILE)
        spreadsheet = gc.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
        
        pqrs = Pqrs.objects.get(pk=pqrs_id)
        
        # Obtener el periodo (año) de la fecha de recepción
        periodo = pqrs.fecha_recepcion_inicial.year
        nombre_hoja = f"PQRSF {periodo}"
        
        # Intentar obtener la hoja del periodo actual, si no existe crearla
        try:
            worksheet = spreadsheet.worksheet(nombre_hoja)
            print(f"✅ Hoja {nombre_hoja} encontrada")
            
            # Verificar si ya tiene encabezados (si tiene datos)
            existing_data = worksheet.get_all_records()
            tiene_encabezados = len(existing_data) > 0
            
        except gspread.WorksheetNotFound:
            print(f"📄 Creando nueva hoja: {nombre_hoja}")
            worksheet = spreadsheet.add_worksheet(title=nombre_hoja, rows="1000", cols="20")
            headers = [
                "Periodo", "Consecutivo", "Peticionario", "Calidad del Peticionario", 
                "Tipo de Trámite", "Radicado", "Fecha Recepción", "Asunto", 
                "Fecha Vencimiento", "Respuesta Definitiva", "Responsable", 
                "Estado", "Estado Tiempo", "URL"
            ]
            worksheet.append_row(headers)
            tiene_encabezados = True
            print(f"✅ Hoja {nombre_hoja} creada exitosamente")

        # SOLO agregar encabezados si la hoja está vacía (recién creada)
        if not tiene_encabezados:
            headers = [
                "Periodo", "Consecutivo", "Peticionario", "Calidad del Peticionario", 
                "Tipo de Trámite", "Radicado", "Fecha Recepción", "Asunto", 
                "Fecha Vencimiento", "Respuesta Definitiva", "Responsable", 
                "Estado", "Estado Tiempo", "URL"
            ]
            worksheet.append_row(headers)
            print(f"📝 Encabezados agregados a {nombre_hoja}")
        
        # Calcular el consecutivo para este periodo
        consecutivo = calcular_consecutivo(worksheet, periodo, pqrs.radicado)
        
        responsable_nombre = pqrs.responsable.get_full_name() if pqrs.responsable else "No Asignado"
        
        # Obtener los nuevos campos
        calidad_peticionario = pqrs.calidad_peticionario.tipo if pqrs.calidad_peticionario else "No especificado"
        tipo_tramite = pqrs.tipo_tramite.nombre if pqrs.tipo_tramite else "No especificado"
        
        # Construir respuesta definitiva incluyendo traslado por competencia si existe
        respuesta_definitiva = ""
        if pqrs.respuesta_tramite:
            respuesta_definitiva = pqrs.respuesta_tramite
        
        # Si hay traslado por competencia, concatenar la información
        if pqrs.estado_traslado == 'En Traslado' and pqrs.dependencia_trasladada:
            traslado_info = f"Trasladado por competencia a: {pqrs.dependencia_trasladada}"
            if respuesta_definitiva:
                respuesta_definitiva = f"{respuesta_definitiva}\n\n{traslado_info}"
            else:
                respuesta_definitiva = traslado_info
        
        # Si no hay respuesta definitiva ni traslado, mostrar "Pendiente"
        if not respuesta_definitiva:
            respuesta_definitiva = "Pendiente"
        
        url_detalle = f"http://192.168.42.175:8000/pqrs/{pqrs.id}/"
        
        # ESTADO TIEMPO SIN EMOJIS - texto normal
        estado_del_tiempo = pqrs.get_estado_tiempo()

        row_data = [
            periodo, 
            consecutivo, 
            pqrs.peticionario_nombre,      # Peticionario
            calidad_peticionario,          # Calidad del Peticionario
            tipo_tramite,                  # Tipo de Trámite
            pqrs.radicado,                 # Radicado
            str(pqrs.fecha_recepcion_inicial),  # Fecha Recepción
            pqrs.asunto,                   # Asunto
            str(pqrs.fecha_vencimiento) if pqrs.fecha_vencimiento else "",  # Fecha Vencimiento
            respuesta_definitiva,          # Respuesta Definitiva (con traslado si aplica)
            responsable_nombre,            # Responsable
            pqrs.estado,                   # Estado
            estado_del_tiempo,             # Estado Tiempo (TEXTO NORMAL)
            url_detalle                    # URL
        ]

        # Buscar si ya existe una fila con este radicado
        cell = worksheet.find(pqrs.radicado, in_column=6)

        if cell:
            worksheet.update(f'A{cell.row}:N{cell.row}', [row_data])
            print(f"📝 Actualizada PQRS existente en {nombre_hoja}")
        else:
            worksheet.append_row(row_data)
            print(f"🆕 Nueva PQRS agregada a {nombre_hoja}")
                    
        apply_conditional_formatting(worksheet)
        print(f"✅ TAREA EN SEGUNDO PLANO: Hoja {nombre_hoja} actualizada para PQRS ID: {pqrs_id}")

    except Pqrs.DoesNotExist:
        print(f"❌ ERROR EN TAREA: No se encontró la PQRS con ID {pqrs_id}")
    
    except BaseException as e:
        print("\n\n" + "="*60)
        print("   ❌ ¡¡¡ERROR CRÍTICO ATRAPADO DENTRO DE LA TAREA!!!")
        print(f"   TIPO DE ERROR: {type(e).__name__}")
        print(f"   MENSAJE: {e}")
        print("="*60 + "\n\n")

def apply_conditional_formatting(worksheet):
    """
    VERSIÓN OPTIMIZADA: Solo formatos condicionales esenciales
    """
    try:
        print("⚡ Aplicando formatos esenciales (sin anchos/alineación)...")

        # --- 1. DEFINICIÓN DE ESTILOS ESENCIALES ---
        formato_anulado = CellFormat(backgroundColor=Color(0.9, 0.9, 0.9), textFormat=TextFormat(strikethrough=True))
        formato_resuelto = CellFormat(backgroundColor=Color(0.93, 0.99, 0.93))
        
        # COLORES DE TEXTO PARA ESTADO TIEMPO (sin fondo)
        formato_vencido = CellFormat(
            textFormat=TextFormat(
                bold=True, 
                foregroundColor=Color(0.8, 0.1, 0.1)  # Rojo oscuro
            )
        )
        
        formato_por_vencer = CellFormat(
            textFormat=TextFormat(
                bold=True, 
                foregroundColor=Color(0.8, 0.5, 0.1)  # Naranja
            )
        )
        
        formato_a_tiempo = CellFormat(
            textFormat=TextFormat(
                bold=True, 
                foregroundColor=Color(0, 0, 0)  # Negro
            )
        )
        
        formato_finalizado = CellFormat(
            textFormat=TextFormat(
                bold=True, 
                foregroundColor=Color(0.1, 0.1, 0.1)  # Negro muy oscuro
            )
        )
        
        colores_responsable = [
            Color(0.98, 0.8, 0.78), Color(0.8, 0.92, 0.98), Color(0.8, 0.98, 0.82),
            Color(0.95, 0.82, 0.99), Color(0.99, 0.9, 0.75),
        ]

        # --- 2. CREACIÓN DE REGLAS ESENCIALES ---
        lista_de_reglas = []
        sheet_id = worksheet.id

        # --- REGLAS PARA RESPONSABLE (Columna K) - fondo de color ---
        range_responsable = {'sheetId': sheet_id, 'startColumnIndex': 10, 'endColumnIndex': 11}
        abogados = User.objects.filter(groups__name='Abogados').order_by('first_name')
        for i, abogado in enumerate(abogados):
            nombre_completo = abogado.get_full_name()
            if not nombre_completo: continue
            color = colores_responsable[i % len(colores_responsable)]
            formato = CellFormat(backgroundColor=color, textFormat=TextFormat(bold=True))
            formula = f'=$K1="{nombre_completo}"'
            regla = ConditionalFormatRule(ranges=[range_responsable], booleanRule=BooleanRule(condition=BooleanCondition('CUSTOM_FORMULA', [formula]), format=formato))
            lista_de_reglas.append(regla)

        # --- REGLAS PARA ESTADO TIEMPO (Columna M) - color de texto ---
        range_estado_tiempo = {'sheetId': sheet_id, 'startColumnIndex': 12, 'endColumnIndex': 13}
        
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[range_estado_tiempo], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$M1="Vencido"']), 
                format=formato_vencido
            )
        ))
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[range_estado_tiempo], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$M1="Por Vencer"']), 
                format=formato_por_vencer
            )
        ))
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[range_estado_tiempo], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$M1="A Tiempo"']), 
                format=formato_a_tiempo
            )
        ))
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[range_estado_tiempo], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$M1="Finalizado"']), 
                format=formato_finalizado
            )
        ))
        
        # --- REGLAS PARA FILA COMPLETA (Estados) ---
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[{'sheetId': sheet_id}], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$L1="Resuelto"']), 
                format=formato_resuelto
            )
        ))
        lista_de_reglas.append(ConditionalFormatRule(
            ranges=[{'sheetId': sheet_id}], 
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=$L1="Anulado"']), 
                format=formato_anulado
            )
        ))

        # --- 3. APLICACIÓN DE TODAS LAS REGLAS (UNA SOLA OPERACIÓN) ---
        rules = get_conditional_format_rules(worksheet)
        rules.clear()
        rules.extend(lista_de_reglas)
        rules.save()
        
        print("✅ Formatos condicionales esenciales aplicados:")
        print("   🎨 Colores por abogado (Columna K)")
        print("   🔴🟠⚫ Colores de texto para Estado Tiempo (Columna M)") 
        print("   ✅❌ Fondo completo para Resuelto/Anulado")
        print("   📝 Nota: Anchos y alineación los puede ajustar el usuario")

    except Exception as e:
        print(f"❌ Error al aplicar formatos condicionales: {e}")

def calcular_consecutivo(worksheet, periodo, radicado_actual):
    """
    Calcula el consecutivo para un periodo específico.
    """
    try:
        all_data = worksheet.get_all_records()
        
        if not all_data:
            return 1
        
        # Buscar si el radicado actual ya existe en la hoja
        for row in all_data:
            if row.get('Radicado') == radicado_actual:
                return row.get('Consecutivo', 1)
        
        # Si no existe, calcular el próximo consecutivo para este periodo
        consecutivos_periodo = []
        for row in all_data:
            if row.get('Periodo') == periodo:
                consecutivo = row.get('Consecutivo', 0)
                if isinstance(consecutivo, (int, float)) and consecutivo > 0:
                    consecutivos_periodo.append(int(consecutivo))
        
        if consecutivos_periodo:
            return max(consecutivos_periodo) + 1
        else:
            return 1
            
    except Exception as e:
        print(f"Error calculando consecutivo: {e}")
        return 1