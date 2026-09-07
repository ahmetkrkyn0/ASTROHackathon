# A fired replan trigger, published by the pose monitor when telemetry
# crosses a threshold from backend/app/replan_triggers.py or
# backend/app/slip_model.py. One message per fired trigger per pose.
string trigger_id            # e.g. "corridor_violation", "slip_accumulation"
string detail                # human-readable evidence string from the check
string recommended_action    # "continue" | "replan" | "stop_and_localize"
builtin_interfaces/Time stamp
