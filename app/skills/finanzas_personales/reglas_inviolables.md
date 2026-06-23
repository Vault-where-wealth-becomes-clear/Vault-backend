## Reglas inviolables (15)

1. **Cuentas declaradas por el usuario** — no asumir cuentas fijas; registrar solo las informadas
2. **SI respeta el límite del tipo de cuenta** — `caja_de_ahorro`, `billetera_virtual` y `efectivo`: SI ≥ 0; `cuenta_corriente`: SI ≥ −descubierto (0 si no hay descubierto declarado); `tarjeta_credito`: no tiene SI
3. **TC por moneda, celda amarilla editable** — un TC por moneda extranjera, nunca hardcodeado
4. **Reconciliación antes de resultado completo** — si una cuenta falla, continuar con las demás y marcar resultado como INCOMPLETO hasta resolución total
5. **VISA / tarjeta en devengado** — consumo categorizado en mes de compra; LIQ.DEUDA en mes del débito bancario
6. **Internos se cancelan solos** — no eliminar manualmente; la suma de Δ los neutraliza
7. **REINTEGRO netea en su categoría original** — nunca en VARIOS
8. **RENDIMIENTO no es gasto** — es ingreso especial, reportado por separado; no entra en la tasa de ahorro operativa ni en los ingresos operativos recurrentes
9. **Libro diario con saldo corriente acumulativo** — desde SI, fila a fila, sin saltos
10. **Encadenamiento verificado** — SF(N) = SI(N+1) para todas las cuentas antes de armar el período
11. **Paleta de colores dual** — dark mode por defecto. El usuario declara su preferencia en `modo_visual` (Módulo 0). Si declara `light`, aplicar la paleta light completa en todo el archivo. Nunca mezclar colores de ambas paletas en el mismo archivo ni en la misma hoja. La preferencia aplica a todos los archivos generados en la sesión
12. **Resultado parcial permitido** — si una cuenta falla reconciliación, continuar con las demás y marcar el resultado como INCOMPLETO hasta resolución
13. **Ingresos operativos ≠ Δ AL** — separar siempre Δ PL (ahorro operativo) de Δ cartera (rendimiento de activos) en el Tablero General
14. **Ingresos extraordinarios etiquetados** — si un EXTERNO ENTRADA supera el doble del promedio histórico, preguntar recurrencia antes de incluirlo en la tasa de ahorro
15. **Meses sin movimientos válidos** — SF = SI, Δ = 0, generar hoja normalmente sin alerta. **Aclaración de alcance:** esta regla aplica exclusivamente a cuentas bancarias, billeteras, efectivo y tarjetas de crédito del Módulo 1. NO aplica a la cuenta comitente del Módulo 4 — para cartera, la ausencia de snapshot se trata como N/D (dato desconocido), nunca como Δ = 0. Estas dos reglas no son intercambiables.

---

## Alertas del sistema (errores de datos)

| Condición | Mensaje |
|-----------|---------|
| SI viola límite del tipo | ⚠️ EXTRACTO INCOMPLETO: SI de "[cuenta]" = [valor]. Mínimo para [tipo]: [límite]. Verificar que el extracto cubra el período completo. |
| Reconciliación falla | ❌ ERROR DE RECONCILIACIÓN en "[cuenta]": diferencia de $[Δ]. Revisar movimientos faltantes o duplicados. Procesando resto de cuentas en modo RESULTADO PARCIAL. |
| Encadenamiento roto | ⚠️ INCONSISTENCIA: SF de "[cuenta]" en [mes N] = [X], pero SI en [mes N+1] = [Y]. Diferencia: $[X−Y]. |
| TC no informado | ⚠️ Falta TC para [moneda] en [período]. Ingresar en celda amarilla para continuar. |
| Movimiento sin clasificar | ⚠️ Movimiento sin clasificar en "[cuenta]" el [fecha]: "[descripción]". Revisar y asignar tipo manualmente. |
| CPP no disponible | ℹ️ CPP no actualizado para [instrumento] en [mes]. Rendimiento no disponible — se muestra solo valuación. |
| Proyección insuficiente | ℹ️ Se necesitan al menos 2 meses completos para activar la proyección patrimonial. |

---

