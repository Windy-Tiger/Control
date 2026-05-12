"""
Control — Email Alert Service
Periodic check for critical events, sends alerts via Resend.
Tracks sent alerts to avoid duplicates.
"""

import os
import json

from datetime import datetime, timezone
from typing import List, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.models.database import SessionLocal, Viagem, Config, LogEntry, gen_id, utcnow



RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "Control <alerts@resend.dev>")

# In-memory tracking of sent alerts to avoid duplicates
# Key: "{tenant_id}:{viagem_id}:{alert_type}:{date}" → True
_sent_alerts: Dict[str, bool] = {}


def _today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _alert_key(tenant_id: str, viagem_id: str, alert_type: str) -> str:
    return f"{tenant_id}:{viagem_id}:{alert_type}:{_today_key()}"


def _was_sent(tenant_id: str, viagem_id: str, alert_type: str) -> bool:
    return _sent_alerts.get(_alert_key(tenant_id, viagem_id, alert_type), False)


def _mark_sent(tenant_id: str, viagem_id: str, alert_type: str):
    _sent_alerts[_alert_key(tenant_id, viagem_id, alert_type)] = True


def _cleanup_old_keys():
    """Remove alert keys older than today to prevent memory growth."""
    today = _today_key()
    to_remove = [k for k in _sent_alerts if not k.endswith(today)]
    for k in to_remove:
        del _sent_alerts[k]


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend API."""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set — skipping email")
        return False

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": RESEND_FROM,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=10.0,
            )
            if r.status_code in (200, 201):
                print(f"Email sent to {to}: {subject}")
                return True
            else:
                print(f"Resend error {r.status_code}: {r.text}")
                return False
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


def _format_alert_email(alerts: List[Dict], tenant_name: str = "Control") -> str:
    """Build HTML email body from a list of alert dicts."""
    rows = ""
    for a in alerts:
        color = "#c62828" if a["severity"] == "critical" else "#f9a825" if a["severity"] == "warning" else "#1565c0"
        icon = "🚫" if a["severity"] == "critical" else "⚠️" if a["severity"] == "warning" else "ℹ️"
        rows += f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:10px;font-weight:600">{a['motorista']}</td>
            <td style="padding:10px">{a['t1']}</td>
            <td style="padding:10px">{a['fronteira']}</td>
            <td style="padding:10px;color:{color};font-weight:700">{icon} {a['message']}</td>
        </tr>"""

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <div style="background:#1a1814;padding:16px 20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0;color:#cda077;font-size:18px">Control — Alertas Operacionais</h2>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.5);font-size:12px">{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC</p>
        </div>
        <div style="background:#fff;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;padding:0">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead>
                    <tr style="background:#f5f5f5">
                        <th style="padding:10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:1px">Motorista</th>
                        <th style="padding:10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:1px">T1</th>
                        <th style="padding:10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:1px">Fronteira</th>
                        <th style="padding:10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:1px">Alerta</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        <p style="font-size:10px;color:#999;margin-top:12px;text-align:center">
            Enviado automaticamente pelo sistema Control. Não responda a este email.
        </p>
    </div>
    """


async def check_and_send_alerts():
    """
    Main alert check. Called periodically.
    Scans all tenants for active viagens with alert conditions.
    Sends one email per new alert event.
    """
    if not RESEND_API_KEY:
        print("[ALERTS] No RESEND_API_KEY — skipping")
        return

    _cleanup_old_keys()

    db: Session = SessionLocal()
    try:
        # Get all configs with email set
        configs = db.query(Config).filter(Config.email != None, Config.email != "").all()
        print(f"[ALERTS] Found {len(configs)} tenant(s) with alert email configured")

        for cfg in configs:
            tenant_id = cfg.tenant_id
            email = cfg.email
            warn_days = cfg.t1_alert_warning_days or 3
            crit_days = cfg.t1_alert_critical_days or 1
            alert_hours = cfg.alert_hours or 3

            # Get route baselines
            baselines = {}
            if cfg.route_baselines_json:
                try:
                    baselines = json.loads(cfg.route_baselines_json)
                except:
                    pass

            # Get active viagens for this tenant
            viagens = db.query(Viagem).filter(
                Viagem.tenant_id == tenant_id,
                Viagem.concluido == False,
            ).all()
            print(f"[ALERTS] Tenant {tenant_id}: {len(viagens)} active viagens, email={email}")

            alerts_to_send: List[Dict] = []
            now = datetime.now(timezone.utc)

            for v in viagens:
                # ── T1 Expiration ──
                if v.t1_validade:
                    days_left = (v.t1_validade.replace(tzinfo=timezone.utc) - now).total_seconds() / 86400

                    if days_left <= 0 and not _was_sent(tenant_id, v.id, "t1_expired"):
                        alerts_to_send.append({
                            "motorista": v.motorista or "—",
                            "t1": v.t1 or "—",
                            "fronteira": v.fronteira or "—",
                            "message": "T1 EXPIRADA",
                            "severity": "critical",
                        })
                        _mark_sent(tenant_id, v.id, "t1_expired")

                        # Also log it
                        db.add(LogEntry(viagem_id=v.id, user="SISTEMA", mov="viagem",
                            text=f"🚫 ALERTA: T1 expirada. Validade: {v.t1_validade.strftime('%d/%m/%Y')}"))

                    elif 0 < days_left <= crit_days and not _was_sent(tenant_id, v.id, "t1_critical"):
                        alerts_to_send.append({
                            "motorista": v.motorista or "—",
                            "t1": v.t1 or "—",
                            "fronteira": v.fronteira or "—",
                            "message": f"T1 expira em {days_left:.1f} dias",
                            "severity": "critical",
                        })
                        _mark_sent(tenant_id, v.id, "t1_critical")

                    elif crit_days < days_left <= warn_days and not _was_sent(tenant_id, v.id, "t1_warning"):
                        alerts_to_send.append({
                            "motorista": v.motorista or "—",
                            "t1": v.t1 or "—",
                            "fronteira": v.fronteira or "—",
                            "message": f"T1 expira em {days_left:.0f} dias",
                            "severity": "warning",
                        })
                        _mark_sent(tenant_id, v.id, "t1_warning")

                # ── Transit Overdue ──
                if v.saida and v.fronteira and v.fronteira in baselines:
                    baseline_days = baselines[v.fronteira]
                    saida_dt = v.saida.replace(tzinfo=timezone.utc) if v.saida.tzinfo is None else v.saida
                    days_in_transit = (now - saida_dt).total_seconds() / 86400

                    if days_in_transit > baseline_days and not _was_sent(tenant_id, v.id, "transit_overdue"):
                        alerts_to_send.append({
                            "motorista": v.motorista or "—",
                            "t1": v.t1 or "—",
                            "fronteira": v.fronteira or "—",
                            "message": f"Trânsito atrasado: dia {int(days_in_transit)}/{baseline_days}",
                            "severity": "warning",
                        })
                        _mark_sent(tenant_id, v.id, "transit_overdue")

                # ── Driver Unreachable ──
                if v.last_update:
                    last_dt = v.last_update.replace(tzinfo=timezone.utc) if v.last_update.tzinfo is None else v.last_update
                    hours_since = (now - last_dt).total_seconds() / 3600

                    if hours_since >= alert_hours and not _was_sent(tenant_id, v.id, "unreachable"):
                        alerts_to_send.append({
                            "motorista": v.motorista or "—",
                            "t1": v.t1 or "—",
                            "fronteira": v.fronteira or "—",
                            "message": f"Sem actualização há {hours_since:.0f}h",
                            "severity": "warning",
                        })
                        _mark_sent(tenant_id, v.id, "unreachable")

            # Send alerts if any
            if alerts_to_send:
                print(f"[ALERTS] {len(alerts_to_send)} alerts to send: {[a['message'] for a in alerts_to_send]}")
                subject = f"Control — {len(alerts_to_send)} alerta{'s' if len(alerts_to_send)>1 else ''} operacional"

                # Check if any critical
                has_critical = any(a["severity"] == "critical" for a in alerts_to_send)
                if has_critical:
                    subject = f"🚨 Control — ALERTA CRÍTICO ({len(alerts_to_send)} evento{'s' if len(alerts_to_send)>1 else ''})"

                html = _format_alert_email(alerts_to_send)
                await send_email(email, subject, html)

                print(f"Tenant {tenant_id}: sent {len(alerts_to_send)} alerts to {email}")

        db.commit()

    except Exception as e:
        print(f"Alert check failed: {e}")
        db.rollback()
    finally:
        db.close()
