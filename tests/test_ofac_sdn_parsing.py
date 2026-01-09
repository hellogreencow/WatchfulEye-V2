import unittest

from watchfuleye.v3.entity_seeds import parse_ofac_sdn_csv_text


class TestOfacSdnParsing(unittest.TestCase):
    def test_parse_minimal_row(self) -> None:
        # ent_num, name, type, program, ... (rest ignored)
        txt = "1001,ACME CORP,Entity,SDGT,,,,,,,\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ent_num, "1001")
        self.assertEqual(rows[0].name, "ACME CORP")
        self.assertEqual(rows[0].sdn_type, "Entity")
        self.assertEqual(rows[0].program, "SDGT")

    def test_multiple_rows(self) -> None:
        txt = "1001,ACME CORP,Entity,SDGT\n1002,OMEGA LLC,Entity,IRAN\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].ent_num, "1001")
        self.assertEqual(rows[1].ent_num, "1002")

    def test_skips_rows_with_too_few_columns(self) -> None:
        txt = "1001,ACME\n1002,OMEGA LLC,Entity\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 0)

    def test_skips_empty_fields(self) -> None:
        txt = " ,ACME CORP,Entity,SDGT\n1001,   ,Entity,SDGT\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 0)

    def test_special_characters_in_name(self) -> None:
        txt = "1001,AL-QA'IDA & CO.,Entity,SDGT\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "AL-QA'IDA & CO.")

    def test_header_row_is_ignored(self) -> None:
        # Some exports include a header; ensure we don't treat it as data.
        txt = "ent_num,sdn_name,sdn_type,program\n1001,ACME CORP,Entity,SDGT\n"
        rows = parse_ofac_sdn_csv_text(txt)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ent_num, "1001")


if __name__ == "__main__":
    unittest.main()


