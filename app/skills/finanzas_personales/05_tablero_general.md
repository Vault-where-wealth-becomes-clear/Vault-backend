## Módulo 5: tablero-general

### Concepto: descomposición de Activos Líquidos en tres capas

El Tablero General responde dos preguntas distintas con métricas distintas:

| Pregunta | Métrica |
|----------|---------|
| ¿Estoy manejando bien mis ingresos y gastos? | Δ PL / Tasa de ahorro operativa |
| ¿Está creciendo mi patrimonio total? | Δ AL |

```
Δ AL_mes = Δ PL_mes  +  Δ cartera_mes
               ↑                ↑
      Ahorro operativo    Rendimiento de activos
      (decisiones)        (mercado + estrategia)
```

**Capa 1 — Ahorro operativo (Δ PL)**
```
Δ PL = Σ(SF_cuentas × TC) − Σ(SI_cuentas × TC)
```
Mide si el usuario vivió dentro de sus posibilidades. Es la métrica de comportamiento financiero cotidiano.

**Capa 2 — Rendimiento de activos (Δ cartera)**
```
Δ cartera = Valor_cartera(mes N) − Valor_cartera(mes N−1)
```
Mide el desempeño de la cartera. Es consecuencia del mercado y de las decisiones de inversión.

**Capa 3 — Variación total de Activos Líquidos (Δ AL)**
```
Δ AL = Δ PL + Δ cartera
AL_mes = PL_mes + Valor_cartera_mes

PL_mes            = Σ(SF_cuenta_i × TC_i)           ← Módulo 1
Valor_cartera_mes = Σ(Cantidad_j × Precio_j × TC_j) ← Módulo 4

AL en moneda base y en moneda de referencia (AL_ref = AL_base / TC_ref)
```

### KPIs del tablero

| KPI | Fórmula | Fuente |
|-----|---------|--------|
| Activos Líquidos base | PL + Valor cartera | Mód 1 + Mód 4 |
| Activos Líquidos ref | AL_base / TC_ref | Calculado |
| Δ AL base | AL_mes − AL_(mes−1) | Calculado |
| Δ AL % | Δ AL / AL_(mes−1) | Calculado |
| Patrimonio Líquido (PL) | Σ SF_cuentas × TC | Mód 1 |
| Valor cartera | Σ posiciones × precio × TC | Mód 4 |
| % cartera / AL | Valor cartera / AL | Calculado |
| **Δ PL (ahorro operativo)** | Σ(SF_i − SI_i) × TC_i | Mód 1 |
| **Δ cartera (rendimiento activos)** | Valor_cartera(N) − Valor_cartera(N−1) | Mód 4 |
| **Ingresos operativos** | Σ EXTERNO ENTRADA recurrentes | Mód 2 |
| **Ingresos extraordinarios** | Σ EXTERNO ENTRADA etiquetados como extraordinarios | Mód 2 |
| **Rendimientos** | Σ RENDIMIENTO de todas las cuentas | Mód 1 |
| **Gastos del mes** | Σ EXTERNO SALIDA − REINTEGROS (sin CONVERSIÓN PATRIMONIAL) | Mód 2 |
| **Tasa de ahorro** | Δ PL / Ingresos_operativos_recurrentes · Si denominador = 0 → N/A | Calculado |
| Rendimiento cartera % | Δ cartera / Valor_cartera_(mes−1) | Mód 4 |

> **Regla de excepción — tasa de ahorro N/A:** Si `Ingresos_operativos_recurrentes = 0` en el mes (todos los ingresos fueron extraordinarios, o no hubo ingresos), la tasa de ahorro se muestra como `N/A` con la nota: *"Sin ingresos recurrentes en el período — tasa no calculable."* La celda correspondiente en la Sección B del Tablero no aplica los colores condicionales de verde/amarillo/rojo. Este caso puede ocurrir en meses donde todos los ingresos provienen de ventas de activos, reintegros extraordinarios o bonos puntuales únicos.

| AL neto | AL − Deuda_pendiente_mes_ARS − Deuda_USD_en_base − Cuotas_futuras_3M_ARS − Cuotas_futuras_USD_en_base (ver fórmula completa en Módulo Complementario: Compromisos Futuros) | Mód 1 + Mód Compromisos Futuros |
| Mejor mes (Δ AL) | max(Δ AL) + nombre | Período |
| Peor mes (Δ AL) | min(Δ AL) + nombre | Período |
| AL acumulado total | Σ Δ AL | Período |

---

### Hoja Tablero General — estructura y orden de secciones

#### Sección A — Panel de métricas del período (parte superior, siempre visible)

