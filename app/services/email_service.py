import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime
from app.core.config import settings
from app.models.alarm import Alarm

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        # Sin password valido el envio nunca funciona; fail-fast para no
        # bloquear el event loop ni ralentizar el escaneo con intentos SMTP.
        self.enabled = bool(self.smtp_password)
        self._reported_disabled = False

    def _send_blocking(self, to_email: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=5)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"Email enviado a {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email: {e}")
            return False

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not self.enabled:
            if not self._reported_disabled:
                self._reported_disabled = True
                logger.info("Envio de email desactivado: SMTP_PASSWORD no configurado")
            return False
        # smtplib es bloqueante; correrlo fuera del event loop
        return await asyncio.to_thread(self._send_blocking, to_email, subject, body)
    
    async def send_alarm_email(self, alarm: Alarm) -> bool:
        subject = f"[Webdom Monitor] ALARMA: {alarm.alarm_type}"
        
        body = f"""
        <h2>Nueva Alarma Detectada</h2>
        <table border="1" cellpadding="5">
            <tr><td><strong>Tipo de Alarma</strong></td><td>{alarm.alarm_type}</td></tr>
            <tr><td><strong>Descripcion</strong></td><td>{alarm.description or 'N/A'}</td></tr>
            <tr><td><strong>Gateway IP</strong></td><td>{alarm.gateway_ip or 'N/A'}</td></tr>
            <tr><td><strong>Fecha</strong></td><td>{alarm.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        <p>Esta alarma permanecera activa hasta que se resuelva el problema.</p>
        """
        
        return await self.send_email("webdomreports@gmail.com", subject, body)
    
    async def send_reminder_email(self, alarm: Alarm) -> bool:
        subject = f"[Webdom Monitor] RECORDATORIO: Alarma activa - {alarm.alarm_type}"
        
        days_active = (datetime.utcnow() - alarm.created_at).days
        
        body = f"""
        <h2>Recordatorio de Alarma Activa</h2>
        <p>La siguiente alarma lleva activa <strong>{days_active} dias</strong>:</p>
        <table border="1" cellpadding="5">
            <tr><td><strong>Tipo de Alarma</strong></td><td>{alarm.alarm_type}</td></tr>
            <tr><td><strong>Descripcion</strong></td><td>{alarm.description or 'N/A'}</td></tr>
            <tr><td><strong>Gateway IP</strong></td><td>{alarm.gateway_ip or 'N/A'}</td></tr>
            <tr><td><strong>Fecha de Creacion</strong></td><td>{alarm.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        """
        
        return await self.send_email("webdomreports@gmail.com", subject, body)

email_service = EmailService()
