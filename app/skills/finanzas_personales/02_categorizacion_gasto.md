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

### Lista canónica de categorías (fuente única de verdad)

Estas son las únicas categorías válidas para el campo `category` de cada transacción. No inventar variantes, sinónimos ni categorías nuevas.

**Gastos (impactan tasa de ahorro):**

| Categoría | Qué incluye |
|-----------|-------------|
| Supermercado | Alimentos en super/hipermercados, almacenes, verdulerías |
| Restaurantes | Comidas fuera de casa, delivery, cafeterías, bares, gastronomía |
| Transporte | Nafta, peajes, estacionamiento, transporte público, remises, Uber |
| Salud | Médicos, farmacia, prepagas, obra social, óptica, odontología |
| Indumentaria | Ropa, calzado, accesorios, bijouterie |
| Tecnología | Equipos, software, suscripciones digitales (Netflix, Spotify, etc.) |
| Entretenimiento | Salidas, cine, teatro, deporte, golf, juegos, cultura |
| Servicios | Luz, gas, agua, internet, teléfono, alquiler, expensas, cargos financieros |
| Educación | Cursos, libros, capacitación, colegio, universidad |
| Viajes | Hoteles, vuelos, turismo, excursiones, alojamiento temporario |
| Suscripciones | Membresías y suscripciones periódicas no digitales |
| Impuestos | IIBB, IVA RG, DB.RG, Impuesto PAIS, Percepción AFIP y cualquier cargo de organismos estatales. Nunca en Varios ni Servicios |
| Varios | Todo gasto que no encaja en otra categoría de gasto |

**Ingresos y movimientos (no impactan tasa de ahorro):**

| Categoría | Cuándo se usa |
|-----------|--------------|
| Ingreso operativo | Salario, honorarios, cobros recurrentes de actividad principal |
| Rendimiento | Intereses, dividendos, rendimientos de inversión, cashback |
| Cambio de moneda | Compra/venta de divisas o moneda extranjera entre cuentas propias o sin cuenta de destino declarada |
| Pago deuda | Pago de liquidación de tarjeta de crédito, cuota de préstamo, LIQ.DEUDA |
| Transferencia interna | Movimiento entre cuentas propias del mismo usuario (INTERNO) |

**Transitorio:**

| Categoría | Cuándo se usa |
|-----------|--------------|
| Reintegro | Devolución o cashback de un gasto previo — netea en la categoría original |
| Sin categoría | Solo cuando es imposible determinar la categoría con la información disponible |

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

