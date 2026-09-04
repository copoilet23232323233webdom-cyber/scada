import asyncio
import os
import re
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import auth, plants, gateways, cards, alarms, users, websocket, vpn, maintenance, scan, report, gw_control
from app.services.gw_control.context import close_all_clients
from app.services.vpn_service_v2 import vpn_service
from app.tasks.scheduler_v2 import start_scheduler, stop_scheduler

_DT_SUFFIX_RE = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\b(?!Z)')

class UTCDatetimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ct = response.headers.get('content-type', '')
        if ct.startswith('application/json') and hasattr(response, 'body'):
            body = response.body if isinstance(response.body, bytes) else b""
            if body:
                text = body.decode('utf-8')
                text = _DT_SUFFIX_RE.sub(r'\1Z', text)
                return Response(content=text, status_code=response.status_code,
                                headers=dict(response.headers), media_type='application/json')
        return response

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler('logs/webdom_monitor.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = FastAPI(
    title='Webdom Monitor',
    description='Plataforma de Monitorización Remota para Webdom Gateway',
    version='2.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(UTCDatetimeMiddleware)

app.include_router(auth.router, prefix='/api/auth', tags=['auth'])
app.include_router(plants.router, prefix='/api/plants', tags=['plants'])
app.include_router(gateways.router, prefix='/api/gateways', tags=['gateways'])
app.include_router(cards.router, prefix='/api/cards', tags=['cards'])
app.include_router(alarms.router, prefix='/api/alarms', tags=['alarms'])
app.include_router(users.router, prefix='/api/users', tags=['users'])
app.include_router(websocket.router, prefix='/api/ws', tags=['websocket'])
app.include_router(vpn.router, prefix='/api/vpn', tags=['vpn'])
app.include_router(maintenance.router, prefix='/api/maintenance', tags=['maintenance'])
app.include_router(scan.router, prefix='/api/scan', tags=['scan'])
app.include_router(report.router, prefix='/api/report', tags=['report'])
app.include_router(gw_control.router, prefix='/api/gateways', tags=['gateway-control'])

@app.on_event('startup')
async def startup_event():
    await init_db()
    print('[OK] Base de datos inicializada')
    
    # Iniciar scheduler en background
    asyncio.create_task(start_scheduler())
    print('[OK] Scheduler iniciado (escaneos cada 5 minutos)')

    await vpn_service.start_monitor()
    print('[OK] Watchdog VPN iniciado (reconexion automatica)')
    print('[OK] Aplicacion lista en http://0.0.0.0:8000')

@app.on_event('shutdown')
async def shutdown_event():
    await stop_scheduler()
    close_all_clients()
    await vpn_service.stop_monitor()
    await vpn_service.disconnect_vpn()
    print('[OK] Scheduler detenido')

@app.get('/')
async def root():
    return {
        'message': 'Webdom Monitor API v2.0',
        'version': '2.0.0',
        'docs': '/docs',
        'health': '/health'
    }

@app.get('/health')
async def health():
    from app.tasks.scheduler_v2 import scheduler
    return {
        'status': 'healthy',
        'scheduler': scheduler.get_status(),
        'vpn': vpn_service.get_diagnostics()
    }
