## Módulo 1: flujo-mensual

### Fórmula central

```
RESULTADO_base = Σ [ Δ_cuenta_i × TC_i ]   para cuentas de tipo
                 caja_de_ahorro, cuenta_corriente, billetera_virtual o efectivo.
                 EXCLUYE explícitamente cuentas de tipo tarjeta_credito,
                 que no tienen SI/SF propio y no participan de esta sumatoria.

Δ_cuenta_i  = SF_i − SI_i
TC_i        = 1               si moneda de cuenta = moneda base
TC_i        = TC del período  si moneda de cuenta = moneda extranjera

RESULTADO_ref = RESULTADO_base / TC_referencia   (expresado en moneda secundaria, ej. USD)
```

Las transferencias entre cuentas propias se cancelan automáticamente en la suma de deltas. No requieren eliminación manual.

### Paso 1 — Verificar saldo inicial

Antes de procesar los movimientos, verificar que el SI de cada cuenta cumpla su límite:

| Tipo de cuenta | Límite de SI |
|---------------|-------------|
| `caja_de_ahorro` | SI ≥ 0 |
| `billetera_virtual` | SI ≥ 0 |
| `efectivo` | SI ≥ 0 |
| `cuenta_corriente` sin descubierto declarado | SI ≥ 0 |
| `cuenta_corriente` con descubierto declarado | SI ≥ −límite_descubierto |

Si el SI viola el límite → emitir alerta EXTRACTO INCOMPLETO y no continuar con esa cuenta.

### Paso 2 — Construir el Libro Diario

Por cada cuenta (excepto `tarjeta_credito`), construir una tabla con esta estructura:

```
Encabezado:
  [NOMBRE CUENTA] — [TIPO] — [MONEDA] — [ENTIDAD]
  TC 1 [MONEDA] = [valor] [BASE]/[MONEDA]  (editable)    ← solo si moneda ≠ base

Columnas: FECHA | DESCRIPCIÓN | DEBE (−) | HABER (+) | SALDO | TIPO
```

**Fila 1 — Saldo Inicial:**
```
FECHA: primer día del mes  |  DESCRIPCIÓN: "SALDO INICIAL DEL MES"
DEBE: —  |  HABER: —  |  SALDO: SI  |  TIPO: "SI →"
```

**Filas de movimiento** (una por cada transacción, orden cronológico):
```
FECHA: fecha del movimiento
DESCRIPCIÓN: descripción tal como figura en el extracto
DEBE: importe si es egreso (resta saldo) — valor positivo en la columna
HABER: importe si es ingreso (suma saldo) — valor positivo en la columna
SALDO: saldo anterior − DEBE + HABER  (acumulativo)
TIPO: clasificación del movimiento (ver árbol de decisión)
```

**Última fila de movimientos — Saldo Final:**
```
FECHA: último día del mes  |  DESCRIPCIÓN: "SALDO FINAL (verificado)"
DEBE: —  |  HABER: —  |  SALDO: SF real informado por el usuario  |  TIPO: "✓ OK" o "✗ ERROR"
```

**Fila delta:**
```
DESCRIPCIÓN: "ΔMOVIMIENTO"  |  SALDO: SF − SI  |  TIPO: "Δ →"
```

**Meses sin movimientos:**
Si el usuario no informa movimientos para una cuenta en un mes: SF = SI del período anterior, Δ = 0. La hoja del libro diario se genera igual con solo las filas de SI y SF. No se emite alerta — es un estado válido. El encadenamiento SF(N) = SI(N+1) se verifica normalmente.

### Paso 3 — Reconciliación

```
SF_calculado = SI + Σ(HABER) − Σ(DEBE)
Δ_reconciliación = SF_calculado − SF_real

Si Δ = 0.00  →  marcar ✓ OK  →  continuar
Si Δ ≠ 0.00  →  marcar ✗ ERROR  →  mostrar diferencia en rojo
```

**Comportamiento post-reconciliación (resultado parcial):**

Si la reconciliación falla en una o más cuentas:
- Emitir alerta individual por cada cuenta fallida con la diferencia exacta:
  `ERROR DE RECONCILIACIÓN en "[cuenta]": diferencia de $[Δ]. Revisar movimientos faltantes o duplicados.`
- Continuar el procesamiento con las cuentas que sí reconciliaron.
- Calcular resultado parcial usando solo las cuentas reconciliadas.
- Marcar el resultado como **RESULTADO PARCIAL — INCOMPLETO** e indicar explícitamente qué cuentas fueron excluidas y por qué.
- No mostrar resultado completo hasta que el usuario resuelva todas las diferencias pendientes.

