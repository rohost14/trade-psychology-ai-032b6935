from app.models.holding import Holding
from app.models.order import Order
from app.models.instrument import Instrument
from app.schemas.holding import Holding as HoldingSchema
from app.schemas.order import Order as OrderSchema

# Check Models
print(f"Holding.tradingsymbol exists: {hasattr(Holding, 'tradingsymbol')}")
print(f"Order.tradingsymbol exists: {hasattr(Order, 'tradingsymbol')}")
print(f"Instrument.tradingsymbol exists: {hasattr(Instrument, 'tradingsymbol')}")

# Check Schemas (pydantic 2.x uses model_fields, 1.x uses __fields__)
try:
    holding_fields = HoldingSchema.model_fields
except AttributeError:
    holding_fields = HoldingSchema.__fields__

try:
    order_fields = OrderSchema.model_fields
except AttributeError:
    order_fields = OrderSchema.__fields__

print(f"HoldingSchema has tradingsymbol: {'tradingsymbol' in holding_fields}")
print(f"OrderSchema has tradingsymbol: {'tradingsymbol' in order_fields}")
