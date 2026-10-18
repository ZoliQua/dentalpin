---
module: reports
last_verified_commit: 27442250
---

# Informes

Hub de informes de la clínica. `reports` es un módulo **solo de
lectura** que agrega datos de los módulos de negocio (facturación,
presupuestos, agenda) y los presenta en cuadros de mando. El
dashboard muestra un acceso directo por cada familia de informes que
puede alcanzar, incluido el informe de cobros que pertenece al módulo
`payments` (ver
[informes de cobros](../payments/screens/reports_payments.md)); cada
acceso aparece sólo para quien tiene el permiso de lectura de esa
familia.

## Pantallas

- [Dashboard de informes](./screens/reports.md) — punto de entrada
  con tarjetas de cada familia de informe.
- [Facturación](./screens/reports_billing.md) — totales facturados,
  por serie, por método de pago, evolución.
- [Presupuestos](./screens/reports_budgets.md) — conversión, tiempo
  en cada estado, motivos de rechazo / cierre.
- [Agenda y ocupación](./screens/reports_scheduling.md) — horas
  ocupadas, no-shows, cancelaciones, mix de profesional.

## Referencia rápida

| Acción | Permiso requerido |
|--------|-------------------|
| Ver el dashboard | cualquiera de los tres permisos siguientes |
| Ver informes de facturación | `reports.billing.read` |
| Ver informes de presupuestos | `reports.budgets.read` |
| Ver informes de agenda | `reports.scheduling.read` |
| Ver informes de cobros (los aporta `payments`) | `payments.reports.read` |
| Ver antigüedad y tendencia | `reports.financial.read` |
| Ver demografía y visitas | `reports.patient_stats.read` |
| Ver productividad | `reports.operational.read` |

## Novedades en v0.2.0 — familias de informes

- **Financiera** (`reports.financial.read`): tramos de antigüedad y
  totales emitidos mensuales, solo eje factura, con `?format=csv`. La
  tarjeta del panel lee estos números.
- **Pacientes** (`reports.patient_stats.read`): demografía actual
  (edad, género, zona con desconocidos explícitos) y frecuencia de
  visitas, con `?format=csv`. Sin pantalla propia todavía — pregunta
  al copiloto o exporta el CSV.
- **Operativa** (`reports.operational.read`): completadas por
  profesional y gabinete más el estado de planes, con `?format=csv`.
  Sin pantalla propia todavía.

## Módulos relacionados

- **Facturación, presupuestos, agenda** — fuentes de los informes
  agregados.
- **Cobros (`payments`)** — es el dueño del informe de cobros al que
  enlaza el dashboard.
- **Catálogo, pacientes** — referencias y enriquecimientos en filas
  agregadas (categoría del tratamiento, paciente, profesional).
