"""
Cliente saliente hacia la API REST de Dolibarr (módulo nativo de salarios).

Transporte puro: recibe los objetos ya cargados, arma la petición y la envía.
No toca el ORM más allá de leer los datos que recibe ni usa messages; ante
cualquier problema lanza una excepción y el llamador (nomina.py) decide.
"""
import calendar
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 15.0  # el push es interactivo desde la vista de cierre de nómina


class DolibarrApiError(Exception):
    """La API de Dolibarr respondió con error (HTTP != 2xx o cuerpo inesperado)."""


def crear_salario(recibo, instancia, dolibarr_user_id):
    """Crea el registro de salario del mes en Dolibarr para un ReciboNomina.

    Solo el registro contable, SIN pago (paye=0): el pago se asienta a mano en
    Dolibarr al hacer la transferencia real. Devuelve el id (int, rowid de
    llx_salary). Lanza DolibarrApiError o httpx.HTTPError; el llamador captura.
    """
    url = instancia.api_base_url.rstrip('/') + '/api/index.php/salaries'
    headers = {
        'DOLAPIKEY': instancia.api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    # Dolibarr espera timestamps Unix para el período del salario.
    ultimo_dia = calendar.monthrange(recibo.year, recibo.month)[1]
    datesp = int(datetime(recibo.year, recibo.month, 1).timestamp())
    dateep = int(datetime(recibo.year, recibo.month, ultimo_dia).timestamp())

    payload = {
        'fk_user': dolibarr_user_id,
        'label': f"Nómina {recibo.year}-{recibo.month:02d} — {recibo.employee.name}",
        'amount': str(recibo.total),   # str: no perder precisión del Decimal en JSON
        'datesp': datesp,
        'dateep': dateep,
        'paye': 0,                     # NO pagado: registro sin pago asociado
    }

    resp = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    if not (200 <= resp.status_code < 300):
        # 403 = el usuario del DOLAPIKEY no tiene permiso "salaries → write";
        # 500 = Dolibarr devuelve un array de errores de validación.
        raise DolibarrApiError(f"HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
        salary_id = int(data if isinstance(data, int) else data.get('id'))
    except (ValueError, TypeError, AttributeError):
        raise DolibarrApiError(f"Respuesta inesperada de Dolibarr: {resp.text[:500]}")

    logger.info("Salario creado en Dolibarr '%s': recibo #%s → salary id %s",
                instancia.name, recibo.pk, salary_id)
    return salary_id