### Paso 4 — Clasificar movimientos

Árbol de decisión (aplicar en orden):

**A. ¿La descripción identifica claramente un comercio, servicio o entidad externa?**
- Sí → saltar al punto E directamente (clasificar sin preguntar)
- No → continuar al punto B

**B. Verificación bidireccional de INTERNO:**
- Si esta fila es un **DEBE** → buscar HABER de mismo monto y fecha aproximada en otra cuenta declarada.
- Si esta fila es un **HABER** → buscar DEBE de mismo monto y fecha aproximada en otra cuenta declarada.

Condición adicional antes de confirmar INTERNO automáticamente: ninguna de las dos descripciones (la fila evaluada y la coincidencia encontrada) debe identificar un tercero externo reconocible (nombre de comercio, entidad, obra social, inmobiliaria, persona).
- Si ambas descripciones son genéricas o coherentes con una transferencia entre cuentas propias → **INTERNO** automático.
- Si alguna de las dos descripciones identifica un tercero externo, aunque el monto y la fecha coincidan → **NO** clasificar automáticamente. Continuar al punto C y preguntar: *"Encontré dos movimientos del mismo monto ($[X]) el [fecha]: uno en [cuenta A] ('[descripción A]') y otro en [cuenta B] ('[descripción B]'). ¿Son una transferencia entre tus cuentas o dos movimientos independientes que coincidieron en monto?"*
- Si no encuentra coincidencia en ningún sentido → continuar al punto C.

**C. ¿La descripción es genérica? (ej. "TRANSFERENCIA ENVIADA", "DÉBITO TRANSFERENCIA", "TRANSFERENCIA RECIBIDA")**
- Sí → Claude pregunta antes de clasificar:
  *"Detecté una [salida/entrada] de $[monto] el [fecha]. ¿A dónde fueron esos fondos / de dónde provienen?"*
  
  Según respuesta:
  - **"A/de una cuenta mía ya declarada"** → INTERNO
  - **"Compré divisas / moneda extranjera y las tengo en efectivo"** → ver punto D
  - **"Salió/entró del sistema (pago externo, tercero)"** → continuar al punto E

**D. Compra de divisas sin cuenta de destino declarada:**
- Claude pregunta: *"¿Querés agregar una cuenta de tipo `efectivo` en [moneda] para que el sistema registre esos fondos y el Δ AL sea correcto?"*
  - Si acepta → crear cuenta efectivo, registrar movimiento como INTERNO. Δ AL = 0.
  - Si no acepta → **EXTERNO SALIDA** con subcategoría `CONVERSIÓN PATRIMONIAL`. Agregar nota en Tablero: *"El Δ AL de este mes incluye $[X] en conversiones patrimoniales no rastreadas en el sistema."* Esta subcategoría no impacta en la tasa de ahorro operativa.

**D-bis. ¿La descripción menciona "DIVIDENDO", "RENTA", "CUPÓN", "ACREDITACIÓN DIVIDENDOS" o términos equivalentes?**
- No → continuar al punto E.
- Sí → clasificar **siempre como RENDIMIENTO**, sin excepción. El dividendo proviene de un emisor externo (empresa que lo paga), no de una cuenta propia del usuario — clasificarlo como INTERNO haría desaparecer el ingreso del patrimonio registrado.
- La clasificación como RENDIMIENTO se aplica **siempre**, sin esperar ningún nivel de información del Módulo 4.
- Si el usuario tiene comitente declarada y ese mes alcanza **Nivel 2 o superior**: verificar si ese monto ya está incluido en el `Efectivo_disponible_comitente`. Si coincide (mismo monto, fecha cercana) → registrar igual como RENDIMIENTO con nota: *"Verificado contra cuenta corriente de comitente — no duplicar en conteo manual."*
- Si el usuario tiene comitente declarada pero ese mes **solo alcanza Nivel 1** (sin voucher cargado): clasificar igual como RENDIMIENTO, sin verificación posible, sin nota adicional ni bloqueo del flujo. La ausencia de Nivel 2 **nunca** pospone ni condiciona la clasificación del movimiento en el libro diario bancario.
- Si no hay comitente declarada → clasificar como RENDIMIENTO sin la nota de verificación.

  > RENDIMIENTO no entra en la tasa de ahorro operativa (Regla 8) ni en los ingresos operativos recurrentes. Se reporta por separado en el Tablero General como línea "Rendimientos".

