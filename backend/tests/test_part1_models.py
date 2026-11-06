"""
Test PART 1: Pydantic model validation and basic health endpoint.

These tests verify that the data models enforce the non-negotiable rules:
- Money is integer paise, never float
- Currency is INR only
- Amounts must be positive
- Bool is rejected (bool is subclass of int in Python)
"""
import pytest
from pydantic import ValidationError

from app.models.account import (
    AccountInDB,
    AccountCreate,
    DepositRequest,
    WithdrawRequest,
    TransferRequest,
)
from app.models.ledger import LedgerEntryInDB, Direction, EntryKind
from app.security import hash_password, verify_password, create_access_token, decode_access_token


class TestMoneyIsIntegerPaise:
    """Money must be integer paise. Float, bool, string, Decimal must be rejected."""

    def test_deposit_rejects_float(self):
        with pytest.raises(ValidationError, match="float"):
            DepositRequest(amount=100.50)

    def test_deposit_rejects_zero(self):
        with pytest.raises(ValidationError):
            DepositRequest(amount=0)

    def test_deposit_rejects_negative(self):
        with pytest.raises(ValidationError):
            DepositRequest(amount=-100)

    def test_deposit_rejects_string(self):
        with pytest.raises(ValidationError):
            DepositRequest(amount="100")

    def test_deposit_rejects_bool(self):
        with pytest.raises(ValidationError, match="bool"):
            DepositRequest(amount=True)

    def test_deposit_accepts_positive_int(self):
        d = DepositRequest(amount=10000)
        assert d.amount == 10000

    def test_withdraw_rejects_float(self):
        with pytest.raises(ValidationError, match="float"):
            WithdrawRequest(amount=50.0)

    def test_transfer_rejects_float(self):
        with pytest.raises(ValidationError, match="float"):
            TransferRequest(from_account_id="a", to_account_id="b", amount=99.99)

    def test_transfer_rejects_bool(self):
        with pytest.raises(ValidationError, match="bool"):
            TransferRequest(from_account_id="a", to_account_id="b", amount=True)

    def test_account_balance_rejects_float(self):
        with pytest.raises(ValidationError):
            AccountInDB(
                number="TEST", name="Test", balance=100.5, version=0,
                currency="INR", status="active"
            )

    def test_account_balance_rejects_bool(self):
        with pytest.raises(ValidationError, match="bool"):
            AccountInDB(
                number="TEST", name="Test", balance=True, version=0,
                currency="INR", status="active"
            )


class TestCurrencyINROnly:
    """Only INR is supported in v1."""

    def test_account_rejects_usd(self):
        with pytest.raises(ValidationError, match="INR"):
            AccountCreate(
                number="TEST", name="Test", owner_ids=["user1"], currency="USD"
            )

    def test_account_accepts_inr(self):
        a = AccountCreate(number="TEST", name="Test", owner_ids=["user1"])
        assert a.currency == "INR"


class TestPasswordHashing:
    """bcrypt hashing and verification."""

    def test_hash_and_verify(self):
        pw = "TestPassword@123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password("wrong", hashed)

    def test_hash_is_not_plaintext(self):
        pw = "TestPassword@123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert hashed.startswith("$2b$")


class TestJWT:
    """JWT creation and verification."""

    def test_create_and_decode(self):
        token = create_access_token("user123", "admin")
        payload = decode_access_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"

    def test_tampered_token_fails(self):
        token = create_access_token("user123", "admin")
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        import jwt
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(tampered)


class TestLedgerEntryModel:
    """Ledger entry validation."""

    def test_amount_must_be_positive_int(self):
        with pytest.raises(ValidationError):
            LedgerEntryInDB(
                txn_id="t1", account_id="a1", direction=Direction.debit,
                amount=0, balance_after=0, seq=1, hash="abc",
                kind=EntryKind.deposit, initiated_by="u1"
            )

    def test_amount_rejects_float(self):
        with pytest.raises(ValidationError, match="float"):
            LedgerEntryInDB(
                txn_id="t1", account_id="a1", direction=Direction.debit,
                amount=100.5, balance_after=0, seq=1, hash="abc",
                kind=EntryKind.deposit, initiated_by="u1"
            )
