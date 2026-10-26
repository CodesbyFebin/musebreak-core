from .order_approve import OrderApproveCircuit
from .audit_chain import AuditChainCircuit
from .utr_unique import UTRUniqueCircuit
from .vuln_chain import VulnChainCircuit
from .business_isolation import BusinessIsolationCircuit
from .fido_binding import FidoBindingCircuit

CIRCUITS = {
    "order_approve": OrderApproveCircuit,
    "audit_chain": AuditChainCircuit,
    "utr_unique": UTRUniqueCircuit,
    "vuln_chain": VulnChainCircuit,
    "business_isolation": BusinessIsolationCircuit,
    "fido_binding": FidoBindingCircuit,
}

__all__ = ["CIRCUITS", "OrderApproveCircuit", "AuditChainCircuit", "UTRUniqueCircuit",
           "VulnChainCircuit", "BusinessIsolationCircuit", "FidoBindingCircuit"]
