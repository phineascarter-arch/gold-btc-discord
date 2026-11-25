import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
import report

class DeliveryTests(unittest.TestCase):
    def test_secret_is_not_in_network_error(self):
        with patch('requests.get',side_effect=requests.ConnectionError('SECRET-KEY')), patch('report.time.sleep'):
            with self.assertRaises(RuntimeError) as caught:
                report.get_json('/history','SECRET-KEY')
        self.assertNotIn('SECRET-KEY',str(caught.exception))

    def test_discord_timeout_does_not_retry_or_leak_webhook(self):
        calls = []
        def network(*args,**kwargs):
            calls.append(1)
            raise requests.Timeout('SECRET-TOKEN')
        with tempfile.TemporaryDirectory() as folder:
            chart = Path(folder)/'chart.png'
            chart.write_bytes(b'png')
            with patch('requests.post',side_effect=network):
                with self.assertRaises(RuntimeError) as caught:
                    report.send_discord('https://discord.com/api/webhooks/123/SECRET-TOKEN','hi',chart)
        self.assertEqual(len(calls),1)
        self.assertNotIn('SECRET-TOKEN',str(caught.exception))

    def test_confirmed_upload_contains_chart_and_disables_mentions(self):
        def network(url,**kwargs):
            self.assertEqual(kwargs['files']['files[0]'][1].read(),b'PNG BYTES')
            self.assertEqual(json.loads(kwargs['data']['payload_json'])['allowed_mentions'],{'parse':[]})
            response = requests.Response()
            response.status_code = 200
            response._content = b'{"id":"123456"}'
            return response
        with tempfile.TemporaryDirectory() as folder:
            chart = Path(folder)/'chart.png'
            chart.write_bytes(b'PNG BYTES')
            with patch('requests.post',side_effect=network):
                result = report.send_discord('https://discord.com/api/webhooks/123/token','hi',chart)
        self.assertEqual(result,'123456')
