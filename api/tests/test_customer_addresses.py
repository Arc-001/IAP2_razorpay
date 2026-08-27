import uuid

import pytest

from app.models import Customer
from app.services.customer_addresses import (
    address_to_dict,
    create_address,
    delete_address,
    get_default_address,
    list_addresses,
    update_address,
)


@pytest.fixture()
def customer(db_session):
    c = Customer(name="Test Customer")
    db_session.add(c)
    db_session.flush()
    return c


def test_first_address_becomes_default_automatically(db_session, customer):
    address = create_address(db_session, customer.id, line1="1 Main St")

    assert address.is_default is True
    assert get_default_address(db_session, customer.id).id == address.id


def test_second_address_is_not_default_unless_requested(db_session, customer):
    create_address(db_session, customer.id, line1="1 Main St")
    second = create_address(db_session, customer.id, line1="2 Side St")

    assert second.is_default is False
    assert get_default_address(db_session, customer.id).line1 == "1 Main St"


def test_creating_a_new_default_unsets_the_previous_one(db_session, customer):
    first = create_address(db_session, customer.id, line1="1 Main St")
    second = create_address(db_session, customer.id, line1="2 Side St", is_default=True)

    db_session.refresh(first)
    assert first.is_default is False
    assert get_default_address(db_session, customer.id).id == second.id


def test_update_address_can_change_fields(db_session, customer):
    address = create_address(db_session, customer.id, line1="1 Main St")

    updated = update_address(db_session, customer.id, address.id, city="Pune")

    assert updated.city == "Pune"
    assert updated.line1 == "1 Main St"


def test_update_address_can_promote_to_default(db_session, customer):
    first = create_address(db_session, customer.id, line1="1 Main St")
    second = create_address(db_session, customer.id, line1="2 Side St")

    update_address(db_session, customer.id, second.id, is_default=True)

    db_session.refresh(first)
    assert first.is_default is False
    assert get_default_address(db_session, customer.id).id == second.id


def test_update_address_raises_for_an_address_owned_by_someone_else(db_session, customer):
    other = Customer(name="Other")
    db_session.add(other)
    db_session.flush()
    address = create_address(db_session, other.id, line1="1 Main St")

    with pytest.raises(LookupError):
        update_address(db_session, customer.id, address.id, city="Nope")


def test_delete_address_promotes_another_to_default(db_session, customer):
    first = create_address(db_session, customer.id, line1="1 Main St")
    second = create_address(db_session, customer.id, line1="2 Side St")

    delete_address(db_session, customer.id, first.id)

    assert get_default_address(db_session, customer.id).id == second.id


def test_delete_address_raises_for_unknown_id(db_session, customer):
    with pytest.raises(LookupError):
        delete_address(db_session, customer.id, uuid.uuid4())


def test_list_addresses_only_returns_the_given_customers_rows(db_session, customer):
    other = Customer(name="Other")
    db_session.add(other)
    db_session.flush()
    create_address(db_session, customer.id, line1="1 Main St")
    create_address(db_session, other.id, line1="9 Other St")

    addresses = list_addresses(db_session, customer.id)

    assert len(addresses) == 1
    assert addresses[0].line1 == "1 Main St"


def test_address_to_dict_shape(db_session, customer):
    address = create_address(db_session, customer.id, line1="1 Main St", city="Pune", country="IN")

    d = address_to_dict(address)

    assert d == {
        "label": None,
        "line1": "1 Main St",
        "line2": None,
        "city": "Pune",
        "state": None,
        "postal_code": None,
        "country": "IN",
    }
