from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class DeterministicPolicy:
    """Tiny deterministic pre-response gate for the exercise.

    Inputs containing the token BLOCK_ME are rejected. No model/provider call
    is made before this decision.
    """

    def check(self, user_input: str) -> PolicyDecision:
        if "BLOCK_ME" in user_input:
            return PolicyDecision(False, "policy_blocked")
        return PolicyDecision(True, "allowed")
