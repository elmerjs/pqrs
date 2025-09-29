# nucleo/management/commands/procesar_correos.py

import email
import imaplib
import re
from datetime import date, datetime
from email.header import decode_header
from nucleo.utils import extraer_datos_de_pdf
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile

from nucleo.models import Pqrs, ArchivoAdjunto, TipoTramite, CalidadPeticionario

class Command(BaseCommand):
    help = 'Lee el buzón de correo, busca PQRS reenviadas y las crea en el sistema.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando el procesamiento de correos reenviados...'))
        try:
            mail = imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST)
            mail.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASSWORD)
            mail.select('inbox')
            
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK': return

            email_ids = messages[0].split()
            if not email_ids:
                self.stdout.write(self.style.SUCCESS('No hay correos nuevos para procesar.'))
                return

            self.stdout.write(f'Se encontraron {len(email_ids)} correos nuevos.')

            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK': continue

                msg = email.message_from_bytes(msg_data[0][1])
                
                # Verificamos que el remitente sea el autorizado
                from_header, _ = decode_header(msg['From'])[0]
                remitente = from_header.decode() if isinstance(from_header, bytes) else from_header
                
                if 'viceacad@unicauca.edu.co' not in remitente:
                    self.stdout.write(self.style.WARNING(f'Correo de "{remitente}" no es de la fuente autorizada. Omitiendo.'))
                    continue
                
                self.stdout.write(self.style.SUCCESS(f'Correo reenviado por "{remitente}" encontrado. Procesando...'))

                # --- ¡NUEVA LÓGICA MEJORADA! ---
                original_subject = None
                original_from = "No identificado"
                pdf_content = None
                pdf_filename = 'adjunto.pdf'
                
                # MÉTODO 1: Buscar el correo original como un paquete adjunto (message/rfc822)
                original_message_part = None
                # DESPUÉS (La nueva versión corregida)
                for part in msg.walk():
                    if part.get_content_maintype() == 'application' and part.get_content_subtype() == 'pdf':
                        
                        # --- ¡ESTA ES LA MEJORA CLAVE! ---
                        # Decodificamos el nombre del archivo correctamente
                        raw_filename = part.get_filename()
                        if raw_filename:
                            # La función decode_header maneja los nombres codificados
                            decoded_header = decode_header(raw_filename)
                            filename_bytes, charset = decoded_header[0]
                            
                            # Convertimos el nombre a un texto normal y limpio
                            if isinstance(filename_bytes, bytes):
                                pdf_filename = filename_bytes.decode(charset or 'utf-8')
                            else:
                                pdf_filename = filename_bytes
                        # --- FIN DE LA MEJORA ---
                        
                        pdf_content = part.get_payload(decode=True)
                        break # Detenemos la búsqueda una vez encontrado
                if original_message_part:
                    self.stdout.write(self.style.NOTICE('  -> Detectado método estándar (message/rfc822).'))
                    
                    # Extraemos datos del paquete
                    subject_header, _ = decode_header(original_message_part['Subject'])[0]
                    original_subject = subject_header.decode() if isinstance(subject_header, bytes) else subject_header

                    from_header, _ = decode_header(original_message_part['From'])[0]
                    original_from = from_header.decode() if isinstance(from_header, bytes) else from_header
                    
                    # Buscamos el PDF dentro del paquete
                    for sub_part in original_message_part.walk():
                        if sub_part.get_content_maintype() == 'application' and sub_part.get_content_subtype() == 'pdf':
                            pdf_filename = sub_part.get_filename()
                            pdf_content = sub_part.get_payload(decode=True)
                            break
                else:
                    # MÉTODO 2: Si falla el primero, asumimos el estilo Gmail/Outlook Web
                    self.stdout.write(self.style.NOTICE('  -> No se encontró paquete. Intentando método alternativo (Gmail/Outlook Web).'))
                    
                    # El asunto original es el asunto del reenvío sin el "Fwd:"
                    subject_header, _ = decode_header(msg['Subject'])[0]
                    main_subject = subject_header.decode() if isinstance(subject_header, bytes) else subject_header
                    original_subject = re.sub(r'^(fwd|rv|reenv|re):\s*', '', main_subject, flags=re.IGNORECASE).strip()

                    # El PDF está adjunto en el correo principal
                    for part in msg.walk():
                        if part.get_content_maintype() == 'application' and part.get_content_subtype() == 'pdf':
                            pdf_filename = part.get_filename()
                            pdf_content = part.get_payload(decode=True)
                            break
                # --- FIN DE LA NUEVA LÓGICA ---

                if not pdf_content or not original_subject:
                    self.stdout.write(self.style.ERROR('  -> No se pudo extraer el asunto original o el PDF. Omitiendo.'))
                    continue

                self.stdout.write(f'  -> Asunto original: "{original_subject}"')
                self.stdout.write(f'  -> PDF encontrado: "{pdf_filename}"')

                # El resto de la lógica para crear la PQRS...
                # --- ¡NUEVA SECCIÓN MEJORADA! CREACIÓN DE LA PQRS CON DATOS COMPLETOS ---
                try:
                    # 1. Llamamos a nuestra función experta para que lea el PDF
                    self.stdout.write('     -> Iniciando análisis OCR del PDF...')
                    # Pasamos el nombre del archivo para que utils.py también pueda usarlo
                    datos_extraidos = extraer_datos_de_pdf(pdf_content, pdf_filename)

                    # Si la extracción falla, datos_extraidos será None.
                    if not datos_extraidos:
                        self.stdout.write(self.style.ERROR('     -> Falló la extracción de datos del PDF. Omitiendo.'))
                        continue # Salta al siguiente correo

                    # Si no se pudo extraer un radicado, usamos el del asunto o uno autogenerado
                    radicado_final = datos_extraidos.get('radicado')
                    if not radicado_final:
                        radicado_match = re.search(r'vu\s*(\d+)', original_subject, re.IGNORECASE)
                        radicado_final = "VU-" + radicado_match.group(1).strip() if radicado_match else f"AUTOGEN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    # Verificamos si ya existe una PQRS con este radicado para no duplicar
                    if Pqrs.objects.filter(radicado=radicado_final).exists():
                        self.stdout.write(self.style.WARNING(f'     -> YA EXISTE una PQRS con el radicado {radicado_final}. Omitiendo.'))
                        continue

                    # 2. Creamos el objeto PQRS con los datos completos del PDF
                    nueva_pqrs = Pqrs.objects.create(
                        radicado=radicado_final,
                        asunto=datos_extraidos.get('asunto', 'Asunto no extraído del PDF'),
                        fecha_recepcion_inicial=datos_extraidos.get('fecha_recepcion_inicial'),
                        peticionario_nombre=datos_extraidos.get('peticionario_nombre', 'Peticionario no extraído'),
                        peticionario_email=datos_extraidos.get('email'),
                        tipo_tramite_id=datos_extraidos.get('tipo_tramite_id'),
                        calidad_peticionario_id=datos_extraidos.get('calidad_peticionario_id'),
                        estado='Recibido',
                        confirmado=False  # <-- ¡ESTA ES LA LÍNEA CLAVE!
                    )
                    self.stdout.write(self.style.SUCCESS(f'     -> CREADA PQRS (PENDIENTE DE REVISIÓN). Radicado: {nueva_pqrs.radicado}'))

                    # --- INICIO DE LA SOLUCIÓN ---
                    # 3. Nos aseguramos de que el nombre del archivo termine en .pdf
                    if pdf_filename and not pdf_filename.lower().endswith('.pdf'):
                        pdf_filename += '.pdf'
                        self.stdout.write(self.style.NOTICE(f'     -> Nombre de archivo corregido a: "{pdf_filename}"'))
                    # --- FIN DE LA SOLUCIÓN ---

                    # 4. Adjuntamos el PDF con el nombre ya corregido
                    ArchivoAdjunto.objects.create(
                        pqrs=nueva_pqrs,
                        archivo=ContentFile(pdf_content, name=pdf_filename),
                        descripcion="Documento PDF original recibido por correo.",
                        # Asegúrate que el tipo de archivo coincide con tus choices del modelo
                        tipo_archivo='PETICIONARIO' 
                    )
                    self.stdout.write(self.style.SUCCESS('     -> PDF adjuntado correctamente.'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR('--- INICIO DEL INFORME DE ERROR DETALLADO ---'))
                    import traceback
                    traceback.print_exc()
                    self.stdout.write(self.style.ERROR('--- FIN DEL INFORME DE ERROR DETALLADO ---'))

            mail.logout()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error general de conexión: {e}'))