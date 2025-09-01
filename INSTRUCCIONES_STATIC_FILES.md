# Solución para el Problema de Archivos Estáticos (CSS/JS) en Apache

Hola,

Como hemos tenido problemas para enviar mensajes largos, he creado este archivo con las instrucciones detalladas para solucionar el problema de que no se carguen los estilos.

## El Problema

Hay una pequeña diferencia entre dónde Django está guardando los archivos estáticos y dónde Apache los está buscando.

-   **Apache (tu archivo `.conf`)** busca en: `/home/ubuntu/employees_overtime/staticfiles/`
-   **Django (tu archivo `settings.py`)** probablemente está configurado para guardarlos en una carpeta llamada `static/` por defecto.

## La Solución (3 Pasos)

Vamos a hacer que Django guarde los archivos en la carpeta `staticfiles/` para que coincida con lo que Apache espera.

---

### Paso 1: Editar `settings.py`

Abre el archivo `salary_management/settings.py`. Busca la línea `STATIC_ROOT` y asegúrate de que se vea exactamente así:

```python
# Al final de salary_management/settings.py

# STATIC_URL ya debería estar ahí
STATIC_URL = 'static/'

# Asegúrate de que esta línea esté así:
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles/')
```

---

### Paso 2: Ejecutar `collectstatic` de Nuevo

Este es el paso más importante. Después de guardar el cambio en `settings.py`, debes volver a ejecutar el comando `collectstatic`. Esto creará la carpeta `staticfiles/` y copiará todo allí.

En tu terminal (recuerda activar el entorno virtual con `source venv/bin/activate`):

```bash
python3 manage.py collectstatic
```

Cuando te pregunte si quieres sobrescribir los archivos, escribe `yes` y presiona Enter.

---

### Paso 3: Reiniciar Apache

Para que Apache aplique todos los cambios, reinícialo:

```bash
sudo systemctl restart apache2
```

---

Después de estos tres pasos, refresca la página en tu navegador (quizás necesites limpiar el caché con Ctrl+Shift+R o Cmd+Shift+R). Los estilos deberían cargar correctamente.
