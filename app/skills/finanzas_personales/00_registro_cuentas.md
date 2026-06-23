## Descripción general

Sistema integral de gestión patrimonial personal. Soporta cualquier cantidad de cuentas bancarias, billeteras, efectivo y tarjetas de crédito en cualquier moneda, más una cuenta comitente con análisis por instrumento. El usuario declara sus cuentas y carga su cartera mensualmente; la skill produce libros diarios, flujo de fondos, análisis de cartera, proyección patrimonial y un Tablero General con los Activos Líquidos descompuestos en tres capas.

Combina seis módulos que se alimentan entre sí:
1. **flujo-mensual** — libro diario por cuenta y resultado del período
2. **categorización-de-gasto** — gastos netos por categoría, ingresos operativos vs extraordinarios
3. **flujo-del-período** — evolución condensada multi-mes
4. **cuenta-comitente** — cartera de inversiones: posiciones, valuación y rendimiento por instrumento
5. **tablero-general** — Activos Líquidos descompuestos: Δ PL (ahorro operativo) + Δ cartera (rendimiento)
6. **proyección-patrimonial** — estimación a 3 meses en tres bandas

---

## Módulo 0: registro de cuentas del usuario

Antes de procesar cualquier mes, el usuario declara sus cuentas y su preferencia visual. Cada cuenta tiene cuatro atributos obligatorios y, según el tipo, campos adicionales:

```
CUENTA
  nombre:   [etiqueta libre — ej. "Galicia ARS", "MP", "Efectivo USD"]
  tipo:     caja_de_ahorro | cuenta_corriente | billetera_virtual | efectivo | tarjeta_credito
  moneda:   ARS | USD | EUR | [cualquier ISO 4217]
  entidad:  [banco, fintech o emisor — ej. "Banco Galicia", "Mercado Pago", "Visa"]

PREFERENCIA VISUAL
  modo_visual: dark | light    ← default: dark
```

### Tipos de cuenta y sus características

| Tipo | Características clave | Campos adicionales |
|------|----------------------|--------------------|
| `caja_de_ahorro` | SI ≥ 0 siempre · puede acreditar intereses (RENDIMIENTO) · ARS o moneda extranjera | — |
| `cuenta_corriente` | SI ≥ 0 salvo descubierto autorizado declarado · cheques propios son LIQ.DEUDA · puede acreditar intereses | `descubierto` (opcional) |
| `billetera_virtual` | SI ≥ 0 siempre · puede acreditar rendimiento diario (RENDIMIENTO) · pagos QR y CVU/CBU a terceros son EXTERNO SALIDA | — |
| `efectivo` | SI ≥ 0 siempre · carga de movimientos 100% manual, sin PDF · moneda ARS, USD o cualquier ISO 4217 · aplica TC del período si moneda ≠ base · se comporta igual que las demás cuentas para Δ y Tablero General | — |
| `tarjeta_credito` | No tiene SI ni SF propio · opera como registro de deuda · consumos se categorizan en mes de compra como EXTERNO SALIDA · pago del resumen aparece en cuenta bancaria como LIQ.DEUDA · genera hoja Compromisos Futuros | `emisor` (Visa / Mastercard / Amex) · `fecha_cierre` (día del mes) · `fecha_vencimiento` (día del mes) |

> **Nota de hoja de ruta:** versión futura incluirá tipo `prestamo` para registro de deuda bancaria y cálculo de patrimonio neto.

### Monedas y tipo de cambio

- Cada cuenta opera en su moneda declarada.
- Para cada moneda distinta de la **moneda base del usuario** (por defecto ARS) se requiere un **TC** por período.
- TC se declara como celda amarilla editable — nunca hardcodeado.
- Si el usuario tiene múltiples monedas extranjeras, cada una tiene su propio TC.

```
Δ_en_moneda_base = Δ_moneda_propia × TC_moneda
```

Si la cuenta ya está en moneda base, TC = 1 (sin conversión).

---

