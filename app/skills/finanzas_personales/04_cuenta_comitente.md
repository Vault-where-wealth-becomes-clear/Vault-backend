## Módulo 4: cuenta-comitente

### Principio central: niveles de información

La skill **solo muestra como cálculo propio aquello de lo que tiene certeza completa** según los archivos efectivamente disponibles para ese mes. No se estiman, aproximan ni se muestran con advertencia datos que no pueden verificarse — simplemente no aparecen hasta alcanzar el nivel que los respalda.

El nivel se evalúa **mes a mes, de forma independiente**. Un período puede tener el Mes 1 en Nivel 3, el Mes 2 en Nivel 1 y el Mes 3 en Nivel 3 sin inconsistencia. Cada mes es una unidad de análisis propia.

Si el usuario sube archivos adicionales para un mes ya procesado, la skill recalcula ese mes al nivel más alto que los archivos permitan (actualización retroactiva), sin exigir reprocesar meses siguientes — salvo que el recálculo modifique el `Δ_cartera_mes`, en cuyo caso se revalida el encadenamiento con el mes siguiente.

---

### Declaración de la cuenta comitente

```
CUENTA COMITENTE
  nombre:              [etiqueta libre — ej. "IOL", "Bull Market", "Balanz"]
  broker:              [entidad — ej. "Invertir Online", "Bull Market Brokers"]
  moneda base:         ARS | USD
```

---

### Tipos de instrumento soportados

| Tipo | Moneda habitual | Precio expresa |
|------|----------------|----------------|
| `accion_local` | ARS | Precio por acción en ARS |
| `cedear` | ARS | Precio por CEDEAR en ARS (subyacente en USD) |
| `bono_ars` | ARS | Precio por lámina VN $100 en ARS |
| `bono_usd` | USD | Precio por lámina VN USD 100 en USD |
| `fci_ars` | ARS | Valor cuotaparte en ARS |
| `fci_usd` | USD | Valor cuotaparte en USD |
| `lecap_boncap` | ARS | Precio bajo la par en ARS |
| `on_ars` | ARS | Obligación negociable en ARS |
| `on_usd` | USD | Obligación negociable en USD |
| `efectivo_comitente` | ARS o USD | Efectivo disponible en el broker, no invertido (precio_cierre = 1) |
| `otro` | ARS o USD | El usuario declara unidad y precio |

---

### Detección automática de nivel por archivo

La skill identifica el nivel que cada archivo habilita por **patrones estructurales**, no por nombres exactos de columna — lo que permite adaptarse a distintos brokers (IOL, Bull Market, Balanz, etc.) sin un parser específico por entidad.

| Nivel habilitado | Patrón estructural detectado | Ejemplo de archivo |
|---|---|---|
| Nivel 1 | Una fila por instrumento, con identificador + cantidad + precio + valor total, en una fecha de corte única (snapshot) | PORTFOLIO_HISTORICO, reporte de tenencias |
| Nivel 2 | Múltiples filas por fecha, columna de saldo corriente acumulativo, descripciones de movimiento (dividendo, interés, retención) | inviu-voucher, cuenta corriente / extracto de comitente |
| Nivel 3 | Archivo multi-hoja o con secciones separadas de operaciones de compra/venta con resultado, rentas/dividendos, vencimientos/amortizaciones | Reporte de Renta Financiera |

**Regla de ambigüedad:** si Claude no puede determinar con certeza el nivel de un archivo nuevo (broker no visto antes, estructura atípica), pregunta al usuario:
> *"Subiste un archivo con esta estructura: [describir columnas detectadas]. ¿Es un snapshot de tenencias, un movimiento de cuenta corriente, o un reporte de operaciones con resultados?"*
No se asume el nivel sin confirmación cuando hay ambigüedad estructural.

**Regla base obligatoria:** el snapshot (Nivel 1) es la base de todos los niveles. Si falta el snapshot del mes, no hay Nivel 1 ni superior para ese mes, sin importar qué otros archivos se hayan subido.

---

### NIVEL 1 — Solo Snapshot de Tenencias

