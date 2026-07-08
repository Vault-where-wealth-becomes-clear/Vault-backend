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
    "posiciones": [
      {
        "instrumento": "GGAL",
        "tipo": "accion_local",
        "moneda": "ARS",
        "cantidad": 100,
        "precio_cierre": 450.5,
        "valor_moneda": 45050,
        "valor_base_ars": 45050,
        "cpp": null,
        "resultado_realizado_ars": null,
        "rendimiento_pct": null
      }
    ],
    "rendimientos_netos_ars": null,
    "retenciones_ars": null,
    "delta_cartera_mes": null
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
  "saldo_tarjeta": {
    "saldo_anterior_ars": 0, "pago_ars": 0, "saldo_anterior_usd": 0, "pago_usd": 0
  },
  "transacciones": [
    { "date": "2025-06-01", "description": "...", "amount": 0, "currency": "ARS", "category": "...", "confidence": 0.95, "installments": null, "cupon": null },
    { "date": "2025-06-02", "description": "...", "amount": -3000, "currency": "ARS", "category": "...", "confidence": 0.95, "installments": { "current": 3, "total": 12, "amount_per": 3000 }, "cupon": "561721" }
  ]
}
```

Reglas estrictas para `cuenta_comitente`:
- `posiciones[].tipo` DEBE ser uno de estos 11 valores exactos: `accion_local`, `cedear`,
  `bono_ars`, `bono_usd`, `fci_ars`, `fci_usd`, `lecap_boncap`, `on_ars`, `on_usd`,
  `efectivo_comitente`, `otro`. Nunca inventar variantes.
- `valor_base_ars` sigue la regla de selección de precio del Módulo 4: si el broker ya
  entrega un campo expresado en pesos (ej. "Total en pesos"), usar ese valor directo —
  nunca reconvertir aplicando el tipo de cambio sobre un valor que ya está en ARS.
- `cpp`, `resultado_realizado_ars`, `rendimiento_pct` van `null` salvo que el archivo
  alcance Nivel 3 (Reporte de Renta Financiera) — nunca estimarlos con datos de Nivel 1/2.
- `rendimientos_netos_ars` y `retenciones_ars` van `null` salvo Nivel 2+ (voucher de cuenta
  corriente disponible).
- `delta_cartera_mes` va `null` salvo Nivel 3; cuando corresponde, es un objeto con
  exactamente estas cuatro claves: `revaluacion_mercado_ars`, `compras_netas_ars`,
  `ventas_netas_ars`, `rentas_cobradas_ars`.
- **Nunca calcules `pct_cartera` (% que representa cada posición), el delta total del mes,
  ni alertas de concentración/caída** — esos tres son agregados que calcula el backend a
  partir de las posiciones crudas, no van en tu respuesta.

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
  - **Error inverso, igual de grave — NUNCA dividir el número impreso por `total`:** el valor que figura impreso en la columna Pesos/Dólares de la fila **ya es** lo que se debita este cierre (la cuota actual), no el precio total de la compra. No lo tomes como "precio total" ni lo dividas por la cantidad de cuotas para obtener `amount_per`.
    - Ejemplo real: la fila dice `MERPAGO*STARTCOMAR C.09/12 561721 19.166,58` → el importe impreso, 19.166,58, es la cuota 9/12 que se cobra en este resumen. Correcto: `"amount": -19166.58, "installments": {"current": 9, "total": 12, "amount_per": 19166.58}`. Incorrecto: `"amount": -1597.22` (=19166.58/12) — eso divide por la cantidad de cuotas un valor que no necesita división, porque el banco ya imprimió el monto de esta cuota específica.
    - Regla simple: `amount` y `amount_per` son SIEMPRE el número tal cual aparece impreso en la fila del PDF — nunca lo multipliques ni lo dividas por `total` ni por `current`.

Reglas estrictas para `tablero_general`:
- `patrimonio_total_usd` es OBLIGATORIO: total de activos líquidos al cierre del período en USD.
  Usar SIEMPRE este nombre exacto — nunca `patrimonio_liquido_final`, `patrimonio_liquido`,
  `activos_liquidos_usd` ni ninguna variante. Si no se puede calcular, usar `0`.
- `alertas` DEBE ser una lista de strings planos, nunca objetos.
  Cada alerta es un string con emoji + texto: `"🟡 Gasto alto en Restaurantes: $168.600 (28%)"`.
  NUNCA usar `{"tipo": "...", "mensaje": "..."}` — eso rompe el parser. Solo strings.

La clave "transacciones" es OBLIGATORIA siempre, sin importar qué módulos se pidieron —
es el detalle transaccional plano que alimenta el registro histórico de movimientos.

**Excepción — archivo sin ninguna fila de movimiento:** si el archivo es un snapshot de
tenencias de cuenta comitente (Nivel 1 del Módulo 4) u otro documento que no contiene una
sola fila de movimiento bancario (fecha + descripción + importe), `transacciones` DEBE
ser `[]`. **Nunca inventar movimientos que el archivo no tiene** — ni de ejemplo, ni
plausibles, ni basados en el tipo de cuenta. Un snapshot de tenencias no es un extracto:
no tiene compras, pagos ni depósitos que reportar.

**Categorías válidas para el campo `category` de cada transacción:**

Gastos: `Supermercado`, `Restaurantes`, `Transporte`, `Salud`, `Indumentaria`, `Tecnología`, `Entretenimiento`, `Servicios`, `Educación`, `Viajes`, `Suscripciones`, `Impuestos`, `Varios`

Ingresos y movimientos: `Ingreso operativo`, `Rendimiento`, `Cambio de moneda`, `Pago deuda`, `Transferencia interna`

Transitorio: `Reintegro`, `Sin categoría`

Usar exactamente estos strings. Nunca usar sinónimos (`Gastronomía`, `Salidas`, `Ropa`, `Interno`, `Liq.deuda`, `Conversión patrimonial`, etc.) — si no encaja en ninguna categoría de gasto, usar `Varios`.

**Reglas estrictas para el array `transacciones`:**

0. **Extractos consolidados que juntan varios meses: `transacciones` incluye TODOS los movimientos de TODOS los meses, sin excepción.** Un mismo PDF puede traer "SALDO ANTERIOR" seguido de movimientos de enero, después febrero, marzo, etc., todos en una sola sección "Movimientos en cuentas" — es un solo documento, no un documento por mes. Terminar de reconciliar el `libro_diario` de un mes (SI → SF cerrando bien) **no es una señal para parar** — es una señal para seguir con el mes siguiente que continúa en el mismo texto. Contá las filas de la sección de movimientos antes de responder: si el extracto tiene N filas con fecha, `transacciones` debe tener N entradas (menos las excluidas explícitamente por otra regla, ej. pagos de tarjeta). Si te faltó una fila, tu respuesta está incompleta — no la envíes así.

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

5. **Campo `cupon` — copiar literal, nunca inventar ni calcular:**
   - Si la fila del extracto tiene una columna "NRO. CUPÓN" (u equivalente: número de operación, número de comprobante), copiar ese valor tal cual, como string: `"cupon": "561721"`.
   - Si el extracto no muestra ese número para esa línea (ej. líneas de impuestos/CR./DB., o bancos que no lo imprimen), usar `"cupon": null`.
   - Este campo se usa para verificar el monto contra el texto original — nunca lo omitas cuando el dato está impreso, y nunca lo completes con un valor que no viste impreso.

**Campo `saldo_tarjeta` (solo resúmenes de tarjeta de crédito):**

Aunque las líneas "SALDO ANTERIOR" y "SU PAGO EN PESOS/USD" se excluyen del array
`transacciones` (regla de arriba, para no duplicar el egreso), sus valores SÍ se
reportan acá tal cual figuran impresos, sin ningún cálculo:
- `saldo_anterior_ars` / `saldo_anterior_usd`: el valor de la fila "SALDO ANTERIOR".
- `pago_ars` / `pago_usd`: el valor absoluto de "SU PAGO EN PESOS" / "SU PAGO EN USD"
  (y variantes: "SU PAGO ANTERIOR", "PAGO MÍNIMO ANTERIOR"). Si hay más de una línea
  de pago en la misma moneda, sumarlas.
Si el extracto no es de tarjeta de crédito, o no muestra estas líneas, usar `0` en
las cuatro claves — nunca omitir el objeto completo.
