"""Built-in stages for SimulateDecision pipeline."""

from __future__ import annotations


class StageStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class Stage:
    """Abstract base class for pipeline stages."""

    def __init__(self, config):
        self.config = config
        self._predictor = None

    @property
    def name(self) -> str:
        return self.config.name

    def get_predictor(self):
        if self._predictor is None:
            from simulate_decision.signatures.registry import get_signature_registry
            registry = get_signature_registry()
            self._predictor = registry.get_predictor(
                self.config.signature_name,
                self.config.signature_type
            )
        return self._predictor

    def prepare_inputs(self, context):
        return {"input_concept": context.concept}

    def execute(self, context):
        raise NotImplementedError

    def _estimate_tokens(self, result: object) -> int:
        total = 0
        for field_name in dir(result):
            if not field_name.startswith("_"):
                try:
                    value = getattr(result, field_name)
                    if isinstance(value, str):
                        total += len(value.split())
                except Exception:
                    pass
        return total


class StageResult:
    def __init__(self, status, output=None, reasoning="", tokens_used=0, error=None, attempts=1):
        self.status = status
        self.output = output or {}
        self.reasoning = reasoning
        self.tokens_used = tokens_used
        self.error = error
        self.attempts = attempts

    @property
    def is_success(self) -> bool:
        return self.status == StageStatus.SUCCESS


class StageConfig:
    def __init__(self, name, signature_name, signature_type=None, enabled=True, retries=1, on_failure="retry"):
        self.name = name
        self.signature_name = signature_name
        self.signature_type = signature_type
        self.enabled = enabled
        self.retries = retries
        self.on_failure = on_failure


class PipelineContext:
    def __init__(self, concept, current_strategy="", iteration=1):
        self.concept = concept
        self.current_strategy = current_strategy
        self.iteration = iteration
        self.stage_results = {}

    def get_output(self, stage_name):
        result = self.stage_results.get(stage_name)
        return result.output if result else None


def register_stage(name: str):
    def decorator(cls):
        return cls
    return decorator


class DeconstructStage(Stage):
    """Stage for atomic deconstruction of concepts."""

    @property
    def name(self) -> str:
        return "deconstruct"

    def prepare_inputs(self, context):
        return {
            "input_concept": context.concept,
            "instruction_strategy": context.current_strategy,
        }

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            output = {
                "atomic_atoms": getattr(result, "atomic_atoms", ""),
                "noise_detected": getattr(result, "noise_detected", ""),
            }

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class VerifyStage(Stage):
    """Stage for axiomatic verification of atoms."""

    @property
    def name(self) -> str:
        return "verify"

    def prepare_inputs(self, context):
        deconstruct_output = context.get_output("deconstruct")
        atomic_atoms = ""
        if deconstruct_output:
            atomic_atoms = deconstruct_output.get("atomic_atoms", "")
        return {"atomic_atoms": atomic_atoms}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)

            if not inputs["atomic_atoms"]:
                return StageResult(status=StageStatus.FAILED, error="No atoms to verify")

            result = predictor(**inputs)

            output = {
                "verified_axioms": getattr(result, "verified_axioms", ""),
                "rejection_reason": getattr(result, "rejection_reason", ""),
            }

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class ReconstructStage(Stage):
    """Stage for technical reconstruction from axioms."""

    @property
    def name(self) -> str:
        return "reconstruct"

    def prepare_inputs(self, context):
        verify_output = context.get_output("verify")
        verified_axioms = ""
        if verify_output:
            verified_axioms = verify_output.get("verified_axioms", "")
        return {"verified_axioms": verified_axioms}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)

            if not inputs["verified_axioms"]:
                return StageResult(status=StageStatus.FAILED, error="No verified axioms")

            result = predictor(**inputs)

            output = {
                "technical_blueprint": getattr(result, "technical_blueprint", ""),
            }

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class AnalyzeStage(Stage):
    """Stage for failure analysis and strategy optimization."""

    @property
    def name(self) -> str:
        return "analyze"

    def prepare_inputs(self, context):
        verify_output = context.get_output("verify")
        error_signal = ""
        if verify_output:
            error_signal = verify_output.get("rejection_reason", "")
        return {
            "error_signal": error_signal,
            "previous_atoms": "",
        }

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            output = {
                "new_instruction_strategy": getattr(result, "new_instruction_strategy", ""),
            }

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class ExpandStage(Stage):
    """Stage for expanding concepts with detail."""

    @property
    def name(self) -> str:
        return "expand"

    def prepare_inputs(self, context):
        return {"concept": context.concept, "depth": "medium"}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            output = {"expanded_content": getattr(result, "expanded_content", "")}

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class AbstractStage(Stage):
    """Stage for abstracting concepts to their essence."""

    @property
    def name(self) -> str:
        return "abstract"

    def prepare_inputs(self, context):
        deconstruct_output = context.get_output("deconstruct")
        content = ""
        if deconstruct_output:
            content = deconstruct_output.get("atomic_atoms", "")
        return {"specific_content": content or context.concept}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            output = {"abstract_form": getattr(result, "abstract_form", "")}

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class CritiqueStage(Stage):
    """Stage for critiquing and evaluating content quality."""

    @property
    def name(self) -> str:
        return "critique"

    def prepare_inputs(self, context):
        reconstruct_output = context.get_output("reconstruct")
        content = ""
        if reconstruct_output:
            content = reconstruct_output.get("technical_blueprint", "")
        return {"content": content or context.concept}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            try:
                score = float(getattr(result, "score", "0"))
            except (ValueError, TypeError):
                score = 0.0

            output = {"score": score, "feedback": getattr(result, "feedback", "")}

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))


class CompareStage(Stage):
    """Stage for comparing concepts or analyzing relationships."""

    @property
    def name(self) -> str:
        return "compare"

    def prepare_inputs(self, context):
        prev_output = None
        for stage_name in ["requirement_extraction", "use_case_mapping", "architecture_design", "deconstruct"]:
            prev_output = context.get_output(stage_name)
            if prev_output:
                break

        content_a = context.concept
        content_b = ""
        if prev_output:
            for key in ["atomic_atoms", "expanded_content", "abstract_form", "use_cases"]:
                if key in prev_output:
                    content_b = prev_output[key]
                    break

        return {"concept_a": content_a, "concept_b": content_b or content_a}

    def execute(self, context):
        try:
            predictor = self.get_predictor()
            inputs = self.prepare_inputs(context)
            result = predictor(**inputs)

            output = {
                "comparison_result": getattr(result, "comparison_result", ""),
                "similarities": getattr(result, "similarities", ""),
                "differences": getattr(result, "differences", ""),
            }

            return StageResult(
                status=StageStatus.SUCCESS,
                output=output,
                reasoning=getattr(result, "reasoning", ""),
                tokens_used=self._estimate_tokens(result),
            )
        except Exception as e:
            return StageResult(status=StageStatus.FAILED, error=str(e))
