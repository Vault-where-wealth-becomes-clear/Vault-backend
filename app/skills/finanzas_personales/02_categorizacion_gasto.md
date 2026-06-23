## Módulo 2: categorización-de-gasto

### Objetivo

Agrupar todos los gastos del período en categorías, y clasificar los ingresos por recurrencia para el cálculo correcto de la tasa de ahorro operativa.

### Fuentes de datos

| Tipo de movimiento | ¿Se categoriza? | Detalle |
|-------------------|----------------|---------|
| EXTERNO SALIDA | **Sí** | Es un gasto. Asignar categoría según descripción |
| REINTEGRO | **Sí (como negativo)** | Netea en la categoría del gasto original |
| LIQ.DEUDA | **No** | El gasto ya fue categorizado en el mes de la compra |
| INTERNO | **No** | Transferencia entre cuentas propias, neutro |
| EXTERNO ENTRADA | **Sí (como ingreso)** | Clasificar por recurrencia (ver sección siguiente) |
| RENDIMIENTO | **No** | Ingreso especial — se reporta por separado en el Tablero |

### Categorías estándar (12)

| Categoría | Qué incluye |
|-----------|-------------|
| SUPERMERCADO | Alimentos en super/hipermercados, almacenes, verdulerías |
| RESTAURANTES | Comidas fuera de casa, delivery, cafeterías, bares |
| TRANSPORTE | Nafta, peajes, estacionamiento, transporte público, remises, Uber |
| SALUD | Médicos, farmacia, prepagas, obra social, óptica, odontología |
| INDUMENTARIA | Ropa, calzado, accesorios, bijouterie |
| TECNOLOGÍA | Equipos, software, suscripciones digitales (Netflix, Spotify, etc.) |
| ENTRETENIMIENTO | Salidas, cine, teatro, deporte, juegos, cultura |
| SERVICIOS | Luz, gas, agua, internet, teléfono, alquiler, expensas |
| EDUCACIÓN | Cursos, libros, capacitación, colegio, universidad |
| VIAJES | Hoteles, vuelos, turismo, excursiones, alojamiento temporario |
| INVERSIONES | Depósitos a plazo, aportes a fondos de inversión (excluye compra de divisas — ver CONVERSIÓN PATRIMONIAL) |
| VARIOS | Todo lo que no encaja en otra categoría |

**Subcategorías especiales (no son categorías de gasto — no afectan la tasa de ahorro):**

| Subcategoría | Cuándo se usa |
|-------------|--------------|
| CONVERSIÓN PATRIMONIAL | Compra de divisas o moneda extranjera sin cuenta de destino declarada en el sistema. Aparece como línea separada en el Tablero — no suma al gasto total ni penaliza la tasa de ahorro operativa. |

Solo agregar categorías nuevas si el usuario lo solicita explícitamente.

### Regla de neto por categoría

```
Gasto_neto_categoría = Gasto_bruto_categoría − Σ(Reintegros de esa categoría)
```

- El neto **puede ser negativo** si los reintegros superan al gasto bruto en el período.
- Los REINTEGROS siempre netan en su **categoría original** — nunca en VARIOS.
- Si no se puede determinar la categoría del reintegro, preguntar al usuario antes de asignar.

### Clasificación de ingresos por recurrencia

Al registrar un movimiento EXTERNO ENTRADA, el sistema evalúa su tamaño relativo al historial del período:

**Regla de activación:**
Si el monto del EXTERNO ENTRADA supera el **doble del promedio histórico** de EXTERNO ENTRADA recurrentes de los meses previos disponibles → Claude pregunta:

> *"Registré un ingreso de $[monto] el [fecha], que es significativamente mayor a tu promedio. ¿Es un ingreso extraordinario (venta, regalo, reembolso único, bono puntual) o es recurrente?"*

Según respuesta, el ingreso se etiqueta:
- `recurrencia: recurrente`
- `recurrencia: extraordinario`

**Impacto en el Tablero General:**
- Los ingresos extraordinarios se muestran como línea separada en el panel de métricas.
- Se **excluyen** del cálculo de promedio de ingresos operativos para la proyección (Módulo 6).
- La tasa de ahorro se calcula sobre **ingresos operativos recurrentes únicamente**.

Si no hay historial previo (primer mes del período), no aplicar la regla — registrar todos los ingresos como recurrentes por defecto.

### Hoja Historial de Gastos (mensual)

Tabla con una fila por transacción categorizada:

```
Columnas: FECHA | CONCEPTO | IMPORTE (base) | IMPORTE (moneda original) | CATEGORÍA | CUENTA ORIGEN | NOTA
```

Al pie, tabla de resumen:

```
Columnas: CATEGORÍA | GASTO BRUTO | REINTEGROS | GASTO NETO | % DEL TOTAL

Una fila por categoría con gasto > 0 en el mes.
Línea separada: CONVERSIÓN PATRIMONIAL (si existe — no suma al total).
Fila final: TOTAL MES (sin incluir CONVERSIÓN PATRIMONIAL).
```

---