**Qué puede calcular la skill con certeza:**

| Cálculo | Disponible |
|---|---|
| `Valor_cartera_base` del mes | ✅ |
| Composición por tipo de instrumento (% bonos, acciones, CEDEARs, etc.) | ✅ |
| Alerta de concentración (instrumento > 40% de cartera) | ✅ |
| `Δ_cartera_mes` | Solo si hay snapshot del mes anterior también cargado |
| CPP, Resultado $, Rendimiento % | ❌ No se muestran aunque el archivo del broker los incluya |

**Hoja Cartera — Posiciones del mes (Nivel 1):**
```
INSTRUMENTO | TIPO | MONEDA | CANTIDAD | PRECIO CIERRE | VALOR (moneda) | VALOR (base) | % CARTERA
```
> Aunque el archivo del broker incluya columnas como "Costo (PPC)" o "Resultado", la skill las ignora completamente en Nivel 1. No se muestran con advertencia ni atenuadas — no aparecen.

**Regla de selección de precio cuando el broker entrega múltiples monedas:**

Si el archivo del broker entrega, para el mismo instrumento, un campo de precio/valor ya expresado en moneda base (ej. "Total en pesos", "Monto $") junto con otro campo en moneda de emisión o equivalente en otra divisa (ej. "Total en moneda de emisión", "Equivalente U$S"):
- La skill toma el campo ya expresado en moneda base **sin aplicar TC_moneda** (evita doble conversión).
- TC_moneda se aplica únicamente cuando el archivo entrega el valor exclusivamente en moneda de emisión o moneda extranjera, sin un campo paralelo ya convertido.
- Si Claude no puede determinar cuál campo es el ya-convertido → preguntar al usuario: *"Encontré dos valores distintos para [instrumento]: $[X] y $[Y]. ¿Cuál de los dos ya está expresado en tu moneda base ([ARS/USD])?"*

> Ejemplo: si el broker entrega "Total en moneda de emisión: USD X" y "Total en pesos: $Y", la skill toma directamente $Y como Valor_posición_base. No multiplica X por TC_USD.

**Valuación:**
```
Valor_posición_base = Cantidad × Precio_cierre × TC_moneda
Valor_cartera_base  = Σ(Valor_posición_i_base)
Valor_cartera_ref   = Valor_cartera_base / TC_ref
```

**Variación (requiere snapshot del mes anterior):**
```
Δ_cartera_base = Valor_cartera_base(mes N) − Valor_cartera_base(mes N−1)
Δ_cartera_%    = Δ_cartera_base / Valor_cartera_base(mes N−1)
```

---

### NIVEL 2 — Snapshot + Cuenta Corriente del Comitente

**Qué agrega sobre el Nivel 1:**

| Cálculo | Disponible |
|---|---|
| `Efectivo_disponible_comitente` al cierre del mes | ✅ saldo final exacto del voucher |
| Rendimientos en efectivo cobrados (dividendos, intereses, cupones) — netos de retención | ✅ |
| Retenciones impositivas sobre rentas | ✅ línea informativa |
| Resultado realizado de ventas | ❌ el voucher muestra el movimiento de efectivo pero no el precio de la operación |
| CPP verificado | ❌ requiere boletos de compra reales (Nivel 3) |

**Regla de segmentación del voucher de cuenta corriente por mes:**

El archivo de cuenta corriente del comitente puede cubrir un rango de fechas mayor a un mes calendario. La skill no procesa el archivo como una unidad — segmenta cada fila según su fecha de concertación/liquidación y la asigna al mes calendario correspondiente.

Para el mes que se está procesando (mes N):

