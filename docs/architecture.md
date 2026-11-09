# Architecture

The rules behind this picture are in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) and the ADRs in
[`adr/`](adr/). In short:

- Layers (spec 2.3): `L0 build` → `L1 contracts, architecture-guard, test-support` → `L2 observability` →
  `L3 redis, messaging, resilience` → `L4 external-call, cache-sync` → `L5 apps and qa`. A module may depend only on
  modules of the same or a lower layer, and never in a cycle.
- Single owner per concern (spec 2.2): exactly one brick creates each infrastructure bean.
- Every brick has `core` (stack-neutral), `reactive` (WebFlux) and `servlet` (Spring MVC) modules.

## Module dependency graph

Generated from the manifests' `requires` by `python tools/manifests.py generate` (transitive edges omitted for
readability). An arrow `A --> B` means "A requires B". Do not edit the block by hand.

<!-- amef:graph:start -->
```mermaid
flowchart BT
  subgraph L1["L1 foundation"]
    architecture_guard["architecture-guard"]
    contracts["contracts"]
    test_support["test-support"]
  end
  subgraph L2["L2 observability"]
    observability["observability"]
  end
  subgraph L3["L3 infrastructure bricks"]
    messaging["messaging"]
    redis["redis"]
    resilience["resilience"]
  end
  subgraph L4["L4 integration bricks"]
    cache_sync["cache-sync"]
    external_call["external-call"]
  end
  subgraph L5["L5 apps and qa"]
    audit_service["audit-service"]
    gateway["gateway"]
    qa["qa"]
    sample_service_reactive["sample-service-reactive"]
    sample_service_servlet["sample-service-servlet"]
  end
  architecture_guard --> contracts
  test_support --> contracts
  observability --> contracts
  messaging --> observability
  redis --> observability
  resilience --> observability
  cache_sync --> messaging
  cache_sync --> redis
  external_call --> messaging
  external_call --> redis
  external_call --> resilience
  audit_service --> messaging
  gateway --> messaging
  gateway --> redis
  gateway --> resilience
  sample_service_reactive --> cache_sync
  sample_service_reactive --> external_call
  sample_service_servlet --> cache_sync
  sample_service_servlet --> external_call
```
<!-- amef:graph:end -->
