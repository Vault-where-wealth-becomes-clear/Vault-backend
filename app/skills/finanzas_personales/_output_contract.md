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
    "alertas": ["..."]
  },
  "proyeccion_patrimonial": {
    "banda_baja": 0, "banda_media": 0, "banda_alta": 0
  },
  "compromisos_futuros": {
    "cuotas_pendientes": [ { "descripcion": "...", "cuota_actual": 0, "total_cuotas": 0, "monto": 0, "proximo_vencimiento": "2025-07-15" } ]
  },
  "transacciones": [
    { "date": "2025-06-01", "description": "...", "amount": 0, "currency": "ARS", "category": "...", "confidence": 0.95, "installments": null }
  ]
}
```

La clave "transacciones" es OBLIGATORIA siempre, sin importar qué módulos se pidieron —
es el detalle transaccional plano que alimenta el registro histórico de movimientos.
