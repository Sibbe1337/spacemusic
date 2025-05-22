from fastapi import APIRouter, Body
from typing import Dict, Any # Added Body and Dict, Any for more specific typing
from libs.py_common.flags import is_enabled
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

CALCULATOR_V2_FLAG = "calculator-v2-range" 

# Example request model (kan utökas)
# from pydantic import BaseModel
# class CalculatorInput(BaseModel):
#     input_value: float
#     operation: str = "multiply"
#     factor: float = 1.0

@router.post("/calculate") # Antag att detta är endpointen
async def calculate_route(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]: 
    """Calculates a value, uses v2 logic if feature flag is ON."""
    
    input_value = data.get("input_value", 0.0)
    operation = data.get("operation", "sum") # exempel på operation
    factor = data.get("factor", 1) # exempel på faktor

    logger.info("calculate_route called", input_data=data, flag_name=CALCULATOR_V2_FLAG)
    
    base_result = 0
    # Enkel exempel-logik baserat på input
    if operation == "sum":
        base_result = input_value + factor
    elif operation == "multiply":
        base_result = input_value * factor
    else:
        base_result = input_value # default

    user_for_flag = data.get("user_id", "system") # Försök hämta user_id, annars default till system

    if is_enabled(CALCULATOR_V2_FLAG, user_key=user_for_flag):
        logger.info(f"Feature flag '{CALCULATOR_V2_FLAG}' is ON for user '{user_for_flag}'. Using V2 logic.")
        # --- Logic for V2 range ---
        # Exempel: V2-logik applicerar en extra bonus eller en annan beräkningsmodell
        final_value = base_result * 2 # Exempel: V2 dubblar värdet
        calculation_details = {
            "version": "v2",
            "info": "Advanced V2 calculation applied (e.g., doubled value).",
            "factors_used": {"base_result": base_result, "v2_multiplier": 2}
        }
    else:
        logger.info(f"Feature flag '{CALCULATOR_V2_FLAG}' is OFF for user '{user_for_flag}'. Using V1 logic.")
        # --- Logic for V1 range (or default behavior) ---
        final_value = base_result
        calculation_details = {
            "version": "v1",
            "info": "Standard V1 calculation applied.",
            "factors_used": {"base_result": base_result}
        }
    
    return {
        "input_data": data,
        "final_value": final_value,
        "calculation_details": calculation_details
    }

# För att inkludera denna router i din huvudapp (t.ex. services/offers/main.py):
# from .routes import calculator as calculator_routes // Eller hur du nu har organiserat det
# app.include_router(calculator_routes.router, prefix="/calc-api", tags=["calculator"])

# ... rest of your calculator routes ... 