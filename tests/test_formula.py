import unittest

from cmne.core import CmneError
from cmne.formula import EvaluationContext, atom_key, context_from_projection, evaluate, validate


def atom(name):
    return {"op": "atom", "predicate": name}


class FormulaTests(unittest.TestCase):
    def test_total_three_valued_evaluation(self):
        context = EvaluationContext(world=frozenset({"door open"}),
                                    beliefs={"mara": {"door open": "accepted", "reason known": "suspended"}},
                                    scenarios={"one": frozenset({"door open"}),
                                               "two": frozenset({"door open", "Len leaves"})},
                                    ranked_scenarios=("one", "two"))
        self.assertIs(evaluate(atom("door open"), context), True)
        self.assertIsNone(evaluate(atom("unknown"), context))
        self.assertIs(evaluate({"op": "not", "operands": [atom("unknown")]}, context), None)
        self.assertIs(evaluate({"op": "necessarily", "operands": [atom("door open")]}, context), True)
        self.assertIs(evaluate({"op": "possibly", "operands": [atom("Len leaves")]}, context), True)
        self.assertIs(evaluate({"op": "believes", "observer_id": "mara", "operands": [atom("door open")]}, context), True)
        self.assertIs(evaluate({"op": "suspends", "observer_id": "mara", "operands": [atom("reason known")]}, context), True)
        self.assertIs(evaluate({"op": "in_scenario", "scenario_id": "one", "operands": [atom("Len leaves")]}, context), None)

    def test_formula_limits_and_unknown_operator(self):
        with self.assertRaises(CmneError) as error:
            validate({"op": "eval", "source": "print('bad')"})
        self.assertEqual(error.exception.code, "E-FORMULA-001")
        deep = atom("x")
        for _ in range(16):
            deep = {"op": "not", "operands": [deep]}
        with self.assertRaises(CmneError):
            validate(deep)
        wide = {"op": "and", "operands": [atom(str(i)) for i in range(16)]}
        self.assertIsNone(evaluate(wide, EvaluationContext()))
        huge = {"op": "and", "operands": [wide for _ in range(16)]}
        with self.assertRaises(CmneError):
            validate(huge)
        exactly_256 = {"op": "and", "operands": [
            {"op": "and", "operands": [atom(f"{group}-{index}") for index in range(16)]}
            for group in range(15)]}
        self.assertIsNone(evaluate(exactly_256, EvaluationContext()))

    def test_typed_predicate_from_projection(self):
        predicate = {"name": "inside", "arguments": ["mara", "kitchen"], "polarity": "positive"}
        projection = {"environment": {"facts": [predicate]},
                      "actor_a": {"id": "mara", "beliefs": {}},
                      "actor_b": {"id": "len", "beliefs": {}}}
        context = context_from_projection(projection)
        self.assertIn(atom_key(predicate), context.world)
        self.assertIs(evaluate({"op": "atom", "predicate": predicate}, context), True)


if __name__ == "__main__":
    unittest.main()
