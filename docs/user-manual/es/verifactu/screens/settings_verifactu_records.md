---
module: verifactu
screen: records
route: /settings/verifactu/records
related_endpoints:
  - DELETE /api/v1/verifactu/certificate/{cert_id}
  - DELETE /api/v1/verifactu/producer/declaracion
  - GET /api/v1/verifactu/certificate
  - GET /api/v1/verifactu/certificate/history
  - GET /api/v1/verifactu/health
  - GET /api/v1/verifactu/nif-check
  - GET /api/v1/verifactu/producer/defaults
  - GET /api/v1/verifactu/queue
  - GET /api/v1/verifactu/records
  - GET /api/v1/verifactu/records/{record_id}
  - GET /api/v1/verifactu/records/{record_id}/attempts
  - GET /api/v1/verifactu/records/{record_id}/xml
  - GET /api/v1/verifactu/settings
  - GET /api/v1/verifactu/vat-mapping
  - POST /api/v1/verifactu/certificate
  - POST /api/v1/verifactu/queue/process-now
  - POST /api/v1/verifactu/queue/retry-all
  - POST /api/v1/verifactu/queue/{record_id}/retry
  - PUT /api/v1/verifactu/producer
  - PUT /api/v1/verifactu/settings
  - PUT /api/v1/verifactu/vat-mapping/{vat_type_id}
related_permissions:
  - verifactu.settings.read
  - verifactu.settings.configure
  - verifactu.records.read
  - verifactu.queue.manage
  - verifactu.environment.promote
related_paths:
  - backend/app/modules/verifactu/frontend/pages/settings/verifactu/records.vue
last_verified_commit: f3ef82cd
---

# Libro fiscal

El historial inmutable de los registros enviados a la AEAT. Cada fila es
un registro encadenado: modificar o borrar un registro aceptado rompería
la cadena de hashes, por lo que esta página es de solo lectura.

## Cómo se usa

1. Abre **Ajustes > Verifactu > Libro fiscal**.
2. Acota la lista con los dos filtros:
   - **Estado**: todos, aceptado, aceptado con errores, rechazado o
     pendiente.
   - **Tipo**: todos, F1, F2 o R1.
   Al cambiar cualquiera de los dos, la lista vuelve a la primera página.
3. Cambia de página con las flechas de abajo (50 registros por página).
   Al lado se muestra el total.

## Qué significa cada columna

| Columna | Significado |
|---------|-------------|
| Fecha | Cuándo se creó el registro. |
| Tipo | `F1` factura completa, `F2` factura simplificada, `R1` rectificativa. |
| Número | Serie y número de la factura a la que pertenece el registro. |
| Importe | Importe total enviado a la AEAT. |
| Estado | `accepted`, `accepted_with_errors`, `rejected` o `pending`. |
| CSV AEAT | El código CSV que devuelve la AEAT cuando acepta el registro. |

## Permisos

| Qué puedes ver / hacer | Permiso |
|------------------------|---------|
| Ver el libro fiscal y usar los filtros | `verifactu.records.read` |

## Problemas frecuentes

- **El libro está vacío.** El módulo solo escribe un registro cuando se
  emite una factura con Verifactu activo. Revisa **Ajustes > Verifactu**
  para la configuración del productor y el entorno activo.
- **Un filtro no devuelve filas.** Los registros solo pasan a aceptado
  cuando la AEAT los confirma; usa **Estado: todos** para ver también los
  pendientes y los rechazados.
- **No aparece la entrada del menú.** El módulo es opcional: un
  administrador debe instalarlo desde la administración de módulos y
  conceder `verifactu.records.read`.