1. Filtrar del voucher únicamente las filas cuya fecha cae dentro del mes N.
2. Calcular `Efectivo_disponible_comitente` al cierre del mes N usando el SALDO de la última fila cronológica dentro de ese rango — no el saldo final del archivo completo.
3. Los Rendimientos netos y Retenciones del mes N se calculan solo con las filas de ese rango.
4. Si el usuario sube el mismo archivo voucher en sesiones posteriores para procesar meses siguientes, la skill reutiliza el archivo ya cargado y cambia el filtro de fecha al mes correspondiente — no exige un archivo nuevo por mes si el voucher ya cubre ese rango.
5. Si el mes N no tiene ninguna fila dentro del rango del voucher cargado, el Nivel 2 no se alcanza para ese mes específico aunque el archivo esté presente en la sesión. Mensaje: *"El archivo de cuenta corriente cargado no cubre [mes N]. Nivel 2 no disponible para ese mes."*

**Verificación de integridad del rango:** el saldo de cierre del mes calculado por suma de movimientos del rango debería coincidir con el saldo que muestra la última fila de ese rango. Si no coincide → alerta informativa: *"El saldo calculado para [mes] no coincide exactamente con el saldo reportado por el broker — diferencia de $[X]. Verificar integridad del archivo."*

**Regla de fuente de verdad:** el saldo reportado por el broker en la última fila cronológica del rango (Camino B) es **siempre** la fuente de verdad utilizada para el cálculo de `Efectivo_disponible_comitente` y, por extensión, del `Valor_cartera_base`. El saldo calculado por la skill sumando los movimientos del rango (Camino A) funciona únicamente como mecanismo de control de integridad. Si A ≠ B: emitir la alerta informativa con la diferencia, pero el cálculo del patrimonio **siempre** continúa usando el valor B. Nunca se usa A en lugar de B para el cálculo del patrimonio reportado al usuario.

---

**Tipo de instrumento especial — `efectivo_comitente`:**

Se agrega como posición adicional en la hoja Cartera representando el saldo disponible en el broker no invertido:
```
instrumento:   "Efectivo disponible"
tipo:          efectivo_comitente
moneda:        ARS | USD (según corresponda)
cantidad:      [saldo final del voucher]
precio_cierre: 1
```
Suma a `Valor_cartera_base` igual que cualquier otra posición.

**Tratamiento de retenciones impositivas sobre rentas:**

Cuando el voucher muestra un dividendo/renta seguido de su retención asociada (mismo instrumento, fecha cercana, signo opuesto):
```
Rendimiento_bruto = monto del dividendo/renta antes de retención
Retención         = monto de la retención impositiva
Rendimiento_neto  = Rendimiento_bruto − Retención   ← este valor entra al Δ AL
```

En el Tablero General:
- **Rendimientos** (línea principal) = Σ Rendimiento_neto del período
- **Retenciones impositivas** (línea informativa, en gris) = Σ Retención del período

Las retenciones **no se categorizan como gasto del Módulo 2** — no compiten con SUPERMERCADO, SALUD, etc. No afectan la tasa de ahorro ni la Sección C.

> Ejemplo: dividendo bruto GGAL $3.105,59, retención −$217,39 → Rendimiento_neto $2.888,20 entra al cálculo del AL. La retención acumulada queda visible como dato informativo del período.

---

### NIVEL 3 — Snapshot + Cuenta Corriente + Reporte de Renta Financiera

**Qué agrega sobre el Nivel 2 — con certeza completa desde el broker:**

| Cálculo | Fuente dentro del Reporte de Renta Financiera |
|---|---|
| Resultado realizado por instrumento vendido | Hoja "Resultado Ventas" — tomado directamente, sin inferencia propia |
| CPP verificado (reconstruido desde compras reales) | Hoja "Boletos" — operaciones de compra con precio y fecha |
| Vencimientos y amortizaciones (LECAPs, bonos) | Hoja "Resultado Ventas" — fila "Amortización" con resultado ya calculado |
| Rendimiento de cauciones | Hoja "Resultado cauciones" |
| Δ_cartera_mes descompuesto | Combinación de hojas Boletos + Resultado Ventas + Rentas y Dividendos |

**Hoja Cartera — Posiciones del mes (Nivel 3 — completo):**
```
INSTRUMENTO | TIPO | MONEDA | CANTIDAD | PRECIO CIERRE | VALOR (moneda) | VALOR (base) | CPP | RESULTADO $ | REND. % | % CARTERA
```
> Las columnas CPP, RESULTADO $ y REND. % se habilitan únicamente en Nivel 3, calculadas desde datos verificables del Reporte de Renta Financiera.

