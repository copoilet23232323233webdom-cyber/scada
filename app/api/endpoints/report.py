import os
import asyncio
import io
import csv
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.alarm import Alarm
from app.services.report_service import ejecutar_escaneo_para_reporte, calcular_stats
from app.services.vpn_service_v2 import vpn_service
from app.tasks.scheduler_v2 import scheduler

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/plant/{plant_id}")
async def generate_report(
    plant_id: int,
    format: str = Query("pdf", description="pdf o csv"),
    incluir_alarmas: bool = Query(True, description="Incluir alarmas"),
    incluir_diag: bool = Query(False, description="Incluir diagnostico"),
    incluir_voltaje: bool = Query(True, description="Incluir voltaje"),
    incluir_strings: bool = Query(False, description="Incluir strings"),
    umbral_strings: int = Query(30, description="Umbral % para anomalias de strings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    opts = {
        "alarmas": incluir_alarmas,
        "diag": incluir_diag,
        "voltaje": incluir_voltaje,
        "strings": incluir_strings,
        "umbral": umbral_strings,
    }

    # Pausar scheduler para priorizar acción manual
    await scheduler.pause_for_action()

    # Conectar VPN antes de escanear
    vpn_was_connected = vpn_service.vpn_connected
    if not vpn_was_connected:
        vpn_file = os.path.join(plant.path, 'vpn.txt')
        if not os.path.exists(vpn_file):
            await scheduler.resume()
            raise HTTPException(status_code=500, detail=f"Archivo VPN no encontrado: {vpn_file}")
        logger.info(f"Conectando VPN para reporte de {plant.name}...")
        success = await vpn_service.connect_vpn(vpn_file, plant.name)
        if not success:
            await scheduler.resume()
            raise HTTPException(status_code=500, detail="No se pudo conectar VPN para el reporte")
        await asyncio.sleep(5)

    try:
        result = await ejecutar_escaneo_para_reporte(plant.name, plant.path, opts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en escaneo: {str(e)}")
    finally:
        if not vpn_was_connected and vpn_service.vpn_connected:
            await vpn_service.disconnect_vpn()
        await scheduler.resume()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

    res_gw = result["gateways"]
    orden = result["orden"]
    stats = result["stats"]

    if format == "csv":
        return _generate_csv(res_gw, orden, plant.name, opts)
    else:
        return _generate_pdf(res_gw, orden, plant.name, stats, opts)

def _generate_csv(res_gw: dict, orden: list, plant_name: str, opts: dict) -> StreamingResponse:
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=";")

    cab = ["Gateway_IP", "ID_Modbus", "Estado"]
    if opts.get("alarmas"):
        cab += ["Alarma_Secc", "Alarma_Sobreten"]
    if opts.get("diag"):
        cab.append("Diagnostico")
    if opts.get("voltaje"):
        cab.append("Voltaje_V")
    wr.writerow(cab)

    for ip in orden:
        for r in (res_gw.get(ip) or []):
            if not isinstance(r.get("id"), int):
                continue
            row = [str(ip), str(r["id"]), r["estado"]]
            if opts.get("alarmas"):
                alm = r.get("alarmas", {})
                row.append("ALARMA" if alm.get("seccionador") else ("OK" if r["estado"] == "COMUNICACION CORRECTA" else "-"))
                row.append("ALARMA" if alm.get("sobretension") else ("OK" if r["estado"] == "COMUNICACION CORRECTA" else "-"))
            if opts.get("diag"):
                d = r.get("diag", [])
                row.append(" / ".join(d) if d else "")
            if opts.get("voltaje"):
                v = r.get("voltaje")
                row.append(f"{v:.0f}" if v is not None else "")
            wr.writerow(row)

    csv_content = buf.getvalue()
    buf.close()

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plant_name}_{fecha}.csv".replace(" ", "_")

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

