# Chequeo automático de cita — Registre Civil de Lleida

Este script revisa, corriendo en la nube de GitHub (no en tu compu), si aparece
algún día disponible para "Jures de nacionalitat espanyola" en el Registre Civil
de Lleida, entre el **14/09/2026** y el **10/12/2026**. Si encuentra algo, te
manda un email de alerta.

## Archivos

- `check_cita.py` — el script que hace el chequeo (Python + Playwright).
- `.github/workflows/check-cita-lleida.yml` — la configuración que lo corre
  automáticamente varias veces al día.

## Pasos para activarlo

1. **Creá un repositorio en GitHub** (puede ser privado). Subí estos dos
   archivos manteniendo la carpeta `.github/workflows/` tal cual.

2. **Generá una "contraseña de aplicación" de Gmail** (necesaria para que el
   script pueda mandar el mail):
   - Activá la verificación en 2 pasos en tu cuenta de Google, si no la tenés:
     https://myaccount.google.com/security
   - Generá la contraseña de aplicación acá:
     https://myaccount.google.com/apppasswords
   - Elegí "Correo" / "Otra app" y copiá el código de 16 letras que te da.

3. **Cargá los secretos en GitHub**: en el repo, andá a
   `Settings → Secrets and variables → Actions → New repository secret` y
   creá:
   - `GMAIL_USER` → `stgobernardi@gmail.com`
   - `GMAIL_APP_PASSWORD` → el código de 16 letras del paso anterior
   - `ALERT_EMAIL` → `stgobernardi@gmail.com` (a dónde llega la alerta; podés
     poner otro mail si querés)

4. **Listo.** El workflow corre solo, 3 veces al día (6, 11 y 17 UTC ≈ 8, 13 y
   19h en España en horario de verano). Podés cambiar el horario editando la
   línea `cron` del archivo `.yml`, o correrlo a mano desde la pestaña
   **Actions** del repo con el botón "Run workflow".

## Notas

- El script solo mira y reporta — nunca completa ni reserva nada.
- Si el sitio de Gencat cambia su diseño, el script puede dejar de funcionar
  (los selectores están atados a la estructura actual de la página). Si eso
  pasa, avisame y lo actualizo.
- La ventana de fechas (14/09 – 10/12/2026) está al principio de
  `check_cita.py` (`WINDOW_START` / `WINDOW_END`) — se puede editar ahí.