**CPP dinámico ante nueva compra:**
```
CPP_nuevo = (Cantidad_anterior × CPP_anterior + Cantidad_comprada × Precio_compra)
            / (Cantidad_anterior + Cantidad_comprada)
```

**Tratamiento de eventos de cartera (vencimientos y ventas):**
```
EVENTO
  tipo:                vencimiento | venta_total | venta_parcial
  instrumento:         [extraído del Reporte]
  fecha:               [Fecha de Liquidación]
  resultado_realizado: [columna "Resultado" — dato directo del broker]
```
El resultado realizado se incorpora a `Δ_cartera_mes` del mes correspondiente a la fecha de liquidación. La skill toma el valor que el broker ya certificó — no calcula uno propio.

**Descomposición de Δ_cartera_mes (exclusiva de Nivel 3):**
```
Δ_cartera_mes = Δ_revaluación_mercado
              + Compras_netas_del_mes
              − Ventas_netas_del_mes
              + Rentas_cobradas_del_mes   (netas de retención)
```
Permite distinguir cuánto del crecimiento se debió a suba de precios de mercado, cuánto al aporte de nuevo capital, y cuánto a resultado de trading activo.

---

### Integración al Tablero General según Nivel

El Tablero no oculta el módulo completo si falta información — muestra exactamente lo que el nivel alcanzado en cada mes permite, y marca explícitamente lo que no está disponible.

| Campo del Tablero | Nivel mínimo requerido |
|---|---|
| Valor cartera / % Cartera-AL | Nivel 1 |
| Δ cartera (mes a mes) | Nivel 1, con 2 snapshots consecutivos |
| Rendimientos de cartera (dividendos/intereses netos) | Nivel 2 |
| Retenciones impositivas (línea informativa) | Nivel 2 |
| Rendimiento % por instrumento | Nivel 3 |
| Resultado realizado de ventas | Nivel 3 |
| Descomposición de Δ cartera (mercado/compras/ventas/rentas) | Nivel 3 |

**Regla de visualización para campos no disponibles:**
Si un campo no alcanza su nivel mínimo en el mes correspondiente, se muestra:
`N/D — requiere [nombre del archivo faltante] de [broker] para [mes/año]`
en lugar de un guion vacío o una aproximación. El usuario sabe exactamente qué archivo subir para desbloquear ese dato.

**Principio general — Granularidad por columna, no por fila:**
Cuando se construye cualquier hoja multi-mes del módulo, cada celda se evalúa contra el nivel mínimo de **su propio dato** (según la tabla de integración anterior), no contra el nivel máximo alcanzado por la fila o por el mes en su conjunto. Esto evita que datos disponibles en Nivel 1 (como la composición por tipo de instrumento) queden ocultos solo porque otras columnas de la misma fila requieren Nivel 3 y no lo alcanzan. Aplicación específica: la tabla de composición por tipo (`% accion_local`, `% cedear`, etc.) requiere únicamente Nivel 1 y se calcula y muestra siempre que el mes tenga snapshot cargado, independientemente del nivel máximo alcanzado ese mes.

---

### Hoja Evolución de Cartera (multi-mes)

Una fila por mes. Columnas:

```
MES | NIVEL | TC | VALOR CARTERA base | VALOR CARTERA ref | Δ CARTERA base | Δ CARTERA % | ACUMULADO Δ
```

La columna **NIVEL** muestra 1, 2 o 3 según los archivos disponibles para ese mes específico, permitiendo identificar de un vistazo qué meses tienen análisis completo y cuáles son parciales.

Sección de composición por tipo (una fila por mes):
```
MES | NIVEL | % accion_local | % cedear | % bono_ars | % bono_usd | % fci | % efectivo_comitente | % otros
```

Campos no alcanzados por el nivel del mes se muestran como `N/D — requiere [archivo faltante] de [broker] para [mes/año]`.

