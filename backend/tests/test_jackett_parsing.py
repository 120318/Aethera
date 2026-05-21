import unittest
from datetime import datetime
from app.clients.jackett import JackettClient
from app.schemas.domain.resource_search import JackettSearchResult, ResourceSearchResult

class TestJackettParsing(unittest.TestCase):
    def setUp(self):
        self.client = JackettClient()

    def test_parse_results(self):
        # Mock Jackett JSON response
        results = [
            JackettSearchResult(
                Title='Test Movie 2024',
                Tracker='TestTracker',
                CategoryDesc='Movies',
                Size=1073741824,
                Link='http://example.com/download',
                Guid='test-guid-1',
                Seeders=10,
                Peers=5,
                PublishDate=datetime.fromisoformat('2024-01-01T00:00:00+00:00'),
            )
        ]

        parsed = self.client._parse_results(results)
        
        self.assertEqual(len(parsed), 1)
        result = parsed[0]
        self.assertIsInstance(result, ResourceSearchResult)
        self.assertEqual(result.title, 'Test Movie 2024')
        self.assertEqual(result.site, 'testtracker') # converted to lower
        self.assertEqual(result.id, 'test-guid-1')
        self.assertTrue(hasattr(result, 'result_id'))
        self.assertIsNotNone(result.result_id)
        self.assertEqual(result.result_id, "test-guid-1")

    def test_parse_torznab_xml(self):
        # Mock Torznab XML response
        xml = """
        <rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
            <channel>
                <item>
                    <title>Test TV Show S01E01</title>
                    <guid>test-guid-2</guid>
                    <jackettindexer>TestTracker</jackettindexer>
                    <comments>http://example.com/details</comments>
                    <enclosure url="http://example.com/download.torrent" length="2147483648" type="application/x-bittorrent" />
                    <torznab:attr name="seeders" value="20" />
                    <torznab:attr name="peers" value="10" />
                </item>
            </channel>
        </rss>
        """
        
        parsed = self.client._parse_torznab_xml(xml)
        
        self.assertEqual(len(parsed), 1)
        result = parsed[0]
        self.assertIsInstance(result, ResourceSearchResult)
        self.assertEqual(result.title, 'Test TV Show S01E01')
        self.assertEqual(result.site, 'testtracker')
        self.assertEqual(result.id, 'test-guid-2')
        self.assertTrue(hasattr(result, 'result_id'))
        self.assertIsNotNone(result.result_id)
        self.assertEqual(len(result.result_id), 36)

if __name__ == '__main__':
    unittest.main()
