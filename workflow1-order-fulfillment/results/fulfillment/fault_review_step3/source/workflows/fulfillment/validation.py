"""Verification against authoritative tables, never gold labels."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

STAGES = ('inventory_agent', 'pricing_agent', 'shipping_agent', 'planning_agent', 'executor_agent')


def money(value):
    return float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def authoritative_inputs(dataset, state, order_id):
    order = dataset.get_order(order_id)
    items = dataset.get_order_items(order_id)
    rate = dataset.get_shipping_rate(order.shipping_zone, order.shipping_service)
    return {
        'get_order_context': {'order': order.model_dump(mode='json'),
                              'items': [item.model_dump(mode='json') for item in items]},
        'get_inventory_inputs': {'order_id': order_id, 'items': [
            {'product_id': item.product_id, 'requested_qty': item.quantity,
             **{key: state.inventory[item.product_id][key] for key in
                ('available_qty', 'reserved_qty', 'warehouse_id', 'updated_at')}} for item in items]},
        'get_pricing_inputs': {'order_id': order_id, 'items': [
            {'product_id': item.product_id, 'quantity': item.quantity,
             'unit_price_usd': item.unit_price_at_purchase_usd} for item in items]},
        'get_shipping_inputs': {
            'order_id': order_id, 'zone': order.shipping_zone, 'service': order.shipping_service,
            'items': [{'product_id': item.product_id, 'quantity': item.quantity,
                       'unit_weight_kg': dataset.get_product(item.product_id).weight_kg} for item in items],
            'rate': rate.model_dump(mode='json'),
        },
    }


def reference_artifacts(dataset, initial, order_id):
    """Compute the business rules without reading fulfillment_ground_truth."""
    order = dataset.get_order(order_id)
    items = dataset.get_order_items(order_id)
    rate = dataset.get_shipping_rate(order.shipping_zone, order.shipping_service)
    inventory_rows = [
        {'product_id': item.product_id, 'requested_qty': item.quantity,
         'available_qty': initial.inventory[item.product_id]['available_qty'],
         'sufficient': initial.inventory[item.product_id]['available_qty'] >= item.quantity} for item in items]
    inventory = {'items': inventory_rows, 'all_items_available': all(row['sufficient'] for row in inventory_rows)}
    pricing_rows = [
        {'product_id': item.product_id, 'quantity': item.quantity,
         'unit_price_usd': item.unit_price_at_purchase_usd,
         'line_total_usd': money(Decimal(str(item.unit_price_at_purchase_usd)) * item.quantity)} for item in items]
    subtotal = money(sum((Decimal(str(item.unit_price_at_purchase_usd)) * item.quantity for item in items), Decimal(0)))
    weight = sum(Decimal(str(dataset.get_product(item.product_id).weight_kg)) * item.quantity for item in items)
    shipping_cost = money(Decimal(str(rate.base_price_usd)) + Decimal(str(rate.price_per_kg_usd)) * weight)
    shipping = {'zone': order.shipping_zone, 'service': order.shipping_service,
                'total_weight_kg': float(weight), 'shipping_cost_usd': shipping_cost,
                'max_weight_kg': rate.max_weight_kg, 'within_weight_limit': weight <= Decimal(str(rate.max_weight_kg)),
                'estimated_days': rate.estimated_days}
    decision = ('reject_insufficient_stock' if not inventory['all_items_available'] else
                'reject_shipping_constraint' if not shipping['within_weight_limit'] else 'approve_fulfillment')
    approved = decision == 'approve_fulfillment'
    plan = {'order_id': order_id, 'decision': decision, 'subtotal_usd': subtotal,
            'shipping_service': order.shipping_service if approved else None,
            'total_weight_kg': float(weight) if approved else None,
            'shipping_usd': shipping_cost if approved else None,
            'total_usd': money(Decimal(str(subtotal)) + Decimal(str(shipping_cost))) if approved else None}
    if approved:
        actions = [
            {'tool': 'reserve_inventory', 'items': [{'product_id': item.product_id, 'quantity': item.quantity} for item in items]},
            {'tool': 'create_shipment', 'shipping_service': order.shipping_service,
             'shipping_cost_usd': shipping_cost, 'total_weight_kg': float(weight)},
            {'tool': 'update_order_status', 'status': 'fulfilled'},
        ]
    else:
        actions = [{'tool': 'update_order_status', 'status': decision.replace('reject_', 'rejected_', 1)}]
    return dict(zip(STAGES, [inventory, {'items': pricing_rows, 'subtotal_usd': subtotal}, shipping, plan, {'actions': actions}]))


def differences(actual, expected, path=''):
    """Line-item order is irrelevant, action order is not; duplicates remain visible."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f'{path or "value"}: expected object']
        errors = []
        for key in sorted(set(actual) | set(expected)):
            if not path and key == 'reason':
                continue
            child = f'{path}.{key}' if path else key
            if key not in actual or key not in expected:
                errors.append(f'{child}: missing or unexpected field')
            else:
                errors.extend(differences(actual[key], expected[key], child))
        return errors
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [f'{path}: wrong list length or type']
        if path.endswith('items') and all(isinstance(v, dict) and 'product_id' in v for v in actual + expected):
            actual, expected = (sorted(rows, key=lambda row: str(row['product_id'])) for rows in (actual, expected))
        return [error for index, (left, right) in enumerate(zip(actual, expected))
                for error in differences(left, right, f'{path}.{index}')]
    if isinstance(expected, bool):
        equal = type(actual) is bool and actual == expected
    elif isinstance(expected, (int, float)):
        equal = isinstance(actual, (int, float)) and not isinstance(actual, bool) and abs(actual - expected) < 1e-6
    else:
        equal = actual == expected
    return [] if equal else [f'{path}: value differs from authoritative record']


def final_state_errors(dataset, initial, final, order_id):
    expected = deepcopy(initial.snapshot())
    reference = reference_artifacts(dataset, initial, order_id)
    actions = reference['executor_agent']['actions']
    expected['order_status'] = actions[-1]['status']
    if reference['planning_agent']['decision'] == 'approve_fulfillment':
        expected['reservations'][order_id] = actions[0]['items']
        expected['shipments'][order_id] = {key: value for key, value in actions[1].items() if key != 'tool'}
        expected['shipments'][order_id].update(order_id=order_id, status='scheduled')
        for item in actions[0]['items']:
            row = expected['inventory'][item['product_id']]
            row['available_qty'] -= item['quantity']
            row['reserved_qty'] += item['quantity']
    actual = final.snapshot()
    actual.pop('idempotency_keys', None)
    expected.pop('idempotency_keys', None)
    return differences(actual, expected)
