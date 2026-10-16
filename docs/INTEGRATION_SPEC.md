# Integration Specification — SAP Equipment Status for Maintenance Agent

**Prepared for:** Client IT / SAP Basis / Information Security · **Prepared by:** Roopa Gager · **Version:** 1.0 · **Status:** for review

## 1. Purpose
Give the maintenance AI assistant **read-only** access to equipment status, location, last maintenance and responsible technician from SAP S/4HANA, through one small service the client controls. No data is written to SAP.

## 2. Source system and APIs
| Item | Value |
|---|---|
| Source system | SAP S/4HANA (Cloud, or on-premise 2020+ with the same released APIs) |
| API 1 | `API_EQUIPMENT` (OData V2) — entity sets `Equipment`, `EquipmentPartner` |
| API 2 | `API_MAINTENANCEORDER` (OData V2) — entity set `MaintenanceOrder` |
| Operations | `GET` only, filtered by equipment number (`$filter`, `$select`, `$top`/`$skip`) |
| Consumer | `SAP Equipment API` (FastAPI) → agent tool `get_equipment_status` |

## 3. Authentication and connectivity
| Environment | Method |
|---|---|
| Proof of concept | SAP Business Accelerator Hub sandbox, `APIKey` header |
| Client (production) | OAuth 2.0 client credentials via SAP BTP destination, or principal propagation so SAP enforces the end user's roles. On-premise: SAP Cloud Connector, no inbound firewall opening. |
| SAP authorisation | Dedicated communication user/arrangement with **display-only** roles for equipment and maintenance orders, restricted to the agreed plants |
| Our service | Behind client SSO / API gateway; optional `X-API-Key`; TLS 1.2+ everywhere |

## 4. Field mapping
| Output field | SAP source | Rule |
|---|---|---|
| `equipment`, `description` | `Equipment.Equipment`, `EquipmentName` | Direct |
| `functional_location`, `functional_location_name` | `Equipment.FunctionalLocation`, `FunctionalLocationName` | Direct |
| `maintenance_plant` | `Equipment.MaintenancePlant` | Direct |
| `manufacturer`, `serial_number` | `AssetManufacturerName`, `ManufacturerSerialNumber` | Direct |
| `status` | `EquipmentIsMarkedForDeletion`, `EquipmentIsInactive`, `EquipmentIsInstalled`, `EquipmentIsAvailable` + any open order | Deleted > Inactive > Under maintenance (order not TECO/CLSD) > Installed > Available |
| `last_maintenance_date` | `MaintenanceOrder.MaintOrdBasicEndDate` | Latest order with system status TECO or CLSD. **Phase 2:** actual dates from order confirmations |
| `open_maintenance_order` | `MaintenanceOrder` not TECO/CLSD | Newest by basic start date |
| `assigned_technician` | `MaintOrdPersonResponsible` → `EquipmentPartner` (function VW, configurable) → `Equipment.MainWorkCenter` | First available; response states which source and whether it is a person or a team |

## 5. Refresh frequency and volumes
- **On demand** per agent question; no bulk extraction. Typical 2–3 SAP calls per lookup, < 1 KB each.
- **Cache 5 minutes** (`CACHE_SECONDS`): equipment master changes rarely; order status can change during the day.
- Expected load: < 1,000 lookups/day. Retries with backoff on 429/5xx; `Retry-After` honoured; 20 s timeout.
- Analytics or history needs go to the data platform (SAP Datasphere / Business Data Cloud → Databricks), not this API.

## 6. Error handling
| Case | Behaviour |
|---|---|
| Invalid equipment number | 400, rejected before reaching SAP (prevents OData injection) |
| Not found in SAP | 404 — the agent says so, never guesses |
| SAP down / auth failure | 502 with reason; no stale data presented as current |

## 7. Security and data protection
Read-only, least privilege, plant-restricted. Technician returned as an SAP ID, not a name, unless HR approves name lookup. Every request logged (user, equipment, timestamp, outcome) to the client's SIEM. Tool output is treated as data by the agent, never as instructions.

## 8. What we need from client IT
1. Communication arrangement / technical user with display roles for equipment and maintenance orders.
2. BTP destination or Cloud Connector route to the S/4HANA OData services.
3. Confirmation of the partner function used for "person responsible" (default VW) and the plants in scope.
4. A test system with representative data, and a named SAP PM contact for field validation.
