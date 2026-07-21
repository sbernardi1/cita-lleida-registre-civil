"""
Chequea disponibilidad de citas para "Jures de nacionalitat espanyola"
en la Oficina General del Registre Civil de Lleida, dentro de una ventana
de fechas objetivo. Si encuentra algún día disponible, manda un email de alerta.

Pensado para correr en GitHub Actions (o cualquier runner con Python + Playwright),
sin depender de ninguna computadora prendida.
"""

import asyncio
import os
import re
import smtplib
from datetime import date
from email.mime.text import MIMEText

from playwright.async_api import async_playwright

URL = (
    "https://ovt.gencat.cat/carpetaciutadana360/mfe-fc-app/gsitfc/AppJava/citpre/"
    "citpre.do?reqCode=simpleSearch&idTemaN2=25629&idTemaN3=27250&idOficina=1761"
)

# --- Ventana de fechas que nos interesa (editá acá si cambia) ---
WINDOW_START = date(2026, 9, 14)
WINDOW_END = date(2026, 12, 10)

# Meses de calendario que hay que revisar para cubrir la ventana de arriba
TARGET_MONTHS = [(2026, 9), (2026, 10), (2026, 11), (2026, 12)]

MONTH_MAP = {
    "gen": 1, "feb": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ag": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "des": 12,
}


def parse_month_year(text_month: str, text_year: str):
    key = text_month.strip().lower().rstrip(".")[:3]
    month = MONTH_MAP.get(key)
    if month is None:
        raise ValueError(f"No pude interpretar el mes: {text_month!r}")
    year = int(text_year.strip())
    return month, year


async def get_current_month_year(frame):
    month_text = await frame.locator(".ui-datepicker-month").inner_text()
    year_text = await frame.locator(".ui-datepicker-year").inner_text()
    return parse_month_year(month_text, year_text)


async def read_month_days(frame):
    days = await frame.eval_on_selector_all(
        "td span.ui-state-default",
        """els => els.map(el => ({
            text: el.textContent.trim(),
            disabled: el.className.includes('ui-state-disabled')
        }))""",
    )
    return [d for d in days if re.fullmatch(r"\d{1,2}", d["text"])]


async def check_availability():
    available_dates = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await _check_availability_inner(page, available_dates)
        except Exception:
            try:
                await page.screenshot(path="debug_failure.png", full_page=True)
            except Exception:
                pass
            raise
        finally:
            await browser.close()

    return sorted(set(available_dates))


async def _check_availability_inner(page, available_dates):
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        # La primera vez que se visita en una sesión nueva aparece un modal
        # de aviso ("Sortir ràpid") que bloquea los clics hasta cerrarlo.
        # Usamos un match parcial/case-insensitive porque "D'acord" puede
        # llevar una comilla tipográfica (') distinta de la recta (').
        for _ in range(3):
            overlay = page.locator(".ui-dialog-mask, .ui-widget-overlay")
            if await overlay.count() == 0:
                break
            try:
                accept_btn = page.get_by_role(
                    "button", name=re.compile("acord", re.IGNORECASE)
                )
                if await accept_btn.count() > 0:
                    await accept_btn.first.click(timeout=3000)
                else:
                    await page.keyboard.press("Escape")
            except Exception:
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
            await page.wait_for_timeout(500)

        # El formulario de cita vive dentro de un iframe (mismo origen)
        frame = next((f for f in page.frames if f != page.main_frame), None)
        if frame is None:
            raise RuntimeError("No se encontró el iframe del formulario de cita")

        date_input = frame.locator("input.ui-inputtext").first
        datepicker_title = frame.locator(".ui-datepicker-title")
        opened = False
        for attempt in range(4):
            try:
                await date_input.click(click_count=3, timeout=8000)
            except Exception:
                try:
                    await date_input.click(click_count=3, timeout=8000, force=True)
                except Exception:
                    pass
            try:
                await datepicker_title.wait_for(state="visible", timeout=4000)
                opened = True
                break
            except Exception:
                await page.wait_for_timeout(500)
        if not opened:
            raise RuntimeError("No se pudo abrir el selector de fecha (datepicker) tras varios intentos")
        await page.wait_for_timeout(300)

        prev_btn = frame.locator("a.ui-datepicker-prev")
        next_btn = frame.locator("a.ui-datepicker-next")

        cur_month, cur_year = await get_current_month_year(frame)
        cur_idx = cur_year * 12 + cur_month
        target_idx = TARGET_MONTHS[0][0] * 12 + TARGET_MONTHS[0][1]

        while cur_idx > target_idx:
            await prev_btn.click()
            await page.wait_for_timeout(300)
            cur_idx -= 1
        while cur_idx < target_idx:
            await next_btn.click()
            await page.wait_for_timeout(300)
            cur_idx += 1

        for (year, month) in TARGET_MONTHS:
            m, y = await get_current_month_year(frame)
            if (y, m) != (year, month):
                raise RuntimeError(f"Desfasaje de mes: esperaba {year}-{month}, vi {y}-{m}")

            for d in await read_month_days(frame):
                day_num = int(d["text"])
                try:
                    this_date = date(year, month, day_num)
                except ValueError:
                    continue
                if WINDOW_START <= this_date <= WINDOW_END and not d["disabled"]:
                    available_dates.append(this_date)

            if (year, month) != TARGET_MONTHS[-1]:
                await next_btn.click()
                await page.wait_for_timeout(300)


def send_email(available_dates):
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("ALERT_EMAIL", sender)

    fechas_str = "\n".join(f"- {d.strftime('%d/%m/%Y')}" for d in available_dates)
    body = (
        "Se encontraron citas disponibles para 'Jures de nacionalitat espanyola' "
        "en el Registre Civil de Lleida, dentro de la ventana "
        f"{WINDOW_START.strftime('%d/%m/%Y')} - {WINDOW_END.strftime('%d/%m/%Y')}:\n\n"
        f"{fechas_str}\n\n"
        "Reservá cuanto antes desde acá:\n"
        f"{URL}"
    )
    msg = MIMEText(body)
    msg["Subject"] = f"Cita disponible Registre Civil Lleida ({len(available_dates)} dia/s)"
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, [recipient], msg.as_string())


async def main():
    available = await check_availability()
    if available:
        print(f"ALERTA: {len(available)} dia(s) disponibles: {available}")
        send_email(available)
    else:
        print(
            f"Sin disponibilidad entre {WINDOW_START.strftime('%d/%m/%Y')} "
            f"y {WINDOW_END.strftime('%d/%m/%Y')}."
        )


if __name__ == "__main__":
    asyncio.run(main())
