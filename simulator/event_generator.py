from models.events import RawEvent
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import random
import json


class EventSimulator:
    """Generates realistic synthetic events for pipeline testing."""
    
    # Event templates
    WEBHOOK_NAMES = [
        "orders/create",
        "orders/update",
        "orders/delete",
        "inventory/update",
        "customers/create",
        "fulfillment/update"
    ]
    
    WEBHOOK_ERRORS = [
        "DELIVERY_FAIL",
        "TIMEOUT",
        "AUTH_FAIL",
        "RATE_LIMIT",
        "INVALID_PAYLOAD"
    ]
    
    API_ENDPOINTS = [
        "/api/v1/products",
        "/api/v1/orders",
        "/api/v1/customers",
        "/api/v1/inventory",
        "/api/v1/auth/token"
    ]
    
    API_ERRORS = {
        401: "TOKEN_INVALID",
        403: "SCOPE_MISSING",
        404: "NOT_FOUND",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE"
    }
    
    TICKET_SUBJECTS = [
        "Webhooks not working after migration",
        "Getting 401 errors on API calls",
        "Checkout page shows error",
        "How do I configure webhooks?",
        "Orders not syncing between systems",
        "Cannot authenticate with new API",
        "Payment processing failing",
        "Inventory updates not working",
        "Migration guide unclear on step X",
        "Getting timeout errors during peak hours"
    ]
    
    INDUSTRIES = ["fashion", "electronics", "food", "beauty", "home", "sports"]
    FRAMEWORKS = ["shopify", "custom", "react", "vue", "nextjs"]
    REGIONS = ["US-WEST", "US-EAST", "EU-CENTRAL", "APAC"]
    
    def __init__(self):
        self.merchant_ids = [f"m_{i:04d}" for i in range(1, 101)]
    
    def generate_random_event(
        self,
        event_type: Optional[Literal["webhook_fail", "api_error", "checkout_fail", "ticket"]] = None,
        merchant_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> RawEvent:
        """
        Generate a single random event.
        
        Args:
            event_type: Type of event (random if None)
            merchant_id: Merchant ID (random if None)
            timestamp: Event timestamp (now if None)
        
        Returns:
            RawEvent object ready for ingestion
        """
        if event_type is None:
            event_type = random.choice(["webhook_fail", "api_error", "checkout_fail", "ticket"])
        
        if merchant_id is None:
            merchant_id = random.choice(self.merchant_ids)
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Generate payload based on type
        if event_type == "webhook_fail":
            payload = {
                "webhook_name": random.choice(self.WEBHOOK_NAMES),
                "error_code": random.choice(self.WEBHOOK_ERRORS),
                "retry_count": random.randint(1, 5),
                "migration_stage": random.randint(1, 4)
            }
            source = "webhook_service"
        
        elif event_type == "api_error":
            status_code = random.choice(list(self.API_ERRORS.keys()))
            payload = {
                "endpoint": random.choice(self.API_ENDPOINTS),
                "status_code": status_code,
                "error_code": self.API_ERRORS[status_code],
                "response_time_ms": random.randint(100, 5000),
                "migration_stage": random.randint(1, 4)
            }
            source = "api_logs"
        
        elif event_type == "checkout_fail":
            payload = {
                "error_code": random.choice(["PAYMENT_DECLINED", "TIMEOUT", "VALIDATION_ERROR"]),
                "cart_value": random.randint(50, 500),
                "customer_region": random.choice(self.REGIONS),
                "migration_stage": random.randint(1, 4)
            }
            source = "checkout_monitor"
        
        else:  # ticket
            payload = {
                "subject": random.choice(self.TICKET_SUBJECTS),
                "description": "Customer reported issue after migration",
                "priority": random.choice(["low", "medium", "high"]),
                "migration_stage": random.randint(1, 4)
            }
            source = "zendesk"
        
        # Generate idempotency key
        idempotency_key = f"{event_type}_{merchant_id}_{timestamp.isoformat()}_{random.randint(0, 9999)}"
        
        return RawEvent(
            event_id=uuid4(),
            event_type=event_type,
            merchant_id=merchant_id,
            timestamp=timestamp,
            payload=payload,
            source=source,
            idempotency_key=idempotency_key
        )
    
    def generate_random_events(self, count: int = 10) -> List[RawEvent]:
        """
        Generate multiple random events.
        
        Args:
            count: Number of events to generate
        
        Returns:
            List of RawEvent objects
        """
        return [self.generate_random_event() for _ in range(count)]
    
    def generate_spike_scenario(
        self,
        event_type: Literal["webhook_fail", "api_error", "checkout_fail"] = "webhook_fail",
        error_pattern: Dict[str, str] = None,
        merchant_count: int = 15,
        event_count: int = 50,
        migration_stage: int = 2,
        time_window_minutes: int = 30
    ) -> List[RawEvent]:
        """
        Generate a concentrated spike scenario (burst of similar errors).
        
        Useful for testing pattern detection and clustering.
        
        Args:
            event_type: Type of event to spike
            error_pattern: Error characteristics (e.g., {"webhook": "orders/create"})
            merchant_count: Number of merchants affected
            event_count: Total events to generate
            migration_stage: Migration stage for affected merchants
            time_window_minutes: Duration of spike
        
        Returns:
            List of RawEvent objects simulating a spike
        """
        if error_pattern is None:
            error_pattern = {}
        
        events = []
        spike_start = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        affected_merchants = random.sample(self.merchant_ids, min(merchant_count, len(self.merchant_ids)))
        
        for i in range(event_count):
            timestamp = spike_start + timedelta(
                minutes=random.uniform(0, time_window_minutes)
            )
            merchant_id = random.choice(affected_merchants)
            
            # Generate event with spike characteristics
            if event_type == "webhook_fail":
                payload = {
                    "webhook_name": error_pattern.get("webhook", random.choice(self.WEBHOOK_NAMES)),
                    "error_code": error_pattern.get("error", random.choice(self.WEBHOOK_ERRORS)),
                    "retry_count": random.randint(1, 5),
                    "migration_stage": migration_stage
                }
                source = "webhook_service"
            
            elif event_type == "api_error":
                status_code = int(error_pattern.get("status_code", random.choice(list(self.API_ERRORS.keys()))))
                payload = {
                    "endpoint": error_pattern.get("endpoint", random.choice(self.API_ENDPOINTS)),
                    "status_code": status_code,
                    "error_code": self.API_ERRORS.get(status_code, "UNKNOWN"),
                    "response_time_ms": random.randint(5000, 30000),
                    "migration_stage": migration_stage
                }
                source = "api_logs"
            
            else:  # checkout_fail
                payload = {
                    "error_code": error_pattern.get("error", "PAYMENT_DECLINED"),
                    "cart_value": random.randint(100, 1000),
                    "customer_region": random.choice(self.REGIONS),
                    "migration_stage": migration_stage
                }
                source = "checkout_monitor"
            
            idempotency_key = f"spike_{timestamp.isoformat()}_{merchant_id}_{i}"
            
            event = RawEvent(
                event_id=uuid4(),
                event_type=event_type,
                merchant_id=merchant_id,
                timestamp=timestamp,
                payload=payload,
                source=source,
                idempotency_key=idempotency_key
            )
            
            events.append(event)
        
        return events
    
    def generate_spike_by_component(
        self,
        component: Literal["webhook", "api", "checkout"],
        merchant_count: int = 15,
        event_count: int = 50,
        migration_stage: int = 2
    ) -> List[RawEvent]:
        """
        Generate spike for a specific component.
        
        Args:
            component: System component (webhook, api, or checkout)
            merchant_count: Number of merchants affected
            event_count: Total events
            migration_stage: Migration stage
        
        Returns:
            List of RawEvent objects
        """
        if component == "webhook":
            return self.generate_spike_scenario(
                event_type="webhook_fail",
                error_pattern={"webhook": "orders/create", "error": "DELIVERY_FAIL"},
                merchant_count=merchant_count,
                event_count=event_count,
                migration_stage=migration_stage
            )
        
        elif component == "api":
            return self.generate_spike_scenario(
                event_type="api_error",
                error_pattern={"endpoint": "/api/v1/orders", "status_code": "500"},
                merchant_count=merchant_count,
                event_count=event_count,
                migration_stage=migration_stage
            )
        
        else:  # checkout
            return self.generate_spike_scenario(
                event_type="checkout_fail",
                error_pattern={"error": "PAYMENT_DECLINED"},
                merchant_count=merchant_count,
                event_count=event_count,
                migration_stage=migration_stage
            )
    
    def generate_background_noise(
        self,
        duration_minutes: int = 60,
        events_per_minute: float = 1.0
    ) -> List[RawEvent]:
        """
        Generate realistic background event noise (normal operations).
        
        Args:
            duration_minutes: Duration of background period
            events_per_minute: Average events per minute
        
        Returns:
            List of RawEvent objects
        """
        events = []
        event_count = int(duration_minutes * events_per_minute)
        start_time = datetime.utcnow() - timedelta(minutes=duration_minutes)
        
        for i in range(event_count):
            timestamp = start_time + timedelta(
                minutes=random.uniform(0, duration_minutes)
            )
            events.append(self.generate_random_event(timestamp=timestamp))
        
        return events


if __name__ == "__main__":
    # Demo
    print("Event Simulator Demo")
    print("=" * 60)
    
    simulator = EventSimulator()
    
    # Generate 5 random events
    print("\n1. Random Events:")
    random_events = simulator.generate_random_events(5)
    for event in random_events:
        print(f"   {event.event_type}: {event.merchant_id} - {event.source}")
    
    # Generate spike
    print("\n2. Spike Scenario (17 merchants, 50 webhook failures):")
    spike_events = simulator.generate_spike_scenario(
        event_type="webhook_fail",
        error_pattern={"webhook": "orders/create", "error": "DELIVERY_FAIL"},
        merchant_count=17,
        event_count=50,
        migration_stage=2
    )
    print(f"   Generated {len(spike_events)} spike events")
    print(f"   Affected merchants: {len(set(e.merchant_id for e in spike_events))}")
    print(f"   Time range: {min(e.timestamp for e in spike_events)} to {max(e.timestamp for e in spike_events)}")
    
    # Generate background noise
    print("\n3. Background Noise (60 min, 1 event/min):")
    noise_events = simulator.generate_background_noise(duration_minutes=60, events_per_minute=1.0)
    print(f"   Generated {len(noise_events)} background events")
    
    print("\n" + "=" * 60)