---

### Árbol de decisión de nivel (por mes)

```
1. ¿Hay snapshot de tenencias para el mes?
   NO → Módulo 4 no procesa ese mes. Todos los campos = N/D.
   SÍ → continuar.

2. Nivel = 1. Calcular Valor_cartera_base, composición, alertas de concentración.
   Si hay snapshot del mes anterior → calcular Δ_cartera_mes.

3. ¿Hay archivo de cuenta corriente (voucher) para el mes?
   NO → Nivel se mantiene en 1.
   SÍ → Nivel = 2. Calcular Efectivo_disponible_comitente, Rendimientos netos,
        Retenciones informativas. Agregar posición efectivo_comitente.

4. ¿Hay Reporte de Renta Financiera que cubra el mes?
   NO → Nivel se mantiene en 2 (o 1).
   SÍ → Nivel = 3. Habilitar CPP verificado, Resultado realizado,
        descomposición completa de Δ_cartera_mes.

5. Registrar el nivel alcanzado en la hoja Evolución de Cartera para ese mes.
   Repetir el proceso de forma independiente para cada mes del período.
```

---

### Regla — Ausencia de snapshot en un mes del período

Si el usuario tiene cuenta comitente declarada pero no carga snapshot de tenencias para un mes específico dentro de un período multi-mes:

1. El AL de ese mes se calcula únicamente con PL (Patrimonio Líquido de cuentas bancarias), sin componente de cartera.
2. El campo Cartera de ese mes en el Tablero General y en la hoja Evolución de Cartera muestra: `N/D — sin snapshot este mes`. No se interpola, no se arrastra el último valor conocido, no se asume $0.
3. `Δ_cartera_mes` NO se calcula para ese mes. Se muestra como `N/D` en lugar de un valor numérico.
4. `Δ_cartera_mes` del mes siguiente a uno o más meses con N/D se calcula contra el **último snapshot real disponible** anterior al hueco, no necesariamente el mes inmediatamente anterior en el calendario. El Tablero muestra nota: *"Δ cartera de [mes] calculado contra [mes base] — [mes N/D] no tuvo snapshot disponible."* Ejemplo: Mes 2 tiene snapshot ($1.200.000). Mes 3 es N/D. Mes 4 tiene snapshot ($1.500.000). El Δ_cartera del Mes 4 = $1.500.000 − $1.200.000 = +$300.000, comparando contra Mes 2.
5. No se dispara ninguna alerta de CAÍDA DE CARTERA, CONCENTRACIÓN ni ninguna otra alerta del Módulo 4 para un mes sin snapshot — la ausencia de datos no es equivalente a una caída de valor.
6. El `Δ AL_mes` para ese mes se calcula como `Δ AL = Δ PL` únicamente, con nota explícita en el Tablero: *"Δ AL de este mes no incluye variación de cartera — snapshot no disponible."*

Esta regla aplica de forma independiente por mes, en línea con el principio central del Módulo 4 de evaluar el nivel de información mes a mes sin arrastrar estados entre períodos.

---

### Alertas de la cartera

| Condición | Nivel | Alerta |
|-----------|-------|--------|
| Un instrumento > 40% del valor total de cartera | 🟡 | CONCENTRACIÓN: [instrumento] = [X]% de la cartera en [mes] |
| Δ cartera < −10% en el mes | 🔴 | CAÍDA DE CARTERA: la cartera perdió [X]% ([$ Y]) en [mes] |
| Δ cartera < −20% en el mes | 🔴 | CAÍDA SEVERA: la cartera perdió [X]% ([$ Y]) en [mes] |
| Rendimiento acumulado de un instrumento < −15% | 🟡 | PÉRDIDA EN [instrumento]: rendimiento acumulado [X]% |
| Cartera sin movimientos por 3 meses | ℹ️ | Sin cambios en posiciones en los últimos 3 meses |
| FCI en cartera + billetera virtual declarada | ⚠️ | Verificar doble representación: [FCI] puede estar reflejado en la billetera y en la cartera simultáneamente |

---

