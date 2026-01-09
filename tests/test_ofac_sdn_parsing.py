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


if __name__ == "__main__":
    unittest.main()


