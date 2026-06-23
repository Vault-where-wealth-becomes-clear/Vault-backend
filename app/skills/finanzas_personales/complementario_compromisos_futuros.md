## Módulo complementario: Compromisos Futuros (tarjeta_credito)

### Hoja Compromisos Futuros

Columnas:

```
CONCEPTO | TARJETA | CUOTAS RESTANTES | IMPORTE POR CUOTA | MES DE DÉBITO | TOTAL PENDIENTE
```

Una fila por cuota pendiente de débito en cuenta bancaria, con mes de débito estimado desde `fecha_cierre` declarada.

### Lógica de cálculo

**Definición precisa de cada conjunto (disjuntos por construcción):**

| Conjunto | Definición exacta | Clasificador |
|---|---|---|
| `Deuda_pendiente_mes` | Cuotas cuyo MES DE DÉBITO = mes corriente N y que aún NO aparecen como LIQ.DEUDA confirmado en el libro diario del mes N | Mes de débito = N |
| `Cuotas_futuras_3M` | Cuotas cuyo MES DE DÉBITO ∈ {N+1, N+2, N+3} — exclusivamente meses futuros | Mes de débito > N |

**Regla de exclusión mutua:** Una cuota solo puede pertenecer a uno de los dos conjuntos. El clasificador es el MES DE DÉBITO estimado desde `fecha_cierre` declarada — no el estado de procesamiento del extracto. `Deuda_pendiente_mes ∩ Cuotas_futuras_3M = ∅` (conjuntos disjuntos — no existe superposición posible).

**Conversión de deudas en moneda extranjera:**

Si el usuario tiene una `tarjeta_credito` en moneda extranjera (ej. USD), las deudas y cuotas se convierten a moneda base antes del descuento:

```
Deuda_USD_en_base        = Deuda_pendiente_mes_USD × TC_cierre_mes
Cuotas_futuras_USD_en_base = Cuotas_futuras_3M_USD × TC_cierre_mes
```

| Situación | TC a usar |
|---|---|
| Moneda base = ARS, deuda en USD | TC_cierre del período (celda amarilla del mes) |
| Moneda base = USD, deuda en ARS | 1 / TC_cierre del período |
| Deuda en la misma moneda base | TC = 1 (sin conversión) |

**Fórmula completa del AL neto:**

```
AL_neto = AL_mes
        − Deuda_pendiente_mes_ARS
        − Deuda_USD_en_base
        − Cuotas_futuras_3M_ARS
        − Cuotas_futuras_USD_en_base
```

AL neto se muestra como métrica secundaria en la Sección A del Tablero — no reemplaza al AL principal.

---