```
COLUMNA IZQUIERDA                               COLUMNA DERECHA
──────────────────────────────────────────────  ────────────────────────────────────────────
Período analizado      Ene-2026 → Jun-2026      Ahorro operativo total (Σ Δ PL)  $ X.XXX.XXX
Activos Líquidos iniciales  $ X.XXX.XXX         Rendimiento cartera total (Σ Δ cartera) $ X
Activos Líquidos finales    $ X.XXX.XXX         Tasa de ahorro promedio  XX.X%
  · PL (cuentas)            $ X.XXX.XXX         Mes de mayor crecimiento  [mes] +$X.XXX
  · Cartera (comitente)     $ X.XXX.XXX         Mes de mayor caída        [mes] −$X.XXX
Δ AL total (ARS)        $ X.XXX (+XX.X%)        Rendimiento cartera acum.  XX.X%
Δ AL total (USD)        u$s X.XXX  ← referencial, en gris
Ingreso operativo total     $ X.XXX.XXX         Categoría mayor gasto     [cat] XX.X%
Gasto total                 $ X.XXX.XXX         TC inicial → TC final     $X.XXX→$X.XXX
Ing. extraordinarios        $ X.XXX.XXX         % Cartera / AL            XX.X%
AL neto (desc. compromisos) $ X.XXX.XXX         AL base proyectado +3M    $ X.XXX (rango)
```

#### Sección B — Evolución de Activos Líquidos mes a mes

Una fila por mes. Columnas:

```
MES | TC | AL base | AL ref | PL | Cartera | % Cart/AL | Δ PL | Δ CARTERA | Δ AL | Δ AL (USD) | Δ AL % | ING.OP | GASTOS | TASA % | ACUMULADO
```

- `Δ PL` y `Δ CARTERA` son columnas separadas — `Δ AL` es su suma.
- `Δ AL (USD)` = Δ AL_base / TC_cierre_mes — vista secundaria referencial, mostrar en color neutro (gris). Si la moneda base ya es USD, esta columna es idéntica a Δ AL y no se muestra.
- `ING.OP` = ingresos operativos recurrentes (excluye extraordinarios y RENDIMIENTO).

> **Nota sobre Δ AL (USD):** esta métrica permite identificar meses donde el usuario ahorró en pesos pero perdió en dólares — el escenario más frecuente y silencioso de deterioro patrimonial en contextos de devaluación. Usa el TC del período como aproximación; en meses de alta volatilidad cambiaria el valor puede ser impreciso. El TC a usar es el `TC_cierre_mes` declarado por el usuario (celda amarilla del mes).

**Colores condicionales:**

| Columna | Condición | Color texto |
|---------|-----------|------------|
| Δ PL | > 0 | Verde `00C853` |
| Δ PL | < 0 | Rojo `FF5252` |
| Δ AL | > 0 | Verde `00C853` |
| Δ AL | < 0 | Rojo `FF5252` |
| TASA % | ≥ 20% | Verde `00C853` |
| TASA % | 0% a 19% | Amarillo `FFD600` |
| TASA % | < 0% | Rojo `FF5252` |
| Δ CARTERA | < −10% en columna | Fondo rojo suave `3D1A1A` |

Filas finales: **PROMEDIO** y **ACUMULADO**.

#### Sección C — Estructura de gasto histórica (categorías × meses)

```
CATEGORÍA  |  Mes_1  |  Mes_2  |  ...  |  Mes_N  |  TOTAL  |  PROM. MENSUAL  |  % DEL GASTO TOTAL
```

- Fila CONVERSIÓN PATRIMONIAL separada al pie (si existe), no incluida en % del total.
- La categoría con mayor % aparece resaltada.

#### Sección D — Evolución de cartera (composición × meses)

```
MES | Valor cartera | Δ cartera | Rend. % | % acc_local | % cedear | % bono | % fci | % otros
```

#### Sección E — Alertas automáticas

| Condición | Nivel | Mensaje |
|-----------|-------|---------|
| Δ AL < 0 en el mes | 🔴 | CAÍDA DE ACTIVOS LÍQUIDOS: −$[X] ([Y]%) en [mes] |
| Δ PL < 0 (tasa de ahorro negativa) | 🔴 | DESAHORRO OPERATIVO en [mes]: flujo de cuentas negativo en $[X] |
| Tasa de ahorro < 10% por 2 meses calculables | 🟡 | AHORRO BAJO en [mes N] y [mes N+1] — los meses con tasa N/A se omiten del conteo (no lo reinician). Ej: ene 5% + feb N/A + mar 8% → alerta activa |
| Δ cartera < −10% | 🔴 | CAÍDA DE CARTERA: −[X]% en [mes] |
| Instrumento > 40% de cartera | 🟡 | CONCENTRACIÓN en [instrumento]: [X]% de cartera |
| Categoría gasto > 40% del mes | 🟡 | CONCENTRACIÓN GASTO: [cat] = [X]% en [mes] |
| Categoría crece > 30% vs promedio | 🟡 | DESVÍO: [cat] subió [X]% en [mes] |
| INVERSIONES = $0 por 3 meses | ℹ️ | Sin nuevas inversiones en los últimos 3 meses |
| CONVERSIÓN PATRIMONIAL > 0 en el mes | ℹ️ | $[X] en conversiones patrimoniales no rastreadas — considerar agregar cuenta efectivo |

---

