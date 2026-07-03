## Formato de salida obligatorio

No generes hojas de cálculo en texto ni tablas en markdown. Tu única salida es un
objeto JSON válido, sin texto adicional antes o después, con esta estructura
(incluí solo las claves de los módulos que efectivamente procesaste):

```json
{
  "flujo_mensual": {
    "libro_diario": { "<nombre_cuenta>": { "movimientos": [...], "saldo_inicial": 0, "saldo_final": 0, "reconciliacion_ok": true } },
    "resultado_periodo": { "delta_pl_ars": 0, "delta_pl_usd": 0, "incompleto": false }
  },
  "categorizacion_gasto": {
    "gasto_neto_por_categoria": { "Supermercado": 0, "...": 0 },
    "ingresos_recurrentes": 0,
    "ingresos_extraordinarios": 0
  },
  "flujo_periodo": {
    "evolucion_mensual": [ { "periodo": "2025-06", "delta_pl": 0 } ]
  },
  "cuenta_comitente": {
    "nivel_detectado": 1,
    "posiciones": [ { "instrumento": "...", "cantidad": 0, "valuacion_ars": 0, "pl_periodo": 0 } ]
  },
  "tablero_general": {
    "patrimonio_total_usd": 0,
    "variacion_mensual_pct": 0,
    "activos_liquidos": { "delta_pl": 0, "delta_cartera": 0 },
    "alertas": ["🟡 Gasto alto en Restaurantes: $168.600 (28% del total)"]
  },

  "proyeccion_patrimonial": {
    "banda_baja": 0, "banda_media": 0, "banda_alta": 0
  },
  "compromisos_futuros": {
    "cuotas_pendientes": [ { "descripcion": "...", "cuota_actual": 0, "total_cuotas": 0, "monto": 0, "proximo_vencimiento": "2025-07-15" } ]
  },
  "transacciones": [
    { "date": "2025-06-01", "description": "...", "amount": 0, "currency": "ARS", "category": "...", "confidence": 0.95, "installments": null },
    { "date": "2025-06-02", "description": "...", "amount": -3000, "currency": "ARS", "category": "...", "confidence": 0.95, "installments": { "current": 3, "total": 12, "amount_per": 3000 } }
  ]
}
```

Reglas estrictas para el campo `installments`:
- Si la transacción NO tiene cuotas: `"installments": null` — nunca omitir la clave.
- Si la transacción SÍ tiene cuotas: `"installments"` DEBE ser un objeto con exactamente estas tres claves:
  - `"current"`: entero — número de cuota actual (ej. `3`)
  - `"total"`: entero — total de cuotas (ej. `12`)
  - `"amount_per"`: número — monto por cuota en la moneda de la transacción (ej. `3000`)
- NUNCA usar un string como `"3/12"` o `"1/1"` — eso rompe el parser. Solo `null` u objeto.
- **`amount` DEBE ser siempre igual a `installments.amount_per`, nunca al precio total de la compra financiada.** El campo `amount` de una transacción en cuotas representa únicamente lo que este resumen debita en este cierre — no el monto original de la compra ni `amount_per * total`. Aunque el PDF muestre el precio total de la compra en algún lugar de la fila, ese valor NUNCA va en `amount`.
  - Correcto: compra en 12 cuotas de $3.000 c/u, esta es la cuota 3/12 → `"amount": -3000, "installments": {"current": 3, "total": 12, "amount_per": 3000}`.
  - Incorrecto: `"amount": -36000` (eso es `amount_per * total`, el precio total de la compra) con `"installments": {"current": 3, "total": 12, "amount_per": 3000}` — `amount` y `amount_per` NUNCA deben diferir en una transacción con cuotas.

Reglas estrictas para `tablero_general`:
- `patrimonio_total_usd` es OBLIGATORIO: total de activos líquidos al cierre del período en USD.
  Usar SIEMPRE este nombre exacto — nunca `patrimonio_liquido_final`, `patrimonio_liquido`,
  `activos_liquidos_usd` ni ninguna variante. Si no se puede calcular, usar `0`.
- `alertas` DEBE ser una lista de strings planos, nunca objetos.
  Cada alerta es un string con emoji + texto: `"🟡 Gasto alto en Restaurantes: $168.600 (28%)"`.
  NUNCA usar `{"tipo": "...", "mensaje": "..."}` — eso rompe el parser. Solo strings.

La clave "transacciones" es OBLIGATORIA siempre, sin importar qué módulos se pidieron —
es el detalle transaccional plano que alimenta el registro histórico de movimientos.

**Categorías válidas para el campo `category` de cada transacción:**

Gastos: `Supermercado`, `Restaurantes`, `Transporte`, `Salud`, `Indumentaria`, `Tecnología`, `Entretenimiento`, `Servicios`, `Educación`, `Viajes`, `Suscripciones`, `Impuestos`, `Varios`

Ingresos y movimientos: `Ingreso operativo`, `Rendimiento`, `Cambio de moneda`, `Pago deuda`, `Transferencia interna`

Transitorio: `Reintegro`, `Sin categoría`

Usar exactamente estos strings. Nunca usar sinónimos (`Gastronomía`, `Salidas`, `Ropa`, `Interno`, `Liq.deuda`, `Conversión patrimonial`, etc.) — si no encaja en ninguna categoría de gasto, usar `Varios`.

**Reglas estrictas para el array `transacciones`:**

1. **Una línea del PDF = una entrada en `transacciones`**. Nunca generar dos entradas para la misma fila del extracto (por ejemplo, una en ARS y otra en USD). Si la fila tiene valores en ambas columnas (Pesos y Dólares), elegir UNO según las reglas de moneda abajo.

2. **Elección de moneda: la determina EXCLUSIVAMENTE la columna del PDF donde figura el importe, nunca el texto de la descripción ni el tipo de comercio.**
   - Monto impreso en la columna **Pesos** → `"currency": "ARS"`, y `"amount"` = ese mismo número, tal cual figura impreso. Nunca reconvertir.
   - Monto impreso en la columna **Dólares** → `"currency": "USD"`, y `"amount"` = ese mismo número, tal cual figura impreso. Nunca reconvertir.
   - Esto aplica igual para compras directas en USD, compras en moneda extranjera que no es USD (CLP, EUR, BRL, GBP, etc. — el banco ya las convirtió a USD en la columna Dólares) e impuestos/percepciones (IIBB, IVA RG, DB.RG, etc.). Si hay valor en ambas columnas para el mismo ítem, registrar solo una vez en la columna del importe principal (típicamente Pesos para extractos locales).
   - **Prohibido**: tomar el número de una columna y guardarlo con la moneda de la otra, o "reconstruir" el monto a partir del tipo de cambio en vez de leer directamente el número impreso en la columna correspondiente. Ejemplo de error real detectado: una compra de "USD 20,00" (columna Dólares) terminó guardada como `amount: -20, currency: "ARS"` — el monto es correcto, la moneda no. El resultado correcto es `amount: -20, currency: "USD"`.

3. El campo `amount` es **siempre negativo para gastos** y positivo para créditos/devoluciones, en la moneda elegida según la regla anterior.

4. **Prefijo DB. vs CR. en cargos fiscales:**
   - Descripción empieza con `DB.` (ej. `DB.RG`, `DB.IVA`) → débito fiscal, `amount` **negativo**, categoría **Impuestos**.
   - Descripción empieza con `CR.` (ej. `CR.RG`, `CR.IVA`) → crédito fiscal (devolución del banco), `amount` **positivo**, categoría **Impuestos**.
