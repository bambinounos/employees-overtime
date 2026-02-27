# Manual de Usuario — Modulo PsicoEvaluacion v2

## Indice

1. [Resumen del sistema](#1-resumen-del-sistema)
2. [Configuracion de Perfiles Objetivo](#2-configuracion-de-perfiles-objetivo)
3. [Perfiles recomendados por tipo de cargo](#3-perfiles-recomendados-por-tipo-de-cargo)
4. [Crear una evaluacion](#4-crear-una-evaluacion)
5. [Que hace el candidato](#5-que-hace-el-candidato)
6. [Revisar pruebas proyectivas](#6-revisar-pruebas-proyectivas)
7. [Calcular resultados](#7-calcular-resultados)
8. [Interpretar los resultados](#8-interpretar-los-resultados)
9. [Asignar veredicto final](#9-asignar-veredicto-final)
10. [Controles de confiabilidad (v2)](#10-controles-de-confiabilidad-v2)
11. [Referencia de formulas](#11-referencia-de-formulas)
12. [Escenarios comunes](#12-escenarios-comunes)
13. [Administracion avanzada](#13-administracion-avanzada)

---

## 1. Resumen del sistema

PsicoEvaluacion es un modulo de evaluacion psicologica para candidatos. Cuenta con una bateria de **343 preguntas** distribuidas en **11 pruebas** que miden personalidad, compromiso, obediencia, inteligencia, memoria y comportamiento situacional.

### Flujo general

```
Evaluador crea evaluacion ──► Sistema genera link con token
                                     │
                              Candidato accede al link
                              (tiene 48 horas)
                                     │
                              Candidato completa las pruebas
                                     │
                              Evaluador revisa pruebas proyectivas
                              (dibujos y frases — puntuacion manual)
                                     │
                              Sistema calcula resultados automaticamente
                                     │
                              Sistema asigna veredicto automatico
                              (APTO / NO APTO / REVISION)
                                     │
                              Evaluador puede confirmar o sobrescribir
```

### Que es automatico y que es manual

| Automatico | Manual |
|-----------|--------|
| Generacion de token y link | Crear la evaluacion |
| Expiracion a las 48 horas | Enviar el link al candidato |
| Seleccion aleatoria de preguntas | Revisar pruebas proyectivas (dibujos/frases) |
| Calculo de TODOS los puntajes | Asignar puntuacion a proyectivas (1-10) |
| Verificacion de deseabilidad social | Sobrescribir veredicto (opcional) |
| Verificacion de consistencia | Agregar notas/observaciones |
| Veredicto automatico | |
| Seguimiento de IP y tiempos | |

---

## 2. Configuracion de Perfiles Objetivo

El **Perfil Objetivo** define los umbrales minimos que un candidato debe cumplir para ser considerado APTO. Se configura en:

```
https://salarios.hellbam.com/admin/psicoevaluacion/perfilobjetivo/
```

### Campos del Perfil Objetivo

| Campo | Escala | Default | Que mide |
|-------|--------|---------|----------|
| **nombre** | Texto | "Perfil Estandar" | Nombre descriptivo del perfil |
| **min_responsabilidad** | 1.0 - 5.0 | 4.0 | Que tan organizado, cumplidor y disciplinado es. Sacado del Big Five. |
| **min_amabilidad** | 1.0 - 5.0 | 3.0 | Empatia, cooperacion, trato con otros. Sacado del Big Five. |
| **max_neuroticismo** | 1.0 - 5.0 | 3.0 | Inestabilidad emocional (escala INVERSA: mas bajo = mas estable). Si el candidato saca MAS que este numero, falla. |
| **min_apertura** | 1.0 - 5.0 | 2.5 | Creatividad, curiosidad, apertura al cambio. Sacado del Big Five. |
| **min_extroversion** | 1.0 - 5.0 | 2.0 | Sociabilidad, energia en grupo. Sacado del Big Five. |
| **min_compromiso_organizacional** | 1.0 - 5.0 | 3.5 | Lealtad y vinculacion emocional con la empresa (Allen & Meyer). |
| **min_obediencia** | 1.0 - 5.0 | 3.5 | Disposicion a seguir reglas, acatar instrucciones, respetar jerarquia. |
| **min_memoria** | 0 - 100% | 60.0 | Porcentaje de secuencias recordadas correctamente. |
| **min_matrices** | 0 - 100% | 50.0 | Porcentaje de aciertos en matrices progresivas (razonamiento logico). |
| **min_situacional** | 0 - 100% | 60.0 | Puntaje en escenarios laborales hipoteticos (nota: este campo no se usa en el veredicto automatico actual, pero se almacena). |
| **activo** | Si/No | Si | Solo los perfiles activos aparecen para seleccionar. |

### Criterios que usa el veredicto automatico

El sistema verifica **6 criterios** contra el perfil. Si falla alguno, cuenta como un "fallo":

1. `puntaje_responsabilidad < min_responsabilidad` → +1 fallo
2. `puntaje_compromiso_total < min_compromiso_organizacional` → +1 fallo
3. `puntaje_obediencia < min_obediencia` → +1 fallo
4. `puntaje_memoria < min_memoria` → +1 fallo
5. `puntaje_matrices < min_matrices` → +1 fallo
6. `puntaje_neuroticismo > max_neuroticismo` → +1 fallo (escala inversa)

**Reglas:**
- **0 fallos** y proyectivas revisadas → **APTO**
- **1 fallo** o proyectivas pendientes → **REVISION**
- **2+ fallos** → **NO APTO**
- Si la evaluacion **no es confiable** (deseabilidad alta o consistencia baja) → **REVISION** sin importar los puntajes

---

## 3. Perfiles recomendados por tipo de cargo

### Perfil "Cargo de Confianza / Liderazgo" (Exigente)

Para gerentes, supervisores, jefes de area, cargos con manejo de informacion sensible:

| Campo | Valor | Razon |
|-------|-------|-------|
| min_responsabilidad | **4.5** | Debe ser extremadamente cumplidor |
| min_amabilidad | **3.5** | Necesita manejar equipos con empatia |
| max_neuroticismo | **2.5** | Debe mantener la calma bajo presion |
| min_apertura | **3.0** | Necesita pensamiento estrategico |
| min_extroversion | **3.0** | Debe comunicarse y liderar |
| min_compromiso | **4.0** | Alta lealtad requerida |
| min_obediencia | **3.5** | Respeta estructura pero puede decidir |
| min_memoria | **70** | Maneja multiples responsabilidades |
| min_matrices | **65** | Necesita razonamiento logico alto |

### Perfil "Atencion al Cliente / Ventas" (Moderado)

Para vendedores, recepcionistas, soporte al cliente:

| Campo | Valor | Razon |
|-------|-------|-------|
| min_responsabilidad | **3.5** | Debe cumplir pero con flexibilidad |
| min_amabilidad | **4.0** | **Critico** — trato constante con personas |
| max_neuroticismo | **3.5** | Tolerancia a clientes dificiles |
| min_apertura | **2.5** | No es critico |
| min_extroversion | **3.5** | Debe ser sociable y comunicativo |
| min_compromiso | **3.0** | Compromiso razonable |
| min_obediencia | **3.0** | Sigue protocolos pero resuelve |
| min_memoria | **55** | Retener informacion de clientes |
| min_matrices | **45** | No requiere razonamiento complejo |

### Perfil "Operativo / Entrada" (Flexible)

Para asistentes, operarios, puestos de entrada con supervision directa:

| Campo | Valor | Razon |
|-------|-------|-------|
| min_responsabilidad | **3.0** | Basico — con supervision |
| min_amabilidad | **2.5** | Minimo para convivencia |
| max_neuroticismo | **3.5** | Tolerancia moderada |
| min_apertura | **2.0** | No critico |
| min_extroversion | **2.0** | Puede ser introvertido |
| min_compromiso | **3.0** | Minimo razonable |
| min_obediencia | **3.5** | **Importante** — debe seguir instrucciones |
| min_memoria | **50** | Basico |
| min_matrices | **40** | Basico |

### Perfil "Seguridad / Custodia" (Estricto en obediencia)

Para guardias, custodios, personal militar o de seguridad:

| Campo | Valor | Razon |
|-------|-------|-------|
| min_responsabilidad | **4.5** | Disciplina total |
| min_amabilidad | **2.5** | No critico para el puesto |
| max_neuroticismo | **2.5** | Debe ser emocionalmente estable |
| min_apertura | **2.0** | Sigue protocolos, no innova |
| min_extroversion | **2.0** | No critico |
| min_compromiso | **4.0** | Lealtad institucional alta |
| min_obediencia | **4.5** | **Critico** — acata ordenes sin dudar |
| min_memoria | **65** | Retener instrucciones y procedimientos |
| min_matrices | **50** | Razonamiento basico |

---

## 4. Crear una evaluacion

### Desde el panel del evaluador

1. Ir a `https://salarios.hellbam.com/psicoevaluacion/panel/crear/`
2. Llenar los datos del candidato:
   - **Nombres completos**
   - **Cedula**
   - **Correo electronico**
   - **Cargo al que postula**
   - **Perfil objetivo** — seleccionar el perfil que corresponda al cargo
3. Hacer clic en **Crear Evaluacion**

### Que pasa internamente

- Se genera un **token unico** de 64 caracteres (seguro e irrepetible)
- Se establece la **fecha de expiracion** a 48 horas desde la creacion
- Se ejecuta la **seleccion aleatoria de preguntas** (v2): de las 343 preguntas del banco, se selecciona un subconjunto balanceado por dimension
- El estado queda como **PENDIENTE**

### El link para el candidato

El link tiene esta forma:

```
https://salarios.hellbam.com/psicoevaluacion/evaluar/abc123def456.../
```

Envie este link al candidato por correo o WhatsApp. **El candidato tiene 48 horas** para completar las pruebas.

---

## 5. Que hace el candidato

El candidato NO necesita cuenta ni login. Solo necesita el link.

### Proceso del candidato

1. **Accede al link** → Ve la pagina de bienvenida con instrucciones generales
2. **Verifica su identidad** → Confirma nombre y cedula
3. **Realiza las pruebas** en este orden:
   - Big Five (personalidad) — preguntas tipo Likert 1-5
   - Compromiso Organizacional — preguntas tipo Likert 1-5
   - Obediencia y Conformidad — preguntas tipo Likert 1-5
   - Test de Memoria — recordar secuencias de digitos
   - Matrices Progresivas — patrones logicos (con tiempo limite de 20 min)
   - Test del Arbol — dibujar un arbol en canvas
   - Persona bajo la Lluvia — dibujar una persona bajo la lluvia
   - Frases Incompletas — completar 30-50 frases
   - Test de Colores — ordenar colores por preferencia
   - Prueba Situacional — escenarios laborales hipoteticos
   - Deseabilidad Social — preguntas de validacion
4. **Finaliza** → Ve pantalla de agradecimiento

### Datos que el sistema captura automaticamente

- Direccion IP del candidato
- Navegador y dispositivo (user agent)
- Tiempo de respuesta por pregunta (en segundos)
- Fecha y hora exacta de cada respuesta
- Prueba actual (para retomar si se interrumpe)

### Si el candidato se interrumpe

Puede retomar dentro de las 48 horas. El sistema recuerda en que prueba se quedo.

---

## 6. Revisar pruebas proyectivas

**Esto es OBLIGATORIO antes de calcular resultados.**

Las pruebas proyectivas requieren evaluacion humana porque involucran dibujos y textos libres.

### Como acceder

```
https://salarios.hellbam.com/psicoevaluacion/panel/evaluacion/<ID>/revisar-proyectivas/
```

O desde el dashboard, buscar la evaluacion y hacer clic en "Revisar Proyectivas".

### Que revisar

| Prueba | Tipo | Que buscar |
|--------|------|-----------|
| **Test del Arbol** | Dibujo | Tamano, ubicacion, raices, copa, tronco, detalles. Arboles pequenos = inseguridad. Sin raices = inestabilidad. |
| **Persona bajo la Lluvia** | Dibujo | Tiene paraguas? (recursos de defensa). Gotas grandes? (presion percibida). Persona pequena? (baja autoestima). |
| **Frases Incompletas** | Texto | Leer cada completacion. Buscar actitudes negativas hacia autoridad, trabajo o compromiso. Respuestas evasivas o agresivas. |
| **Test de Colores** | Seleccion | Orden de preferencia de colores segun interpretacion Luscher. |

### Puntuacion

Para cada respuesta proyectiva:
- Asignar **puntuacion manual** de 1 a 10
- Escribir **observaciones** (lo que se interpreta)
- Marcar como **revisado** (checkbox)

**IMPORTANTE:** Si quedan proyectivas sin revisar (`revisado=False`), el veredicto automatico siempre sera REVISION.

---

## 7. Calcular resultados

Una vez que todas las pruebas proyectivas estan revisadas:

1. Ir a la evaluacion: `https://salarios.hellbam.com/psicoevaluacion/panel/evaluacion/<ID>/`
2. Hacer clic en **Calcular Resultados**

El sistema ejecuta automaticamente:
1. Verifica deseabilidad social y consistencia (confiabilidad)
2. Calcula Big Five (5 dimensiones)
3. Calcula Compromiso Organizacional (3 subdimensiones + total)
4. Calcula Obediencia
5. Calcula % memoria y max span
6. Calcula % matrices (ponderado por dificultad)
7. Calcula puntaje situacional (3 subdimensiones)
8. Calcula indices compuestos (responsabilidad total, lealtad, obediencia total)
9. Compara contra el perfil objetivo y asigna veredicto automatico

---

## 8. Interpretar los resultados

### Puntajes por prueba

| Puntaje | Escala | Bajo | Normal | Alto |
|---------|--------|------|--------|------|
| Responsabilidad (Big Five) | 1-5 | < 3.0 | 3.0-4.0 | > 4.0 |
| Amabilidad (Big Five) | 1-5 | < 2.5 | 2.5-3.5 | > 3.5 |
| Neuroticismo (Big Five) | 1-5 | < 2.0 (estable) | 2.0-3.5 | > 3.5 (inestable) |
| Apertura (Big Five) | 1-5 | < 2.5 | 2.5-3.5 | > 3.5 |
| Extroversion (Big Five) | 1-5 | < 2.5 | 2.5-3.5 | > 3.5 |
| Compromiso Total | 1-5 | < 3.0 | 3.0-4.0 | > 4.0 |
| Obediencia | 1-5 | < 3.0 | 3.0-4.0 | > 4.0 |
| Memoria | 0-100% | < 50% | 50-75% | > 75% |
| Matrices | 0-100% | < 40% | 40-70% | > 70% |
| Deseabilidad Social | 1-5 | < 2.5 (honesto) | 2.5-3.5 | > 4.0 (sospechoso) |
| Consistencia | 0-100% | < 60% (sospechoso) | 60-80% | > 80% (confiable) |

### Indices compuestos

| Indice | Formula | Que indica |
|--------|---------|-----------|
| **Responsabilidad Total** | 50% Big Five + 30% Situacional + 20% Memoria | Que tan confiable y cumplidor sera en el puesto |
| **Lealtad** | 60% Compromiso + 20% Responsabilidad + 20% Obediencia | Probabilidad de permanencia y fidelidad |
| **Obediencia Total** | 60% Escala Obediencia + 40% Situacional | Disposicion a seguir reglas e instrucciones |

### Banderas rojas

- **Deseabilidad Social > 4.0**: El candidato probablemente esta mintiendo o exagerando sus respuestas positivas
- **Consistencia < 60%**: El candidato contesto de forma aleatoria, inconsistente, o no presto atencion
- **Neuroticismo > 4.0**: Alta inestabilidad emocional
- **Responsabilidad < 2.5**: Problemas serios de disciplina y cumplimiento
- **Obediencia < 2.5**: Resistencia marcada a la autoridad

---

## 9. Asignar veredicto final

### Veredicto automatico vs manual

El sistema asigna un **veredicto automatico** basado en los umbrales del perfil. El evaluador puede:

- **Confirmar** el veredicto automatico (lo mas comun)
- **Sobrescribir** con un veredicto diferente si tiene razones justificadas

### Como asignar

1. Ir a `https://salarios.hellbam.com/psicoevaluacion/panel/evaluacion/<ID>/veredicto/`
2. Revisar el veredicto automatico
3. Seleccionar el veredicto final: **APTO**, **NO APTO** o **REVISION**
4. Agregar observaciones explicando la decision
5. Guardar

### Cuando sobrescribir

| Situacion | Veredicto automatico | Accion sugerida |
|-----------|---------------------|----------------|
| Todo bien, proyectivas normales | APTO | Confirmar APTO |
| Un solo fallo menor y proyectivas excelentes | REVISION | Considerar APTO |
| Falla en 2+ criterios | NO APTO | Confirmar NO APTO |
| Deseabilidad alta pero entrevista personal fue buena | REVISION | Evaluar caso a caso |
| Consistencia baja (< 60%) | REVISION | Considerar re-evaluacion o NO APTO |
| Proyectivas revelan problemas graves no detectados en psicometricas | APTO | Sobrescribir a REVISION o NO APTO |

---

## 10. Controles de confiabilidad (v2)

### Escala de Deseabilidad Social

Son 12 preguntas disenadas para detectar si el candidato esta respondiendo de forma "socialmente deseable" (mintiendo para verse bien).

Ejemplos de preguntas:
- "Nunca he dicho una mentira en mi vida"
- "Jamas he sentido envidia por los logros de otra persona"
- "Siempre soy completamente honesto/a en todas las situaciones"

Una persona honesta normalmente **no** estaria "totalmente de acuerdo" con estas afirmaciones. Si el promedio es > 4.0, el candidato probablemente esta falseando sus respuestas.

**Umbral:** Promedio > 4.0 → evaluacion marcada como **no confiable**

### Pares de consistencia

8 pares de preguntas que miden lo mismo pero con diferente redaccion. Se distribuyen en Big Five, Compromiso, Obediencia y Situacional.

Ejemplo de par:
- Pregunta A: "Siempre termino lo que empiezo, sin importar cuanto tiempo me tome"
- Pregunta B: "Cuando asumo un compromiso, lo cumplo sin excusas"

Si el candidato responde 5 en una y 1 en la otra, algo no cuadra.

**Formula:** `concordancia = 1 - (|respuesta_A - respuesta_B| / 4)` por cada par
**Umbral:** Promedio < 60% → evaluacion marcada como **no confiable**

### Efecto en el veredicto

Si la evaluacion es **no confiable**, el veredicto automatico es **REVISION** obligatoriamente, sin importar que todos los otros puntajes sean perfectos. El evaluador decide que hacer:

- Solicitar **re-evaluacion** presencial
- Complementar con **entrevista** profunda
- Marcar como **NO APTO** si la evidencia es clara

---

## 11. Referencia de formulas

### Big Five (cada dimension)
```
Para cada pregunta de la dimension:
  Si es_inversa: valor = 6 - valor_original
  Sino: valor = valor_original
Puntaje = promedio(todos los valores)
Rango: 1.0 - 5.0
```

### Compromiso Total
```
Total = promedio(compromiso_afectivo, compromiso_normativo)
Nota: compromiso de continuidad NO se incluye en el total
Rango: 1.0 - 5.0
```

### Memoria
```
Porcentaje = (respuestas_correctas / total_respuestas) x 100
Max span = longitud de la secuencia mas larga recordada correctamente
```

### Matrices Progresivas (ponderado por dificultad)
```
Peso de pregunta i = 1 + (i x 0.1)
  Ejemplo: pregunta 1 = peso 1.0, pregunta 10 = peso 2.0, pregunta 20 = peso 3.0
Puntaje = (suma_aciertos_ponderados / suma_pesos_totales) x 100
```

### Indice de Responsabilidad Total
```
= (puntaje_responsabilidad x 0.5)
+ (puntaje_situacional / 20 x 0.3)
+ (puntaje_memoria / 20 x 0.2)
```

### Indice de Lealtad
```
= (puntaje_compromiso_total x 0.6)
+ (puntaje_responsabilidad x 0.2)
+ (puntaje_obediencia x 0.2)
```

### Indice de Obediencia Total
```
= (puntaje_obediencia x 0.6)
+ (puntaje_situacional / 20 x 0.4)
```

### Consistencia (por par)
```
concordancia = 1 - (|valor_ajustado_A - valor_ajustado_B| / 4)
  donde valor_ajustado = 6 - valor si es_inversa, sino valor
Indice final = promedio(todas las concordancias) x 100
Rango: 0% - 100%
```

---

## 12. Escenarios comunes

### Candidato perfecto
- Todos los puntajes superan los umbrales
- Deseabilidad < 4.0
- Consistencia > 60%
- Proyectivas revisadas y normales
- **Resultado:** APTO automaticamente

### Candidato con un area debil
- Falla en un solo criterio (ej. memoria = 55% con minimo 60%)
- Todo lo demas esta bien
- **Resultado:** REVISION
- **Accion:** Evaluar si esa area es critica para el puesto. Si no, el evaluador puede marcar APTO manualmente.

### Candidato que falla multiples areas
- Falla en 2+ criterios
- **Resultado:** NO APTO automaticamente
- **Accion:** Confirmar NO APTO. Si hay circunstancias atenuantes, el evaluador puede sobrescribir a REVISION.

### Candidato sospechoso de mentir
- Deseabilidad social > 4.0
- **Resultado:** REVISION (no confiable)
- **Accion:** Programar entrevista presencial. Comparar respuestas con impresion personal. Considerar re-evaluacion.

### Candidato que respondio al azar
- Consistencia < 60%
- **Resultado:** REVISION (no confiable)
- **Accion:** Muy probablemente NO APTO. El candidato no tomo la evaluacion en serio o intento manipularla.

### Proyectivas pendientes
- El evaluador no ha revisado los dibujos/frases
- **Resultado:** REVISION automaticamente (sin importar puntajes)
- **Accion:** Completar la revision de proyectivas y recalcular.

---

## 13. Administracion avanzada

### Panel de administracion Django

Acceder a: `https://salarios.hellbam.com/admin/psicoevaluacion/`

#### Perfiles Objetivo
- Crear multiples perfiles para diferentes cargos
- Editar umbrales directamente en la lista
- Solo los perfiles marcados como "activo" se pueden seleccionar al crear evaluaciones

#### Pruebas
- Ver todas las pruebas con su conteo de preguntas
- **items_banco**: total de preguntas disponibles en el banco
- **items_a_aplicar**: cuantas se seleccionan por evaluacion (0 = todas)
- Activar/desactivar pruebas individuales
- Cambiar orden de presentacion

#### Preguntas
- Buscar preguntas por texto
- Filtrar por prueba, dimension, tipo de escala
- Ver cuales son inversas
- Ver pares de consistencia vinculados

#### Resultados
- Ver todos los puntajes calculados (solo lectura)
- Filtrar por veredicto y confiabilidad
- Columna `evaluacion_confiable` para identificar rapidamente evaluaciones sospechosas

### Cargar banco de preguntas

Si necesita recargar o actualizar las preguntas:

```bash
python3 manage.py seed_pruebas
```

Este comando es **idempotente** — se puede ejecutar multiples veces sin duplicar datos.

### Limpiar evaluaciones expiradas

```bash
python3 manage.py limpiar_evaluaciones_expiradas
```

Marca como EXPIRADA las evaluaciones cuyo plazo de 48 horas vencio sin completarse.
