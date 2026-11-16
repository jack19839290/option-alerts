import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.constants import NOTIFICATION_QUEUE_HEADERS
from app.sheets import SheetsRepository


class NotificationPayloadTests(unittest.TestCase):
    def repository(self, existing=()):
        repo = object.__new__(SheetsRepository)
        repo.spreadsheet_id = 'test'
        repo.service = MagicMock()
        repo._ensure_sheets = MagicMock()
        repo._ensure_header = MagicMock()
        api = repo.service.spreadsheets.return_value.values.return_value
        api.get.return_value.execute.return_value = {'values': [[key] for key in existing]}
        return repo, api

    def event(self, payload):
        return {'事件ID': 'test-event', '事件類型': 'FIRST_CLOSE', '狀態': 'PENDING', '內容JSON': payload}

    def round_trip(self, payload):
        repo, api = self.repository()
        repo.append_notification_events([self.event(payload)])
        calls = api.append.call_args_list
        rows = calls[-1].kwargs['body']['values']
        raw = rows[0][NOTIFICATION_QUEUE_HEADERS.index('內容JSON')]
        chunks = calls[0].kwargs['body']['values'] if len(calls) > 1 else []
        for call in calls:
            self.assertEqual(call.kwargs['valueInputOption'], 'RAW')
            for row in call.kwargs['body']['values']:
                for cell in row:
                    self.assertLessEqual(len(str(cell).encode('utf-16-le')) // 2, 40000)
        if chunks:
            restored = json.loads(''.join(row[2] for row in chunks))
            self.assertEqual(restored, payload)
        else:
            self.assertEqual(json.loads(raw), payload)
        if shutil.which('node'):
            result = subprocess.run(['node', 'scripts/verify_notification_payload.mjs'],
                cwd=Path(__file__).resolve().parents[1], input=json.dumps({
                    'raw': raw, 'chunks': chunks, 'expected': payload}),
                text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return chunks

    def test_small_legacy_json_stays_inline(self):
        self.assertEqual(self.round_trip({'note': '舊通知🙂'}), [])

    def test_large_close_keeps_every_contract_across_python_and_apps_script(self):
        items = [{'contract_symbol': f'P{i}', 'strike': 1000 + i,
                  'option_type': 'PUT', 'note': '中文🙂' * 50} for i in range(400)]
        chunks = self.round_trip({'groups': [{'scan_id': 'MU|2027-01-15', 'ticker': 'MU',
            'expiry': '2027-01-15', 'items': items}]})
        self.assertGreater(len(chunks), 1)

    def test_utf16_boundary_and_emoji(self):
        for length in (39980, 40000, 50001):
            with self.subTest(length=length):
                self.round_trip({'note': '🙂' * (length // 2)})

    def test_existing_event_and_repeated_input_are_not_enqueued_twice(self):
        repo, api = self.repository(['test-event'])
        repo.append_notification_events([self.event({'note': 'x' * 100000})])
        api.append.assert_not_called()
        repo, api = self.repository()
        event = self.event({'note': 'small'})
        repo.append_notification_events([event, event])
        self.assertEqual(len(api.append.call_args.kwargs['body']['values']), 1)

    def test_chunk_failure_does_not_publish_queue_entry(self):
        repo, api = self.repository()
        api.append.return_value.execute.side_effect = RuntimeError('write failed')
        with self.assertRaises(RuntimeError):
            repo.append_notification_events([self.event({'note': 'x' * 100000})])
        self.assertEqual(api.append.call_count, 1)
        self.assertIn('A:C', api.append.call_args.kwargs['range'])