def _generate_pdf(res_gw: dict, orden: list, plant_name: str, stats: dict, opts: dict) -> StreamingResponse:
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Table, TableStyle, Paragraph, Spacer, PageBreak, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.pagesizes import A4

    AW, AH = A4
    CA = colors.HexColor
    CF = {"dark": "#0f172a", "med": "#1e293b", "border": "#334155", "primary": "#0ea5e9",
          "green": "#16a34a", "red": "#dc2626", "yellow": "#d97706", "orange": "#ea580c",
          "purple": "#7c3aed", "gtext": "#475569", "gclear": "#f1f5f9", "gmed": "#e2e8f0"}
    CE = {"COMUNICACION CORRECTA": CA(CF["green"]), "SIN COMUNICACION": CA(CF["red"]),
          "ERROR": CA(CF["red"]), "SIN CONEXION": CA(CF["purple"])}

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    fallos = stats["sin_com"] + stats["error"] + stats["sin_conexion"]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=2*cm, rightMargin=2*cm,
                          topMargin=2.8*cm, bottomMargin=1.8*cm)
    aw = AW - doc.leftMargin - doc.rightMargin
    fr = Frame(doc.leftMargin, doc.bottomMargin, aw, AH - doc.topMargin - doc.bottomMargin, id="n")
    doc.addPageTemplates([PageTemplate(id="normal", frames=[fr])])

    st = getSampleStyleSheet()
    def _s(nm, **kw):
        return ParagraphStyle(nm, parent=st["Normal"], **kw)
    sh1 = _s("h1", fontSize=22, fontName="Helvetica-Bold", textColor=CA(CF["dark"]), alignment=1, spaceAfter=6)
    sh2 = _s("h2", fontSize=11, fontName="Helvetica-Bold", textColor=CA(CF["primary"]), spaceBefore=14, spaceAfter=5)
    sh3 = _s("h3", fontSize=9.5, fontName="Helvetica-Bold", textColor=CA(CF["border"]), spaceBefore=8, spaceAfter=3)
    sn = _s("n", fontSize=8.5, textColor=CA(CF["gtext"]))
    sp = _s("p", fontSize=10, fontName="Helvetica", textColor=CA(CF["gtext"]), alignment=1)

    EST = [
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), CA(CF["med"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CA(CF["gclear"]), CA(CF["gmed"])]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, CA(CF["primary"])),
        ("GRID", (0, 1), (-1, -1), 0.35, CA("#cbd5e1")),
        ("BOX", (0, 0), (-1, -1), 0.8, CA(CF["border"])),
    ]

    elems = []

    # Portada
    elems += [Spacer(1, 2.5*cm),
              HRFlowable(width="100%", thickness=2.5, color=CA(CF["primary"]), spaceAfter=14),
              Paragraph("WEBDOM MONITOR - REPORTE", sh1),
              Spacer(1, 0.4*cm),
              HRFlowable(width="60%", thickness=0.8, color=CA(CF["border"]), spaceAfter=10),
              Paragraph(f"Planta: {plant_name}", _s("sub", fontSize=18, fontName="Helvetica-Bold",
                        textColor=CA(CF["dark"]), alignment=1, spaceAfter=14)),
              Paragraph(f"Generado el {fecha}", sp),
              Spacer(1, 1.0*cm),
              HRFlowable(width="100%", thickness=0.8, color=CA(CF["border"]), spaceAfter=12)]

    kw = aw / 3
    def kpi(lbl, val, sub, col):
        return Paragraph(
            f'<font size="7" color="#64748b"><b>{lbl}</b></font><br/><br/>'
            f'<font size="24" color="{col}"><b>{val}</b></font><br/>'
            f'<font size="10" color="#64748b">{sub}</font>',
            _s(f"kp{lbl[:2]}", alignment=1, leading=16))

    kt = Table([[kpi("TOTAL", str(stats["total"]), "cajas escaneadas", "#0f172a"),
                 kpi("COMUNICAN OK", str(stats["correcta"]), f"{stats['pct_correcta']:.1f}%", "#16a34a"),
                 kpi("CON FALLO", str(fallos), f"{stats['pct_fallo']:.1f}%", "#dc2626")]],
               colWidths=[kw]*3, rowHeights=[3.5*cm])
    kt.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER", (0, 0), (1, -1), 0.6, CA(CF["border"])),
        ("BOX", (0, 0), (-1, -1), 0.8, CA(CF["border"])),
        ("BACKGROUND", (0, 0), (-1, -1), CA(CF["gclear"])),
    ]))
    elems.append(kt)
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        f"Sin conexion: {stats['sin_conexion']} | Error lectura: {stats['error']} | Sin com Modbus: {stats['sin_com']}",
        _s("d", fontSize=8.5, textColor=CA(CF["gtext"]), alignment=1)))
    elems += [Spacer(1, 0.5*cm), HRFlowable(width="100%", thickness=2.5, color=CA(CF["primary"]), spaceAfter=6), PageBreak()]

    # Detalle por gateway
    elems.append(Paragraph("1. DETALLE POR GATEWAY", sh2))
    elems.append(HRFlowable(width="100%", thickness=0.8, color=CA(CF["primary"]), spaceAfter=8))

    usar_alarm = opts.get("alarmas", False)
    usar_diag = opts.get("diag", False)
    usar_volt = opts.get("voltaje", False)

    for ip in orden:
        res = res_gw.get(ip)
        if not res:
            continue
        elems.append(Paragraph(f"Gateway: {ip}", sh3))

        cab = ["GW IP", "ID", "ESTADO"]
        cw = [4.0*cm, 2.0*cm, 6.0*cm]
        if usar_alarm:
            cab.append("ALARMAS")
            cw.append(2.5*cm)
        if usar_diag:
            cab.append("DIAG")
            cw.append(2.2*cm)
        if usar_volt:
            cab.append("V DC")
            cw.append(1.6*cm)

        total_cw = sum(cw)
        if total_cw < aw - 0.5*cm:
            cw[-1] += (aw - 0.5*cm - total_cw)

        data = [cab]
        cmds = list(EST)
        idx_est = cab.index("ESTADO")
        idx_alr = cab.index("ALARMAS") if usar_alarm else None

        for r in res:
            if not isinstance(r.get("id"), int):
                continue
            est = r["estado"]
            row = [str(ip), str(r["id"]), est]
            c_est = CE.get(est)
            if c_est:
                cmds.append(("TEXTCOLOR", (idx_est, len(data)), (idx_est, len(data)), c_est))
                cmds.append(("FONTNAME", (idx_est, len(data)), (idx_est, len(data)), "Helvetica-Bold"))
            if usar_alarm:
                alm = r.get("alarmas", {})
                al_txt = []
                if alm.get("seccionador"):
                    al_txt.append("SECC.")
                if alm.get("sobretension"):
                    al_txt.append("SOBRETEN.")
                cel = " / ".join(al_txt) if al_txt else ("OK" if est == "COMUNICACION CORRECTA" else "-")
                row.append(cel)
                if al_txt:
                    cmds.append(("TEXTCOLOR", (idx_alr, len(data)-1), (idx_alr, len(data)-1), CA(CF["orange"])))
                    cmds.append(("FONTNAME", (idx_alr, len(data)-1), (idx_alr, len(data)-1), "Helvetica-Bold"))
            if usar_diag:
                d = r.get("diag", [])
                row.append(" / ".join(d) if d else ("-" if est != "COMUNICACION CORRECTA" else ""))
            if usar_volt:
                v = r.get("voltaje")
                row.append(f"{v:.0f}V" if v is not None else "-")
            data.append(row)

        if len(data) > 1:
            t = Table(data, colWidths=cw, repeatRows=1)
            t.setStyle(TableStyle(cmds))
            elems.append(t)
            elems.append(Spacer(1, 0.4*cm))

    # Resumen incidencias
    elems += [Spacer(1, 0.3*cm),
              Paragraph("2. RESUMEN DE INCIDENCIAS", sh2),
              HRFlowable(width="100%", thickness=0.8, color=CA(CF["red"]), spaceAfter=8),
              Paragraph(f"Total: {stats['total']} cajas | Correctas: {stats['correcta']} ({stats['pct_correcta']:.1f}%) | Fallos: {fallos} ({stats['pct_fallo']:.1f}%)", sn),
              Spacer(1, 0.3*cm)]

    data2 = [["GW IP", "ID", "ESTADO"]]
    cw2 = [4.5*cm, 2.5*cm, 8.2*cm]
    hay = False
    for ip in orden:
        for r in (res_gw.get(ip) or []):
            if r["estado"] != "COMUNICACION CORRECTA":
                hay = True
                data2.append([str(ip), str(r["id"]), r["estado"]])
    if hay:
        ie = [("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
              ("RIGHTPADDING", (0, 0), (-1, -1), 6),
              ("BACKGROUND", (0, 0), (-1, 0), CA("#7f1d1d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
              ("LINEBELOW", (0, 0), (-1, 0), 1.2, CA("#f87171")),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CA("#fff1f2"), CA("#ffe4e6")]),
              ("GRID", (0, 1), (-1, -1), 0.35, CA("#fca5a5")), ("BOX", (0, 0), (-1, -1), 0.8, CA("#ef4444"))]
        ti = Table(data2, colWidths=cw2, repeatRows=1)
        ti.setStyle(TableStyle(ie))
        elems.append(ti)
    else:
        elems.append(Paragraph("Sin incidencias. Todos los dispositivos comunican correctamente.", sn))

    # Alarmas
    if usar_alarm:
        cajas_alm = []
        for ip in orden:
            for r in (res_gw.get(ip) or []):
                alm = r.get("alarmas", {})
                if alm:
                    cajas_alm.append({"ip": ip, "id": r["id"], "alarmas": alm})
        ns = sum(1 for x in cajas_alm if x["alarmas"].get("seccionador"))
        nb = sum(1 for x in cajas_alm if x["alarmas"].get("sobretension"))

        elems += [Spacer(1, 0.4*cm),
                  Paragraph("3. ALARMAS", sh2),
                  HRFlowable(width="100%", thickness=0.8, color=CA(CF["orange"]), spaceAfter=8),
                  Paragraph(f"Seccionador abierto: {ns} | Sobretension: {nb} | Total con alarma: {len(cajas_alm)}", sn),
                  Spacer(1, 0.3*cm)]
        if cajas_alm:
            ca2 = ["GW IP", "ID", "SECCIONADOR", "SOBRETENSION"]
            cwa = [4.5*cm, 2.0*cm, 3.5*cm, 3.5*cm]
            da = [ca2]
            ae = [("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                  ("BACKGROUND", (0, 0), (-1, 0), CA("#7c2d12")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                  ("LINEBELOW", (0, 0), (-1, 0), 1.2, CA("#fb923c")),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CA("#fff7ed"), CA("#ffedd5")]),
                  ("GRID", (0, 1), (-1, -1), 0.35, CA("#fdba74")),
                  ("BOX", (0, 0), (-1, -1), 0.8, CA("#ea580c")),
                  ("TEXTCOLOR", (0, 1), (-1, -1), CA("#9a3412")),
                  ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold")]
            is_ = ca2.index("SECCIONADOR")
            ib_ = ca2.index("SOBRETENSION")
            for i, item in enumerate(cajas_alm, 1):
                s_ = "ABIERTO" if item["alarmas"].get("seccionador") else "OK"
                b_ = "ALARMA" if item["alarmas"].get("sobretension") else "OK"
                da.append([str(item["ip"]), str(item["id"]), s_, b_])
                ae.append(("TEXTCOLOR", (is_, i), (is_, i), CA(CF["orange"]) if item["alarmas"].get("seccionador") else CA(CF["green"])))
                ae.append(("TEXTCOLOR", (ib_, i), (ib_, i), CA(CF["orange"]) if item["alarmas"].get("sobretension") else CA(CF["green"])))
            ta = Table(da, colWidths=cwa, repeatRows=1)
            ta.setStyle(TableStyle(ae))
            elems.append(ta)
        else:
            elems.append(Paragraph("No se han detectado alarmas.", sn))

    doc.build(elems)
    buf.seek(0)

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plant_name}_{fecha}.pdf".replace(" ", "_")

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
