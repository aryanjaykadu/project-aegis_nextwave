import unittest
from unittest.mock import patch
from starlette.requests import Request
from backend import main


def request():
    return Request({'type':'http','method':'GET','path':'/api/route','headers':[],
                    'query_string':b'','server':('test',8000),'client':('127.0.0.1',1234),
                    'scheme':'http'})


class RouteFallbackTests(unittest.TestCase):
    @patch('backend.main.requests.get', side_effect=RuntimeError('offline'))
    def test_route_fallback_is_marked_non_navigable_and_unsafe_to_assume(self, _):
        result = main.route(request(), 25.59, 85.13, 25.60, 85.14, 'public')
        self.assertEqual(result['routing_source'], 'straight_line_fallback')
        self.assertEqual(result['safety_status'], 'not_verified')
        self.assertIn('not a navigable', result['warning'])
        self.assertFalse(result['road_closure_data_available'])


if __name__ == '__main__':
    unittest.main()
