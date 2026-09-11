import unittest

import model
import parser as lua_parser


class TestSetCollections(unittest.TestCase):
    def test_extract_from_lua_roundtrip(self):
        lua_text = '''
        WornGearSetCollectionsSV =
        {
            ["@khedron83"] =
            {
                ["lastUpdated"] = 1784070000,
                ["sets"] =
                {
                    [1] = { ["id"] = 1, ["name"] = "Hakeijo's Views", ["category"] = "Scions of Ithelia", ["total"] = 5, ["unlocked"] = 5 },
                    [2] = { ["id"] = 2, ["name"] = "Half-Finished", ["category"] = "Lucent Citadel", ["total"] = 5, ["unlocked"] = 2 },
                },
            },
        }
        '''
        lua_data = lua_parser.load(lua_text)
        accounts = model.extract_set_collections(lua_data)

        self.assertEqual(len(accounts), 1)
        acct = accounts[0]
        self.assertEqual(acct.account, '@khedron83')
        self.assertEqual(len(acct.sets), 2)
        self.assertTrue(acct.sets[0].complete)
        self.assertFalse(acct.sets[1].complete)

    def test_missing_sv_key_returns_empty(self):
        self.assertEqual(model.extract_set_collections({}), [])

    def test_type_bucket_from_libsets_type(self):
        self.assertEqual(
            model.SetCollectionEntry(1, 'Oakensoul Ring', set_type='Mythic').type_bucket, 'Mythic')
        self.assertEqual(
            model.SetCollectionEntry(2, "Aerie's Cry", set_type='Class').type_bucket, 'Class')
        # Monster bucket covers both the plain and Cyrodiil/Imperial City variants
        self.assertEqual(
            model.SetCollectionEntry(3, 'Colovian Highlands General', set_type='CyrodiilMonster').type_bucket,
            'Monster')
        self.assertEqual(
            model.SetCollectionEntry(4, 'Some Trial Set', set_type='Trial').type_bucket, 'Trial')
        # unrecognized/missing set_type falls back to Other
        self.assertEqual(
            model.SetCollectionEntry(5, 'Unknown', set_type='SomethingNew').type_bucket, 'Other')


if __name__ == '__main__':
    unittest.main()
