from .order_approve import OrderApproveCircuit
from .audit_chain import AuditChainCircuit
from .utr_unique import UTRUniqueCircuit
from .vuln_chain import VulnChainCircuit
from .business_isolation import BusinessIsolationCircuit

CIRCUITS = {
    "order_approve": OrderApproveCircuit,
    "audit_chain": AuditChainCircuit,
    "utr_unique": UTRUniqueCircuit,
    "vuln_chain": VulnChainCircuit,
    "business_isolation": BusinessIsolationCircuit,
}

__all__ = ["CIRCUITS", "OrderApproveCircuit", "AuditChainCircuit", "UTRUniqueCircuit",
           "VulnChainCircuit", "BusinessIsolationCircuit"]
