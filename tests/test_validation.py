import json

from data.loader import DEFAULT_DATASET_PATH
from test_fulfillment import FakeModelClient
from workflows.fulfillment.validation import differences
from workflows.fulfillment.workflow import FulfillmentWorkflow


def test_comparison_detects_duplicate_items_and_preserves_action_order():
    expected = {'items': [{'product_id': 'A', 'quantity': 1}, {'product_id': 'B', 'quantity': 2}]}
    assert not differences({'items': list(reversed(expected['items']))}, expected)
    assert differences({'items': [expected['items'][0], expected['items'][0]]}, expected)
    assert differences({'actions': [2, 1]}, {'actions': [1, 2]})


def test_overweight_order_has_a_valid_rejection_path(tmp_path):
    data = json.loads(DEFAULT_DATASET_PATH.read_text())
    next(row for row in data['products'] if row['product_id'] == 'P101')['weight_kg'] = 26
    truth = next(row for row in data['fulfillment_ground_truth'] if row['order_id'] == 'ORD-1001')
    truth.update(expected_decision='reject_shipping_constraint', expected_shipping_usd='', expected_total_usd='')
    path = tmp_path / 'overweight.json'
    path.write_text(json.dumps(data))
    result = FulfillmentWorkflow(model_client=FakeModelClient(), dataset_path=path, log_dir=tmp_path).run('ORD-1001')
    assert result.check.passed, result.check.errors
    assert result.outcome == 'rejected_shipping_constraint'
    assert result.final_state['reservations'] == {}
