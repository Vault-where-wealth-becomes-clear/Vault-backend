## Módulo 6: proyección-patrimonial

### Objetivo

Estimar la evolución del AL para los próximos 3 meses basándose en el comportamiento histórico del período cargado.

### Comportamiento según cantidad de meses disponibles

| Meses cargados | Bandas disponibles | Comportamiento |
|---|---|---|
| 1 mes | Ninguna | No proyectar. Mostrar: *"Se necesitan al menos 2 meses completos para activar la proyección patrimonial."* |
| 2 meses | Solo banda base | Calcular únicamente AL_proyectado base (promedio simple de los 2 Δ PL). No mostrar bandas conservadora ni optimista. Agregar nota al pie. |
| 3 meses o más | Las tres bandas | Calcular base + conservadora + optimista con ±1σ de Δ PL histórico. |

### Fórmulas base

```
Ahorro_promedio_base  = promedio(Δ PL de meses recurrentes,
                         excluyendo meses con ingresos extraordinarios)
                         ← calculado automáticamente (refleja comportamiento de
                           ingresos/gastos, razonablemente estable y predecible)

Δ_cartera_supuesto    = valor declarado por el usuario en celda amarilla editable
                         en la hoja Proyección
                         ← default: 0 (supuesto conservador de rendimiento nulo)
                         ← el promedio histórico de Δ cartera se muestra como
                           referencia informativa junto a la celda, sin usarse
                           en el cálculo: "Δ cartera promedio histórico del
                           período: $[X] — informativo, no se usa en la
                           proyección salvo que lo declares como supuesto."
                         ← este promedio se calcula EXCLUSIVAMENTE con los meses
                           donde Δ_cartera_mes fue efectivamente numérico (no N/D).
                           Los meses sin snapshot no se computan como $0 — se
                           excluyen completamente. Si no hay ningún mes con valor
                           numérico → mostrar "N/D — sin datos suficientes para
                           referencia histórica" en lugar de un valor calculado.

AL_proyectado(N+k)    = AL_actual + k × (Ahorro_promedio_base + Δ_cartera_supuesto)
```

> El rendimiento pasado de la cartera no es un estimador confiable del rendimiento futuro en activos volátiles. Por eso `Δ_cartera_supuesto` es siempre editable por el usuario, no calculado automáticamente.

### Tres bandas de proyección (requiere ≥ 3 meses)

```
Conservadora = AL_actual + k × (Ahorro_promedio_base − 1σ de Δ PL histórico)
Base         = AL_actual + k × Ahorro_promedio_base
Optimista    = AL_actual + k × (Ahorro_promedio_base + 1σ de Δ PL histórico)
```

El TC futuro es un **supuesto del usuario** (editable en celda amarilla en la hoja Proyección).

### Hoja Proyección

Columnas:

```
MES | AL CONSERVADOR | AL BASE | AL OPTIMISTA | SUPUESTO TC
```

Tres filas: N+1, N+2, N+3 desde el último mes cargado.

Nota al pie general: *"La proyección se basa en el comportamiento histórico del período cargado. No considera eventos extraordinarios futuros ni cambios en el tipo de cambio distintos al declarado."*

Nota al pie adicional cuando hay exactamente 2 meses: *"Con 2 meses de historial se muestra solo la proyección base. Se necesitan al menos 3 meses para calcular las bandas conservadora y optimista. Un mes atípico (bono, gasto extraordinario) puede distorsionar significativamente esta estimación."*

### Integración al Tablero General

En la Sección A, bloque de proyección:

```
AL base proyectado a 3 meses: $ [valor base]   Rango: $ [conservador] — $ [optimista]
```

---

