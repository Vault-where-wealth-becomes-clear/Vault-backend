## Módulo 3: flujo-del-período (multi-mes)

### Regla de encadenamiento

```
SF_cuenta_i(mes N) = SI_cuenta_i(mes N+1)   →   para todas las cuentas i
```

Verificar antes de construir la vista del período. Si falla en alguna cuenta: emitir alerta con el mes exacto y la diferencia, y no construir el período hasta que se resuelva.

**Cuentas incorporadas a mitad de período:**

Si una cuenta se declara por primera vez en el mes N de un período ya iniciado:

1. El SI de esa cuenta en el mes N es el saldo real declarado por el usuario al primer día de ese mes (no se asume 0, salvo que la cuenta haya abierto ese mes).
2. El encadenamiento SF(mes) = SI(mes+1) se verifica **únicamente desde el mes N en adelante**. No se exige ni evalúa para meses previos a N.
3. En la hoja Flujo del Período, las columnas de esa cuenta muestran `—` en todas las filas correspondientes a meses anteriores a N.
4. La columna ACUMULADO de esa cuenta inicia su suma desde el mes N.

Esta regla aplica a cualquier tipo de cuenta (`caja_de_ahorro`, `billetera_virtual`, `efectivo`, `tarjeta_credito`) incorporada después del primer mes del período.

### Hoja Flujo del Período

Una fila por mes. Las columnas se generan dinámicamente según las cuentas declaradas:

```
MES  |  [TC moneda_1]  |  [TC moneda_2 ...]  |  Δ Cta_1 (propia)  |  Δ Cta_1 (base)  |  Δ Cta_2 ...  |  RESULTADO base  |  RESULTADO ref  |  ACUMULADO
```

Reglas de columnas:
- Una columna TC por cada moneda extranjera presente en el set de cuentas.
- Por cada cuenta en moneda extranjera: dos columnas Δ (una en moneda propia, una en base).
- Por cada cuenta en moneda base: una columna Δ.
- Fila final: TOTAL ACUMULADO con suma de cada columna.
- Columna ACUMULADO: resultado corriente acumulado desde el primer mes del período.

### Hoja Tablero de Gastos (multi-mes)

Matriz categorías × meses:

```
Columnas: CATEGORÍA | Mes_1 | Mes_2 | ... | Mes_N | TOTAL | PROM. MENSUAL
```

- Valores: gasto neto en moneda base.
- Celdas con reintegros (valores negativos): fondo verde oscuro `1A3D2B`.
- Celdas vacías (sin gasto en ese mes): mostrar `—` o `0`, no dejar en blanco.
- Fila CONVERSIÓN PATRIMONIAL separada al pie (si existe), no incluida en TOTAL MES.

---