**E. Clasificación estándar:**
1. ¿La contraparte es otra cuenta propia del mismo usuario? → **INTERNO**
2. ¿Es débito de tarjeta de crédito, cheque propio o cuota de préstamo? → **LIQ.DEUDA**
3. ¿Es devolución o cashback de un gasto previo? → **REINTEGRO**
4. ¿Es interés o rendimiento acreditado por la entidad? → **RENDIMIENTO**
5. ¿Ingresa dinero desde fuera del conjunto de cuentas propias? → **EXTERNO ENTRADA**
6. ¿Egresa dinero hacia fuera del conjunto de cuentas propias? → **EXTERNO SALIDA**
7. No encaja en ninguno → alerta MOVIMIENTO SIN CLASIFICAR, pedir revisión manual

**Colores de fila por tipo:**

| Tipo | Color fondo |
|------|------------|
| EXTERNO ENTRADA | BG alternado (`1C2526` / `243030`) |
| EXTERNO SALIDA | BG alternado (`1C2526` / `243030`) |
| RENDIMIENTO | Azul noche `1A2E3B` |
| REINTEGRO | Verde oscuro `1A3D2B` |
| INTERNO | Azul oscuro `1F3A4A` |
| LIQ.DEUDA | Bordo oscuro `2E1A1A` |

### Paso 5 — Calcular resultado del período

Una vez que todas las cuentas tienen reconciliación ✓ (o se procesan las reconciliadas en modo RESULTADO PARCIAL):

```
RESULTADO_base = Σ [ (SF_i − SI_i) × TC_i ]   para cuentas reconciliadas

Desglose por cuenta:
  Cuenta 1 (ARS):  Δ = SF − SI             → Δ_base = Δ × 1
  Cuenta 2 (USD):  Δ = SF − SI  (en USD)   → Δ_base = Δ × TC_USD
  ...
  TOTAL             →  RESULTADO_base
  TOTAL en ref USD  →  RESULTADO_base / TC_USD
```

### Paso 6 — Hoja Flujo de Fondos

Tabla resumen del mes con una fila por cuenta:

```
Columnas: CUENTA | TIPO | MONEDA | TC | SI | SF | Δ (moneda propia) | Δ (base) | Δ (ref USD)
```

Fila final RESULTADO: suma de Δ_base y Δ_ref. Si es RESULTADO PARCIAL, indicar cuentas excluidas al pie.

Nota metodológica al pie:
- Los movimientos internos se cancelan automáticamente en la suma de Δ.
- TC es la referencia del período — editable en celda amarilla.
- RESULTADO = variación real del patrimonio líquido en el período (Δ PL).

### VISA / tarjeta de crédito en devengado

Los consumos de tarjeta pertenecen al **mes de la compra**, no al mes del pago.

- En el mes de la **compra**: el gasto se registra en el Historial de Gastos y en la hoja Compromisos Futuros como EXTERNO SALIDA, categorizado normalmente. No impacta en el libro diario de la cuenta bancaria ese mes.
- En el mes del **débito bancario**: el pago de la liquidación entra en el libro diario de la cuenta bancaria como LIQ.DEUDA. No se categoriza como gasto (ya fue categorizado antes).

### Reglas de procesamiento para resúmenes de tarjeta de crédito

**EXCLUIR siempre del array `transacciones`:**
- Líneas que describan el pago del saldo de la tarjeta: "SU PAGO EN PESOS", "SU PAGO EN DOLARES", "SU PAGO EN USD", "SU PAGO ANTERIOR", "PAGO MINIMO ANTERIOR" y variantes. Estas ya figuran en el extracto bancario como débito; incluirlas duplicaría el egreso.
- Regla general: cualquier ítem cuya descripción identifique el pago total o parcial del saldo del período anterior.

**INCLUIR como consumos reales — categorizar según el árbol estándar:**
- Todos los gastos con comercios, tiendas, servicios y proveedores externos.
- Cargos financieros (intereses, financiación, CFT) → categoría: **Servicios**.

**INCLUIR — categoría obligatoria "Impuestos":**
- Ingresos Brutos (IIBB / Ing. Brutos), IVA RG, DB.RG (Débito Reglamentario General), Impuesto PAIS, Impuesto para una Argentina Inclusiva y Solidaria (PAIS), Percepción AFIP, Percepción IIBB y cualquier otro cargo emitido por organismos estatales o recaudatorios. Estos nunca van a VARIOS.

---

