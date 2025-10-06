# nucleo/management/commands/procesar_correos.py

import os
import base64
import re
import io
import traceback

# --- IMPORTACIONES DE GOOGLE ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- TUS IMPORTACIONES ORIGINALES ---
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
from nucleo.models import Pqrs, ArchivoAdjunto
from nucleo.utils import extraer_datos_de_pdf

# --- PERMISOS REQUERIDOS ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/drive.readonly']

def descargar_pdf_desde_drive(creds, texto_correo):
    """Busca un enlace de Drive y descarga el PDF usando las credenciales del usuario."""
    match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', texto_correo)
    if not match:
        return None, None

    file_id = match.group(1)
    print(f"   -> Enlace de Drive encontrado. ID: {file_id}")
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"   -> Descargando desde Drive: {int(status.progress() * 100)}%.")

        file_metadata = drive_service.files().get(fileId=file_id, fields='name').execute()
        nombre_archivo = file_metadata.get('name', 'adjunto_drive.pdf')
        print(f"   -> PDF '{nombre_archivo}' descargado desde Drive.")
        fh.seek(0)
        return fh.read(), nombre_archivo
    except Exception as e:
        print(f"   -> ❌ Error al descargar desde Drive: {e}")
        return None, None

class Command(BaseCommand):
    help = 'Lee correos no leídos, busca PQRS y las crea en el sistema.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando el procesamiento de correos...'))
        creds = None
        
        # --- NUEVA LÓGICA DE AUTENTICACIÓN DE USUARIO ---
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials_oauth.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], q="from:viceacad@unicauca.edu.co").execute()
            messages = results.get('messages', [])

            if not messages:
                self.stdout.write(self.style.SUCCESS('No hay correos nuevos para procesar.'))
                return

            self.stdout.write(f'Se encontraron {len(messages)} correos nuevos.')

            for message_info in messages:
                msg = service.users().messages().get(userId='me', id=message_info['id']).execute()
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'Sin Asunto')
                
                # El asunto original es el asunto del reenvío sin el "Fwd:"
                original_subject = re.sub(r'^(fwd|rv|reenv|re):\s*', '', subject, flags=re.IGNORECASE).strip()
                self.stdout.write(self.style.SUCCESS(f'Procesando correo: "{original_subject}"'))

                pdf_content = None
                pdf_filename = None
                body = ""

                parts = payload.get('parts', [])
                for part in parts:
                    if part.get('filename') and part.get('filename').lower().endswith('.pdf'):
                        attachment_id = part['body']['attachmentId']
                        attachment = service.users().messages().attachments().get(userId='me', messageId=msg['id'], id=attachment_id).execute()
                        pdf_content = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                        pdf_filename = part['filename']
                        self.stdout.write(f"   -> Adjunto directo encontrado: {pdf_filename}")
                        break
                
                body_part = next((p for p in payload.get('parts', []) if p.get("mimeType") == "text/plain"), None)
                if body_part:
                    body_data = body_part.get('body', {}).get('data', '')
                    if body_data:
                        body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')

                if not pdf_content:
                    self.stdout.write("   -> No se encontraron adjuntos. Buscando enlace de Drive...")
                    pdf_content, pdf_filename = descargar_pdf_desde_drive(creds, body)

                if not pdf_content:
                    self.stdout.write(self.style.ERROR("   -> No se pudo obtener el PDF. Omitiendo."))
                    service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                    continue
                
                # --- ¡TU LÓGICA ORIGINAL PARA CREAR LA PQRS! (INTACTA) ---
                try:
                    self.stdout.write('     -> Iniciando análisis del PDF...')
                    datos_extraidos = extraer_datos_de_pdf(pdf_content, pdf_filename)
                    if not datos_extraidos:
                        self.stdout.write(self.style.ERROR('     -> Falló la extracción de datos del PDF. Omitiendo.'))
                        continue

                    radicado_final = datos_extraidos.get('radicado')
                    if not radicado_final:
                        radicado_match = re.search(r'vu\s*(\d+)', original_subject, re.IGNORECASE)
                        radicado_final = "VU-" + radicado_match.group(1).strip() if radicado_match else f"AUTOGEN-{message_info['id']}"
                    
                    if Pqrs.objects.filter(radicado=radicado_final).exists():
                        self.stdout.write(self.style.WARNING(f'     -> YA EXISTE una PQRS con el radicado {radicado_final}. Omitiendo.'))
                        continue

                    nueva_pqrs = Pqrs.objects.create(
                        radicado=radicado_final,
                        asunto=datos_extraidos.get('asunto', 'Asunto no extraído del PDF'),
                        fecha_recepcion_inicial=datos_extraidos.get('fecha_recepcion_inicial'),
                        peticionario_nombre=datos_extraidos.get('peticionario_nombre', 'Peticionario no extraído'),
                        peticionario_email=datos_extraidos.get('email'),
                        tipo_tramite_id=datos_extraidos.get('tipo_tramite_id'),
                        calidad_peticionario_id=datos_extraidos.get('calidad_peticionario_id'),
                        estado='Recibido',
                        confirmado=False
                    )
                    self.stdout.write(self.style.SUCCESS(f'     -> CREADA PQRS (PENDIENTE DE REVISIÓN). Radicado: {nueva_pqrs.radicado}'))

                    if pdf_filename and not pdf_filename.lower().endswith('.pdf'):
                        pdf_filename += '.pdf'
                    
                    ArchivoAdjunto.objects.create(
                        pqrs=nueva_pqrs,
                        archivo=ContentFile(pdf_content, name=pdf_filename),
                        descripcion="Documento PDF original recibido por correo.",
                        tipo_archivo='PETICIONARIO' 
                    )
                    self.stdout.write(self.style.SUCCESS('     -> PDF adjuntado correctamente.'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR('--- INICIO DEL INFORME DE ERROR DETALLADO ---'))
                    traceback.print_exc()
                    self.stdout.write(self.style.ERROR('--- FIN DEL INFORME DE ERROR DETALLADO ---'))

                # Marcar correo como leído al final del proceso
                service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()

        except Exception as e:
            self.stdout.write(self.style.ERROR('--- INICIO DEL INFORME DE ERROR GENERAL ---'))
            traceback.print_exc()
            self.stdout.write(self.style.ERROR('--- FIN DEL INFORME DE ERROR GENERAL ---'))