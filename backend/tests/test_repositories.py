"""Depo yardımcılarının testleri (veritabanı gerektirmez)."""

import pytest

from exceptions import InvalidIdentifierError
from repositories.mongo_repository import MongoTaskRepository
from repositories.mssql_repository import MSSQLTaskRepository


class TestMSSQLKimlikCozumleme:
    @pytest.mark.parametrize("deger,beklenen", [("1", 1), ("42", 42), ("007", 7)])
    def test_gecerli_kimlikler(self, deger, beklenen):
        assert MSSQLTaskRepository._parse_id(deger) == beklenen

    @pytest.mark.parametrize("deger", ["abc", "", "1.5", "1a", None])
    def test_gecersiz_kimlikler(self, deger):
        with pytest.raises(InvalidIdentifierError):
            MSSQLTaskRepository._parse_id(deger)

    @pytest.mark.parametrize("deger", ["²", "⑦", "½", "Ⅴ"])
    def test_unicode_rakam_benzerleri_reddedilir(self, deger):
        """str.isdigit() bunlara True der ama int() çeviremez.

        Eski kod önce isdigit() kontrolü yaptığı için bu değerler
        doğrulamayı geçip int() aşamasında çöküyor ve 400 yerine
        500 üretiyordu.
        """
        with pytest.raises(InvalidIdentifierError):
            MSSQLTaskRepository._parse_id(deger)


class TestMongoKimlikCozumleme:
    def test_gecerli_objectid(self):
        assert MongoTaskRepository._parse_id("507f1f77bcf86cd799439011")

    @pytest.mark.parametrize("deger", ["1", "abc", "", "507f1f77bcf86cd79943901"])
    def test_gecersiz_objectid(self, deger):
        with pytest.raises(InvalidIdentifierError):
            MongoTaskRepository._parse_id(deger)
