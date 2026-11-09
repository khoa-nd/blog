"""The answerers' contract, tested without a GPU or an API key.

The Claude test runs a tiny local server that plays the Messages API, so it checks the exact
request the SDK sends (image blocks, JSON schema, fallbacks) and how the reply is parsed."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image

from answer import Claude, label, parse_lines

PAGES = ["jpmorgan_chase_2024#108", "jpmorgan_chase_2024#42"]


class LocalParsing(unittest.TestCase):
    def test_labels_map_back_to_page_ids(self):
        out = parse_lines("ANSWER: Yes, $18.8 billion.\nPAGES: P2, P1\nQUOTE: \"Aggregate purchase price\"", PAGES)
        self.assertEqual(out["citations"], ["jpmorgan_chase_2024#42", "jpmorgan_chase_2024#108"])
        self.assertEqual(out["quote"], "Aggregate purchase price")

    def test_out_of_range_labels_are_dropped(self):
        self.assertEqual(parse_lines("ANSWER: x\nPAGES: P7", PAGES)["citations"], [])

    def test_answer_without_prefix_uses_first_line(self):
        self.assertEqual(parse_lines("Yes, it did.\nPAGES: P1", PAGES)["answer"], "Yes, it did.")

    def test_label_names_the_document(self):
        self.assertEqual(label(0, "wells_fargo_2024#12"), "P1 (wells fargo 2024, page 12):")


class FakeMessagesAPI(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeMessagesAPI.seen.append((self.path, dict(self.headers), body))
        reply = {"id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                 "content": [{"type": "text", "text": json.dumps(
                     {"answer": "Yes. It repurchased $18.8 billion.", "citations": ["P1"], "quote": "Aggregate purchase price"})}],
                 "stop_reason": "end_turn", "stop_sequence": None,
                 "usage": {"input_tokens": 3000, "output_tokens": 40}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class ClaudeRequest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeMessagesAPI)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{cls.server.server_port}"
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_images_schema_and_parsing(self):
        res = Claude().answer("Did JPM buy back more than half?", PAGES, images=[Image.new("RGB", (40, 50))] * 2)
        path, headers, body = FakeMessagesAPI.seen[-1]
        self.assertTrue(path.startswith("/v1/messages"))
        kinds = [b["type"] for b in body["messages"][0]["content"]]
        self.assertEqual(kinds, ["text", "image", "text", "image", "text"])
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(body["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", headers.get("anthropic-beta", ""))
        self.assertEqual(res["citations"], ["jpmorgan_chase_2024#108"])
        self.assertAlmostEqual(res["usd"], (3000 * 4.00 + 40 * 20.00) / 1e6)


if __name__ == "__main__":
    unittest.main()
