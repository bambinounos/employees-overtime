# Solución para el Problema de Archivos Estáticos (CSS/JS) en Apache

Hola,

Nuestros mensajes se están cortando. He creado este archivo para darte la solución completa y definitiva.

## El Problema Exacto

Gracias al enlace de GitHub y tu configuración de Apache, el problema está 100% claro:

1.  **Tu Apache** está configurado para buscar los archivos estáticos en la carpeta: `/home/ubuntu/employees_overtime/staticfiles/`
2.  **Tu Django** no sabe que debe poner los archivos en esa carpeta. Por defecto, no los agrupa en ningún lado en un servidor de producción.
3.  El comando `ls` falló porque la carpeta `static/` no existía, lo cual es correcto. Necesitamos crear y usar `staticfiles/`.

## La Solución (3 Pasos)

Sigue estos 3 pasos en orden en la terminal de tu servidor.

---

### Paso 1: Editar `settings.py`

Vamos a decirle a Django que use la carpeta `staticfiles/`.

Abre el archivo `salary_management/settings.py`. Al final del todo, asegúrate de que estas dos líneas existan y se vean así:

```python
# salary_management/settings.py

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles/')
```
*(Es posible que necesites añadir `import os` al principio del archivo si no está ya allí).*

---

### Paso 2: Ejecutar `collectstatic`

Este comando agrupará todos los archivos CSS y JS en la carpeta `staticfiles/` que acabas de configurar.

En tu terminal (recuerda activar el entorno virtual primero con `source venv/bin/activate`):

```bash
python3 manage.py collectstatic
```

Te preguntará si quieres sobrescribir los archivos. Escribe `yes` y presiona Enter.

---

### Paso 3: Reiniciar Apache

Para que Apache reconozca la nueva carpeta y los archivos, reinicia el servicio:

```bash
sudo systemctl restart apache2
```

---

Después de esto, el problema debería estar resuelto. Limpia el caché de tu navegador (`Ctrl+Shift+R` o `Cmd+Shift+R`) y visita tu página. Los estilos deberían cargar.
